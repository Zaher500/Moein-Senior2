from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BoundingBox:
    """
    Represents the position of an element inside a page/slide.

    x, y      -> top-left position
    width     -> element width
    height    -> element height
    """
    x: float
    y: float
    width: float
    height: float


@dataclass
class DocumentElement:
    """
    Represents one element inside the document.

    Examples:
    - heading
    - text
    - list
    - table
    - image_text
    - diagram
    - chart
    - image
    """

    # Position of this element in the reading order
    order: int

    # Element type:
    # text, heading, list, table, image_text, diagram, chart, image
    type: str

    # Where this information came from:
    # native, ocr, vision, structured, hybrid
    source: str

    # Main extracted text
    text: Optional[str] = None

    # Text that was physically visible inside an image/diagram/chart
    visible_text: list[str] = field(default_factory=list)

    # AI/Vision explanation of a visual element
    description: Optional[str] = None

    # Relationships detected inside diagrams / flowcharts
    # Example:
    # ["Client -> Server", "Server -> Database"]
    relationships: list[str] = field(default_factory=list)

    # Structured data for things such as tables and charts
    #
    # Example:
    # {
    #     "labels": ["A", "B", "C"],
    #     "values": [20, 40, 80]
    # }
    data: dict[str, Any] = field(default_factory=dict)

    # Position inside the page / slide
    bbox: Optional[BoundingBox] = None

    # Extra information we may need later
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentUnit:
    """
    Represents one logical unit of a document.

    PDF  -> page
    PPTX -> slide
    DOCX -> section / block
    """

    index: int

    # page, slide, section
    unit_type: str

    elements: list[DocumentElement] = field(default_factory=list)
    # Page / slide information such as width and height
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_element(self, element: DocumentElement) -> None:
        """
        Add an element to this unit.
        """
        self.elements.append(element)

    def get_ordered_elements(self) -> list[DocumentElement]:
        """
        Return elements according to their reading order.
        """
        return sorted(
            self.elements,
            key=lambda element: element.order
        )


@dataclass
class ProcessedDocument:
    """
    Final structured representation of an uploaded lecture file.
    """

    file_path: str

    # pdf, docx, pptx
    file_type: str

    units: list[DocumentUnit] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def add_unit(self, unit: DocumentUnit) -> None:
        """
        Add a page / slide / section to the document.
        """
        self.units.append(unit)

    def get_ordered_units(self) -> list[DocumentUnit]:
        """
        Return pages/slides/sections in their original order.
        """
        return sorted(
            self.units,
            key=lambda unit: unit.index
        )