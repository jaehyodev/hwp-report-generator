"""
Test PlanRequest model's is_template_used field

TC-MODEL-001: PlanRequest default is_template_used (True)
TC-MODEL-002: PlanRequest alias isTemplateUsed (camelCase)
TC-MODEL-003: PlanRequest validation (topic length > 200 → ValidationError)
"""
import pytest
from pydantic import ValidationError

from app.models.topic import PlanRequest


class TestPlanRequestModel:
    """Test suite for PlanRequest model is_template_used field"""

    def test_plan_request_default_is_template_used(self):
        """TC-MODEL-001: PlanRequest 기본값 (is_template_used == True)"""
        # Given: PlanRequest with minimal fields
        request = PlanRequest(topic="AI 시장 분석")

        # Then: is_template_used defaults to True
        assert request.is_template_used is True
        assert request.topic == "AI 시장 분석"
        assert request.template_id is None
        assert request.is_web_search is False

    def test_plan_request_alias_is_template_used(self):
        """TC-MODEL-002: PlanRequest alias (isTemplateUsed camelCase)"""
        # Given: PlanRequest using camelCase alias
        request = PlanRequest(
            topic="디지털 뱅킹 트렌드",
            isTemplateUsed=False,  # camelCase alias
            isWebSearch=True
        )

        # Then: is_template_used is correctly set
        assert request.is_template_used is False
        assert request.is_web_search is True
        assert request.topic == "디지털 뱅킹 트렌드"

    def test_plan_request_explicit_is_template_used_true(self):
        """TC-MODEL-002 (variant): Explicit is_template_used=True"""
        # Given: PlanRequest with explicit is_template_used=True
        request = PlanRequest(
            topic="금융 규제 동향",
            is_template_used=True,
            template_id=5
        )

        # Then: is_template_used is True
        assert request.is_template_used is True
        assert request.template_id == 5

    def test_plan_request_validation_topic_too_long(self):
        """TC-MODEL-003: PlanRequest 검증 (topic 길이 초과 → ValidationError)"""
        # Given: Topic exceeds max_length (200)
        long_topic = "A" * 201

        # Then: ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            PlanRequest(topic=long_topic)

        # Verify error message mentions max_length
        error = exc_info.value
        assert "topic" in str(error).lower()
        assert len(error.errors()) > 0

    def test_plan_request_validation_topic_empty(self):
        """TC-MODEL-003 (variant): Topic is empty → ValidationError"""
        # Given: Empty topic
        # Then: ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            PlanRequest(topic="")

        error = exc_info.value
        assert "topic" in str(error).lower()

    def test_plan_request_validation_topic_missing(self):
        """TC-MODEL-003 (variant): Topic is missing → ValidationError"""
        # Given: No topic provided
        # Then: ValidationError is raised
        with pytest.raises(ValidationError) as exc_info:
            PlanRequest()

        error = exc_info.value
        assert "topic" in str(error).lower()

    def test_plan_request_all_fields(self):
        """Test PlanRequest with all fields populated"""
        # Given: PlanRequest with all fields
        request = PlanRequest(
            topic="ESG 투자 전략",
            template_id=10,
            isTemplateUsed=True,
            isWebSearch=True
        )

        # Then: All fields are correctly set
        assert request.topic == "ESG 투자 전략"
        assert request.template_id == 10
        assert request.is_template_used is True
        assert request.is_web_search is True

    def test_plan_request_json_schema_example(self):
        """Test PlanRequest with example from schema"""
        # Given: Example from Config.json_schema_extra
        request = PlanRequest(
            topic="AI 시장 분석",
            template_id=1,
            isWebSearch=True,
            isTemplateUsed=True
        )

        # Then: All fields match expected values
        assert request.topic == "AI 시장 분석"
        assert request.template_id == 1
        assert request.is_web_search is True
        assert request.is_template_used is True

    def test_plan_request_populate_by_name(self):
        """Test PlanRequest with both alias and field name"""
        # Given: PlanRequest using both alias and field name
        request = PlanRequest(
            topic="블록체인 기술 동향",
            is_template_used=False,  # field name
            is_web_search=True       # field name
        )

        # Then: Fields are correctly set
        assert request.is_template_used is False
        assert request.is_web_search is True
