"""Pydantic models used during Markdown to HWPX conversion."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel


class MdType(str, Enum):
    """Enumeration describing Markdown element types."""

    TITLE = "title"
    SECTION = "section"
    ORDERED_LIST_DEP1 = "orderedList_dep1"
    ORDERED_LIST_DEP2 = "orderedList_dep2"
    UNORDERED_LIST_DEP1 = "unorderedList_dep1"
    UNORDERED_LIST_DEP2 = "unorderedList_dep2"
    QUOTATION = "quotation"
    NORMAL_TEXT = "NormalText"
    HORIZON_LINE = "HorizonLine"
    DATE = "Date"
    NO_CONVERT = "NO_CONVERT"


class MdElement(BaseModel):
    """Represents a parsed Markdown element destined for conversion.

    Attributes:
        type: Enum describing the semantic type of the element.
        content: Raw text content extracted from Markdown.
        number: Optional index used for numbering sections or list entries.
        ref_filename: Optional reference filename for cross-document mapping.
    """

    type: MdType
    content: str
    number: Optional[int] = None
    ref_filename: Optional[str] = None


class FilterContext(BaseModel):
    """Holds contextual filters applied during preprocessing.

    Attributes:
        code_blocks: Inclusive line ranges for fenced code blocks.
        tables: Inclusive line ranges for table sections.
        link_lines: Line numbers containing Markdown links.
        image_lines: Line numbers containing image references.
        html_lines: Line numbers containing embedded raw HTML.
    """

    code_blocks: List[Tuple[int, int]]
    tables: List[Tuple[int, int]]
    link_lines: List[int]
    image_lines: List[int]
    html_lines: List[int]


class ConvertResponse(BaseModel):
    """Response payload describing an HWPX conversion artifact.

    Attributes:
        hwpx_filename: Generated filename of the converted document.
        hwpx_version: Internal version used for generated documents.
        artifact_id: Identifier referencing the persisted artifact.
        created_at: Timestamp when the artifact was created.
        file_size: Size of the generated file in bytes.
    """

    hwpx_filename: str
    hwpx_version: int
    artifact_id: int
    created_at: datetime
    file_size: int
