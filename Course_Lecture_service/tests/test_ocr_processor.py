import sys
import time
from pathlib import Path

import easyocr
from paddleocr import PaddleOCR


def run_easyocr(image_path: str) -> dict:
    """
    Run EasyOCR on one image.
    """

    reader = easyocr.Reader(
        ["ar", "en"],
        gpu=False,
    )

    start_time = time.perf_counter()

    results = reader.readtext(
        image_path,
        detail=1,
        paragraph=False,
    )

    elapsed = time.perf_counter() - start_time

    lines = []

    for result in results:
        if len(result) < 3:
            continue

        bbox = result[0]
        text = str(result[1]).strip()
        confidence = float(result[2])

        if not text:
            continue

        lines.append({
            "text": text,
            "confidence": confidence,
            "bbox": bbox,
        })

    full_text = "\n".join(
        line["text"]
        for line in lines
    )

    average_confidence = 0.0

    if lines:
        average_confidence = (
            sum(
                line["confidence"]
                for line in lines
            )
            / len(lines)
        )

    return {
        "engine": "EasyOCR",
        "full_text": full_text,
        "lines": lines,
        "text_count": len(lines),
        "average_confidence": average_confidence,
        "elapsed_seconds": elapsed,
    }


def run_paddleocr(image_path: str) -> dict:
    """
    Run PaddleOCR on one image.
    """

    ocr = PaddleOCR(
        lang="ar",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    start_time = time.perf_counter()

    results = ocr.predict(
        image_path
    )

    elapsed = time.perf_counter() - start_time

    lines = []

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

        for index, text in enumerate(texts):

            cleaned_text = str(text).strip()

            if not cleaned_text:
                continue

            confidence = 0.0

            if index < len(scores):
                confidence = float(
                    scores[index]
                )

            polygon = None

            if index < len(polygons):

                raw_polygon = polygons[index]

                if hasattr(
                    raw_polygon,
                    "tolist",
                ):
                    polygon = raw_polygon.tolist()
                else:
                    polygon = raw_polygon

            lines.append({
                "text": cleaned_text,
                "confidence": confidence,
                "bbox": polygon,
            })

    full_text = "\n".join(
        line["text"]
        for line in lines
    )

    average_confidence = 0.0

    if lines:
        average_confidence = (
            sum(
                line["confidence"]
                for line in lines
            )
            / len(lines)
        )

    return {
        "engine": "PaddleOCR",
        "full_text": full_text,
        "lines": lines,
        "text_count": len(lines),
        "average_confidence": average_confidence,
        "elapsed_seconds": elapsed,
    }


def print_result(result: dict):

    print()
    print("=" * 70)
    print(result["engine"])
    print("=" * 70)

    print()
    print("Detected text:")
    print("-" * 70)

    if result["full_text"]:
        print(result["full_text"])
    else:
        print("[No text detected]")

    print()
    print("-" * 70)

    print(
        f"Text count         : "
        f"{result['text_count']}"
    )

    print(
        f"Average confidence : "
        f"{result['average_confidence']:.4f}"
    )

    print(
        f"OCR time           : "
        f"{result['elapsed_seconds']:.2f} seconds"
    )

    print("-" * 70)


def compare_ocr(image_path: str):

    path = Path(image_path)

    if not path.exists():
        print(
            f"ERROR: Image does not exist: "
            f"{image_path}"
        )
        return

    if not path.is_file():
        print(
            f"ERROR: Path is not a file: "
            f"{image_path}"
        )
        return

    print("=" * 70)
    print("OCR COMPARISON TEST")
    print("=" * 70)

    print(f"Image: {path.name}")
    print(f"Path : {path.resolve()}")

    # =========================================================
    # EasyOCR
    # =========================================================

    try:
        easy_result = run_easyocr(
            str(path)
        )

        print_result(
            easy_result
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("EasyOCR FAILED")
        print("=" * 70)
        print(str(e))

    # =========================================================
    # PaddleOCR
    # =========================================================

    try:
        paddle_result = run_paddleocr(
            str(path)
        )

        print_result(
            paddle_result
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("PaddleOCR FAILED")
        print("=" * 70)
        print(str(e))


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 test_ocr_processor.py "
            '"path/to/image.png"'
        )

        sys.exit(1)

    compare_ocr(
        sys.argv[1]
    )