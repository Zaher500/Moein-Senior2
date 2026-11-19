"""Parallel Qwen vision pipeline for Moein.

Drop-in replacement for vision_pipeline.py.
The existing VisionProcessor and metadata schema are unchanged.
"""

from collections import OrderedDict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from threading import local
from time import perf_counter

from .image_router import OCR_VISION, VISION_ONLY
from .schemas import ProcessedDocument
from .vision_processor import VisionProcessor


# Start conservatively. Increase to 3 only after checking API errors/quota.
MAX_VISION_WORKERS = 2
MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"
_worker_state = local()


def _process_one_image(image_path: str, visible_text: list[str] | None) -> dict:
    """Reuse one InferenceClient per thread; do not share clients across threads."""
    processor = getattr(_worker_state, "processor", None)
    if processor is None:
        processor = VisionProcessor()
        _worker_state.processor = processor

    started = perf_counter()
    try:
        return processor.process_image(
            image_path=image_path,
            visible_text=visible_text,
        )
    finally:
        print(
            f"[PERF][VISION_REQUEST] image={image_path} "
            f"seconds={perf_counter() - started:.2f}",
            flush=True,
        )


def _credits_unavailable(error: Exception) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in (
        "402", "payment required", "depleted your monthly included credits",
        "insufficient credits",
    ))


def _set_success(item: dict, result: dict, *, cache_hit: bool) -> None:
    """Only the main thread modifies document elements."""
    element = item["element"]
    element.description = deepcopy(result.get("description"))
    element.relationships = deepcopy(result.get("relationships", []))
    element.metadata["vision"] = {
        "model": MODEL_NAME,
        "route": item["route"],
    }
    element.metadata["vision_status"] = "DONE"
    element.metadata["vision_cache_hit"] = cache_hit
    element.metadata.pop("vision_error", None)

    print(
        f"[VISION] {'CACHE_HIT' if cache_hit else 'DONE'} "
        f"page={item['page']} image={item['image_path']}",
        flush=True,
    )


def _set_failure(item: dict, error: Exception) -> None:
    element = item["element"]
    element.metadata["vision_status"] = "FAILED"
    element.metadata["vision_error"] = str(error)
    element.metadata["vision_cache_hit"] = False
    print(
        f"[VISION] FAILED page={item['page']} "
        f"image={item['image_path']} error={error}",
        flush=True,
    )


def _set_unavailable(item: dict) -> None:
    element = item["element"]
    element.metadata["vision_status"] = "SKIPPED_VISION_UNAVAILABLE"
    element.metadata["vision_cache_hit"] = False
    print(
        f"[VISION] SKIPPED page={item['page']} "
        "reason=vision_unavailable",
        flush=True,
    )


def apply_vision_to_document(document: ProcessedDocument) -> ProcessedDocument:
    """Run at most MAX_VISION_WORKERS distinct Qwen image requests concurrently.

    - OCR_ONLY images are not sent to Vision.
    - Exact duplicates share successful results within this one document.
    - Failures are not cached: if a duplicate exists, the next occurrence
      gets its own attempt until one succeeds or occurrences run out.
    - Stop scheduling new requests after a 402/credits error; already-running
      requests are allowed to finish.
    - Results are saved on their original elements, preserving document order.
    """
    # Keep the original immediate validation of credentials/config.
    VisionProcessor()

    groups = OrderedDict()
    unique_number = 0

    for unit in document.get_ordered_units():
        for element in unit.get_ordered_elements():
            if element.type != "image":
                continue
            if not element.metadata.get("process_with_ai", False):
                continue

            route = element.metadata.get("processing_route")
            if route not in (OCR_VISION, VISION_ONLY):
                continue

            image_path = element.metadata.get("extracted_image_path")
            if not image_path:
                element.metadata["vision_status"] = "SKIPPED_NO_IMAGE_PATH"
                element.metadata["vision_cache_hit"] = False
                continue

            # Reset these if this document is run through the pipeline again.
            element.metadata.pop("vision_status", None)
            element.metadata.pop("vision_cache_hit", None)

            image_hash = element.metadata.get("extracted_image_hash")
            if image_hash:
                key = ("hash", image_hash)
            else:
                unique_number += 1
                key = ("single", unique_number)

            item = {
                "element": element,
                "page": unit.index,
                "route": route,
                "image_path": image_path,
            }
            if key not in groups:
                groups[key] = {"items": [], "next": 0}
            groups[key]["items"].append(item)

    pending = deque(groups.values())
    in_flight = {}
    vision_available = True

    print(
        f"[VISION] workers={MAX_VISION_WORKERS} "
        f"unique_images={len(groups)} "
        f"total_images={sum(len(g['items']) for g in groups.values())}",
        flush=True,
    )

    with ThreadPoolExecutor(
        max_workers=MAX_VISION_WORKERS,
        thread_name_prefix="moein-qwen",
    ) as pool:

        def fill_slots() -> None:
            while (
                vision_available
                and pending
                and len(in_flight) < MAX_VISION_WORKERS
            ):
                group = pending.popleft()
                item = group["items"][group["next"]]
                element = item["element"]

                print(
                    f"[VISION] PROCESSING page={item['page']} "
                    f"image={item['image_path']} route={item['route']}",
                    flush=True,
                )
                future = pool.submit(
                    _process_one_image,
                    item["image_path"],
                    element.visible_text,
                )
                in_flight[future] = group

        fill_slots()
        while in_flight:
            finished, _ = wait(tuple(in_flight), return_when=FIRST_COMPLETED)
            for future in finished:
                group = in_flight.pop(future)
                index = group["next"]
                item = group["items"][index]

                try:
                    result = future.result()
                except Exception as error:
                    _set_failure(item, error)
                    group["next"] += 1

                    if _credits_unavailable(error):
                        vision_available = False
                        print(
                            "[VISION] DISABLED "
                            "reason=huggingface_credits_unavailable",
                            flush=True,
                        )
                    elif group["next"] < len(group["items"]):
                        # A failure is not cached. Retry a *different*
                        # duplicate occurrence, matching sequential behavior.
                        pending.appendleft(group)
                else:
                    _set_success(item, result, cache_hit=False)
                    for duplicate in group["items"][index + 1:]:
                        _set_success(duplicate, result, cache_hit=True)

            fill_slots()

    if not vision_available:
        # Do not overwrite FAILED / DONE statuses from requests already sent.
        for group in groups.values():
            for item in group["items"]:
                if "vision_status" not in item["element"].metadata:
                    _set_unavailable(item)

    return document
