"""
Markdown 파일을 파싱하여 HWPHandler에 필요한 content dict로 변환
"""
import re
from typing import Dict, List, Optional, Tuple

from app.models.convert_models import FilterContext, MdElement, MdType

PATTERNS = {
    "code_block_start": re.compile(r"^\s*(`{3,}|~{3,})"),
    "table_separator": re.compile(r"^\s*\|[\s:|-]+\|"),
    "inline_link": re.compile(r"(?<!\\)\[([^\[\]]*)\]\(([^)]+)\)"),
    "ref_link": re.compile(r"\[([^\[\]]*)\]\[([^\]]*)\]"),
    "auto_link": re.compile(r"<([^>]+)>"),
    "image": re.compile(r"!\[([^\[\]]*)\]\(([^)]+)\)"),
    "checkbox": re.compile(r"^\s*[-*]\s+\[[\sx]\]\s+"),
    "html_tag": re.compile(r"<(script|style|iframe|embed|object)[^>]*>", re.IGNORECASE),
    "date": re.compile(r"^생성일\s*:\s*(\d{4}\.\d{2}\.\d{2})$"),
    "h1": re.compile(r"^#\s+(.+)$"),
    "h2": re.compile(r"^##\s+(.+)$"),
    "ordered_list": re.compile(r"^(\s*)\d+\.\s+(.+)$"),
    "unordered_list": re.compile(r"^(\s*)[-*]\s+(.+)$"),
    "quotation": re.compile(r"^>\s+(.+)$"),
    "horizon_line": re.compile(r"^(---+|\*\*\*+|___+)$"),
}

REF_DEFINITION_PATTERN = re.compile(r"^\s*\[[^\]]+\]:\s*\S+")

REF_FILENAME_MAP = {
    MdType.SECTION: "Ref_01_Section",
    MdType.ORDERED_LIST_DEP1: "Ref07_OrderedList_dep1",
    MdType.ORDERED_LIST_DEP2: "Ref08_OrderedList_dep2",
    MdType.UNORDERED_LIST_DEP1: "Ref05_UnOrderedList_dep1",
    MdType.UNORDERED_LIST_DEP2: "Ref06_UnOrderedList_dep2",
    MdType.QUOTATION: "Ref04_Quotation",
    MdType.NORMAL_TEXT: "Ref02_NormalText",
    MdType.HORIZON_LINE: "Ref03_HorizonLine",
    MdType.DATE: "Ref09_Date",
}


def extract_code_blocks(lines: List[str]) -> List[Tuple[int, int]]:
    """Extract fenced code blocks as inclusive line ranges.

    Args:
        lines: Markdown content split by newline.

    Returns:
        Start/end line index pairs for each detected code block.
    """

    code_blocks: List[Tuple[int, int]] = []
    in_block = False
    block_start = 0
    fence_char: Optional[str] = None

    for idx, line in enumerate(lines):
        match = PATTERNS["code_block_start"].match(line)
        if not match:
            continue

        current_char = match.group(1)[0]
        if not in_block:
            # Mark the beginning of a fenced block and remember the fence type.
            in_block = True
            block_start = idx
            fence_char = current_char
            continue

        # Only close blocks that use the same fence character.
        if fence_char == current_char:
            code_blocks.append((block_start, idx))
            in_block = False
            fence_char = None

    if in_block:
        # Unterminated fences extend to the final line.
        code_blocks.append((block_start, len(lines) - 1 if lines else 0))

    return code_blocks


def extract_tables(lines: List[str]) -> List[Tuple[int, int]]:
    """Extract GitHub-style tables as line ranges.

    Args:
        lines: Markdown content split by newline.

    Returns:
        Start/end line index pairs for each table.
    """

    def _is_table_row(candidate: str) -> bool:
        stripped = candidate.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return False
        # Require at least two cell separators to avoid | in plain text.
        return stripped.count("|") >= 3

    def _parse_cells(candidate: str) -> List[str]:
        stripped = candidate.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            return []
        return [cell.strip() for cell in stripped.split("|")[1:-1]]

    def _is_valid_table(start_idx: int, end_idx: int) -> bool:
        if start_idx >= len(lines) or start_idx + 1 >= len(lines):
            return False
        header_cells = _parse_cells(lines[start_idx])
        separator_cells = _parse_cells(lines[start_idx + 1])
        if len(header_cells) < 2 or len(header_cells) != len(separator_cells):
            return False
        # Ensure separator cells contain at least one dash each.
        for cell in separator_cells:
            if "-" not in cell.replace(":", ""):
                return False
        # Verify data rows (if present) keep the same column count.
        for row_idx in range(start_idx + 2, end_idx + 1):
            row_cells = _parse_cells(lines[row_idx])
            if row_cells and len(row_cells) != len(header_cells):
                return False
        return True

    tables: List[Tuple[int, int]] = []
    idx = 0
    total = len(lines)

    while idx < total - 1:
        if not _is_table_row(lines[idx]):
            idx += 1
            continue

        separator_line = lines[idx + 1]
        if not PATTERNS["table_separator"].match(separator_line.strip()):
            idx += 1
            continue

        start = idx
        idx += 2
        while idx < total and _is_table_row(lines[idx]):
            idx += 1
        end = idx - 1
        if end <= start + 1:
            # Require at least one data row; otherwise skip.
            idx = start + 1
            continue

        if _is_valid_table(start, end):
            tables.append((start, end))
        else:
            idx = start + 1
            continue

    return tables


def _is_valid_auto_link(content: str) -> bool:
    """Return True when the auto-link body looks like a real URL or email."""

    candidate = content.strip()
    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "ftp://", "mailto:")):
        return True
    return "@" in candidate and " " not in candidate


def extract_link_lines(lines: List[str]) -> List[int]:
    """Collect line numbers that contain Markdown links.

    Args:
        lines: Markdown content split by newline.

    Returns:
        Line numbers containing inline, reference, or auto links.
    """

    link_lines: List[int] = []
    for idx, line in enumerate(lines):
        # Inline link detection (e.g., [text](url)).
        if PATTERNS["inline_link"].search(line):
            link_lines.append(idx)
            continue

        # Reference style link usage (e.g., [text][ref]).
        if PATTERNS["ref_link"].search(line):
            link_lines.append(idx)
            continue

        auto_matches = list(PATTERNS["auto_link"].finditer(line))
        if any(_is_valid_auto_link(match.group(1)) for match in auto_matches):
            link_lines.append(idx)
            continue

        # Reference definition lines (e.g., [ref]: https://example.com).
        if REF_DEFINITION_PATTERN.match(line.strip()):
            link_lines.append(idx)

    return link_lines


def extract_image_lines(lines: List[str]) -> List[int]:
    """Collect line numbers that contain inline images."""

    return [idx for idx, line in enumerate(lines) if PATTERNS["image"].search(line)]


def extract_html_lines(lines: List[str]) -> List[int]:
    """Collect line numbers that include dangerous HTML tags."""

    return [idx for idx, line in enumerate(lines) if PATTERNS["html_tag"].search(line)]


def prepare_filter_context(md_content: str) -> FilterContext:
    """Prepare a filter context before parsing Markdown lines.

    Args:
        md_content: Raw markdown content.

    Returns:
        A populated FilterContext used for constant-time lookups.
    """

    lines = md_content.split("\n")
    return FilterContext(
        code_blocks=extract_code_blocks(lines),
        tables=extract_tables(lines),
        link_lines=extract_link_lines(lines),
        image_lines=extract_image_lines(lines),
        html_lines=extract_html_lines(lines),
    )


def should_filter_element(line_no: int, filter_ctx: FilterContext) -> bool:
    """Return True when a line should be marked as NO_CONVERT.

    Args:
        line_no: Zero-based line number.
        filter_ctx: Pre-computed filter context.

    Returns:
        True when the line belongs to a filtered range.
    """

    # Range lookups for fences and tables are inclusive.
    for start, end in filter_ctx.code_blocks:
        if start <= line_no <= end:
            return True

    for start, end in filter_ctx.tables:
        if start <= line_no <= end:
            return True

    if line_no in filter_ctx.link_lines:
        return True

    if line_no in filter_ctx.image_lines:
        return True

    if line_no in filter_ctx.html_lines:
        return True

    return False


def _detect_list_depth(leading_whitespace: str) -> Optional[int]:
    """Translate indentation into a supported list depth."""

    spaces = len(leading_whitespace.replace("\t", "    "))
    if spaces == 0:
        return 1
    if spaces >= 2:
        return 2
    return None


def _build_element(md_type: MdType, content: str, number: Optional[int] = None) -> MdElement:
    """Create an MdElement with an auto-mapped ref filename."""

    return MdElement(
        type=md_type,
        content=content,
        number=number,
        ref_filename=REF_FILENAME_MAP.get(md_type),
    )


def markdown_to_plain_text(md_text: str) -> str:
    """Markdown 문법을 Plain Text로 변환합니다.

    HWP에 삽입될 본문 내용에서 Markdown 문법 요소들을 제거하여
    순수한 텍스트로 변환합니다. 각 문단 앞에는 2칸 공백을 추가하여
    들여쓰기를 적용합니다.

    Args:
        md_text: Markdown 형식의 텍스트

    Returns:
        Plain text로 변환된 텍스트 (들여쓰기 포함)

    Examples:
        >>> text = "### 소제목\\n\\n**굵은** 글씨와 *기울임*"
        >>> markdown_to_plain_text(text)
        '소제목\\n\\n  굵은 글씨와 기울임'
        >>> text = "1. 첫 번째\\n\\n일반 문단"
        >>> markdown_to_plain_text(text)
        '1. 첫 번째\\n\\n  일반 문단'
    """
    text = md_text

    # 1. H3~H6 헤더 마커 제거 (텍스트만 남김)
    text = re.sub(r'^######\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^#####\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^####\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s+(.+)$', r'\1', text, flags=re.MULTILINE)

    # 2. 굵게 + 기울임 (***text*** 또는 ___text___)
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'___(.+?)___', r'\1', text)

    # 3. 굵게 (**text** 또는 __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 4. 기울임 (*text* 또는 _text_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)

    # 5. 취소선 (~~text~~)
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # 6. 인라인 코드 (`code`)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # 7. 링크 ([text](url))
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # 8. 이미지 (![alt](url))
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'[이미지: \1]', text)

    # 9. 리스트 마커
    # 순서 없는 리스트 (-, *, +) → 불릿(•)으로 변환
    text = re.sub(r'^[\s]*[-\*\+]\s+', '• ', text, flags=re.MULTILINE)
    # 순서 있는 리스트 (1., 2., ...)는 그대로 유지

    # 10. 인용 (> text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # 11. 수평선 (---, ***, ___)
    text = re.sub(r'^[\s]*[-\*_]{3,}[\s]*$', '', text, flags=re.MULTILINE)

    # 12. 문단 들여쓰기 추가
    # 각 문단(빈 줄로 구분된 텍스트 블록)의 시작에 2칸 공백 추가
    # 단, 순서 있는 리스트나 불릿 리스트는 제외
    paragraphs = text.split('\n\n')
    indented_paragraphs = []
    for para in paragraphs:
        if para.strip():
            # 순서 있는 리스트나 불릿으로 시작하지 않으면 들여쓰기
            if not re.match(r'^\d+\.', para.strip()) and not para.strip().startswith('•'):
                para = '  ' + para
            indented_paragraphs.append(para)
    text = '\n\n'.join(indented_paragraphs)

    return text.strip()


def parse_markdown_to_content(md_text: str) -> Dict[str, str]:
    """Markdown 텍스트를 파싱하여 HWPHandler.generate_report()에 필요한 content dict로 변환.

    섹션 제목을 동적으로 추출하여 HWP 템플릿의 {{TITLE_XXX}} 플레이스홀더에 대입합니다.

    Args:
        md_text: Markdown 형식의 텍스트

    Returns:
        HWP 플레이스홀더에 매핑될 content 딕셔너리:
            - title: 보고서 제목
            - summary: 요약 내용
            - background: 배경 내용
            - main_content: 주요 내용
            - conclusion: 결론 내용
            - title_summary: 요약 섹션 제목 (동적 추출)
            - title_background: 배경 섹션 제목 (동적 추출)
            - title_main_content: 주요 내용 섹션 제목 (동적 추출)
            - title_conclusion: 결론 섹션 제목 (동적 추출)

    Examples:
        >>> md = "# 디지털뱅킹 트렌드\\n\\n## 핵심 요약\\n\\n2025년..."
        >>> content = parse_markdown_to_content(md)
        >>> content['title_summary']
        '핵심 요약'
        >>> len(content['summary']) > 0
        True
    """
    content = {
        "title": "",
        "summary": "",
        "background": "",
        "main_content": "",
        "conclusion": "",
        "title_summary": "요약",
        "title_background": "배경 및 목적",
        "title_main_content": "주요 내용",
        "title_conclusion": "결론 및 제언"
    }

    # 1. H1 제목 추출
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    if title_match:
        content["title"] = title_match.group(1).strip()

    # 2. 모든 H2 섹션 추출 (제목 + 내용)
    h2_sections = extract_all_h2_sections(md_text)

    # 3. 키워드 기반으로 섹션 분류 및 매핑
    for section_title, section_content in h2_sections:
        section_type = classify_section(section_title)


        if section_type == "background":
            content["title_background"] = section_title
            content["background"] = section_content
        elif section_type == "main_content":
            content["title_main_content"] = section_title
            content["main_content"] = section_content
        elif section_type == "conclusion":
            content["title_conclusion"] = section_title
            content["conclusion"] = section_content
        elif section_type == "summary":
            content["title_summary"] = section_title
            content["summary"] = section_content

    # 4. 내용이 비어있으면 전체 텍스트를 main_content로 사용
    if not any([content["summary"], content["background"],
                content["main_content"], content["conclusion"]]):
        if title_match:
            content["main_content"] = md_text[title_match.end():].strip()
        else:
            content["main_content"] = md_text.strip()

    return content


def extract_all_h2_sections(md_text: str) -> List[Tuple[str, str]]:
    """Markdown에서 모든 H2 섹션을 추출합니다.

    Args:
        md_text: Markdown 텍스트

    Returns:
        (섹션 제목, 섹션 내용) 튜플의 리스트
        섹션 내용은 Markdown 문법이 제거된 Plain Text입니다.

    Examples:
        >>> md = "# Title\\n\\n## 요약\\n\\nSummary text\\n\\n## 배경\\n\\nBackground text"
        >>> sections = extract_all_h2_sections(md)
        >>> len(sections)
        2
        >>> sections[0]
        ('요약', '  Summary text')
    """
    # H2 헤더와 그 내용을 추출하는 정규식
    # 패턴: ## 제목\n\n내용 (다음 ##까지 또는 끝까지)
    pattern = r'^##\s+(.+?)\s*$\n+(.*?)(?=\n+^##\s|\Z)'
    matches = re.findall(pattern, md_text, re.MULTILINE | re.DOTALL)

    # 섹션 내용에서 Markdown 문법 제거 및 들여쓰기 적용
    return [(title.strip(), markdown_to_plain_text(content.strip()))
            for title, content in matches]


def classify_section(section_title: str) -> str:
    """섹션 제목을 분석하여 종류를 분류합니다.

    키워드 기반으로 섹션이 요약/배경/주요내용/결론 중 어디에 해당하는지 판단합니다.

    Args:
        section_title: H2 섹션 제목

    Returns:
        섹션 타입: "summary", "background", "main_content", "conclusion", "unknown"

    Examples:
        >>> classify_section("핵심 요약")
        'summary'
        >>> classify_section("추진 배경")
        'background'
        >>> classify_section("Executive Summary")
        'summary'
        >>> classify_section("향후 계획 및 제언")
        'conclusion'
    """
    title_lower = section_title.lower()

    # 요약 키워드
    summary_keywords = ["요약", "summary", "핵심", "개요", "executive"]
    if any(keyword in title_lower for keyword in summary_keywords):
        return "summary"

    # 결론 키워드 (배경/주요내용보다 먼저 체크)
    # "향후 추진 계획"처럼 "추진"(배경 키워드)과 "향후"(결론 키워드)를 모두 포함하는 경우,
    # 결론으로 분류되도록 순서를 앞으로 이동
    conclusion_keywords = ["결론", "제언", "conclusion", "향후", "계획", "시사점", "recommendation"]
    if any(keyword in title_lower for keyword in conclusion_keywords):
        return "conclusion"

    # 배경 키워드
    background_keywords = ["배경", "목적", "background", "추진", "사업", "필요성", "경위"]
    if any(keyword in title_lower for keyword in background_keywords):
        return "background"

    # 주요내용 키워드
    main_keywords = ["주요", "내용", "분석", "결과", "세부", "상세", "내역", "현황", "main", "detail", "analysis"]
    if any(keyword in title_lower for keyword in main_keywords):
        return "main_content"

    return "unknown"


def extract_title_from_markdown(md_text: str) -> str:
    """Markdown에서 제목만 추출 (간편 함수).

    Args:
        md_text: Markdown 텍스트

    Returns:
        추출된 제목 (없으면 "보고서")

    Examples:
        >>> md = "# 2025 디지털뱅킹 보고서\\n\\n내용..."
        >>> title = extract_title_from_markdown(md)
        >>> title
        '2025 디지털뱅킹 보고서'
    """
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()
    return "보고서"


def parse_markdown_to_md_elements(md_content: str) -> List[MdElement]:
    """Markdown 문자열을 분석하여 Section 7.1 규칙에 따라 MdElement 객체 목록으로 변환합니다.

    Args:
        md_content: 변환 대상이 되는 원본 Markdown 문자열.

    Returns:
        변환 가능하거나 필터링된 각 라인을 순서대로 표현하는 MdElement 객체들의 리스트.
    """

    lines = md_content.split("\n") if md_content else []
    if not lines:
        return []

    filter_ctx = prepare_filter_context(md_content)
    elements: List[MdElement] = []
    title_added = False
    section_number = 0
    ordered_dep1_count = 0
    ordered_dep2_count = 0
    previous_type: Optional[MdType] = None

    for idx, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r")
        stripped_line = line.strip()

        if not stripped_line:
            previous_type = None
            continue

        is_checkbox_line = bool(PATTERNS["checkbox"].match(line))
        if should_filter_element(idx, filter_ctx) or is_checkbox_line:
            elements.append(MdElement(type=MdType.NO_CONVERT, content=stripped_line))
            previous_type = MdType.NO_CONVERT
            continue

        # 1. Title (# Heading)
        h1_match = PATTERNS["h1"].match(stripped_line)
        if h1_match:
            content = h1_match.group(1).strip()
            if not title_added:
                elements.append(MdElement(type=MdType.TITLE, content=content))
                title_added = True
                previous_type = MdType.TITLE
            else:
                section_number += 1
                elements.append(
                    _build_element(MdType.SECTION, content, number=section_number)
                )
                previous_type = MdType.SECTION
            continue

        # 2. Sections (## Heading)
        h2_match = PATTERNS["h2"].match(stripped_line)
        if h2_match:
            section_number += 1
            elements.append(
                _build_element(MdType.SECTION, h2_match.group(1).strip(), number=section_number)
            )
            previous_type = MdType.SECTION
            continue

        # 3. Ordered lists
        ordered_match = PATTERNS["ordered_list"].match(line)
        if ordered_match:
            depth = _detect_list_depth(ordered_match.group(1))
            content = ordered_match.group(2).strip()
            if depth == 1:
                if previous_type != MdType.ORDERED_LIST_DEP1:
                    ordered_dep1_count = 0
                ordered_dep1_count += 1
                elements.append(
                    _build_element(
                        MdType.ORDERED_LIST_DEP1,
                        content,
                        number=ordered_dep1_count,
                    )
                )
                previous_type = MdType.ORDERED_LIST_DEP1
                continue
            if depth == 2:
                if previous_type != MdType.ORDERED_LIST_DEP2:
                    ordered_dep2_count = 0
                ordered_dep2_count += 1
                elements.append(
                    _build_element(
                        MdType.ORDERED_LIST_DEP2,
                        content,
                        number=ordered_dep2_count,
                    )
                )
                previous_type = MdType.ORDERED_LIST_DEP2
                continue

        # 4. Unordered lists
        unordered_match = PATTERNS["unordered_list"].match(line)
        if unordered_match:
            depth = _detect_list_depth(unordered_match.group(1))
            content = unordered_match.group(2).strip()
            if depth == 1:
                elements.append(_build_element(MdType.UNORDERED_LIST_DEP1, content))
                previous_type = MdType.UNORDERED_LIST_DEP1
                continue
            if depth == 2:
                elements.append(_build_element(MdType.UNORDERED_LIST_DEP2, content))
                previous_type = MdType.UNORDERED_LIST_DEP2
                continue

        # 5. Date
        date_match = PATTERNS["date"].match(stripped_line)
        if date_match:
            elements.append(_build_element(MdType.DATE, date_match.group(1).strip()))
            previous_type = MdType.DATE
            continue

        # 6. Quotations
        quote_match = PATTERNS["quotation"].match(stripped_line)
        if quote_match:
            elements.append(_build_element(MdType.QUOTATION, quote_match.group(1).strip()))
            previous_type = MdType.QUOTATION
            continue

        # 7. Horizontal rules
        if PATTERNS["horizon_line"].match(stripped_line):
            elements.append(_build_element(MdType.HORIZON_LINE, stripped_line))
            previous_type = MdType.HORIZON_LINE
            continue

        # 8. Fallback: normal text
        elements.append(_build_element(MdType.NORMAL_TEXT, stripped_line))
        previous_type = MdType.NORMAL_TEXT

    return elements
