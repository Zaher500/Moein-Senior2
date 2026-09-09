import hashlib

import fitz  # PyMuPDF

from ..schemas import (
    BoundingBox,
    DocumentElement,
    DocumentUnit,
    ProcessedDocument,
)

from ..image_filter import mark_image_candidates


def parse_pdf(file_path: str) -> ProcessedDocument:
    """
    Parse a PDF document.

    Current version:
    - Reads PDF page by page.
    - Extracts native text blocks.
    - Detects embedded images.
    - Stores bounding boxes.
    - Preserves approximate visual reading order.
    - Stores page dimensions.
    - Computes a content hash for every image.
    - Marks meaningful images for future OCR / Vision processing.

    Not implemented yet:
    - OCR
    - image text extraction
    - diagram understanding
    - chart understanding
    """

    document = ProcessedDocument(
        file_path=file_path,
        file_type="pdf",
    )

    try:
        with fitz.open(file_path) as pdf:

            # =====================================================
            # Document metadata
            # =====================================================

            document.metadata = {
                "page_count": pdf.page_count,
                "title": pdf.metadata.get("title"),
                "author": pdf.metadata.get("author"),
            }

            # Cache image hashes by xref.
            #
            # If the same xref is used multiple times,
            # we do not calculate its hash again.
            image_hash_cache = {}

            # =====================================================
            # Process pages
            # =====================================================

            for page_number, page in enumerate(
                pdf,
                start=1,
            ):

                unit = DocumentUnit(
                    index=page_number,
                    unit_type="page",
                )

                # Save page dimensions.
                #
                # Needed by image_filter.py to calculate
                # normalized image position and size.
                unit.metadata = {
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                }

                # Temporary list containing text + images.
                #
                # We collect everything first and then
                # sort it according to visual position.
                page_elements = []

                # =================================================
                # 1. Extract native text blocks
                # =================================================

                text_blocks = page.get_text(
                    "blocks",
                    sort=True,
                )

                for block in text_blocks:

                    if len(block) < 7:
                        continue

                    x0 = float(block[0])
                    y0 = float(block[1])
                    x1 = float(block[2])
                    y1 = float(block[3])

                    text = block[4]
                    block_number = block[5]
                    block_type = block[6]

                    # PyMuPDF block types:
                    #
                    # 0 = text
                    # 1 = image
                    #
                    # Images are processed separately below.
                    if block_type != 0:
                        continue

                    cleaned_text = _clean_text(text)

                    if not cleaned_text:
                        continue

                    bbox = BoundingBox(
                        x=x0,
                        y=y0,
                        width=x1 - x0,
                        height=y1 - y0,
                    )

                    element = DocumentElement(
                        order=0,
                        type="text",
                        source="native",
                        text=cleaned_text,
                        bbox=bbox,
                        metadata={
                            "block_number": block_number,
                            "page_number": page_number,
                        },
                    )

                    page_elements.append(
                        {
                            "x": x0,
                            "y": y0,
                            "element": element,
                        }
                    )

                # =================================================
                # 2. Detect embedded images
                # =================================================

                images = page.get_images(
                    full=True
                )

                # Prevent duplicate detections on the same page.
                seen_images = set()

                for image_index, image_info in enumerate(
                    images,
                    start=1,
                ):

                    # First item returned by get_images()
                    # is the image xref.
                    xref = image_info[0]

                    # ---------------------------------------------
                    # Compute hash of actual image content
                    # ---------------------------------------------

                    if xref not in image_hash_cache:

                        image_hash_cache[xref] = (
                            _compute_image_hash(
                                pdf,
                                xref,
                            )
                        )

                    image_hash = (
                        image_hash_cache[xref]
                    )

                    # ---------------------------------------------
                    # Find where this image appears on the page
                    # ---------------------------------------------

                    try:
                        image_rects = (
                            page.get_image_rects(
                                xref
                            )
                        )

                    except Exception:
                        continue

                    for rect_index, rect in enumerate(
                        image_rects,
                        start=1,
                    ):

                        x0 = float(rect.x0)
                        y0 = float(rect.y0)
                        x1 = float(rect.x1)
                        y1 = float(rect.y1)

                        # Ignore invalid rectangles.
                        if (
                            x1 <= x0
                            or y1 <= y0
                        ):
                            continue

                        # -----------------------------------------
                        # Avoid duplicate detections
                        # -----------------------------------------

                        image_key = (
                            xref,
                            round(x0, 2),
                            round(y0, 2),
                            round(x1, 2),
                            round(y1, 2),
                        )

                        if image_key in seen_images:
                            continue

                        seen_images.add(
                            image_key
                        )

                        bbox = BoundingBox(
                            x=x0,
                            y=y0,
                            width=x1 - x0,
                            height=y1 - y0,
                        )

                        element = DocumentElement(
                            order=0,
                            type="image",
                            source="structured",
                            bbox=bbox,
                            metadata={
                                "xref": xref,
                                "image_index": image_index,
                                "rect_index": rect_index,
                                "page_number": page_number,

                                # Hash based on the actual
                                # image pixel content.
                                "content_hash": image_hash,
                            },
                        )

                        page_elements.append(
                            {
                                "x": x0,
                                "y": y0,
                                "element": element,
                            }
                        )

                # =================================================
                # 3. Put text + images into visual order
                # =================================================

                page_elements.sort(
                    key=lambda item: (
                        item["y"],
                        item["x"],
                    )
                )

                for order, item in enumerate(
                    page_elements,
                    start=1,
                ):

                    element = item["element"]

                    element.order = order

                    unit.add_element(
                        element
                    )

                # Add completed page to document.
                document.add_unit(
                    unit
                )

        # =========================================================
        # 4. Decide which images should go to OCR / Vision later
        # =========================================================
        #
        # Important:
        #
        # No image is deleted here.
        #
        # image_filter.py only adds metadata such as:
        #
        # process_with_ai = True
        #
        # or:
        #
        # process_with_ai = False
        # skip_reason = "repeated_header_footer"
        #
        # The filter can now use:
        #
        # - actual image content hash
        # - image position
        # - image size
        # - repetition across pages
        #

        mark_image_candidates(
            document
        )

    except Exception as e:

        raise RuntimeError(
            f"Failed to process PDF "
            f"'{file_path}': {str(e)}"
        ) from e

    return document


def _clean_text(text: str) -> str:
    """
    Clean extracted PDF text without changing its meaning.
    """

    if not text:
        return ""

    # Remove null characters.
    text = (
        text
        .replace("\x00", "")
        .replace("\u0000", "")
    )

    # Merge lines belonging to the same text block.
    #
    # Example:
    #
    # تحسين
    # جودة
    # البرمجيات
    #
    # becomes:
    #
    # تحسين جودة البرمجيات
    #

    parts = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return " ".join(
        parts
    ).strip()


def _compute_image_hash(
    pdf: fitz.Document,
    xref: int,
) -> str | None:
    """
    Compute a SHA-256 hash from the actual pixel content
    of an embedded PDF image.

    Why pixel content instead of xref?

    xref is only an internal PDF identifier.

    For example:

        Page 1 logo -> xref 100
        Page 2 logo -> xref 150

    They may still contain exactly the same image.

    By hashing the pixel content:

        Page 1 logo -> hash ABC
        Page 2 logo -> hash ABC

    we can recognize that they are actually the same image.
    """

    try:

        pixmap = fitz.Pixmap(
            pdf,
            xref,
        )

        # Some images may use CMYK or another colorspace.
        #
        # Normalize them to RGB so comparing their hashes
        # becomes more reliable.
        if (
            pixmap.colorspace
            and pixmap.colorspace.n > 3
        ):

            pixmap = fitz.Pixmap(
                fitz.csRGB,
                pixmap,
            )

        # Include dimensions in the hash input.
        #
        # This prevents unrelated raw pixel buffers from
        # accidentally being treated as identical.
        image_header = (
            f"{pixmap.width}:"
            f"{pixmap.height}:"
            f"{pixmap.n}:"
        ).encode(
            "utf-8"
        )

        image_pixels = bytes(
            pixmap.samples
        )

        image_hash = hashlib.sha256(
            image_header
            + image_pixels
        ).hexdigest()

        return image_hash

    except Exception:

        # Hash failure should NOT break
        # the entire lecture processing.
        #
        # image_filter.py will treat an image
        # without a hash conservatively.
        return None