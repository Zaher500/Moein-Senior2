from .ocr_processor import OCRProcessor
from .schemas import ProcessedDocument


def apply_ocr_to_document(
    document: ProcessedDocument,
) -> ProcessedDocument:
    """
    Run OCR on candidate images inside a processed document.

    Only images with:
        process_with_ai = True

    and:
        extracted_image_path

    will be processed.

    OCR results are stored inside the same DocumentElement.
    """

    ocr_processor = OCRProcessor()

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            # Only process images
            if element.type != "image":
                continue

            # Only images marked as candidates
            if not element.metadata.get(
                "process_with_ai",
                False,
            ):
                continue

            # Image must already be extracted
            image_path = element.metadata.get(
                "extracted_image_path"
            )

            if not image_path:
                element.metadata["ocr_status"] = (
                    "SKIPPED_NO_IMAGE_PATH"
                )
                continue

            try:
                result = ocr_processor.process_image(
                    image_path
                )

            except Exception as e:

                element.metadata["ocr_status"] = "FAILED"
                element.metadata["ocr_error"] = str(e)

                continue

            # =================================================
            # Store visible text
            # =================================================

            element.visible_text = result[
                "visible_text"
            ]

            # =================================================
            # Store OCR metadata
            # =================================================

            element.metadata["ocr"] = {
                "engine": "paddleocr",
                "average_confidence": result[
                    "average_confidence"
                ],
                "text_count": result[
                    "text_count"
                ],
                "lines": result[
                    "lines"
                ],
            }

            element.metadata["ocr_status"] = "DONE"

    return document