# from .ocr_processor import OCRProcessor
# from .schemas import ProcessedDocument


# def apply_ocr_to_document(
#     document: ProcessedDocument,
# ) -> ProcessedDocument:
#     """
#     Run OCR on candidate images inside a processed document.

#     Only images with:
#         process_with_ai = True

#     and:
#         extracted_image_path

#     will be processed.

#     OCR results are stored inside the same DocumentElement.
#     """

#     ocr_processor = OCRProcessor()

#     for unit in document.get_ordered_units():

#         for element in unit.get_ordered_elements():

#             # Only process images
#             if element.type != "image":
#                 continue

#             # Only images marked as candidates
#             if not element.metadata.get(
#                 "process_with_ai",
#                 False,
#             ):
#                 continue

#             # Image must already be extracted
#             image_path = element.metadata.get(
#                 "extracted_image_path"
#             )

#             if not image_path:
#                 element.metadata["ocr_status"] = (
#                     "SKIPPED_NO_IMAGE_PATH"
#                 )
#                 continue

#             try:
#                 result = ocr_processor.process_image(
#                     image_path
#                 )

#             except Exception as e:

#                 element.metadata["ocr_status"] = "FAILED"
#                 element.metadata["ocr_error"] = str(e)

#                 continue

#             # =================================================
#             # Store visible text
#             # =================================================

#             element.visible_text = result[
#                 "visible_text"
#             ]

#             # =================================================
#             # Store OCR metadata
#             # =================================================

#             element.metadata["ocr"] = {
#                 "engine": "paddleocr",
#                 "average_confidence": result[
#                     "average_confidence"
#                 ],
#                 "text_count": result[
#                     "text_count"
#                 ],
#                 "lines": result[
#                     "lines"
#                 ],
#             }

#             element.metadata["ocr_status"] = "DONE"

#     return document










from copy import deepcopy

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

    Exact duplicate extracted images reuse the OCR result
    when they have the same:
        extracted_image_hash

    The cache exists only during processing of the current
    document. It is not shared between lectures.

    OCR results are stored inside the same DocumentElement.
    """

    ocr_processor = OCRProcessor()

    # =========================================================
    # Per-document OCR cache
    #
    # Key:
    #   extracted_image_hash
    #
    # Value:
    #   OCR result already produced for the exact same
    #   extracted image.
    #
    # The cache is local to this function call, so it is
    # automatically discarded when this lecture finishes.
    # =========================================================

    ocr_cache = {}

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            # =================================================
            # Only process images
            # =================================================

            if element.type != "image":
                continue

            # =================================================
            # Only images marked as candidates
            # =================================================

            if not element.metadata.get(
                "process_with_ai",
                False,
            ):
                continue

            # =================================================
            # Image must already be extracted
            # =================================================

            image_path = element.metadata.get(
                "extracted_image_path"
            )

            if not image_path:

                element.metadata["ocr_status"] = (
                    "SKIPPED_NO_IMAGE_PATH"
                )

                continue

            # =================================================
            # Exact extracted-image hash
            #
            # This hash is produced by image_extractor.py from
            # the final image file that will actually be sent
            # to OCR / Vision.
            #
            # If the hash is missing for any reason, OCR still
            # works normally; that image simply cannot use the
            # duplicate cache.
            # =================================================

            image_hash = element.metadata.get(
                "extracted_image_hash"
            )

            # =================================================
            # OCR CACHE HIT
            # =================================================

            if (
                image_hash
                and image_hash in ocr_cache
            ):

                cached_result = ocr_cache[
                    image_hash
                ]

                element.visible_text = deepcopy(
                    cached_result[
                        "visible_text"
                    ]
                )

                element.metadata["ocr"] = deepcopy(
                    cached_result[
                        "ocr"
                    ]
                )

                # Keep the same DONE status so existing
                # downstream logic is not affected.
                element.metadata["ocr_status"] = "DONE"

                element.metadata[
                    "ocr_cache_hit"
                ] = True

                continue

            # =================================================
            # OCR CACHE MISS
            # =================================================

            try:

                result = ocr_processor.process_image(
                    image_path
                )

            except Exception as e:

                element.metadata["ocr_status"] = "FAILED"
                element.metadata["ocr_error"] = str(e)

                element.metadata[
                    "ocr_cache_hit"
                ] = False

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

            element.metadata[
                "ocr_cache_hit"
            ] = False

            # Remove a previous error if this element somehow
            # gets successfully processed after one existed.
            element.metadata.pop(
                "ocr_error",
                None,
            )

            # =================================================
            # Save successful OCR result in cache
            #
            # Failed OCR attempts are intentionally NOT cached.
            # This way, a temporary OCR failure on one image
            # does not force all later duplicates to fail too.
            # =================================================

            if image_hash:

                ocr_cache[
                    image_hash
                ] = {
                    "visible_text": deepcopy(
                        element.visible_text
                    ),
                    "ocr": deepcopy(
                        element.metadata[
                            "ocr"
                        ]
                    ),
                }

    return document