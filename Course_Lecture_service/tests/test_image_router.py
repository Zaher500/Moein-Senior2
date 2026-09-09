import sys
import time
from pathlib import Path

from Course.utils.document_processing.processor import (
    process_document,
)

from Course.utils.document_processing.image_extractor import (
    extract_candidate_images,
)

from Course.utils.document_processing.ocr_pipeline import (
    apply_ocr_to_document,
)

from Course.utils.document_processing.image_router import (
    apply_image_routing,
    OCR_ONLY,
    OCR_VISION,
    VISION_ONLY,
)


def test_image_router(file_path: str):

    print("=" * 70)
    print("IMAGE ROUTER TEST")
    print("=" * 70)

    path = Path(file_path)

    if not path.exists():
        print(f"ERROR: File does not exist: {file_path}")
        return

    print(f"File: {path.name}")
    print(f"Path: {path.resolve()}")
    print()

    start_time = time.perf_counter()

    # =========================================================
    # 1. Process document
    # =========================================================

    print("[1/4] Processing document...")

    document = process_document(
        str(path)
    )

    # =========================================================
    # 2. Extract candidate images
    # =========================================================

    print("[2/4] Extracting candidate images...")

    output_dir = (
        Path("test_router_output")
        / path.stem
    )

    extracted_images = extract_candidate_images(
        document=document,
        output_dir=str(output_dir),
        zoom=2.0,
    )

    print(
        f"Extracted candidate images: "
        f"{len(extracted_images)}"
    )

    # =========================================================
    # 3. OCR
    # =========================================================

    print("[3/4] Running OCR...")

    document = apply_ocr_to_document(
        document
    )

    # =========================================================
    # 4. Image routing
    # =========================================================

    print("[4/4] Routing images...")

    document = apply_image_routing(
        document
    )

    # =========================================================
    # Statistics
    # =========================================================

    route_counts = {
        OCR_ONLY: 0,
        OCR_VISION: 0,
        VISION_ONLY: 0,
        "unknown": 0,
    }

    candidates = []

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            if not element.metadata.get(
                "process_with_ai",
                False,
            ):
                continue

            route = element.metadata.get(
                "processing_route",
                "unknown",
            )

            route_counts[route] = (
                route_counts.get(route, 0)
                + 1
            )

            candidates.append(
                (
                    unit,
                    element,
                )
            )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    # =========================================================
    # Summary
    # =========================================================

    print()
    print("=" * 70)
    print("ROUTING SUMMARY")
    print("=" * 70)

    print(
        f"Total candidates : "
        f"{len(candidates)}"
    )

    print(
        f"OCR_ONLY         : "
        f"{route_counts[OCR_ONLY]}"
    )

    print(
        f"OCR_VISION       : "
        f"{route_counts[OCR_VISION]}"
    )

    print(
        f"VISION_ONLY      : "
        f"{route_counts[VISION_ONLY]}"
    )

    print(
        f"Unknown          : "
        f"{route_counts['unknown']}"
    )

    print(
        f"Total time       : "
        f"{elapsed:.2f} seconds"
    )

    print("=" * 70)

    # =========================================================
    # Important sample pages
    # =========================================================

    sample_pages = {
        9,
        17,
        26,
    }

    print()
    print("=" * 70)
    print("IMPORTANT ROUTING SAMPLES")
    print("=" * 70)

    for unit, element in candidates:

        if unit.index not in sample_pages:
            continue

        print()

        print(
            f"Page    : {unit.index}"
        )

        print(
            f"Element : {element.order}"
        )

        print(
            "Route   : "
            f"{element.metadata.get(
                'processing_route'
            )}"
        )

        print(
            "Reason  : "
            f"{element.metadata.get(
                'routing_reason'
            )}"
        )

        print(
            "Metrics : "
            f"{element.metadata.get(
                'routing_metrics',
                {}
            )}"
        )

        text_preview = " ".join(
            element.visible_text
        )

        if len(text_preview) > 250:
            text_preview = (
                text_preview[:250]
                + "..."
            )

        print(
            f"Text    : {text_preview}"
        )

        print("-" * 70)

    # =========================================================
    # All routed candidates
    # =========================================================

    print()
    print("=" * 70)
    print("ALL CANDIDATE ROUTES")
    print("=" * 70)

    for unit, element in candidates:

        route = element.metadata.get(
            "processing_route",
            "unknown",
        )

        reason = element.metadata.get(
            "routing_reason",
            "unknown",
        )

        text_preview = " ".join(
            element.visible_text
        )

        if len(text_preview) > 80:
            text_preview = (
                text_preview[:80]
                + "..."
            )

        print(
            f"Page {unit.index:02d} | "
            f"Element {element.order:02d} | "
            f"{route:12} | "
            f"{reason:28} | "
            f"{text_preview}"
        )


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 test_image_router.py "
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_image_router(
        sys.argv[1]
    )