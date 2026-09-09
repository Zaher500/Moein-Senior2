from pathlib import Path
from tempfile import TemporaryDirectory

from Course.utils.document_processing.processor import (
    process_document,
)
from Course.utils.document_processing.image_extractor import (
    extract_candidate_images,
)


file_path = r"C:\Users\yahya\Downloads\I M 07.pptx"


document = process_document(
    file_path
)


with TemporaryDirectory(
    prefix="test_pptx_images_"
) as temp_dir:

    print("=" * 80)
    print("TEMP DIR:")
    print(temp_dir)
    print("=" * 80)

    extracted_files = extract_candidate_images(
        document=document,
        output_dir=temp_dir,
        zoom=2.0,
    )

    print()
    print(
        "EXTRACTED IMAGES:",
        len(extracted_files),
    )

    print("=" * 80)

    for image_path in extracted_files:

        print(
            "IMAGE:",
            image_path,
        )

    print()
    print("=" * 80)
    print("ELEMENT RESULTS")
    print("=" * 80)

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            print()
            print(
                f"SLIDE: {unit.index}"
            )

            print(
                f"ORDER: {element.order}"
            )

            print(
                "visual_type:",
                element.metadata.get(
                    "visual_type"
                ),
            )

            print(
                "original extension:",
                element.metadata.get(
                    "image_extension"
                ),
            )

            print(
                "process_with_ai:",
                element.metadata.get(
                    "process_with_ai"
                ),
            )

            print(
                "extraction_status:",
                element.metadata.get(
                    "extraction_status"
                ),
            )

            print(
                "extraction_strategy:",
                element.metadata.get(
                    "extraction_strategy"
                ),
            )

            print(
                "extracted_extension:",
                element.metadata.get(
                    "extracted_extension"
                ),
            )

            print(
                "extracted_image_path:",
                element.metadata.get(
                    "extracted_image_path"
                ),
            )

            print("-" * 60)

    input(
        "\nPress Enter to delete temporary images..."
    )