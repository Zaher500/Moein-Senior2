import sys
import time
from pathlib import Path

from Course.utils.document_processing.vision_processor import (
    VisionProcessor,
)


def test_vision_processor(image_path: str):

    print("=" * 70)
    print("VISION PROCESSOR TEST")
    print("=" * 70)

    path = Path(image_path)

    if not path.exists():
        print(f"ERROR: Image not found: {image_path}")
        return

    print(f"Image: {path.name}")
    print(f"Path : {path.resolve()}")
    print()

    # نص OCR تقريبي من الصورة
    # فقط حتى نجرب image + OCR context مع بعض
    visible_text = [
        "1.3 – Maturity Level",
        "2.0 – Maturity Level",
        "Optimizing",
        "Quantitatively Managed",
        "Defined",
        "Managed",
        "Initial",
        "Focus on process improvement",
        "Process measured and controlled",
        "Process characterized for the organization",
        "Process characterized for projects",
    ]

    try:
        print("Creating VisionProcessor...")

        processor = VisionProcessor()

    except Exception as e:
        print()
        print("VISION PROCESSOR INITIALIZATION FAILED")
        print("-" * 70)
        print(str(e))
        return

    print("Sending image to Qwen3-VL...")
    print()

    start_time = time.perf_counter()

    try:
        result = processor.process_image(
            image_path=str(path),
            visible_text=visible_text,
        )

    except Exception as e:
        print()
        print("VISION REQUEST FAILED")
        print("-" * 70)
        print(str(e))
        return

    elapsed = time.perf_counter() - start_time

    print("=" * 70)
    print("QWEN3-VL RESULT")
    print("=" * 70)
    print()

    print("Description:")
    print("-" * 70)
    print(result.get("description", ""))
    print("-" * 70)

    print()
    print(
        f"Relationships: "
        f"{result.get('relationships', [])}"
    )

    print()
    print(
        f"Vision time: {elapsed:.2f} seconds"
    )

    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "py -3.12 test_vision_processor.py "
            '"path/to/image.png"'
        )

        sys.exit(1)

    test_vision_processor(
        sys.argv[1]
    )