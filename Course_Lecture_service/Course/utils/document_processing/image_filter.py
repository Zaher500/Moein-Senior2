from collections import Counter
from math import ceil

from .schemas import ProcessedDocument


def mark_image_candidates(
    document: ProcessedDocument,
) -> None:
    """
    Mark detected images as candidates for future
    OCR / Vision processing.

    Important:
    No image is deleted.

    Every image receives:

        process_with_ai = True / False

    Skipped images also receive:

        skip_reason = "..."

    Repeated decorative images are detected using:

        actual image content hash
        +
        approximate position
        +
        repetition across pages

    This is safer than using position alone.
    """

    # =========================================================
    # DOCX handling
    # =========================================================
    #
    # DOCX does not expose reliable physical page coordinates
    # like PDF.
    #
    # Therefore we do not apply the PDF position-based rules.
    # Keep DOCX image handling conservative and send every
    # detected embedded image to OCR / Vision.
    #

    if document.file_type == "docx":

        _mark_docx_image_candidates(
            document
        )

        return

    # =========================================================
    # PPTX handling
    # =========================================================
    #
    # PowerPoint slides do provide coordinates,
    # but their visual structure differs from PDF pages.
    #
    # For now, keep PPTX handling conservative:
    #
    # - normal pictures
    # - picture placeholders
    # - charts
    # - grouped diagrams
    #
    # are all kept as AI candidates.
    #
    # We do not apply the PDF repeated-header/footer rules
    # to PPTX slides at this stage.
    #

    if document.file_type == "pptx":

        _mark_pptx_image_candidates(
            document
        )

        return

    # =========================================================
    # PDF handling
    # =========================================================

    image_records = []

    # =========================================================
    # 1. Collect image information
    # =========================================================

    for unit in document.units:

        page_width = float(
            unit.metadata.get(
                "width",
                0,
            )
        )

        page_height = float(
            unit.metadata.get(
                "height",
                0,
            )
        )

        if (
            page_width <= 0
            or page_height <= 0
        ):
            continue

        for element in unit.elements:

            if element.type != "image":
                continue

            if element.bbox is None:
                continue

            bbox = element.bbox

            x_ratio = (
                bbox.x / page_width
            )

            y_ratio = (
                bbox.y / page_height
            )

            width_ratio = (
                bbox.width / page_width
            )

            height_ratio = (
                bbox.height / page_height
            )

            area_ratio = (
                bbox.width
                * bbox.height
            ) / (
                page_width
                * page_height
            )

            # Approximate visual position.
            position_signature = (
                round(x_ratio, 2),
                round(y_ratio, 2),
                round(width_ratio, 2),
                round(height_ratio, 2),
            )

            content_hash = (
                element.metadata.get(
                    "content_hash"
                )
            )

            image_records.append({
                "unit": unit,
                "element": element,
                "content_hash": content_hash,
                "position_signature":
                    position_signature,
                "x_ratio": x_ratio,
                "y_ratio": y_ratio,
                "width_ratio": width_ratio,
                "height_ratio": height_ratio,
                "area_ratio": area_ratio,
            })

    # =========================================================
    # 2. Count truly repeated images
    # =========================================================

    repetition_keys = []

    for record in image_records:

        content_hash = record[
            "content_hash"
        ]

        if not content_hash:
            continue

        repetition_key = (
            content_hash,
            record[
                "position_signature"
            ],
        )

        repetition_keys.append(
            repetition_key
        )

    repetition_counts = Counter(
        repetition_keys
    )

    repeat_threshold = max(
        3,
        ceil(
            len(document.units)
            * 0.10
        ),
    )

    # =========================================================
    # 3. Classify each image
    # =========================================================

    for record in image_records:

        element = record["element"]

        area_ratio = record[
            "area_ratio"
        ]

        x_ratio = record[
            "x_ratio"
        ]

        y_ratio = record[
            "y_ratio"
        ]

        width_ratio = record[
            "width_ratio"
        ]

        height_ratio = record[
            "height_ratio"
        ]

        content_hash = record[
            "content_hash"
        ]

        bottom_ratio = (
            y_ratio
            + height_ratio
        )

        right_ratio = (
            x_ratio
            + width_ratio
        )

        near_top = (
            y_ratio < 0.10
        )

        near_bottom = (
            bottom_ratio > 0.85
        )

        near_left = (
            x_ratio < 0.04
        )

        near_right = (
            right_ratio > 0.96
        )

        # ---------------------------------------------
        # Determine actual repetition count
        # ---------------------------------------------

        repeated_count = 1

        if content_hash:

            repetition_key = (
                content_hash,
                record[
                    "position_signature"
                ],
            )

            repeated_count = (
                repetition_counts.get(
                    repetition_key,
                    1,
                )
            )

        repeated = (
            repeated_count
            >= repeat_threshold
        )

        process_with_ai = True
        skip_reason = None

        # =====================================================
        # Rule 1: extremely tiny image
        # =====================================================

        if area_ratio < 0.001:

            process_with_ai = False

            skip_reason = (
                "tiny_image"
            )

        # =====================================================
        # Rule 2:
        # Same actual image + same position + repeated
        # near header/footer.
        # =====================================================

        elif (
            repeated
            and (
                near_top
                or near_bottom
            )
            and area_ratio < 0.08
        ):

            process_with_ai = False

            skip_reason = (
                "repeated_header_footer"
            )

        # =====================================================
        # Rule 3:
        # Small repeated decoration on an edge.
        # =====================================================

        elif (
            repeated
            and (
                near_left
                or near_right
            )
            and area_ratio < 0.02
        ):

            process_with_ai = False

            skip_reason = (
                "repeated_edge_decoration"
            )

        # =====================================================
        # Store decision
        # =====================================================

        element.metadata[
            "process_with_ai"
        ] = process_with_ai

        element.metadata[
            "area_ratio"
        ] = round(
            area_ratio,
            4,
        )

        element.metadata[
            "repeated_count"
        ] = repeated_count

        if skip_reason:

            element.metadata[
                "skip_reason"
            ] = skip_reason

        else:

            element.metadata.pop(
                "skip_reason",
                None,
            )

    # =========================================================
    # 4. Safety fallback
    # =========================================================

    for unit in document.units:

        page_height = float(
            unit.metadata.get(
                "height",
                0,
            )
        )

        if page_height <= 0:
            continue

        image_elements = [
            element
            for element in unit.elements
            if (
                element.type == "image"
                and element.bbox
            )
        ]

        if not image_elements:
            continue

        body_text_parts = []

        for element in unit.elements:

            if element.type != "text":
                continue

            if not element.text:
                continue

            if not element.bbox:
                continue

            y_ratio = (
                element.bbox.y
                / page_height
            )

            # Ignore obvious bottom footer text
            # when estimating useful native content.
            if y_ratio >= 0.85:
                continue

            body_text_parts.append(
                element.text.strip()
            )

        body_text = " ".join(
            body_text_parts
        ).strip()

        body_text_length = len(
            body_text
        )

        has_candidate = any(
            element.metadata.get(
                "process_with_ai",
                False,
            )
            for element
            in image_elements
        )

        # ---------------------------------------------
        # Page safety condition
        # ---------------------------------------------

        if (
            body_text_length < 80
            and not has_candidate
        ):

            largest_image = max(
                image_elements,
                key=lambda element: (
                    element.bbox.width
                    * element.bbox.height
                ),
            )

            largest_image.metadata[
                "process_with_ai"
            ] = True

            largest_image.metadata.pop(
                "skip_reason",
                None,
            )

            largest_image.metadata[
                "selection_reason"
            ] = (
                "low_text_page_fallback"
            )


def _mark_docx_image_candidates(
    document: ProcessedDocument,
) -> None:
    """
    Conservatively mark DOCX images for OCR / Vision.

    DOCX files do not provide reliable physical page
    coordinates through python-docx.

    Therefore:
    - do not apply PDF position-based filtering
    - do not skip repeated images automatically
    - keep every embedded image as an AI candidate

    Repetition information is still stored for debugging
    and possible future refinement.
    """

    image_elements = []

    # =========================================================
    # 1. Collect DOCX image elements
    # =========================================================

    for unit in document.units:

        for element in unit.elements:

            if element.type != "image":
                continue

            image_elements.append(
                element
            )

    # =========================================================
    # 2. Count repeated images by content hash
    # =========================================================

    hash_counts = Counter(
        element.metadata.get(
            "content_hash"
        )
        for element in image_elements
        if element.metadata.get(
            "content_hash"
        )
    )

    # =========================================================
    # 3. Mark all DOCX images as AI candidates
    # =========================================================

    for element in image_elements:

        content_hash = (
            element.metadata.get(
                "content_hash"
            )
        )

        repeated_count = 1

        if content_hash:

            repeated_count = (
                hash_counts.get(
                    content_hash,
                    1,
                )
            )

        element.metadata[
            "process_with_ai"
        ] = True

        element.metadata[
            "repeated_count"
        ] = repeated_count

        element.metadata[
            "selection_reason"
        ] = (
            "docx_conservative_image_selection"
        )

        element.metadata.pop(
            "skip_reason",
            None,
        )


def _mark_pptx_image_candidates(
    document: ProcessedDocument,
) -> None:
    """
    Conservatively mark PPTX visual elements for OCR / Vision.

    PPTX visual elements can include:
    - normal embedded pictures
    - picture placeholders
    - charts
    - grouped diagrams

    For the first PPTX implementation:

    - do not apply PDF header/footer filtering
    - do not automatically skip repeated visuals
    - keep every detected visual as an AI candidate

    Repetition information is stored when a content hash
    is available.
    """

    image_elements = []

    # =========================================================
    # 1. Collect PPTX visual elements
    # =========================================================

    for unit in document.units:

        for element in unit.elements:

            if element.type != "image":
                continue

            image_elements.append(
                element
            )

    # =========================================================
    # 2. Count repeated embedded images
    # =========================================================
    #
    # Normal pictures usually have content_hash.
    #
    # Charts and grouped diagrams may not have one,
    # because they are not stored as a single embedded image.
    #

    hash_counts = Counter(
        element.metadata.get(
            "content_hash"
        )
        for element in image_elements
        if element.metadata.get(
            "content_hash"
        )
    )

    # =========================================================
    # 3. Mark all PPTX visuals as AI candidates
    # =========================================================

    for element in image_elements:

        content_hash = (
            element.metadata.get(
                "content_hash"
            )
        )

        repeated_count = 1

        if content_hash:

            repeated_count = (
                hash_counts.get(
                    content_hash,
                    1,
                )
            )

        element.metadata[
            "process_with_ai"
        ] = True

        element.metadata[
            "repeated_count"
        ] = repeated_count

        element.metadata[
            "selection_reason"
        ] = (
            "pptx_conservative_image_selection"
        )

        element.metadata.pop(
            "skip_reason",
            None,
        )