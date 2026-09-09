from pathlib import Path
from statistics import mean

from paddleocr import PaddleOCR


class OCRProcessor:
    """
    OCR processor using PaddleOCR.

    Responsibilities:
    - Extract visible text from an image.
    - Return text regions.
    - Return confidence scores.
    - Return bounding polygons.

    It does NOT:
    - understand diagrams
    - explain charts
    - infer relationships
    """

    def __init__(self):

        self.ocr = PaddleOCR(
        lang="ar",
        ocr_version="PP-OCRv5",
        device="gpu:0",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    def process_image(
        self,
        image_path: str,
    ) -> dict:
        """
        Run OCR on one image.

        Returns:

        {
            "full_text": "...",

            "visible_text": [
                "...",
                "..."
            ],

            "lines": [
                {
                    "text": "...",
                    "confidence": 0.95,
                    "bbox": [...]
                }
            ],

            "average_confidence": 0.93,
            "text_count": 10
        }
        """

        path = Path(image_path)

        # =====================================================
        # Validate image path
        # =====================================================

        if not path.exists():

            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        if not path.is_file():

            raise ValueError(
                f"Path is not a file: {image_path}"
            )

        # =====================================================
        # Run PaddleOCR
        # =====================================================

        try:

            results = self.ocr.predict(
                str(path)
            )

        except Exception as e:

            raise RuntimeError(
                f"OCR failed for "
                f"'{image_path}': {str(e)}"
            ) from e

        lines = []

        # =====================================================
        # Parse PaddleOCR results
        # =====================================================

        for result in results:

            result_data = result.json

            data = result_data.get(
                "res",
                result_data,
            )

            texts = data.get(
                "rec_texts",
                [],
            )

            scores = data.get(
                "rec_scores",
                [],
            )

            polygons = data.get(
                "rec_polys",
                [],
            )

            for index, text in enumerate(
                texts
            ):

                cleaned_text = (
                    str(text).strip()
                )

                if not cleaned_text:
                    continue

                # ---------------------------------------------
                # Confidence
                # ---------------------------------------------

                confidence = 0.0

                if index < len(scores):

                    confidence = float(
                        scores[index]
                    )

                # ---------------------------------------------
                # Bounding polygon
                # ---------------------------------------------

                bbox = None

                if index < len(polygons):

                    raw_polygon = polygons[
                        index
                    ]

                    if hasattr(
                        raw_polygon,
                        "tolist",
                    ):

                        bbox = (
                            raw_polygon.tolist()
                        )

                    else:

                        bbox = (
                            raw_polygon
                        )

                lines.append({
                    "text": cleaned_text,
                    "confidence": confidence,
                    "bbox": bbox,
                })

        # =====================================================
        # Build visible text
        # =====================================================

        visible_text = [
            line["text"]
            for line in lines
        ]

        full_text = "\n".join(
            visible_text
        )

        # =====================================================
        # Average confidence
        # =====================================================

        confidences = [
            line["confidence"]
            for line in lines
            if line["confidence"] > 0
        ]

        average_confidence = (
            mean(confidences)
            if confidences
            else 0.0
        )

        # =====================================================
        # Final OCR result
        # =====================================================

        return {
            "full_text": full_text,
            "visible_text": visible_text,
            "lines": lines,

            "average_confidence": round(
                average_confidence,
                4,
            ),

            "text_count": len(lines),
        }