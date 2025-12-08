"""Utilities for converting Markdown elements to HWPX files."""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from app.models.convert_models import MdElement, MdType
from shared.constants import ProjectPath

logger = logging.getLogger(__name__)

HWPX_TEMPLATE_PATH = ProjectPath.BACKEND / "templates" / "templateRef" / "Template_Hwpx.hwpx"
TEMPLATE_REF_DIR = ProjectPath.BACKEND / "templates" / "templateRef"

_TEMP_DIR_OVERRIDE: Optional[Path] = None
_TEMP_DIR_HANDLES: Dict[str, tempfile.TemporaryDirectory] = {}

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


def escape_xml(text: str) -> str:
    """Markdown 문자열에 포함된 XML 특수 문자를 안전한 엔티티로 변환합니다.

    Args:
        text: 원본 Markdown 내용.

    Returns:
        XML에서 안전하게 사용할 수 있도록 특수 문자가 이스케이프된 문자열.
    """

    if text is None:
        return ""

    replacements = [
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
    ]
    escaped = text
    for target, replacement in replacements:
        escaped = escaped.replace(target, replacement)
    return escaped


def load_template() -> Tuple[str, str]:
    """HWPX 템플릿 파일을 로드하여 임시 디렉터리에 풀어냅니다.

    Returns:
        Tuple[str, str]: (temp_dir, section0_path)
            - temp_dir: 템플릿이 추출된 임시 디렉터리 경로
            - section0_path: 추출된 템플릿 내부의 Contents/section0.xml 파일 경로

    Raises:
        FileNotFoundError: 템플릿 파일 또는 section0.xml을 찾을 수 없는 경우 발생합니다.
    """

    if not HWPX_TEMPLATE_PATH.exists():
        logger.error("Template file not found at %s", HWPX_TEMPLATE_PATH)
        raise FileNotFoundError(f"Template file not found: {HWPX_TEMPLATE_PATH}")

    temp_dir_path: Path
    if _TEMP_DIR_OVERRIDE:
        temp_dir_path = _TEMP_DIR_OVERRIDE
        temp_dir_path.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir_handle = tempfile.TemporaryDirectory(prefix="hwpx_template_")
        temp_dir_path = Path(temp_dir_handle.name)
        _TEMP_DIR_HANDLES[str(temp_dir_path)] = temp_dir_handle

    logger.info("Extracting template %s into %s", HWPX_TEMPLATE_PATH, temp_dir_path)
    with zipfile.ZipFile(HWPX_TEMPLATE_PATH, "r") as zip_ref:
        zip_ref.extractall(str(temp_dir_path))

    section0_path = temp_dir_path / "Contents" / "section0.xml"
    if not section0_path.exists():
        logger.error("section0.xml not found inside extracted template")
        raise FileNotFoundError("Contents/section0.xml not found in template")

    return str(temp_dir_path), str(section0_path)


def apply_markdown_to_hwpx(
    md_elements: List[MdElement],
    section0_path: str,
    ref_dir: str,
) -> None:
    """파싱된 Markdown 요소를 section0.xml에 적용합니다.

    Args:
        md_elements: 파서가 생성한 Markdown 요소 목록.
        section0_path: Contents/section0.xml의 절대 경로.
        ref_dir: 참조(Ref) 스니펫 파일들이 위치한 디렉터리(읽기 전용).

    Raises:
        FileNotFoundError: section0.xml 또는 필요한 Ref 파일이 존재하지 않을 경우.
        ET.ParseError: section0.xml을 파싱할 수 없을 때 발생합니다.
    """


    section_path = Path(section0_path)
    if not section_path.exists():
        raise FileNotFoundError(f"section0.xml not found: {section0_path}")

    ref_path = Path(ref_dir)
    if not ref_path.exists():
        raise FileNotFoundError(f"Reference directory not found: {ref_dir}")

    namespaces = _collect_namespaces(section_path)
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    try:
        tree = ET.parse(str(section_path), parser=parser)
    except ET.ParseError as exc:
        logger.error("Failed to parse section0.xml: %s", exc)
        raise

    root = tree.getroot()

    title_value = _extract_title(md_elements)
    _apply_title_placeholder(root, title_value, namespaces)

    content_start_idx, content_end_idx = _find_content_comment_indices(root)
    if content_start_idx is None or content_end_idx is None or content_start_idx >= content_end_idx:
        logger.error("Content Start/End comments missing in section0.xml")
        raise ValueError("Content comment markers not found in section0.xml")

    # Remove old nodes between comments before inserting new snippets.
    children = list(root)
    to_remove = children[content_start_idx + 1 : content_end_idx]
    for node in to_remove:
        root.remove(node)

    insertion_index = content_start_idx + 1
    content_start_comment = root[content_start_idx]
    content_end_comment = root[content_end_idx]
    content_start_comment.tail = "\n"

    for element in md_elements:
        if element.type in (MdType.TITLE, MdType.NO_CONVERT):
            continue
        snippet = _build_snippet_from_ref(element, ref_path)
        if not snippet:
            continue
        snippet_elements = _parse_snippet(snippet, namespaces)
        if not snippet_elements:
            continue
        for snippet_elem in snippet_elements:
            root.insert(insertion_index, snippet_elem)
            snippet_elem.tail = "\n"
            insertion_index += 1

    content_end_comment.tail = "\n"

    tree.write(str(section_path), encoding="utf-8", xml_declaration=True)
    logger.info("section0.xml updated with Markdown content at %s", section0_path)


def create_hwpx_file(temp_dir: str, output_path: str) -> None:
    """수정된 템플릿 디렉터리를 다시 HWPX 압축 파일로 패키징합니다.

    Args:
        temp_dir: 수정된 템플릿 파일들이 들어 있는 디렉터리.
        output_path: 생성될 HWPX 파일의 출력 경로.

    Raises:
        FileNotFoundError: mimetype 파일이 존재하지 않을 경우.
        OSError: 출력 파일을 생성하거나 기록하는 과정에서 오류가 발생한 경우.
    """


    temp_dir_path = Path(temp_dir)
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    mimetype_path = temp_dir_path / "mimetype"
    if not mimetype_path.exists():
        raise FileNotFoundError("mimetype file missing from extracted template")

    logger.info("Creating HWPX archive at %s", output_path_obj)
    with zipfile.ZipFile(output_path_obj, "w") as zip_ref:
        zip_ref.write(str(mimetype_path), "mimetype", compress_type=zipfile.ZIP_STORED)
        for root_dir, _, files in os.walk(temp_dir):
            for file_name in files:
                abs_path = Path(root_dir) / file_name
                rel_path = abs_path.relative_to(temp_dir_path)
                if str(rel_path) == "mimetype":
                    continue
                zip_ref.write(
                    str(abs_path),
                    str(rel_path).replace("\\", "/"),
                    compress_type=zipfile.ZIP_DEFLATED,
                )


def convert_markdown_to_hwpx(
    md_elements: List[MdElement],
    output_path: str,
) -> bytes:
    """Markdown 요소를 최종 HWPX 파일로 변환합니다.

    Args:
        md_elements: 파싱된 Markdown 요소들.
        output_path: 생성된 HWPX 파일을 저장할 경로.

    Returns:
        bytes: 생성된 HWPX 파일의 바이너리 데이터.
    """


    with tempfile.TemporaryDirectory(prefix="hwpx_work_") as work_dir:
        extracted_dir = Path(work_dir) / "template"
        extracted_dir.mkdir(parents=True, exist_ok=True)

        global _TEMP_DIR_OVERRIDE
        previous_override = _TEMP_DIR_OVERRIDE
        _TEMP_DIR_OVERRIDE = extracted_dir
        try:
            temp_dir, section0_path = load_template()
        finally:
            _TEMP_DIR_OVERRIDE = previous_override

        try:
            apply_markdown_to_hwpx(md_elements, section0_path, str(TEMPLATE_REF_DIR))
            create_hwpx_file(temp_dir, output_path)
        finally:
            _cleanup_temp_dir(temp_dir)

    generated_bytes = Path(output_path).read_bytes()
    logger.info("HWPX conversion complete: %s", output_path)
    return generated_bytes


def _collect_namespaces(section_path: Path) -> Dict[str, str]:
    """XML 문서에서 네임스페이스 선언을 수집합니다."""

    namespaces: Dict[str, str] = {}
    for event, elem in ET.iterparse(str(section_path), events=("start-ns",)):
        prefix, uri = elem
        if prefix in namespaces:
            continue
        namespaces[prefix or ""] = uri
    return namespaces


def _extract_title(md_elements: List[MdElement]) -> str:
    """Markdown 요소에서 첫 번째 제목을 추출합니다."""

    for element in md_elements:
        if element.type == MdType.TITLE and element.content.strip():
            return escape_xml(element.content.strip())
    return "Untitled"


def _apply_title_placeholder(
    root: ET.Element,
    title_value: str,
    namespaces: Dict[str, str],
) -> None:
    """section0.xml 내부의 {{TITLE}} 플레이스홀더를 실제 값으로 대체합니다."""

    hp_namespace = namespaces.get("hp")
    if hp_namespace is None:
        logger.warning("hp namespace missing; unable to locate title placeholder reliably")
        return

    title_xpath = f".//{{{hp_namespace}}}t"
    for node in root.findall(title_xpath):
        if node.text and "{{TITLE}}" in node.text:
            node.text = title_value
            return
    logger.warning("Title placeholder not found in section0.xml")


def _find_content_comment_indices(root: ET.Element) -> Tuple[Optional[int], Optional[int]]:
    """Content 시작/종료 위치를 나타내는 주석 노드의 인덱스를 찾습니다."""

    start_idx: Optional[int] = None
    end_idx: Optional[int] = None
    for idx, child in enumerate(list(root)):
        if child.tag is ET.Comment:
            text = (child.text or "").strip()
            if text == "Content Start":
                start_idx = idx
            elif text == "Content End":
                end_idx = idx
    return start_idx, end_idx


def _build_snippet_from_ref(element: MdElement, ref_dir: Path) -> str:
    """Markdown 요소에 대응하는 참조(Ref) 파일을 이용해 XML 스니펫을 생성합니다."""

    filename = element.ref_filename or REF_FILENAME_MAP.get(element.type)
    if not filename:
        logger.info("No reference mapping for element type %s; skipping", element.type)
        return ""

    ref_file = _resolve_ref_path(ref_dir, filename)
    template = ref_file.read_text(encoding="utf-8")
    content = escape_xml(element.content.strip())
    number_value = str(element.number if element.number is not None else 1)

    if element.type == MdType.DATE:
        template = template.replace(
            "<!-- Date_Start -->{{ DATE }}<!-- Date_End -->",
            f"<!-- Date_Start -->{content}<!-- Date_End -->",
        )
    elif element.type == MdType.SECTION:
        template = template.replace(
            "<!-- SubTitleNo_Start -->5<!-- SubTitleNo_End -->",
            f"<!-- SubTitleNo_Start -->{number_value}<!-- SubTitleNo_End -->",
        )
        template = template.replace(
            "<!-- SubTitle_Start -->{{SUB_TITLE}}<!-- SubTitle_End -->",
            f"<!-- SubTitle_Start -->{content or 'Untitled'}<!-- SubTitle_End -->",
        )
    elif element.type == MdType.ORDERED_LIST_DEP1:
        template = template.replace(
            "<!-- OrderedNo_1_Start -->1<!-- OrderedNo_1_End -->",
            f"<!-- OrderedNo_1_Start -->{number_value}<!-- OrderedNo_1_End -->",
        )
        template = template.replace(
            "<!-- OrderedNm_1_Start -->사업 목표<!-- OrderedNm_1_End -->",
            f"<!-- OrderedNm_1_Start -->{content}<!-- OrderedNm_1_End -->",
        )
    elif element.type == MdType.ORDERED_LIST_DEP2:
        template = template.replace(
            "<!-- OrderedNo_2_Start -->(1)<!-- OrderedNo_2_End -->",
            f"<!-- OrderedNo_2_Start -->({number_value})<!-- OrderedNo_2_End -->",
        )
        template = template.replace(
            "<!-- OrderedNm_2_Start -->내용<!-- OrderedNm_2_End -->",
            f"<!-- OrderedNm_2_Start -->{content}<!-- OrderedNm_2_End -->",
        )
    elif element.type == MdType.UNORDERED_LIST_DEP1:
        template = template.replace(
            "<!-- UnOrdered_1_Start -->검증 목표<!-- UnOrdered_1_End -->",
            f"<!-- UnOrdered_1_Start -->{content}<!-- UnOrdered_1_End -->",
        )
    elif element.type == MdType.UNORDERED_LIST_DEP2:
        template = template.replace(
            "<!-- UnOrdered_1_Start -->SQL 생성 성능 및 주요 검증사항 충족 여부 검증을 통한 업무 적용 범위 도출<!-- UnOrdered_2_End -->",
            f"<!-- UnOrdered_1_Start -->{content}<!-- UnOrdered_2_End -->",
        )
    elif element.type == MdType.QUOTATION:
        template = template.replace(
            "<!-- BlockQuote_Start --> BlockQuote <!-- BlockQuote_End -->",
            f"<!-- BlockQuote_Start --> {content} <!-- BlockQuote_End -->",
        )
    elif element.type == MdType.NORMAL_TEXT:
        template = template.replace(
            "<!-- Content_Start--> Content <!-- Content_End -->",
            f"<!-- Content_Start--> {content} <!-- Content_End -->",
        )

    return template.strip()


def _parse_snippet(snippet: str, namespaces: Dict[str, str]) -> List[ET.Element]:
    """스니펫 XML 문자열을 파싱하여 ET 요소로 변환합니다."""

    stripped = snippet.strip()
    if not stripped:
        return []

    ns_attributes = " ".join(
        f'xmlns:{prefix}="{uri}"' if prefix else f'xmlns="{uri}"'
        for prefix, uri in namespaces.items()
    )
    wrapper_open = f"<wrapper {ns_attributes}>" if ns_attributes else "<wrapper>"
    wrapper_xml = f"{wrapper_open}{stripped}</wrapper>"

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    wrapper_element = ET.fromstring(wrapper_xml, parser=parser)

    snippet_elements = list(wrapper_element)
    for element in snippet_elements:
        wrapper_element.remove(element)
    return snippet_elements


def _resolve_ref_path(ref_dir: Path, filename: str) -> Path:
    """언더스코어 변형 파일명을 포함하여 실제 참조(Ref) 파일 경로를 찾아 반환합니다."""

    candidate = ref_dir / filename
    if candidate.exists():
        return candidate

    # Handle files stored without an underscore after Ref (e.g., Ref01_*).
    if filename.startswith("Ref_"):
        fallback = ref_dir / (filename.replace("Ref_", "Ref", 1))
        if fallback.exists():
            return fallback

    logger.error("Reference file %s not found in %s", filename, ref_dir)
    raise FileNotFoundError(f"Reference file not found: {filename}")


def _cleanup_temp_dir(path: str) -> None:
    """지정된 경로를 위해 생성된 TemporaryDirectory 객체가 있다면 정리합니다."""

    handle = _TEMP_DIR_HANDLES.pop(path, None)
    if handle:
        handle.cleanup()
