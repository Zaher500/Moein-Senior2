import os
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
from Course.utils.document_processing.content_builder import (
    build_summarization_content,
)


TEST_PAGE = 26


def test_content_builder(file_path: str):

    print("=" * 70)
    print("CONTENT BUILDER TEST")
    print("=" * 70)

    path = Path(file_path)

    if not path.exists():
        print(f"ERROR: File not found: {file_path}")
        return

    # =========================================================
    # Check Hugging Face token before doing expensive OCR
    # =========================================================

    if not os.getenv("HF_TOKEN"):
        print("ERROR: HF_TOKEN environment variable was not found.")
        print("Set HF_TOKEN before running this test.")
        return

    print(f"File      : {path.name}")
    print(f"Test page : {TEST_PAGE}")
    print()

    # =========================================================
    # 1. Parse PDF
    # =========================================================

    print("[1/6] Processing document...")

    document = process_document(
        str(path)
    )

    # =========================================================
    # 2. Extract candidate images
    # =========================================================

    print("[2/6] Extracting candidate images...")

    output_dir = (
        Path("test_content_builder_output")
        / path.stem
    )

    extracted_images = extract_candidate_images(
        document=document,
        output_dir=str(output_dir),
        zoom=2.0,
    )

    print(
        f"Extracted images: {len(extracted_images)}"
    )

    # =========================================================
    # 3. OCR
    # =========================================================

    print("[3/6] Running OCR...")

    document = apply_ocr_to_document(
        document
    )

    # =========================================================
    # 4. Route images
    # =========================================================

    print("[4/6] Routing images...")

    document = apply_image_routing(
        document
    )

    # =========================================================
    # For this test:
    # only allow Qwen on Page 26.
    #
    # This avoids API calls for all other pages.
    # =========================================================

    for unit in document.get_ordered_units():

        if unit.index == TEST_PAGE:
            continue

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            element.metadata[
                "processing_route"
            ] = "ocr_only"

    # =========================================================
    # 5. Vision
    # =========================================================

    print(
        f"[5/6] Running Qwen Vision "
        f"only on Page {TEST_PAGE}..."
    )

    document = apply_vision_to_document(
        document
    )

    # =========================================================
    # 6. Build final summarization content
    # =========================================================

    print("[6/6] Building final content...")

    final_content = (
        build_summarization_content(
            document
        )
    )

    # =========================================================
    # Extract only Page 26 from final content
    # =========================================================

    page_marker = (
        f"===== PAGE {TEST_PAGE} ====="
    )

    next_page_marker = (
        f"===== PAGE {TEST_PAGE + 1} ====="
    )

    start = final_content.find(
        page_marker
    )

    if start == -1:
        print()
        print(
            f"ERROR: Page {TEST_PAGE} "
            f"was not found in final content."
        )
        return

    end = final_content.find(
        next_page_marker,
        start,
    )

    if end == -1:
        page_content = final_content[
            start:
        ]
    else:
        page_content = final_content[
            start:end
        ]

    # =========================================================
    # Print Page 26
    # =========================================================

    print()
    print("=" * 70)
    print(
        f"FINAL CONTENT - PAGE {TEST_PAGE}"
    )
    print("=" * 70)

    print(page_content.strip())

    print()
    print("=" * 70)
    print("CHECKS")
    print("=" * 70)

    print(
        "Has image OCR text       :",
        "[TEXT INSIDE IMAGE]"
        in page_content,
    )

    print(
        "Has visual description  :",
        "[VISUAL DESCRIPTION]"
        in page_content,
    )

    print(
        "Has relationships       :",
        "[VISUAL RELATIONSHIPS]"
        in page_content,
    )

    print(
        "Page content characters :",
        len(page_content),
    )

    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 test_content_builder.py "
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_content_builder(
        sys.argv[1]
    )