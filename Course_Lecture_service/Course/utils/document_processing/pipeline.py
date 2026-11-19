import time
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from .processor import process_document
from .image_extractor import extract_candidate_images
from .ocr_pipeline import apply_ocr_to_document
from .image_router import apply_image_routing
from .vision_pipeline import apply_vision_to_document
from .content_builder import build_summarization_content


def process_document_for_summarization(
    file_path: str,
) -> str:

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    total_start = time.perf_counter()
    stage_times = {}

    # Measure one pipeline stage without changing its behavior.
    def measure(stage_name, function, *args, **kwargs):

        start = time.perf_counter()

        try:
            return function(*args, **kwargs)

        finally:
            elapsed = time.perf_counter() - start
            stage_times[stage_name] = elapsed

            print(
                f"[PERF][{stage_name}] "
                f"seconds={elapsed:.2f}",
                flush=True,
            )

    print(
        f"[PERF][START] file={path.name}",
        flush=True,
    )

    try:

        # 1. Document parsing
        document = measure(
            "DOCUMENT_PARSING",
            process_document,
            str(path),
        )

        with TemporaryDirectory(
            prefix="moein_document_images_"
        ) as temp_dir:

            # 2. Image extraction
            extracted_images = measure(
                "IMAGE_EXTRACTION",
                extract_candidate_images,
                document=document,
                output_dir=temp_dir,
                zoom=2.0,
            )

            print(
                f"[PERF][EXTRACTED_IMAGES] "
                f"count={len(extracted_images)}",
                flush=True,
            )

            # 3. OCR
            document = measure(
                "OCR_TOTAL",
                apply_ocr_to_document,
                document,
            )

            # 4. Image routing
            document = measure(
                "IMAGE_ROUTING",
                apply_image_routing,
                document,
            )

            routes = Counter(
                element.metadata.get(
                    "processing_route", "unknown"
                )
                for unit in document.get_ordered_units()
                for element in unit.get_ordered_elements()
                if (
                    element.type == "image"
                    and element.metadata.get(
                        "process_with_ai", False
                    )
                )
            )

            print(
                f"[PERF][ROUTING_STATS] "
                f"{dict(routes)}",
                flush=True,
            )

            # 5. Vision
            document = measure(
                "VISION_TOTAL",
                apply_vision_to_document,
                document,
            )

            vision_statuses = Counter(
                element.metadata.get(
                    "vision_status", "NOT_PROCESSED"
                )
                for unit in document.get_ordered_units()
                for element in unit.get_ordered_elements()
                if (
                    element.type == "image"
                    and element.metadata.get(
                        "process_with_ai", False
                    )
                )
            )

            print(
                f"[PERF][VISION_STATS] "
                f"{dict(vision_statuses)}",
                flush=True,
            )

            # 6. Build final content
            final_content = measure(
                "CONTENT_BUILDING",
                build_summarization_content,
                document,
            )

        return final_content

    finally:

        total_elapsed = (
            time.perf_counter() - total_start
        )

        print(
            "\n========== PERFORMANCE SUMMARY ==========",
            flush=True,
        )

        for stage, elapsed in stage_times.items():

            percentage = (
                elapsed / total_elapsed * 100
                if total_elapsed > 0
                else 0.0
            )

            print(
                f"{stage}: {elapsed:.2f}s "
                f"({percentage:.1f}%)",
                flush=True,
            )

        print(
            f"TOTAL_TIME: {total_elapsed:.2f}s",
            flush=True,
        )

        print(
            "=========================================\n",
            flush=True,
        )