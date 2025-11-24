"""
Tests for Markdown → HWPX conversion utilities and API.
"""

from __future__ import annotations

import io
import textwrap
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.database.artifact_db import ArtifactDB
from app.database.message_db import MessageDB
from app.database.topic_db import TopicDB
from app.database.user_db import UserDB
from app.models.artifact import ArtifactCreate
from app.models.convert_models import MdElement, MdType
from app.models.message import MessageCreate
from app.models.topic import TopicCreate
from app.models.user import UserCreate, UserUpdate
from app.utils.auth import hash_password
from app.utils.md_to_hwpx_converter import apply_markdown_to_hwpx, convert_markdown_to_hwpx
from app.utils.markdown_parser import parse_markdown_to_md_elements
from app.utils.response_helper import ErrorCode
from shared.types.enums import ArtifactKind, MessageRole


@pytest.fixture
def sample_md_content() -> str:
    """샘플 마크다운 콘텐츠."""

    return """# Report Title
## Section 1
Content for section 1
1. First item
2. Second item
- Bullet point
- Another bullet
> Important quote
---
"""


@pytest.fixture
def temp_template_path(tmp_path):
    """임시 템플릿 경로와 Ref 디렉토리를 생성한다."""

    contents_dir = tmp_path / "Contents"
    contents_dir.mkdir(parents=True, exist_ok=True)
    section0_path = contents_dir / "section0.xml"
    section0_path.write_text(
        textwrap.dedent(
            """\
            <?xml version="1.0" encoding="UTF-8"?>
            <hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
              <hp:p>
                <hp:run>
                  <hp:t>{{TITLE}}</hp:t>
                </hp:run>
              </hp:p>
              <!-- Content Start -->
              <!-- Content End -->
            </hp:section>
            """
        ),
        encoding="utf-8",
    )

    ref_dir = tmp_path / "refs"
    ref_dir.mkdir(parents=True, exist_ok=True)

    def _write_ref(filename: str, content: str) -> None:
        (ref_dir / filename).write_text(content.strip(), encoding="utf-8")

    _write_ref(
        "Ref_01_Section",
        """
        <hp:p>
          <hp:run>
            <hp:t><!-- SubTitleNo_Start -->5<!-- SubTitleNo_End --></hp:t>
          </hp:run>
          <hp:run>
            <hp:t><!-- SubTitle_Start -->{{SUB_TITLE}}<!-- SubTitle_End --></hp:t>
          </hp:run>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref07_OrderedList_dep1",
        """
        <hp:p>
          <hp:t><!-- OrderedNo_1_Start -->1<!-- OrderedNo_1_End --></hp:t>
          <hp:t><!-- OrderedNm_1_Start -->사업 목표<!-- OrderedNm_1_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref08_OrderedList_dep2",
        """
        <hp:p>
          <hp:t><!-- OrderedNo_2_Start -->(1)<!-- OrderedNo_2_End --></hp:t>
          <hp:t><!-- OrderedNm_2_Start -->내용<!-- OrderedNm_2_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref05_UnOrderedList_dep1",
        """
        <hp:p>
          <hp:t><!-- UnOrdered_1_Start -->검증 목표<!-- UnOrdered_1_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref06_UnOrderedList_dep2",
        """
        <hp:p>
          <hp:t><!-- UnOrdered_1_Start -->SQL 생성 성능 및 주요 검증사항 충족 여부 검증을 통한 업무 적용 범위 도출<!-- UnOrdered_2_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref04_Quotation",
        """
        <hp:p>
          <hp:t><!-- BlockQuote_Start --> BlockQuote <!-- BlockQuote_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref02_NormalText",
        """
        <hp:p>
          <hp:t><!-- Content_Start--> Content <!-- Content_End --></hp:t>
        </hp:p>
        """,
    )
    _write_ref(
        "Ref03_HorizonLine",
        """
        <hp:p>
          <hp:t>---</hp:t>
        </hp:p>
        """,
    )

    return section0_path, ref_dir


@pytest.fixture
def artifact_storage(tmp_path, monkeypatch):
    """변환 결과물이 기록될 임시 아티팩트 경로."""

    storage_dir = tmp_path / "artifacts"

    def _build(topic_id: int, version: int, filename: str):
        base = storage_dir / str(topic_id) / f"v{version}"
        base.mkdir(parents=True, exist_ok=True)
        return base, base / filename

    monkeypatch.setattr("app.routers.artifacts.build_artifact_paths", _build)
    return storage_dir


def _create_markdown_artifact(user_id: int, md_text: str, tmp_path: Path):
    """Create topic/message/artifact trio for API tests."""

    topic = TopicDB.create_topic(
        user_id,
        TopicCreate(input_prompt=f"Auto topic {uuid.uuid4().hex[:6]}"),
    )
    message = MessageDB.create_message(
        topic.id,
        MessageCreate(role=MessageRole.USER, content="seed content"),
    )
    md_file = tmp_path / f"{uuid.uuid4().hex}.md"
    md_file.write_text(md_text, encoding="utf-8")
    artifact = ArtifactDB.create_artifact(
        topic_id=topic.id,
        message_id=message.id,
        artifact_data=ArtifactCreate(
            kind=ArtifactKind.MD,
            locale="ko",
            version=1,
            filename=md_file.name,
            file_path=str(md_file),
            file_size=md_file.stat().st_size,
            sha256=None,
        ),
    )
    return artifact, topic, message


def _extract_section_xml(content: bytes) -> str:
    """Return section0.xml content from generated HWPX bytes."""

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read("Contents/section0.xml").decode("utf-8")


@pytest.mark.unit
def test_parse_markdown_all_types():
    """MD 파서가 모든 타입을 정확히 분류한다."""

    # Arrange
    md_text = "# Title\n## Section\n1. ordered\n- unordered\n> quote\ntext"

    # Act
    elements = parse_markdown_to_md_elements(md_text)

    # Assert
    assert len(elements) == 6
    expected_types = [
        MdType.TITLE,
        MdType.SECTION,
        MdType.ORDERED_LIST_DEP1,
        MdType.UNORDERED_LIST_DEP1,
        MdType.QUOTATION,
        MdType.NORMAL_TEXT,
    ]
    assert [element.type for element in elements] == expected_types


@pytest.mark.unit
def test_apply_markdown_placeholder_replacement(temp_template_path):
    """각 타입별 Ref 플레이스홀더가 올바르게 치환된다."""

    # Arrange
    section0_path, ref_dir = temp_template_path
    md_elements = [
        MdElement(type=MdType.TITLE, content="Inline Title"),
        MdElement(type=MdType.SECTION, content="Alpha", number=3),
        MdElement(type=MdType.ORDERED_LIST_DEP1, content="Roadmap", number=2),
        MdElement(type=MdType.ORDERED_LIST_DEP2, content="Detail", number=4),
        MdElement(type=MdType.UNORDERED_LIST_DEP1, content="First bullet"),
        MdElement(type=MdType.UNORDERED_LIST_DEP2, content="Second bullet"),
        MdElement(type=MdType.QUOTATION, content="C-level quote"),
        MdElement(type=MdType.NORMAL_TEXT, content="Closing paragraph"),
        MdElement(type=MdType.HORIZON_LINE, content="---"),
    ]

    # Act
    apply_markdown_to_hwpx(md_elements, str(section0_path), str(ref_dir))

    # Assert
    xml_text = section0_path.read_text(encoding="utf-8")
    assert "<!-- SubTitleNo_Start -->3<!-- SubTitleNo_End -->" in xml_text
    assert "<!-- SubTitle_Start -->Alpha<!-- SubTitle_End -->" in xml_text
    assert "<!-- OrderedNo_1_Start -->2<!-- OrderedNo_1_End -->" in xml_text
    assert "<!-- OrderedNm_1_Start -->Roadmap<!-- OrderedNm_1_End -->" in xml_text
    assert "<!-- OrderedNo_2_Start -->(4)<!-- OrderedNo_2_End -->" in xml_text
    assert "<!-- OrderedNm_2_Start -->Detail<!-- OrderedNm_2_End -->" in xml_text
    assert "<!-- UnOrdered_1_Start -->First bullet<!-- UnOrdered_1_End -->" in xml_text
    assert "<!-- UnOrdered_1_Start -->Second bullet<!-- UnOrdered_2_End -->" in xml_text
    assert "<!-- BlockQuote_Start --> C-level quote <!-- BlockQuote_End -->" in xml_text
    assert "<!-- Content_Start--> Closing paragraph <!-- Content_End -->" in xml_text


@pytest.mark.unit
def test_title_placeholder_replacement(temp_template_path):
    """Title 요소만 플레이스홀더를 교체하고 Content 영역에는 삽입하지 않는다."""

    # Arrange
    section0_path, ref_dir = temp_template_path
    md_elements = [
        MdElement(type=MdType.TITLE, content="Executive Update"),
        MdElement(type=MdType.SECTION, content="Section A", number=1),
        MdElement(type=MdType.SECTION, content="Section B", number=2),
    ]

    # Act
    apply_markdown_to_hwpx(md_elements, str(section0_path), str(ref_dir))

    # Assert
    xml_text = section0_path.read_text(encoding="utf-8")
    assert "Executive Update" in xml_text
    assert "{{TITLE}}" not in xml_text

    tree = ET.parse(section0_path)
    root = tree.getroot()
    children = list(root)
    start_idx = end_idx = None
    for idx, node in enumerate(children):
        if node.tag is ET.Comment:
            text = (node.text or "").strip()
            if text == "Content Start":
                start_idx = idx
            if text == "Content End":
                end_idx = idx
    assert start_idx is not None and end_idx is not None
    assert len(children[start_idx + 1 : end_idx]) == 2


@pytest.mark.unit
def test_number_auto_increment():
    """섹션 및 순서 리스트 번호가 자동 증가한다."""

    # Arrange
    md_text = textwrap.dedent(
        """\
        # Title
        ## Chapter 1
        ## Chapter 2
        ## Chapter 3
        1. Alpha
        2. Beta
        3. Gamma
        """
    )

    # Act
    elements = parse_markdown_to_md_elements(md_text)

    # Assert
    sections = [el for el in elements if el.type == MdType.SECTION]
    ordered_items = [el for el in elements if el.type == MdType.ORDERED_LIST_DEP1]
    assert [section.number for section in sections] == [1, 2, 3]
    assert [item.number for item in ordered_items] == [1, 2, 3]


@pytest.mark.integration
def test_complete_conversion_normal_path(sample_md_content, tmp_path):
    """정상적인 마크다운을 HWPX 파일로 변환한다."""

    # Arrange
    md_elements = parse_markdown_to_md_elements(sample_md_content)
    output_path = tmp_path / "report.hwpx"

    # Act
    convert_markdown_to_hwpx(md_elements, str(output_path))

    # Assert
    assert output_path.exists()
    with zipfile.ZipFile(output_path, "r") as archive:
        xml_text = archive.read("Contents/section0.xml").decode("utf-8")
    assert "Report Title" in xml_text
    assert "Content for section 1" in xml_text


@pytest.mark.api
def test_artifact_not_found(client, auth_headers):
    """존재하지 않는 artifact 변환 요청 시 404를 반환한다."""

    # Arrange & Act
    response = client.post("/api/artifacts/999999/convert-hwpx", headers=auth_headers)

    # Assert
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.ARTIFACT_NOT_FOUND


@pytest.mark.api
def test_no_convert_filtering(client, auth_headers, create_test_user, tmp_path, artifact_storage):
    """코드/테이블/이미지/링크/체크박스를 변환 대상에서 제외한다."""

    # Arrange
    md_text = textwrap.dedent(
        """\
        # Mixed Content
        ## Allowed
        ```python
        print("code")
        ```
        | Col1 | Col2 |
        | ---- | ---- |
        | 1 | 2 |
        ![alt](http://example.com/logo.png)
        [Doc](http://example.com)
        - [ ] unchecked
        Actual paragraph
        > Keep this quotation
        """
    )
    artifact, _, _ = _create_markdown_artifact(create_test_user.id, md_text, tmp_path)

    # Act
    response = client.post(
        f"/api/artifacts/{artifact.id}/convert-hwpx",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 200
    xml_text = _extract_section_xml(response.content)
    assert "print(" not in xml_text
    assert "Col1" not in xml_text
    assert "http://example.com" not in xml_text
    assert "unchecked" not in xml_text
    assert "Actual paragraph" in xml_text
    assert "Keep this quotation" in xml_text


@pytest.mark.api
def test_conversion_performance(client, auth_headers, create_test_user, tmp_path, artifact_storage):
    """중간 크기 마크다운은 30초 이내에 변환되어야 한다."""

    # Arrange
    lines = ["# Performance", "## Section"]
    for idx in range(50):
        lines.append(f"{idx + 1}. Item number {idx + 1}")
    md_text = "\n".join(lines)
    artifact, _, _ = _create_markdown_artifact(create_test_user.id, md_text, tmp_path)

    # Act
    start = time.perf_counter()
    response = client.post(
        f"/api/artifacts/{artifact.id}/convert-hwpx",
        headers=auth_headers,
    )
    duration = time.perf_counter() - start

    # Assert
    assert response.status_code == 200
    assert duration < 30.0


@pytest.mark.unit
def test_special_characters_escape(temp_template_path):
    """XML 특수문자를 안전하게 이스케이프한다."""

    # Arrange
    section0_path, ref_dir = temp_template_path
    md_text = textwrap.dedent(
        """\
        # Infra
        저장 공간 < 1GB & 메모리 > 2GB
        <script>alert(1)</script>
        """
    )
    md_elements = parse_markdown_to_md_elements(md_text)

    # Act
    apply_markdown_to_hwpx(md_elements, str(section0_path), str(ref_dir))

    # Assert
    xml_text = section0_path.read_text(encoding="utf-8")
    assert "저장 공간 &lt; 1GB &amp; 메모리 &gt; 2GB" in xml_text
    assert "alert(1)" not in xml_text


@pytest.mark.api
def test_user_permission_denied(
    client,
    create_test_user,
    tmp_path,
    artifact_storage,
):
    """비소유자가 변환 요청 시 403을 반환한다."""

    # Arrange
    md_text = "# Owned\n## Secret\nDo not touch."
    artifact, _, _ = _create_markdown_artifact(create_test_user.id, md_text, tmp_path)

    intruder_data = UserCreate(
        email="intruder@example.com",
        username="침입자",
        password="Other1234!@#",
    )
    intruder = UserDB.create_user(intruder_data, hash_password(intruder_data.password))
    UserDB.update_user(intruder.id, UserUpdate(is_active=True))
    login = client.post(
        "/api/auth/login",
        json={"email": intruder_data.email, "password": intruder_data.password},
    )
    intruder_token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {intruder_token}"}

    # Act
    response = client.post(
        f"/api/artifacts/{artifact.id}/convert-hwpx",
        headers=headers,
    )

    # Assert
    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.TOPIC_UNAUTHORIZED


@pytest.mark.api
def test_artifact_invalid_kind(
    client,
    auth_headers,
    create_test_user,
    tmp_path,
    artifact_storage,
):
    """MD 이외 아티팩트는 변환할 수 없다."""

    # Arrange
    md_text = "# Placeholder\nStill invalid."
    artifact, topic, message = _create_markdown_artifact(create_test_user.id, md_text, tmp_path)
    hwpx_artifact = ArtifactDB.create_artifact(
        topic_id=topic.id,
        message_id=message.id,
        artifact_data=ArtifactCreate(
            kind=ArtifactKind.HWPX,
            locale="ko",
            version=1,
            filename="existing.hwpx",
            file_path=str(tmp_path / "existing.hwpx"),
            file_size=0,
            sha256=None,
        ),
    )

    # Act
    response = client.post(
        f"/api/artifacts/{hwpx_artifact.id}/convert-hwpx",
        headers=auth_headers,
    )

    # Assert
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == ErrorCode.ARTIFACT_INVALID_KIND


@pytest.mark.unit
def test_false_positive_table_detection():
    """파이프가 포함되어도 표가 아니면 NORMAL_TEXT로 분류한다."""

    # Arrange
    md_text = "2022-11-20 | 판매액: 1,000원\nA & B | C & D"

    # Act
    elements = parse_markdown_to_md_elements(md_text)

    # Assert
    assert len(elements) == 2
    assert all(element.type == MdType.NORMAL_TEXT for element in elements)


@pytest.mark.unit
def test_false_positive_link_detection():
    """대괄호/괄호 조합이 있어도 실제 링크가 아니면 필터링하지 않는다."""

    # Arrange
    md_text = "가격: (100원)\n함수명: get_user()\n이스케이프: \\[텍스트\\](url)"

    # Act
    elements = parse_markdown_to_md_elements(md_text)

    # Assert
    assert len(elements) == 3
    assert all(element.type == MdType.NORMAL_TEXT for element in elements)
