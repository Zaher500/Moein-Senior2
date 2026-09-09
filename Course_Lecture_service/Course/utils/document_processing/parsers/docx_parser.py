import hashlib
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from ..schemas import (
    DocumentElement,
    DocumentUnit,
    ProcessedDocument,
)

from ..image_filter import mark_image_candidates
def parse_docx(file_path: str) -> ProcessedDocument:
    """
    Parse a DOCX document into the common document IR.

    Current version:
    - Reads DOCX body blocks in document order.
    - Extracts native paragraph text.
    - Extracts tables as structured native text.
    - Detects inline / embedded images.
    - Preserves approximate document order.
    - Stores image relationship IDs.
    - Stores original image part names.
    - Computes SHA-256 hashes for image content.

    Important:
    DOCX does not provide reliable page coordinates like PDF,
    so image elements do not use BoundingBox values here.

    Image extraction to temporary files will be handled later
    by image_extractor.py.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"DOCX file not found: {file_path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Path is not a file: {file_path}"
        )

    document = ProcessedDocument(
        file_path=str(path),
        file_type="docx",
    )

    try:
        doc = Document(str(path))

        # =====================================================
        # Document metadata
        # =====================================================

        core_properties = doc.core_properties

        document.metadata = {
            "title": core_properties.title,
            "author": core_properties.author,
            "subject": core_properties.subject,
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
        }

        # =====================================================
        # DOCX currently represented as one ordered document unit
        # =====================================================
        #
        # Unlike PDF, Word files do not expose stable physical
        # page boundaries through python-docx.
        #
        # Therefore we preserve logical document order instead
        # of inventing page numbers.
        #

        unit = DocumentUnit(
            index=1,
            unit_type="document",
        )

        ordered_elements = []

        # =====================================================
        # Process document body in native order
        # =====================================================

        for block_index, block in enumerate(
            _iter_block_items(doc),
            start=1,
        ):

            # =================================================
            # Paragraph
            # =================================================

            if isinstance(block, Paragraph):

                paragraph_elements = (
                    _parse_paragraph(
                        paragraph=block,
                        doc=doc,
                        block_index=block_index,
                    )
                )

                ordered_elements.extend(
                    paragraph_elements
                )

            # =================================================
            # Table
            # =================================================

            elif isinstance(block, Table):

                table_elements = (
                    _parse_table(
                        table=block,
                        doc=doc,
                        block_index=block_index,
                    )
                )

                ordered_elements.extend(
                    table_elements
                )

        # =====================================================
        # Assign final sequential order
        # =====================================================

        for order, element in enumerate(
            ordered_elements,
            start=1,
        ):
            element.order = order

            unit.add_element(
                element
            )

        unit.metadata = {
            "element_count": len(
                ordered_elements
            ),
        }

        document.add_unit(
            unit
        )

        mark_image_candidates(
        document
       )

    except Exception as e:
        raise RuntimeError(
            f"Failed to process DOCX "
            f"'{file_path}': {str(e)}"
        ) from e

    return document


def _parse_paragraph(
    paragraph: Paragraph,
    doc: DocumentObject,
    block_index: int,
) -> list[DocumentElement]:
    """
    Parse one paragraph while preserving the approximate order
    between text and embedded images.

    Example:

        some text
        [image]
        more text

    becomes:

        text element
        image element
        text element
    """

    elements = []

    text_buffer = []

    def flush_text():
        text = _clean_text(
            "".join(text_buffer)
        )

        text_buffer.clear()

        if not text:
            return

        elements.append(
            DocumentElement(
                order=0,
                type="text",
                source="native",
                text=text,
                metadata={
                    "block_index": block_index,
                    "block_type": "paragraph",
                    "style": (
                        paragraph.style.name
                        if paragraph.style
                        else None
                    ),
                },
            )
        )

    # =========================================================
    # Read paragraph run by run
    # =========================================================

    for run_index, run in enumerate(
        paragraph.runs,
        start=1,
    ):

        # Add run text first.
        if run.text:
            text_buffer.append(
                run.text
            )

        # Detect images inside this run.
        relationship_ids = (
            _extract_image_relationship_ids(
                run
            )
        )

        if not relationship_ids:
            continue

        # Text before the image should remain before it.
        flush_text()

        for relationship_id in relationship_ids:

            image_element = (
                _build_image_element(
                    doc=doc,
                    relationship_id=relationship_id,
                    block_index=block_index,
                    run_index=run_index,
                    location="paragraph",
                )
            )

            if image_element:
                elements.append(
                    image_element
                )

    # Remaining text after final image.
    flush_text()

    # =========================================================
    # Some paragraphs can contain text but no runs in edge cases.
    # =========================================================

    if not elements:

        cleaned_text = _clean_text(
            paragraph.text
        )

        if cleaned_text:

            elements.append(
                DocumentElement(
                    order=0,
                    type="text",
                    source="native",
                    text=cleaned_text,
                    metadata={
                        "block_index": block_index,
                        "block_type": "paragraph",
                        "style": (
                            paragraph.style.name
                            if paragraph.style
                            else None
                        ),
                    },
                )
            )

    return elements


def _parse_table(
    table: Table,
    doc: DocumentObject,
    block_index: int,
) -> list[DocumentElement]:
    """
    Convert a native Word table into structured text.

    The table remains native text because Word already exposes
    its cell structure reliably.

    Any images inside table cells are also registered as image
    elements so they can later pass through OCR / Vision.
    """

    elements = []

    table_lines = []

    # =========================================================
    # Build readable native table text
    # =========================================================

    for row in table.rows:

        cell_values = []

        for cell in row.cells:

            cell_text = _clean_text(
                cell.text
            )

            cell_values.append(
                cell_text
            )

        if any(cell_values):

            table_lines.append(
                " | ".join(
                    cell_values
                )
            )

    table_text = "\n".join(
        table_lines
    ).strip()

    if table_text:

        elements.append(
            DocumentElement(
                order=0,
                type="text",
                source="native",
                text=table_text,
                metadata={
                    "block_index": block_index,
                    "block_type": "table",
                    "row_count": len(
                        table.rows
                    ),
                    "column_count": (
                        len(table.columns)
                        if table.columns
                        else 0
                    ),
                },
            )
        )

    # =========================================================
    # Find images embedded inside table cells
    # =========================================================

    seen_relationship_ids = set()

    for row_index, row in enumerate(
        table.rows,
        start=1,
    ):

        for column_index, cell in enumerate(
            row.cells,
            start=1,
        ):

            for paragraph in cell.paragraphs:

                for run_index, run in enumerate(
                    paragraph.runs,
                    start=1,
                ):

                    relationship_ids = (
                        _extract_image_relationship_ids(
                            run
                        )
                    )

                    for relationship_id in relationship_ids:

                        # Avoid registering the exact same drawing
                        # more than once while inspecting a table.
                        image_key = (
                            relationship_id,
                            row_index,
                            column_index,
                            run_index,
                        )

                        if image_key in seen_relationship_ids:
                            continue

                        seen_relationship_ids.add(
                            image_key
                        )

                        image_element = (
                            _build_image_element(
                                doc=doc,
                                relationship_id=relationship_id,
                                block_index=block_index,
                                run_index=run_index,
                                location="table",
                                extra_metadata={
                                    "row_index":
                                        row_index,
                                    "column_index":
                                        column_index,
                                },
                            )
                        )

                        if image_element:

                            elements.append(
                                image_element
                            )

    return elements


def _build_image_element(
    doc: DocumentObject,
    relationship_id: str,
    block_index: int,
    run_index: int,
    location: str,
    extra_metadata: dict | None = None,
) -> DocumentElement | None:
    """
    Create one image DocumentElement from a DOCX relationship ID.

    The actual image bytes are NOT written to disk here.

    Instead we store enough information for image_extractor.py
    to extract the original image later.
    """

    try:

        related_part = (
            doc.part.related_parts[
                relationship_id
            ]
        )

    except Exception:
        return None

    blob = getattr(
        related_part,
        "blob",
        None,
    )

    if not blob:
        return None

    content_hash = hashlib.sha256(
        blob
    ).hexdigest()

    partname = str(
        getattr(
            related_part,
            "partname",
            "",
        )
    )

    content_type = getattr(
        related_part,
        "content_type",
        None,
    )

    metadata = {
        "block_index": block_index,
        "block_type": "image",
        "image_location": location,
        "run_index": run_index,

        # Important for later extraction.
        "relationship_id":
            relationship_id,

        "image_partname":
            partname,

        "content_type":
            content_type,

        "content_hash":
            content_hash,
    }

    if extra_metadata:
        metadata.update(
            extra_metadata
        )

    return DocumentElement(
        order=0,
        type="image",
        source="structured",
        bbox=None,
        metadata=metadata,
    )


def _extract_image_relationship_ids(
    run,
) -> list[str]:
    """
    Find image relationship IDs inside a Word run.

    Most modern DOCX images use:

        <a:blip r:embed="rIdX">

    Older Word documents may also contain VML images.
    """

    relationship_ids = []

    # =========================================================
    # Modern DrawingML images
    # =========================================================

    try:

        blips = run._element.xpath(
            ".//a:blip"
        )

        for blip in blips:

            relationship_id = blip.get(
                qn("r:embed")
            )

            if (
                relationship_id
                and relationship_id
                not in relationship_ids
            ):
                relationship_ids.append(
                    relationship_id
                )

    except Exception:
        pass

    # =========================================================
    # Legacy VML images
    # =========================================================

    try:

        image_nodes = run._element.xpath(
            ".//v:imagedata"
        )

        for node in image_nodes:

            relationship_id = node.get(
                qn("r:id")
            )

            if (
                relationship_id
                and relationship_id
                not in relationship_ids
            ):
                relationship_ids.append(
                    relationship_id
                )

    except Exception:
        pass

    return relationship_ids


def _iter_block_items(
    parent,
):
    """
    Yield paragraphs and tables in the order they appear
    in the Word document.

    python-docx normally exposes:

        document.paragraphs
        document.tables

    separately, which loses their interleaved order.

    This helper reads the underlying XML body so we can preserve:

        paragraph
        table
        paragraph
        table
        ...
    """

    if isinstance(
        parent,
        DocumentObject,
    ):

        parent_element = (
            parent.element.body
        )

    elif isinstance(
        parent,
        _Cell,
    ):

        parent_element = (
            parent._tc
        )

    else:

        raise ValueError(
            "Unsupported parent type "
            "for DOCX block iteration."
        )

    for child in (
        parent_element.iterchildren()
    ):

        if isinstance(
            child,
            CT_P,
        ):

            yield Paragraph(
                child,
                parent,
            )

        elif isinstance(
            child,
            CT_Tbl,
        ):

            yield Table(
                child,
                parent,
            )


def _clean_text(
    text: str,
) -> str:
    """
    Clean extracted DOCX text without changing
    its educational meaning.
    """

    if not text:
        return ""

    text = (
        text
        .replace("\x00", "")
        .replace("\u0000", "")
    )

    parts = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return " ".join(
        parts
    ).strip()