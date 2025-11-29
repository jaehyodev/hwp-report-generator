"""
Test cases for Structured Outputs JSON Schema fixes
Anthropic Structured Outputs API compliance validation
"""

import pytest
import json
from app.utils.structured_client import StructuredClaudeClient


class TestStructuredOutputsJsonSchema:
    """Structured Outputs JSON Schema 테스트"""

    @pytest.fixture
    def client(self):
        """StructuredClaudeClient 초기화"""
        return StructuredClaudeClient()

    @pytest.fixture
    def basic_section_schema(self):
        """BASIC 모드 섹션 스키마"""
        return {
            "TITLE": {"placeholder": "{{TITLE}}", "order": 1},
            "BACKGROUND": {"placeholder": "{{BACKGROUND}}", "order": 3},
            "MAIN_CONTENT": {"placeholder": "{{MAIN_CONTENT}}", "order": 4},
            "SUMMARY": {"placeholder": "{{SUMMARY}}", "order": 5},
            "CONCLUSION": {"placeholder": "{{CONCLUSION}}", "order": 6},
        }

    # ==================== TC-001 ====================
    def test_metadata_additional_properties_basic_mode(self, client, basic_section_schema):
        """TC-001: JSON Schema 빌드 - metadata additionalProperties 검증 (BASIC 모드)

        Scenario: BASIC 모드에서 JSON Schema 생성
        Expected:
          - schema["properties"]["metadata"] 존재
          - schema["properties"]["metadata"]["additionalProperties"] = false
          - schema["properties"]["metadata"]["properties"] 존재
          - properties에는 generated_at, model, topic, total_sections 필드만 정의
        """
        json_schema = client._build_json_schema(basic_section_schema, "basic")

        # metadata 필드 존재 확인
        assert "metadata" in json_schema["properties"], "metadata 필드 없음"
        metadata = json_schema["properties"]["metadata"]

        # additionalProperties: false 확인
        assert metadata.get("additionalProperties") is False, \
            "metadata.additionalProperties가 False가 아님"

        # properties 존재 확인
        assert "properties" in metadata, "metadata.properties 없음"
        assert metadata["properties"] is not None, "metadata.properties가 None"

        # 필드 개수 확인 (4개만)
        assert len(metadata["properties"]) == 4, \
            f"metadata 필드가 {len(metadata['properties'])}개인데, 4개여야 함"

        # 필드명 확인
        expected_fields = {"generated_at", "model", "topic", "total_sections"}
        actual_fields = set(metadata["properties"].keys())
        assert actual_fields == expected_fields, \
            f"필드가 {actual_fields}인데, {expected_fields}여야 함"

    # ==================== TC-002 ====================
    def test_metadata_properties_accuracy(self, client, basic_section_schema):
        """TC-002: JSON Schema 빌드 - metadata properties 정확성

        Scenario: BASIC 모드 metadata properties 생성
        Expected:
          - 4개 필드만 정의됨: generated_at, model, topic, total_sections
          - 각 필드 type 정의됨 (string, string, string, integer)
          - 각 필드 description 정의됨
          - max_length, min_length 등 비표준 필드는 포함되지 않음
        """
        json_schema = client._build_json_schema(basic_section_schema, "basic")
        metadata = json_schema["properties"]["metadata"]
        props = metadata["properties"]

        # generated_at 검증
        assert props["generated_at"]["type"] == "string", \
            "generated_at.type이 string이 아님"
        assert "description" in props["generated_at"], \
            "generated_at.description 없음"

        # model 검증
        assert props["model"]["type"] == "string", \
            "model.type이 string이 아님"
        assert "description" in props["model"], \
            "model.description 없음"

        # topic 검증
        assert props["topic"]["type"] == "string", \
            "topic.type이 string이 아님"
        assert "description" in props["topic"], \
            "topic.description 없음"

        # total_sections 검증
        assert props["total_sections"]["type"] == "integer", \
            "total_sections.type이 integer가 아님"
        assert "description" in props["total_sections"], \
            "total_sections.description 없음"

        # 비표준 필드 없음 확인
        for field_name, field_def in props.items():
            assert "max_length" not in field_def, \
                f"{field_name}에 max_length가 있음 (비표준)"
            assert "min_length" not in field_def, \
                f"{field_name}에 min_length가 있음 (비표준)"

    # ==================== TC-003 ====================
    def test_metadata_template_mode(self, client, basic_section_schema):
        """TC-003: JSON Schema 빌드 - TEMPLATE 모드에서도 적용

        Scenario: TEMPLATE 모드에서 JSON Schema 생성
        Expected:
          - source_type enum = ["template", "system"] (BASIC과 다름)
          - metadata.additionalProperties = false (동일)
          - metadata.properties 동일 구조
        """
        json_schema = client._build_json_schema(basic_section_schema, "template")

        # sections.items의 source_type enum 확인 (template)
        sections_items = json_schema["properties"]["sections"]["items"]
        source_type_enum = sections_items["properties"]["source_type"]["enum"]
        assert source_type_enum == ["template", "system"], \
            f"TEMPLATE 모드의 source_type enum이 {source_type_enum}인데, ['template', 'system']이어야 함"

        # metadata.additionalProperties 확인 (동일해야 함)
        metadata = json_schema["properties"]["metadata"]
        assert metadata.get("additionalProperties") is False, \
            "TEMPLATE 모드에서도 metadata.additionalProperties = false여야 함"

        # metadata.properties 구조 확인
        expected_fields = {"generated_at", "model", "topic", "total_sections"}
        actual_fields = set(metadata["properties"].keys())
        assert actual_fields == expected_fields, \
            f"TEMPLATE 모드 metadata 필드가 {actual_fields}인데, {expected_fields}여야 함"

    # ==================== TC-004 ====================
    def test_sections_items_properties_no_deprecated_fields(self, client, basic_section_schema):
        """TC-004: sections.items.properties에서 비표준 필드 제거 확인

        Scenario: JSON Schema 생성 시 비표준 필드 미포함
        Expected:
          - max_length 필드 없음
          - min_length 필드 없음
          - description 필드 없음 (섹션 메타에는)
          - example 필드 없음
          - id, type, content, order, source_type, placeholder_key만 존재
        """
        json_schema = client._build_json_schema(basic_section_schema, "basic")
        sections_items_props = json_schema["properties"]["sections"]["items"]["properties"]

        # 비표준 필드 없음 확인
        assert "max_length" not in sections_items_props, \
            "sections.items.properties에 max_length가 있음"
        assert "min_length" not in sections_items_props, \
            "sections.items.properties에 min_length가 있음"
        assert "description" not in sections_items_props, \
            "sections.items.properties에 description이 있음"
        assert "example" not in sections_items_props, \
            "sections.items.properties에 example이 있음"

        # 유지 필드만 존재 확인
        expected_fields = {"id", "type", "content", "order", "source_type", "placeholder_key"}
        actual_fields = set(sections_items_props.keys())
        assert actual_fields == expected_fields, \
            f"섹션 필드가 {actual_fields}인데, {expected_fields}여야 함"

    # ==================== TC-005 ====================
    def test_json_schema_compliance_validation(self, client, basic_section_schema):
        """TC-005: 전체 JSON Schema 구조 검증 (Anthropic Structured Outputs 준수)

        Scenario: 생성된 JSON Schema가 Anthropic 요구사항 충족
        Expected:
          - Root: additionalProperties: false
          - sections.items: additionalProperties: false
          - metadata: additionalProperties: false
          - 모든 object 타입에 additionalProperties 명시됨
        """
        json_schema = client._build_json_schema(basic_section_schema, "basic")

        # Root level
        assert json_schema.get("additionalProperties") is False, \
            "Root additionalProperties가 False가 아님"

        # sections.items level
        sections_items = json_schema["properties"]["sections"]["items"]
        assert sections_items.get("additionalProperties") is False, \
            "sections.items.additionalProperties가 False가 아님"

        # metadata level
        metadata = json_schema["properties"]["metadata"]
        assert metadata.get("additionalProperties") is False, \
            "metadata.additionalProperties가 False가 아님"

        # JSON으로 직렬화 가능한지 확인
        try:
            schema_json = json.dumps(json_schema, ensure_ascii=False)
            assert len(schema_json) > 0, "JSON 직렬화 실패"
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON 직렬화 실패: {str(e)}")

        # type: ["object", "null"]인 경우 additionalProperties 확인
        metadata_type = metadata.get("type")
        assert isinstance(metadata_type, list), \
            f"metadata.type이 list가 아님: {metadata_type}"
        assert "object" in metadata_type, \
            f"metadata.type에 'object'가 없음: {metadata_type}"
        assert metadata.get("additionalProperties") is False, \
            "metadata가 object 타입인데 additionalProperties가 False가 아님"


class TestBackwardCompatibility:
    """기존 기능 호환성 테스트"""

    @pytest.fixture
    def client(self):
        """StructuredClaudeClient 초기화"""
        return StructuredClaudeClient()

    @pytest.fixture
    def basic_section_schema(self):
        """BASIC 모드 섹션 스키마"""
        return {
            "TITLE": {"placeholder": "{{TITLE}}", "order": 1},
            "BACKGROUND": {"placeholder": "{{BACKGROUND}}", "order": 3},
            "MAIN_CONTENT": {"placeholder": "{{MAIN_CONTENT}}", "order": 4},
            "SUMMARY": {"placeholder": "{{SUMMARY}}", "order": 5},
            "CONCLUSION": {"placeholder": "{{CONCLUSION}}", "order": 6},
        }

    def test_basic_mode_still_works(self, client, basic_section_schema):
        """기존 BASIC 모드 정상 작동 확인"""
        json_schema = client._build_json_schema(basic_section_schema, "basic")

        # 기본 구조 확인
        assert "properties" in json_schema
        assert "sections" in json_schema["properties"]
        assert "metadata" in json_schema["properties"]

        # sections는 배열
        sections = json_schema["properties"]["sections"]
        assert sections["type"] == "array"
        assert "items" in sections

        # 각 섹션은 object
        items = sections["items"]
        assert items["type"] == "object"
        assert "properties" in items

    def test_type_enum_still_works_basic_mode(self, client, basic_section_schema):
        """BASIC 모드의 type enum 정상 작동 확인"""
        json_schema = client._build_json_schema(basic_section_schema, "basic")

        sections_type = json_schema["properties"]["sections"]["items"]["properties"]["type"]
        expected_enum = ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"]

        assert sections_type["enum"] == expected_enum, \
            f"type enum이 {sections_type['enum']}인데, {expected_enum}이어야 함"

    def test_source_type_enum_still_works_basic_mode(self, client, basic_section_schema):
        """BASIC 모드의 source_type enum 정상 작동 확인"""
        json_schema = client._build_json_schema(basic_section_schema, "basic")

        source_type_def = json_schema["properties"]["sections"]["items"]["properties"]["source_type"]
        expected_enum = ["basic", "system"]

        assert source_type_def["enum"] == expected_enum, \
            f"source_type enum이 {source_type_def['enum']}인데, {expected_enum}이어야 함"
