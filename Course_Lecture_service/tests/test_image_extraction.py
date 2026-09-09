import sys
from pathlib import Path

from Course.utils.document_processing.processor import (
    process_document,
)

from Course.utils.document_processing.image_extractor import (
    extract_candidate_images,
)


def test_image_extraction(file_path: str):

    path = Path(file_path)

    if not path.exists():
        print(f"File not found: {file_path}")
        return

    print("=" * 70)
    print("IMAGE EXTRACTION TEST")
    print("=" * 70)

    document = process_document(
        str(path)
    )

    output_dir = (
        Path("test_extracted_images")
        / path.stem
    )

    extracted_images = (
        extract_candidate_images(
            document=document,
            output_dir=str(output_dir),
            zoom=2.0,
        )
    )

    print()
    print("=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    print(
        f"Extracted images : "
        f"{len(extracted_images)}"
    )

    print(
        f"Output directory : "
        f"{output_dir.resolve()}"
    )

    print("=" * 70)

    for image_path in extracted_images:
        print(image_path)


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            'python test_image_extraction.py '
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_image_extraction(
        sys.argv[1]
    )