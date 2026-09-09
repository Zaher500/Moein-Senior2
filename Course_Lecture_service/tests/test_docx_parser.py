from Course.utils.document_processing.processor import process_document


file_path = r"C:\Users\yahya\OneDrive\سطح المكتب\fine tunning (Resnet18).docx"

document = process_document(file_path)

print("=" * 70)
print("FILE TYPE:", document.file_type)
print("UNITS:", len(document.units))
print("=" * 70)

for unit in document.get_ordered_units():

    print(
        f"\nUNIT index={unit.index} "
        f"type={unit.unit_type}"
    )

    for element in unit.get_ordered_elements():

        print("-" * 60)

        print(
            f"order={element.order} "
            f"type={element.type} "
            f"source={element.source}"
        )

        if element.type == "text":

            print(
                "TEXT:",
                element.text[:300]
                if element.text
                else ""
            )

        elif element.type == "image":

            print(
                "relationship_id:",
                element.metadata.get(
                    "relationship_id"
                )
            )

            print(
                "image_partname:",
                element.metadata.get(
                    "image_partname"
                )
            )

            print(
                "content_hash:",
                element.metadata.get(
                    "content_hash"
                )
            )


            print(
        "process_with_ai:",
        element.metadata.get(
            "process_with_ai"
        )
    )