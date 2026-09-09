import sys
import time
from pathlib import Path

from sympy import content

from Course.utils.document_processing.pipeline import (
    process_document_for_summarization,
)


def test_document_pipeline(
    file_path: str,
):

    print("=" * 70)
    print("FULL DOCUMENT PIPELINE TEST")
    print("=" * 70)

    path = Path(file_path)

    if not path.exists():

        print(
            f"ERROR: File not found: "
            f"{file_path}"
        )

        return

    print(
        f"File: {path.name}"
    )

    print()

    start_time = (
        time.perf_counter()
    )

    try:

        content = (
            process_document_for_summarization(
                str(path)
            )
        )

    except Exception as e:

        print(
            "PIPELINE FAILED"
        )

        print("-" * 70)

        print(str(e))

        return

    elapsed = (
        time.perf_counter()
        - start_time
    )

    print()
    print("=" * 70)
    print("PIPELINE SUCCESS")
    print("=" * 70)

    print(
        f"Final characters : "
        f"{len(content)}"
    )

    print(
        f"Processing time  : "
        f"{elapsed:.2f} seconds"
    )

    # =========================================================
    # Check pages
    # =========================================================

    print(
        "Has Page 35:",
        "===== PAGE 35 =====" in content
    )

    page_count = sum(
        1
        for i in range(1, 36)
        if f"===== PAGE {i} =====" in content
    )

    print(
        "Pages found in content:",
        page_count
    )

    print()

    print("=" * 70)
    print("CONTENT PREVIEW")
    print("=" * 70)

    print(
        content[:5000]
    )

    print()
    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "py -3.12 "
            "test_document_pipeline.py "
            '"path/to/file.pdf"'
        )

        sys.exit(1)

    test_document_pipeline(
        sys.argv[1]
    )