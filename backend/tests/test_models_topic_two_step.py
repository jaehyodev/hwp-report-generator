"""
Unit tests for Topic and TopicCreate models with prompt fields.

Test Coverage:
- TC-MODEL-001: TopicCreate prompt 필드 저장
- TC-MODEL-002: TopicCreate prompt 필드 optional
"""
import pytest
from app.models.topic import TopicCreate, Topic
from datetime import datetime
from shared.types.enums import TopicStatus


class TestTopicCreatePromptFields:
    """TopicCreate 모델의 prompt 필드 테스트"""

    def test_topic_create_with_prompt_fields(self):
        """TC-MODEL-001: TopicCreate prompt 필드 저장"""
        topic_data = TopicCreate(
            input_prompt="AI 시장 분석",
            prompt_user="## 선택된 역할: Financial Analyst\n",
            prompt_system="## BACKGROUND\n..."
        )

        assert topic_data.input_prompt == "AI 시장 분석"
        assert topic_data.prompt_user == "## 선택된 역할: Financial Analyst\n"
        assert topic_data.prompt_system == "## BACKGROUND\n..."

    def test_topic_create_prompt_optional(self):
        """TC-MODEL-002: TopicCreate prompt 필드 optional"""
        topic_data = TopicCreate(input_prompt="AI 시장 분석")

        assert topic_data.input_prompt == "AI 시장 분석"
        assert topic_data.prompt_user is None
        assert topic_data.prompt_system is None

    def test_topic_create_prompt_with_template_id(self):
        """TopicCreate with template_id and prompt fields"""
        topic_data = TopicCreate(
            input_prompt="AI 시장 분석",
            template_id=1,
            prompt_user="## 선택된 역할: Financial Analyst\n",
            prompt_system="## BACKGROUND\n..."
        )

        assert topic_data.template_id == 1
        assert topic_data.prompt_user == "## 선택된 역할: Financial Analyst\n"
        assert topic_data.prompt_system == "## BACKGROUND\n..."

    def test_topic_create_with_only_prompt_user(self):
        """TopicCreate with only prompt_user"""
        topic_data = TopicCreate(
            input_prompt="AI 시장 분석",
            prompt_user="## 선택된 역할: Financial Analyst\n"
        )

        assert topic_data.prompt_user == "## 선택된 역할: Financial Analyst\n"
        assert topic_data.prompt_system is None

    def test_topic_create_with_only_prompt_system(self):
        """TopicCreate with only prompt_system"""
        topic_data = TopicCreate(
            input_prompt="AI 시장 분석",
            prompt_system="## BACKGROUND\n..."
        )

        assert topic_data.prompt_user is None
        assert topic_data.prompt_system == "## BACKGROUND\n..."


class TestTopicPromptFields:
    """Topic 모델의 prompt 필드 테스트"""

    def test_topic_with_prompt_fields(self):
        """Topic 모델에서 prompt 필드 포함"""
        topic = Topic(
            id=1,
            user_id=1,
            input_prompt="AI 시장 분석",
            prompt_user="## 선택된 역할: Financial Analyst\n",
            prompt_system="## BACKGROUND\n...",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        assert topic.prompt_user == "## 선택된 역할: Financial Analyst\n"
        assert topic.prompt_system == "## BACKGROUND\n..."

    def test_topic_prompt_fields_optional(self):
        """Topic 모델에서 prompt 필드 optional"""
        topic = Topic(
            id=1,
            user_id=1,
            input_prompt="AI 시장 분석",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        assert topic.prompt_user is None
        assert topic.prompt_system is None
