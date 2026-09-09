from Course.utils.document_processing.processor import (
    process_document,
)

from Course.utils.document_processing.image_extractor import (
    extract_candidate_images,
)


file_path = r"C:\Users\yahya\OneDrive\سطح المكتب\fine tunning (Resnet18).docx"

document = process_document(
    file_path
)

images = extract_candidate_images(
    document=document,
    output_dir="temp_docx_images",
)

print("=" * 70)
print("EXTRACTED IMAGES:", len(images))
print("=" * 70)

for image_path in images:
    print(image_path)

print("=" * 70)

for unit in document.get_ordered_units():

    for element in unit.get_ordered_elements():

        if element.type != "image":
            continue

        print(
            "order:",
            element.order
        )

        print(
            "process_with_ai:",
            element.metadata.get(
                "process_with_ai"
            )
        )

        print(
            "relationship_id:",
            element.metadata.get(
                "relationship_id"
            )
        )

        print(
            "extracted_image_path:",
            element.metadata.get(
                "extracted_image_path"
            )
        )

        print(
            "extraction_status:",
            element.metadata.get(
                "extraction_status"
            )
        )

        print("-" * 70)