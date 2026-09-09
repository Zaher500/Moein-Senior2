import sys
from pathlib import Path

from Course.utils.document_processing.processor import process_document


def test_document(file_path: str):
    print("=" * 70)
    print("DOCUMENT PROCESSING TEST")
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

    try:
        document = process_document(str(path))
    except Exception as e:
        print("PROCESSING FAILED:")
        print(str(e))
        return

    print(f"File type: {document.file_type}")
    print(f"Units count: {len(document.units)}")
    print(f"Metadata: {document.metadata}")

    print()
    print("=" * 70)

    # =========================================================
    # Counters
    # =========================================================

    text_count = 0

    total_images = 0
    ai_candidates = 0
    skipped_images = 0

    other_count = 0

    # =========================================================
    # Print document units
    # =========================================================

    for unit in document.get_ordered_units():

        print()
        print(f"{unit.unit_type.upper()} {unit.index}")
        print("-" * 70)

        ordered_elements = unit.get_ordered_elements()

        if not ordered_elements:
            print("[No elements found]")
            continue

        for element in ordered_elements:

            print()
            print(f"Element #{element.order}")
            print(f"Type   : {element.type}")
            print(f"Source : {element.source}")

            # -------------------------------------------------
            # Bounding box
            # -------------------------------------------------

            if element.bbox:
                print(
                    "BBox   : "
                    f"x={element.bbox.x:.2f}, "
                    f"y={element.bbox.y:.2f}, "
                    f"width={element.bbox.width:.2f}, "
                    f"height={element.bbox.height:.2f}"
                )

            # =================================================
            # Text elements
            # =================================================

            if element.type in {
                "text",
                "heading",
                "list",
                "image_text",
            }:

                text_count += 1

                if element.text:
                    print("Text:")
                    print(element.text)
                else:
                    print("Text: [empty]")

            # =================================================
            # Image elements
            # =================================================

            elif element.type == "image":

                total_images += 1

                process_with_ai = element.metadata.get(
                    "process_with_ai",
                    False,
                )

                if process_with_ai:
                    ai_candidates += 1
                else:
                    skipped_images += 1

                print("Image detected")

                print(
                    "AI Candidate:",
                    "YES" if process_with_ai else "NO"
                )

                if element.metadata:

                    print("Metadata:")

                    for key, value in element.metadata.items():
                        print(f"  {key}: {value}")

            # =================================================
            # Future element types
            # =================================================

            else:

                other_count += 1

                if element.text:
                    print("Text:")
                    print(element.text)

                if element.visible_text:
                    print("Visible text:")

                    for item in element.visible_text:
                        print(f"  - {item}")

                if element.description:
                    print("Description:")
                    print(element.description)

                if element.relationships:
                    print("Relationships:")

                    for relation in element.relationships:
                        print(f"  - {relation}")

                if element.data:
                    print(f"Data: {element.data}")

                if element.metadata:
                    print(f"Metadata: {element.metadata}")

            print("-" * 30)

    # =========================================================
    # Test summary
    # =========================================================

    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    print(f"Units          : {len(document.units)}")
    print(f"Text           : {text_count}")
    print(f"Images total   : {total_images}")
    print(f"AI candidates  : {ai_candidates}")
    print(f"Skipped images : {skipped_images}")
    print(f"Other          : {other_count}")

    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            'python test_document_processor.py "path/to/file.pdf"'
        )

        sys.exit(1)

    test_document(sys.argv[1])