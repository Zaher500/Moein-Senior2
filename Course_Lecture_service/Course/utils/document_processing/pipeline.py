from pathlib import Path
from tempfile import TemporaryDirectory

from .processor import process_document
from .image_extractor import extract_candidate_images
from .ocr_pipeline import apply_ocr_to_document
from .image_router import apply_image_routing
from .vision_pipeline import apply_vision_to_document
from .content_builder import build_summarization_content


def process_document_for_summarization(
    file_path: str,
) -> str:
    """
    Full document-understanding pipeline.

    Flow:
        document parsing
        -> image extraction
        -> OCR
        -> image routing
        -> vision understanding
        -> final ordered text

    Returns:
        Final textual content ready for summarization.
    """

    path = Path(file_path)

    # =========================================================
    # Validate input
    # =========================================================

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    # =========================================================
    # 1. Parse document
    # =========================================================

    document = process_document(
        str(path)
    )

    # =========================================================
    # Temporary directory for extracted images
    #
    # We don't need to permanently keep the images after
    # OCR + Vision are finished.
    # =========================================================

    with TemporaryDirectory(
        prefix="moein_document_images_"
    ) as temp_dir:

        # =====================================================
        # 2. Extract candidate images
        # =====================================================

        extract_candidate_images(
            document=document,
            output_dir=temp_dir,
            zoom=2.0,
        )

        # =====================================================
        # 3. OCR
        # =====================================================

        document = apply_ocr_to_document(
            document
        )

        # =====================================================
        # 4. Decide which images need Vision
        # =====================================================

        document = apply_image_routing(
            document
        )

        # =====================================================
        # 5. Vision understanding
        # =====================================================

        document = apply_vision_to_document(
            document
        )

        # =====================================================
        # 6. Build ordered final content
        # =====================================================

        final_content = (
            build_summarization_content(
                document
            )
        )

    return final_content