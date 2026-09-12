# from .image_router import (
#     OCR_VISION,
#     VISION_ONLY,
# )
# from .schemas import ProcessedDocument
# from .vision_processor import VisionProcessor


# def apply_vision_to_document(
#     document: ProcessedDocument,
# ) -> ProcessedDocument:
#     """
#     Run Qwen3-VL only on images that need visual understanding.

#     Processes:
#         OCR_VISION
#         VISION_ONLY

#     Skips:
#         OCR_ONLY

#     Vision results are stored in:
#         element.description
#         element.relationships
#     """

#     # =================================================
#     # Load/create the API client only once
#     # =================================================

#     vision_processor = VisionProcessor()

#     # =================================================
#     # NEW:
#     # If Hugging Face Vision credits become unavailable,
#     # stop sending the remaining images to Vision.
#     # OCR content will still remain available.
#     # =================================================

#     vision_available = True

#     for unit in document.get_ordered_units():

#         for element in unit.get_ordered_elements():

#             # =================================================
#             # Only images
#             # =================================================

#             if element.type != "image":
#                 continue

#             # =================================================
#             # Only candidate images
#             # =================================================

#             if not element.metadata.get(
#                 "process_with_ai",
#                 False,
#             ):
#                 continue

#             # =================================================
#             # Check routing decision
#             # =================================================

#             route = element.metadata.get(
#                 "processing_route"
#             )

#             if route not in {
#                 OCR_VISION,
#                 VISION_ONLY,
#             }:
#                 continue

#             # =================================================
#             # NEW:
#             # Stop Vision calls after a permanent credits error
#             # =================================================

#             if not vision_available:

#                 element.metadata[
#                     "vision_status"
#                 ] = "SKIPPED_VISION_UNAVAILABLE"

#                 print(
#                     "[VISION]",
#                     "SKIPPED",
#                     f"page={unit.index}",
#                     "reason=vision_unavailable",
#                 )

#                 continue

#             # =================================================
#             # Image must already be extracted
#             # =================================================

#             image_path = element.metadata.get(
#                 "extracted_image_path"
#             )

#             if not image_path:

#                 element.metadata[
#                     "vision_status"
#                 ] = "SKIPPED_NO_IMAGE_PATH"

#                 continue

#             # =================================================
#             # Send image to Qwen
#             # =================================================

#             # =================================================
#             # OLD VERSION
#             # =================================================
#             #
#             # try:
#             #
#             #     result = vision_processor.process_image(
#             #         image_path=image_path,
#             #         visible_text=element.visible_text,
#             #     )
#             #
#             # except Exception as e:
#             #
#             #     # One failed image should NOT stop
#             #     # processing the whole lecture.
#             #
#             #     element.metadata[
#             #         "vision_status"
#             #     ] = "FAILED"
#             #
#             #     element.metadata[
#             #         "vision_error"
#             #     ] = str(e)
#             #
#             #     continue

#             # =================================================
#             # OLD DEBUG VERSION
#             # =================================================
#             #
#             # try:
#             #
#             #     print(
#             #         "[VISION]",
#             #         f"processing image={image_path}",
#             #         f"route={route}",
#             #     )
#             #
#             #     result = vision_processor.process_image(
#             #         image_path=image_path,
#             #         visible_text=element.visible_text,
#             #     )
#             #
#             #     print(
#             #         "[VISION]",
#             #         "DONE",
#             #         f"description={bool(result.get('description'))}",
#             #         f"relationships={len(result.get('relationships', []))}",
#             #     )
#             #
#             # except Exception as e:
#             #
#             #     print(
#             #         "[VISION]",
#             #         "FAILED",
#             #         f"image={image_path}",
#             #         f"error={e}",
#             #     )
#             #
#             #     element.metadata[
#             #         "vision_status"
#             #     ] = "FAILED"
#             #
#             #     element.metadata[
#             #         "vision_error"
#             #     ] = str(e)
#             #
#             #     continue

#             # =================================================
#             # NEW DEBUG + CREDIT HANDLING VERSION
#             # =================================================

#             try:

#                 print(
#                     "[VISION]",
#                     "PROCESSING",
#                     f"page={unit.index}",
#                     f"image={image_path}",
#                     f"route={route}",
#                 )

#                 result = vision_processor.process_image(
#                     image_path=image_path,
#                     visible_text=element.visible_text,
#                 )

#                 print(
#                     "[VISION]",
#                     "DONE",
#                     f"page={unit.index}",
#                     f"description={bool(result.get('description'))}",
#                     f"relationships={len(result.get('relationships', []))}",
#                 )

#             except Exception as e:

#                 error_message = str(e)

#                 print(
#                     "[VISION]",
#                     "FAILED",
#                     f"page={unit.index}",
#                     f"image={image_path}",
#                     f"error={error_message}",
#                 )

#                 # =================================================
#                 # Store failure on current image
#                 # =================================================

#                 element.metadata[
#                     "vision_status"
#                 ] = "FAILED"

#                 element.metadata[
#                     "vision_error"
#                 ] = error_message

#                 # =================================================
#                 # NEW:
#                 # Detect exhausted Hugging Face credits.
#                 #
#                 # A 402 is not an image-specific error.
#                 # Sending more images would only generate
#                 # the same failure again.
#                 # =================================================

#                 if (
#                     "402" in error_message
#                     or "Payment Required" in error_message
#                     or "depleted your monthly included credits"
#                     in error_message
#                 ):

#                     vision_available = False

#                     print(
#                         "[VISION]",
#                         "DISABLED",
#                         "reason=huggingface_credits_unavailable",
#                     )

#                 # =================================================
#                 # Other errors should NOT disable Vision.
#                 #
#                 # Example:
#                 # invalid JSON from one image should allow
#                 # the next image to still be processed.
#                 # =================================================

#                 continue

#             # =================================================
#             # Store visual understanding
#             # =================================================

#             element.description = result.get(
#                 "description"
#             )

#             element.relationships = result.get(
#                 "relationships",
#                 [],
#             )

#             # =================================================
#             # Store metadata
#             # =================================================

#             element.metadata["vision"] = {
#                 "model": (
#                     "Qwen/Qwen3-VL-8B-Instruct"
#                 ),
#                 "route": route,
#             }

#             element.metadata[
#                 "vision_status"
#             ] = "DONE"

#     return document

















from copy import deepcopy

from .image_router import (
    OCR_VISION,
    VISION_ONLY,
)
from .schemas import ProcessedDocument
from .vision_processor import VisionProcessor


def apply_vision_to_document(
    document: ProcessedDocument,
) -> ProcessedDocument:
    """
    Run Qwen3-VL only on images that need visual understanding.

    Processes:
        OCR_VISION
        VISION_ONLY

    Skips:
        OCR_ONLY

    Exact duplicate extracted images reuse the Vision result
    when they have the same:
        extracted_image_hash

    The cache exists only during processing of the current
    document. It is not shared between lectures.

    Vision results are stored in:
        element.description
        element.relationships
    """

    # =================================================
    # Load/create the API client only once
    # =================================================

    vision_processor = VisionProcessor()

    # =================================================
    # Per-document Vision cache
    #
    # Key:
    #   extracted_image_hash
    #
    # Value:
    #   Successful Vision result already produced for
    #   the exact same extracted image.
    #
    # Failed Vision attempts are NOT cached.
    #
    # The cache is local to this function call, so it is
    # automatically discarded when this lecture finishes.
    # =================================================

    vision_cache = {}

    # =================================================
    # If Hugging Face Vision credits become unavailable,
    # stop sending NEW images to Vision.
    #
    # Important:
    # Already-cached duplicate images can still reuse their
    # previous Vision result without making a new API call.
    # =================================================

    vision_available = True

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            # =================================================
            # Only images
            # =================================================

            if element.type != "image":
                continue

            # =================================================
            # Only candidate images
            # =================================================

            if not element.metadata.get(
                "process_with_ai",
                False,
            ):
                continue

            # =================================================
            # Check routing decision
            # =================================================

            route = element.metadata.get(
                "processing_route"
            )

            if route not in {
                OCR_VISION,
                VISION_ONLY,
            }:
                continue

            # =================================================
            # Image must already be extracted
            # =================================================

            image_path = element.metadata.get(
                "extracted_image_path"
            )

            if not image_path:

                element.metadata[
                    "vision_status"
                ] = "SKIPPED_NO_IMAGE_PATH"

                continue

            # =================================================
            # Exact extracted-image hash
            #
            # This hash is produced by image_extractor.py from
            # the final image file that will actually be sent
            # to OCR / Vision.
            #
            # If the hash is missing for any reason, Vision
            # still works normally; that image simply cannot
            # use the duplicate cache.
            # =================================================

            image_hash = element.metadata.get(
                "extracted_image_hash"
            )

            # =================================================
            # VISION CACHE HIT
            #
            # Do this BEFORE checking vision_available.
            #
            # If credits became unavailable after an earlier
            # successful Vision call, an exact duplicate can
            # still reuse the already-cached result without
            # making another API request.
            # =================================================

            if (
                image_hash
                and image_hash in vision_cache
            ):

                cached_result = vision_cache[
                    image_hash
                ]

                element.description = deepcopy(
                    cached_result[
                        "description"
                    ]
                )

                element.relationships = deepcopy(
                    cached_result[
                        "relationships"
                    ]
                )

                element.metadata["vision"] = {
                    "model": (
                        "Qwen/Qwen3-VL-8B-Instruct"
                    ),
                    "route": route,
                }

                element.metadata[
                    "vision_status"
                ] = "DONE"

                element.metadata[
                    "vision_cache_hit"
                ] = True

                element.metadata.pop(
                    "vision_error",
                    None,
                )

                print(
                    "[VISION]",
                    "CACHE_HIT",
                    f"page={unit.index}",
                    f"image={image_path}",
                    f"route={route}",
                )

                continue

            # =================================================
            # Stop NEW Vision calls after a permanent
            # Hugging Face credits error
            # =================================================

            if not vision_available:

                element.metadata[
                    "vision_status"
                ] = "SKIPPED_VISION_UNAVAILABLE"

                element.metadata[
                    "vision_cache_hit"
                ] = False

                print(
                    "[VISION]",
                    "SKIPPED",
                    f"page={unit.index}",
                    "reason=vision_unavailable",
                )

                continue

            # =================================================
            # Send image to Qwen
            # =================================================

            # =================================================
            # OLD VERSION
            # =================================================
            #
            # try:
            #
            #     result = vision_processor.process_image(
            #         image_path=image_path,
            #         visible_text=element.visible_text,
            #     )
            #
            # except Exception as e:
            #
            #     # One failed image should NOT stop
            #     # processing the whole lecture.
            #
            #     element.metadata[
            #         "vision_status"
            #     ] = "FAILED"
            #
            #     element.metadata[
            #         "vision_error"
            #     ] = str(e)
            #
            #     continue

            # =================================================
            # OLD DEBUG VERSION
            # =================================================
            #
            # try:
            #
            #     print(
            #         "[VISION]",
            #         f"processing image={image_path}",
            #         f"route={route}",
            #     )
            #
            #     result = vision_processor.process_image(
            #         image_path=image_path,
            #         visible_text=element.visible_text,
            #     )
            #
            #     print(
            #         "[VISION]",
            #         "DONE",
            #         f"description={bool(result.get('description'))}",
            #         f"relationships={len(result.get('relationships', []))}",
            #     )
            #
            # except Exception as e:
            #
            #     print(
            #         "[VISION]",
            #         "FAILED",
            #         f"image={image_path}",
            #         f"error={e}",
            #     )
            #
            #     element.metadata[
            #         "vision_status"
            #     ] = "FAILED"
            #
            #     element.metadata[
            #         "vision_error"
            #     ] = str(e)
            #
            #     continue

            # =================================================
            # DEBUG + CREDIT HANDLING + CACHE VERSION
            # =================================================

            try:

                print(
                    "[VISION]",
                    "PROCESSING",
                    f"page={unit.index}",
                    f"image={image_path}",
                    f"route={route}",
                )

                result = vision_processor.process_image(
                    image_path=image_path,
                    visible_text=element.visible_text,
                )

                print(
                    "[VISION]",
                    "DONE",
                    f"page={unit.index}",
                    f"description={bool(result.get('description'))}",
                    f"relationships={len(result.get('relationships', []))}",
                )

            except Exception as e:

                error_message = str(e)

                print(
                    "[VISION]",
                    "FAILED",
                    f"page={unit.index}",
                    f"image={image_path}",
                    f"error={error_message}",
                )

                # =================================================
                # Store failure on current image
                # =================================================

                element.metadata[
                    "vision_status"
                ] = "FAILED"

                element.metadata[
                    "vision_error"
                ] = error_message

                element.metadata[
                    "vision_cache_hit"
                ] = False

                # =================================================
                # Detect exhausted Hugging Face credits.
                #
                # A 402 is not an image-specific error.
                # Sending more NEW images would only generate
                # the same failure again.
                # =================================================

                if (
                    "402" in error_message
                    or "Payment Required" in error_message
                    or "depleted your monthly included credits"
                    in error_message
                ):

                    vision_available = False

                    print(
                        "[VISION]",
                        "DISABLED",
                        "reason=huggingface_credits_unavailable",
                    )

                # =================================================
                # Other errors should NOT disable Vision.
                #
                # Example:
                # invalid JSON from one image should allow
                # the next image to still be processed.
                #
                # Failed attempts are intentionally NOT cached.
                # =================================================

                continue

            # =================================================
            # Store visual understanding
            # =================================================

            element.description = result.get(
                "description"
            )

            element.relationships = result.get(
                "relationships",
                [],
            )

            # =================================================
            # Store metadata
            # =================================================

            element.metadata["vision"] = {
                "model": (
                    "Qwen/Qwen3-VL-8B-Instruct"
                ),
                "route": route,
            }

            element.metadata[
                "vision_status"
            ] = "DONE"

            element.metadata[
                "vision_cache_hit"
            ] = False

            element.metadata.pop(
                "vision_error",
                None,
            )

            # =================================================
            # Save successful Vision result in cache
            #
            # Only successful results are cached.
            # =================================================

            if image_hash:

                vision_cache[
                    image_hash
                ] = {
                    "description": deepcopy(
                        element.description
                    ),
                    "relationships": deepcopy(
                        element.relationships
                    ),
                }

    return document
