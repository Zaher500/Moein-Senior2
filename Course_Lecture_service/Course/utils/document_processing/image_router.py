# from statistics import median

# from PIL import Image

# from .schemas import DocumentElement, ProcessedDocument


# OCR_ONLY = "ocr_only"
# OCR_VISION = "ocr_vision"
# VISION_ONLY = "vision_only"


# def apply_image_routing(
#     document: ProcessedDocument,
# ) -> ProcessedDocument:
#     """
#     Decide what should happen to every OCR-processed image.

#     Routes:
#         ocr_only
#             Text-heavy scanned image.
#             OCR result is enough.

#         ocr_vision
#             Contains text, but probably has visual structure
#             such as diagrams, flowcharts, charts or infographics.

#         vision_only
#             Little or no useful OCR text.
#             Visual understanding is required.
#     """

#     for unit in document.get_ordered_units():

#         for element in unit.get_ordered_elements():

#             if element.type != "image":
#                 continue

#             if not element.metadata.get(
#                 "process_with_ai",
#                 False,
#             ):
#                 continue

#             route_image_element(element)

#     return document


# def route_image_element(
#     element: DocumentElement,
# ) -> str:

#     ocr_status = element.metadata.get(
#         "ocr_status"
#     )

#     ocr_metadata = element.metadata.get(
#         "ocr",
#         {},
#     )

#     visible_text = element.visible_text or []

#     # =========================================================
#     # OCR failed / no OCR result
#     # =========================================================

#     if ocr_status != "DONE":

#         _save_route(
#             element=element,
#             route=VISION_ONLY,
#             reason="ocr_not_available",
#         )

#         return VISION_ONLY

#     # =========================================================
#     # No visible text detected
#     # =========================================================

#     if not visible_text:

#         _save_route(
#             element=element,
#             route=VISION_ONLY,
#             reason="no_visible_text_detected",
#         )

#         return VISION_ONLY

#     image_path = element.metadata.get(
#         "extracted_image_path"
#     )

#     if not image_path:

#         _save_route(
#             element=element,
#             route=OCR_VISION,
#             reason="missing_image_dimensions",
#         )

#         return OCR_VISION

#     # =========================================================
#     # Image dimensions
#     # =========================================================

#     try:

#         with Image.open(image_path) as image:

#             image_width = float(image.width)
#             image_height = float(image.height)

#     except Exception:

#         _save_route(
#             element=element,
#             route=OCR_VISION,
#             reason="could_not_read_image_dimensions",
#         )

#         return OCR_VISION

#     if image_width <= 0 or image_height <= 0:

#         _save_route(
#             element=element,
#             route=OCR_VISION,
#             reason="invalid_image_dimensions",
#         )

#         return OCR_VISION

#     # =========================================================
#     # OCR metrics
#     # =========================================================

#     lines = ocr_metadata.get(
#         "lines",
#         [],
#     )

#     confidence = float(
#         ocr_metadata.get(
#             "average_confidence",
#             0.0,
#         )
#     )

#     text_count = int(
#         ocr_metadata.get(
#             "text_count",
#             len(visible_text),
#         )
#     )

#     total_characters = sum(
#         len(text.strip())
#         for text in visible_text
#     )

#     width_ratios = []

#     for line in lines:

#         bbox = line.get("bbox")

#         if not bbox:
#             continue

#         try:

#             xs = [
#                 float(point[0])
#                 for point in bbox
#             ]

#             box_width = max(xs) - min(xs)

#             width_ratio = (
#                 box_width / image_width
#             )

#             width_ratios.append(
#                 width_ratio
#             )

#         except Exception:
#             continue

#     # =========================================================
#     # Text layout metrics
#     # =========================================================

#     if width_ratios:

#         median_width_ratio = median(
#             width_ratios
#         )

#         wide_lines = [
#             ratio
#             for ratio in width_ratios
#             if ratio >= 0.45
#         ]

#         wide_line_ratio = (
#             len(wide_lines)
#             / len(width_ratios)
#         )

#     else:

#         median_width_ratio = 0.0
#         wide_line_ratio = 0.0

#     metrics = {
#         "average_confidence": round(
#             confidence,
#             4,
#         ),
#         "text_count": text_count,
#         "total_characters": total_characters,
#         "median_text_width_ratio": round(
#             median_width_ratio,
#             4,
#         ),
#         "wide_line_ratio": round(
#             wide_line_ratio,
#             4,
#         ),
#     }

#     # =========================================================
#     # Strong evidence that image is mostly normal text
#     # =========================================================

#     text_heavy = (
#         confidence >= 0.75
#         and text_count >= 5
#         and total_characters >= 120
#         and wide_line_ratio >= 0.40
#     )

#     if text_heavy:

#         _save_route(
#             element=element,
#             route=OCR_ONLY,
#             reason="text_heavy_image",
#             metrics=metrics,
#         )

#         return OCR_ONLY

#     # =========================================================
#     # Otherwise keep visual understanding
#     # =========================================================

#     _save_route(
#         element=element,
#         route=OCR_VISION,
#         reason="possible_visual_structure",
#         metrics=metrics,
#     )

#     return OCR_VISION


# def _save_route(
#     element: DocumentElement,
#     route: str,
#     reason: str,
#     metrics: dict | None = None,
# ) -> None:

#     element.metadata["processing_route"] = route
#     element.metadata["routing_reason"] = reason

#     if metrics is not None:

#         element.metadata[
#             "routing_metrics"
#         ] = metrics













from statistics import median

from PIL import Image

from .schemas import DocumentElement, ProcessedDocument


OCR_ONLY = "ocr_only"
OCR_VISION = "ocr_vision"
VISION_ONLY = "vision_only"


def apply_image_routing(
    document: ProcessedDocument,
) -> ProcessedDocument:
    """
    Decide what should happen to every OCR-processed image.

    Routes:
        ocr_only
            Strong evidence that the image is mainly normal
            paragraph-like text and OCR is sufficient.

        ocr_vision
            OCR text exists, but visual/layout understanding
            may be important.

        vision_only
            OCR failed or no useful OCR text was detected.
    """

    for unit in document.get_ordered_units():

        for element in unit.get_ordered_elements():

            if element.type != "image":
                continue

            if not element.metadata.get(
                "process_with_ai",
                False,
            ):
                continue

            route_image_element(element)

    return document


def route_image_element(
    element: DocumentElement,
) -> str:

    ocr_status = element.metadata.get(
        "ocr_status"
    )

    ocr_metadata = element.metadata.get(
        "ocr",
        {},
    )

    visible_text = element.visible_text or []

    # =========================================================
    # OCR failed / unavailable
    # =========================================================

    if ocr_status != "DONE":

        _save_route(
            element=element,
            route=VISION_ONLY,
            reason="ocr_not_available",

        )

        return VISION_ONLY

    # =========================================================
    # No OCR text
    # =========================================================

    if not visible_text:

        _save_route(
            element=element,
            route=VISION_ONLY,
            reason="no_visible_text_detected",
        )

        return VISION_ONLY

    image_path = element.metadata.get(
        "extracted_image_path"
    )

    if not image_path:

        _save_route(
            element=element,
            route=OCR_VISION,
            reason="missing_image_dimensions",
        )

        return OCR_VISION

    # =========================================================
    # Read image dimensions
    # =========================================================

    try:

        with Image.open(image_path) as image:

            image_width = float(image.width)
            image_height = float(image.height)

    except Exception:

        _save_route(
            element=element,
            route=OCR_VISION,
            reason="could_not_read_image_dimensions",
        )

        return OCR_VISION

    if image_width <= 0 or image_height <= 0:

        _save_route(
            element=element,
            route=OCR_VISION,
            reason="invalid_image_dimensions",
        )

        return OCR_VISION

    # =========================================================
    # OCR metrics
    # =========================================================

    lines = ocr_metadata.get(
        "lines",
        [],
    )

    confidence = float(
        ocr_metadata.get(
            "average_confidence",
            0.0,
        )
    )

    text_count = int(
        ocr_metadata.get(
            "text_count",
            len(visible_text),
        )
    )

    total_characters = sum(
        len(str(text).strip())
        for text in visible_text
    )

    width_ratios = []
    left_positions = []
    right_positions = []

    for line in lines:

        bbox = line.get("bbox")

        if not bbox:
            continue

        try:

            xs = [
                float(point[0])
                for point in bbox
            ]

            box_left = min(xs)
            box_right = max(xs)
            box_width = box_right - box_left

            if box_width <= 0:
                continue

            width_ratios.append(
                box_width / image_width
            )

            left_positions.append(
                box_left / image_width
            )

            right_positions.append(
                box_right / image_width
            )

        except Exception:
            continue

    # =========================================================
    # If OCR did not provide usable geometry,
    # visual understanding is safer.
    # =========================================================

    if not width_ratios:

        metrics = {
            "average_confidence": round(
                confidence,
                4,
            ),
            "text_count": text_count,
            "total_characters": total_characters,
        }

        _save_route(
            element=element,
            route=OCR_VISION,
            reason="missing_ocr_layout_geometry",
            metrics=metrics,
        )

        return OCR_VISION

    # =========================================================
    # Layout metrics
    # =========================================================

    median_width_ratio = median(
        width_ratios
    )

    wide_lines = [
        ratio
        for ratio in width_ratios
        if ratio >= 0.45
    ]

    short_lines = [
        ratio
        for ratio in width_ratios
        if ratio <= 0.30
    ]

    very_short_lines = [
        ratio
        for ratio in width_ratios
        if ratio <= 0.15
    ]

    wide_line_ratio = (
        len(wide_lines)
        / len(width_ratios)
    )

    short_line_ratio = (
        len(short_lines)
        / len(width_ratios)
    )

    very_short_line_ratio = (
        len(very_short_lines)
        / len(width_ratios)
    )

    # Paragraph text usually has either:
    # - similar left edges (English / LTR)
    # - similar right edges (Arabic / RTL)
    #
    # Tables / diagrams usually have text distributed
    # across many horizontal positions.

    left_alignment_spread = _median_absolute_deviation(
        left_positions
    )

    right_alignment_spread = _median_absolute_deviation(
        right_positions
    )

    edge_alignment_spread = min(
        left_alignment_spread,
        right_alignment_spread,
    )

    metrics = {
        "average_confidence": round(
            confidence,
            4,
        ),
        "text_count": text_count,
        "total_characters": total_characters,
        "median_text_width_ratio": round(
            median_width_ratio,
            4,
        ),
        "wide_line_ratio": round(
            wide_line_ratio,
            4,
        ),
        "short_line_ratio": round(
            short_line_ratio,
            4,
        ),
        "very_short_line_ratio": round(
            very_short_line_ratio,
            4,
        ),
        "edge_alignment_spread": round(
            edge_alignment_spread,
            4,
        ),
    }

    # =========================================================
    # Evidence of visual structure
    #
    # Many short/scattered text boxes often indicate:
    # - tables
    # - diagrams
    # - flowcharts
    # - infographics
    # - matrices
    # - multi-column layouts
    # =========================================================

    possible_visual_structure = (
        short_line_ratio >= 0.45
        or (
            text_count >= 8
            and very_short_line_ratio >= 0.25
        )
        or (
            short_line_ratio >= 0.25
            and edge_alignment_spread >= 0.12
        )
        or (
            text_count >= 10
            and median_width_ratio < 0.30
        )
    )

    if possible_visual_structure:

        _save_route(
            element=element,
            route=OCR_VISION,
            reason="layout_sensitive_image",
            metrics=metrics,
        )

        return OCR_VISION

    # =========================================================
    # Strong evidence of normal paragraph-like text
    #
    # OCR_ONLY must be conservative.
    # =========================================================

    paragraph_like_text = (
        confidence >= 0.78
        and text_count >= 5
        and total_characters >= 160
        and median_width_ratio >= 0.40
        and wide_line_ratio >= 0.50
        and short_line_ratio <= 0.35
        and edge_alignment_spread <= 0.10
    )

    if paragraph_like_text:

        _save_route(
            element=element,
            route=OCR_ONLY,
            reason="strong_paragraph_like_text",
            metrics=metrics,
        )

        return OCR_ONLY

    # =========================================================
    # Anything uncertain gets OCR + Vision
    # =========================================================

    _save_route(
        element=element,
        route=OCR_VISION,
        reason="uncertain_layout_keep_visual_understanding",
        metrics=metrics,
    )

    return OCR_VISION


def _median_absolute_deviation(
    values: list[float],
) -> float:
    """
    Robust measurement of how spread out values are.

    Lower value:
        text edges are aligned, which is common in paragraphs.

    Higher value:
        text is scattered horizontally, which may indicate
        tables, diagrams, charts, or other structured layouts.
    """

    if not values:
        return 0.0

    center = median(values)

    deviations = [
        abs(value - center)
        for value in values
    ]

    return median(deviations)


def _save_route(
    element: DocumentElement,
    route: str,
    reason: str,
    metrics: dict | None = None,
) -> None:

    element.metadata["processing_route"] = route
    element.metadata["routing_reason"] = reason

    if metrics is not None:

        element.metadata[
            "routing_metrics"
        ] = metrics

    print(
        "[ROUTER]",
        f"route={route}",
        f"reason={reason}",
        f"metrics={metrics}"
    )