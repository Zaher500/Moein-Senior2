from pathlib import Path

from .schemas import ProcessedDocument


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
}


def process_document(file_path: str) -> ProcessedDocument:
    """
    Main entry point for processing lecture documents.

    Detects the uploaded file type and sends it to
    the appropriate parser.

    Supported:
    - PDF
    - DOCX
    - PPTX
    """

    path = Path(file_path)

    # 1. Make sure the file exists
    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    # 2. Detect file extension
    extension = path.suffix.lower()

    # 3. Check supported types
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )

    # 4. Route file to the correct parser
    if extension == ".pdf":
        from .parsers.pdf_parser import parse_pdf

        return parse_pdf(str(path))

    if extension == ".docx":
        from .parsers.docx_parser import parse_docx

        return parse_docx(str(path))

    if extension == ".pptx":
        from .parsers.pptx_parser import parse_pptx

        return parse_pptx(str(path))

    # This should never happen because we checked
    # SUPPORTED_EXTENSIONS above.
    raise ValueError(
        f"No parser configured for: {extension}"
    )