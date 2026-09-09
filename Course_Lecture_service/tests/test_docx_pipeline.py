from Course.utils.document_processing.pipeline import (
    process_document_for_summarization,
)


file_path = r"C:\Users\yahya\OneDrive\سطح المكتب\fine tunning (Resnet18).docx"

content = process_document_for_summarization(
    file_path
)

print("=" * 80)
print("FINAL CONTENT LENGTH:", len(content))
print("=" * 80)

print(content)