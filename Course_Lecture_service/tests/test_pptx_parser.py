from Course.utils.document_processing.processor import (
    process_document,
)


file_path = r"C:\Users\yahya\Downloads\I M 07.pptx"

document = process_document(
    file_path
)

print("=" * 80)
print("FILE TYPE:", document.file_type)
print(
    "SLIDES:",
    len(document.units),
)
print("=" * 80)

for unit in document.get_ordered_units():

    print()
    print(
        f"SLIDE index={unit.index} "
        f"type={unit.unit_type}"
    )

    print("-" * 70)

    for element in unit.get_ordered_elements():

        print(
            f"order={element.order} "
            f"type={element.type} "
            f"source={element.source}"
        )

        if element.type == "text":

            print(
                "TEXT:",
                element.text,
            )

            print(
                "content_type:",
                element.metadata.get(
                    "content_type"
                ),
            )

        elif element.type == "image":

            print(
                "visual_type:",
                element.metadata.get(
                    "visual_type"
                ),
            )

            print(
                "shape_id:",
                element.metadata.get(
                    "shape_id"
                ),
            )

            print(
                "shape_name:",
                element.metadata.get(
                    "shape_name"
                ),
            )

            print(
                "render_mode:",
                element.metadata.get(
                    "render_mode"
                ),
            )

            print(
                "content_hash:",
                element.metadata.get(
                    "content_hash"
                ),
            )


            print(
            "process_with_ai:",
            element.metadata.get(
                "process_with_ai"
            )
        )

        print(
            "selection_reason:",
            element.metadata.get(
                "selection_reason"
            )
        )

        print("-" * 70)