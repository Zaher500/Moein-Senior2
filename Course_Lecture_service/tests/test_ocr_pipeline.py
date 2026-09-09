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


def test_ocr_pipeline(file_path: str):

    print("=" * 70)
    print("DOCUMENT OCR PIPELINE TEST")
    print("=" * 70)

    path = Path(file_path)

    if not path.exists():
        print(f"ERROR: File does not exist: {file_path}")
        return

    if not path.is_file():
        print(f"ERROR: Path is not a file: {file_path}")
        return

    print(f"File: {path.name}")
    print(f"Path: {path.resolve()}")
    print()

    start_time = time.perf_counter()

    # =========================================================
    # 1. Parse document
    # =========================================================

    print("[1/3] Processing document...")

    try:
        document = process_document(
            str(path)
        )

    except Exception as e:
        print("DOCUMENT PROCESSING FAILED:")
        print(str(e))
        return

    # =========================================================
    # 2. Extract candidate images
    # =========================================================

    print("[2/3] Extracting candidate images...")

    output_dir = (
        Path("test_ocr_pipeline_output")
        / path.stem
    )

    try:
        extracted_images = extract_candidate_images(
            document=document,
            output_dir=str(output_dir),
            zoom=2.0,
        )

    except Exception as e:
        print("IMAGE EXTRACTION FAILED:")
        print(str(e))
        return

    print(
        f"Extracted candidate images: "
        f"{len(extracted_images)}"
    )

    # =========================================================
    # 3. Apply OCR
    # =========================================================

    print("[3/3] Running PaddleOCR...")
    print(
        "This may take a few minutes on CPU."
    )
    print()

    try:
        document = apply_ocr_to_document(
            document
        )

    except Exception as e:
        print("OCR PIPELINE FAILED:")
        print(str(e))
        return

    # =========================================================
    # Collect statistics
    # =========================================================

    total_images = 0
    ai_candidates = 0
    skipped_images = 0

    ocr_done = 0
    ocr_failed = 0
    ocr_no_path = 0

    total_ocr_lines = 0

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            total_images += 1

            process_with_ai = element.metadata.get(
                "process_with_ai",
                False,
            )

            if not process_with_ai:
                skipped_images += 1
                continue

            ai_candidates += 1

            status = element.metadata.get(
                "ocr_status"
            )

            if status == "DONE":

                ocr_done += 1

                ocr_metadata = element.metadata.get(
                    "ocr",
                    {},
                )

                total_ocr_lines += (
                    ocr_metadata.get(
                        "text_count",
                        0,
                    )
                )

            elif status == "FAILED":
                ocr_failed += 1

            elif status == "SKIPPED_NO_IMAGE_PATH":
                ocr_no_path += 1

    elapsed = (
        time.perf_counter()
        - start_time
    )

    # =========================================================
    # Summary
    # =========================================================

    print()
    print("=" * 70)
    print("OCR PIPELINE SUMMARY")
    print("=" * 70)

    print(
        f"Units             : "
        f"{len(document.units)}"
    )

    print(
        f"Images total      : "
        f"{total_images}"
    )

    print(
        f"AI candidates     : "
        f"{ai_candidates}"
    )

    print(
        f"Skipped images    : "
        f"{skipped_images}"
    )

    print(
        f"OCR done          : "
        f"{ocr_done}"
    )

    print(
        f"OCR failed        : "
        f"{ocr_failed}"
    )

    print(
        f"OCR no image path : "
        f"{ocr_no_path}"
    )

    print(
        f"OCR text regions  : "
        f"{total_ocr_lines}"
    )

    print(
        f"Total time        : "
        f"{elapsed:.2f} seconds"
    )

    print("=" * 70)

    # =========================================================
    # Print useful samples
    # =========================================================

    sample_pages = {
        17,
        26,
    }

    print()
    print("=" * 70)
    print("OCR SAMPLE RESULTS")
    print("=" * 70)

    for unit in document.get_ordered_units():

        if unit.index not in sample_pages:
            continue

        print()
        print(
            f"PAGE {unit.index}"
        )
        print("-" * 70)

        found_ocr = False

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            if (
                element.metadata.get(
                    "ocr_status"
                )
                != "DONE"
            ):
                continue

            found_ocr = True

            print()
            print(
                f"Image element "
                f"#{element.order}"
            )

            ocr_metadata = (
                element.metadata.get(
                    "ocr",
                    {},
                )
            )

            print(
                "Average confidence: "
                f"{ocr_metadata.get(
                    'average_confidence',
                    0
                )}"
            )

            print("Visible text:")
            print("-" * 30)

            if element.visible_text:

                for text in element.visible_text:
                    print(text)

            else:
                print(
                    "[No visible text detected]"
                )

            print("-" * 30)

        if not found_ocr:
            print(
                "[No OCR result on this page]"
            )


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 test_ocr_pipeline.py "
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_ocr_pipeline(
        sys.argv[1]
    )