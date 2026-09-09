import sys
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
)

from Course.utils.document_processing.vision_pipeline import (
    apply_vision_to_document,
)


def test_vision_pipeline(file_path: str):

    path = Path(file_path)

    print("=" * 70)
    print("VISION PIPELINE TEST")
    print("=" * 70)

    if not path.exists():
        print(f"File not found: {file_path}")
        return

    # 1) Parse
    document = process_document(str(path))

    # 2) Extract candidate images
    output_dir = (
        Path("test_vision_pipeline_output")
        / path.stem
    )

    extract_candidate_images(
        document=document,
        output_dir=str(output_dir),
        zoom=2.0,
    )

    # 3) OCR
    document = apply_ocr_to_document(
        document
    )

    # 4) Router
    document = apply_image_routing(
        document
    )

    # =========================================================
    # IMPORTANT:
    # For this test, disable vision on everything
    # except pages 9 and 26.
    # =========================================================

    allowed_pages = {
        9,
        26,
    }

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            if unit.index not in allowed_pages:
                element.metadata[
                    "processing_route"
                ] = "ocr_only"

    # 5) Vision
    print("Running Qwen Vision on test pages...")

    document = apply_vision_to_document(
        document
    )

    # 6) Print results
    print()
    print("=" * 70)
    print("VISION RESULTS")
    print("=" * 70)

    for unit in document.get_ordered_units():

        if unit.index not in allowed_pages:
            continue

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            status = element.metadata.get(
                "vision_status"
            )

            if not status:
                continue

            print()
            print(f"Page    : {unit.index}")
            print(f"Element : {element.order}")
            print(f"Status  : {status}")
            print(
                f"Route   : "
                f"{element.metadata.get('processing_route')}"
            )

            if status == "DONE":

                print()
                print("Description:")
                print(element.description)

                print()
                print("Relationships:")

                for relation in element.relationships:
                    print(f"- {relation}")

            elif status == "FAILED":

                print(
                    "Error:",
                    element.metadata.get(
                        "vision_error"
                    )
                )

            print("-" * 70)


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 test_vision_pipeline.py "
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_vision_pipeline(
        sys.argv[1]
    )