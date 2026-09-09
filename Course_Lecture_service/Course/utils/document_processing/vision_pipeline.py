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

    Vision results are stored in:
        element.description
        element.relationships
    """

    # =================================================
    # Load/create the API client only once
    # =================================================

    vision_processor = VisionProcessor()

    # =================================================
    # NEW:
    # If Hugging Face Vision credits become unavailable,
    # stop sending the remaining images to Vision.
    # OCR content will still remain available.
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
            # NEW:
            # Stop Vision calls after a permanent credits error
            # =================================================

            if not vision_available:

                element.metadata[
                    "vision_status"
                ] = "SKIPPED_VISION_UNAVAILABLE"

                print(
                    "[VISION]",
                    "SKIPPED",
                    f"page={unit.index}",
                    "reason=vision_unavailable",
                )

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
            # NEW DEBUG + CREDIT HANDLING VERSION
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

                # =================================================
                # NEW:
                # Detect exhausted Hugging Face credits.
                #
                # A 402 is not an image-specific error.
                # Sending more images would only generate
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

    return document