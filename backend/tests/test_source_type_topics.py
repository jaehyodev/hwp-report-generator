"""
Test source_type column addition to topics table

This test suite validates the implementation of TopicSourceType enum and source_type column
for the topics table, enabling support for template-based and basic (optimization-based) workflows.

Test Categories:
- TC-001 to TC-002: Enum and DB Schema validation
- TC-003 to TC-009: Topic CRUD operations with source_type
- TC-010 to TC-014: API endpoint behavior with source_type

Requirements:
- source_type is determined by isTemplateUsed parameter (true='template', false='basic')
- source_type is immutable after topic creation
- source_type affects template_id validation in /api/topics/{id}/generate API
- Backward compatibility: existing topics continue to work
"""
import pytest
from unittest.mock import patch, MagicMock
import sqlite3

from shared.types.enums import TopicSourceType
from app.models.topic import TopicCreate, TopicUpdate, PlanRequest
from app.database.topic_db import TopicDB
from app.database.connection import get_db_connection
from app.models.template import TemplateCreate
from app.database.template_db import TemplateDB


# ============================================================
# TC-001 to TC-002: Enum and DB Schema
# ============================================================

class TestSourceTypeEnumAndSchema:
    """Enum definition and database schema validation"""

    def test_tc_001_source_type_enum_defined(self):
        """TC-001: TopicSourceType enum must be defined with TEMPLATE and BASIC values"""
        # When: Check if TopicSourceType enum exists
        assert hasattr(TopicSourceType, 'TEMPLATE')
        assert hasattr(TopicSourceType, 'BASIC')

        # Then: Values must be correct
        assert TopicSourceType.TEMPLATE.value == 'template'
        assert TopicSourceType.BASIC.value == 'basic'

        # And: Must be string enum
        assert isinstance(TopicSourceType.TEMPLATE, str)
        assert isinstance(TopicSourceType.BASIC, str)

    def test_tc_002_db_schema_has_source_type_column(self, test_db):
        """TC-002: topics table must have source_type column with proper constraints"""
        # When: Query the schema of topics table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(topics)")
        columns = cursor.fetchall()
        conn.close()

        # Then: source_type column must exist
        column_names = [col[1] for col in columns]
        assert 'source_type' in column_names

        # And: Find the column definition
        source_type_col = next(col for col in columns if col[1] == 'source_type')
        # Column index 2 contains the type
        assert source_type_col[2] == 'TEXT'  # Type must be TEXT
        assert source_type_col[3] == 1  # NOT NULL constraint


# ============================================================
# TC-003 to TC-009: Topic CRUD Operations
# ============================================================

class TestTopicCRUDWithSourceType:
    """Topic creation, retrieval, and updates with source_type"""

    @pytest.mark.allow_topic_without_template
    def test_tc_003_create_template_source_type_topic(self, create_test_user, test_db):
        """TC-003: Create topic with source_type='template' via isTemplateUsed=true"""
        # Given: User data and template
        user = create_test_user
        template = TemplateDB.create_template(
            user.id,
            TemplateCreate(
                title="Test Template",
                filename="test.hwpx",
                file_path="/tmp/test.hwpx",
                file_size=100,
                sha256="test_sha256",
                prompt_system="Test system prompt"
            )
        )

        # When: Create topic with isTemplateUsed=true
        topic_data = TopicCreate(
            input_prompt="Test topic",
            language="ko",
            template_id=template.id,
            source_type=TopicSourceType.TEMPLATE
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # Then: Topic must have source_type='template'
        assert topic.source_type == TopicSourceType.TEMPLATE

    @pytest.mark.allow_topic_without_template
    def test_tc_004_create_basic_source_type_without_template_id(self, create_test_user, test_db):
        """TC-004: Create topic with source_type='basic' without template_id"""
        # Given: User data
        user = create_test_user

        # When: Create topic with source_type='basic' and no template_id
        topic_data = TopicCreate(
            input_prompt="Test topic",
            language="ko",
            template_id=None,
            source_type=TopicSourceType.BASIC
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # Then: Topic must have source_type='basic' and template_id=None
        assert topic.source_type == TopicSourceType.BASIC
        assert topic.template_id is None

    @pytest.mark.allow_topic_without_template
    def test_tc_005_create_basic_source_type_with_template_id(self, create_test_user, test_db):
        """TC-005: Create topic with source_type='basic' WITH template_id (optional)"""
        # Given: User data and template
        user = create_test_user
        template = TemplateDB.create_template(
            user.id,
            TemplateCreate(
                title="Test Template",
                filename="test.hwpx",
                file_path="/tmp/test.hwpx",
                file_size=100,
                sha256="test_sha256",
                prompt_system="Test system prompt"
            )
        )

        # When: Create topic with source_type='basic' but include template_id
        topic_data = TopicCreate(
            input_prompt="Test topic",
            language="ko",
            template_id=template.id,
            source_type=TopicSourceType.BASIC
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # Then: Topic must have both source_type='basic' and template_id
        assert topic.source_type == TopicSourceType.BASIC
        assert topic.template_id == template.id

    @pytest.mark.allow_topic_without_template
    def test_tc_006_retrieve_topic_includes_source_type(self, create_test_user, test_db):
        """TC-006: Retrieved topics must include source_type field"""
        # Given: User and created topic
        user = create_test_user
        topic_data = TopicCreate(
            input_prompt="Test topic",
            language="ko",
            source_type=TopicSourceType.BASIC
        )
        created_topic = TopicDB.create_topic(user.id, topic_data)

        # When: Retrieve topic by ID
        retrieved_topic = TopicDB.get_topic_by_id(created_topic.id)

        # Then: Retrieved topic must have source_type field
        assert retrieved_topic is not None
        assert hasattr(retrieved_topic, 'source_type')
        assert retrieved_topic.source_type == TopicSourceType.BASIC

    @pytest.mark.allow_topic_without_template
    def test_tc_007_topic_list_includes_source_type(self, create_test_user, test_db):
        """TC-007: Topic list queries must include source_type"""
        # Given: User with multiple topics
        user = create_test_user
        topic_data_1 = TopicCreate(
            input_prompt="Topic 1",
            source_type=TopicSourceType.TEMPLATE
        )
        topic_data_2 = TopicCreate(
            input_prompt="Topic 2",
            source_type=TopicSourceType.BASIC
        )
        TopicDB.create_topic(user.id, topic_data_1)
        TopicDB.create_topic(user.id, topic_data_2)

        # When: Retrieve topics for user
        topics, total = TopicDB.get_topics_by_user(user.id, limit=10, offset=0)

        # Then: All topics must have source_type
        assert total >= 2
        for topic in topics:
            assert hasattr(topic, 'source_type')
            assert topic.source_type in (TopicSourceType.TEMPLATE, TopicSourceType.BASIC)

    def test_tc_008_topic_create_model_requires_source_type(self):
        """TC-008: TopicCreate model must require source_type field"""
        # When: Try to create TopicCreate without source_type
        try:
            topic_data = TopicCreate(
                input_prompt="Test topic",
                language="ko"
            )
            # If we get here, the field is optional (FAIL)
            assert False, "source_type must be a required field in TopicCreate"
        except TypeError:
            # Expected: source_type is required
            pass

    @pytest.mark.allow_topic_without_template
    def test_tc_009_backward_compatibility_existing_topics(self, create_test_user, test_db):
        """TC-009: Existing topics without source_type must still work"""
        # Given: Manually insert a topic without source_type (simulating pre-migration data)
        user = create_test_user
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert topic without source_type column (using SQL directly)
        cursor.execute("""
            INSERT INTO topics (user_id, input_prompt, language, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (user.id, "Legacy topic", "ko", "active"))
        conn.commit()
        topic_id = cursor.lastrowid
        conn.close()

        # When: Retrieve the topic
        topic = TopicDB.get_topic_by_id(topic_id)

        # Then: Topic must be retrievable
        assert topic is not None
        assert topic.input_prompt == "Legacy topic"
        # source_type might be None for legacy records (db migration)


# ============================================================
# TC-010 to TC-014: API Endpoint Tests
# ============================================================

class TestGenerateAPIWithSourceType:
    """Test /api/topics/{id}/generate endpoint with source_type validation"""

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_tc_plan_endpoint_sets_source_type_based_on_is_template_used(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """Plan endpoint must set source_type based on isTemplateUsed parameter"""
        # Given: Mock response
        mock_planning.return_value = {
            "plan": "# 계획",
            "sections": [{"title": "개요", "description": "설명", "order": 1}]
        }
        topic_mock = MagicMock()
        topic_mock.id = 1
        mock_create_topic.return_value = topic_mock

        # When: POST /plan with isTemplateUsed=true
        response = client.post(
            "/api/topics/plan",
            json={"topic": "Test topic", "isTemplateUsed": True},
            headers=auth_headers
        )

        # Then: TopicCreate should be called with source_type='template'
        assert response.status_code == 200
        call_args = mock_create_topic.call_args
        topic_create_arg = call_args[0][1]  # Second argument is topic_data
        assert topic_create_arg.source_type == TopicSourceType.TEMPLATE

    @patch("app.routers.topics.sequential_planning")
    @patch("app.routers.topics.TopicDB.create_topic")
    def test_tc_plan_endpoint_basic_source_type_when_false(
        self, mock_create_topic, mock_planning, client, auth_headers
    ):
        """Plan endpoint must set source_type='basic' when isTemplateUsed=false"""
        # Given: Mock response
        mock_planning.return_value = {
            "plan": "# 계획",
            "sections": [{"title": "개요", "description": "설명", "order": 1}]
        }
        topic_mock = MagicMock()
        topic_mock.id = 1
        mock_create_topic.return_value = topic_mock

        # When: POST /plan with isTemplateUsed=false
        response = client.post(
            "/api/topics/plan",
            json={"topic": "Test topic", "isTemplateUsed": False},
            headers=auth_headers
        )

        # Then: TopicCreate should be called with source_type='basic'
        assert response.status_code == 200
        call_args = mock_create_topic.call_args
        topic_create_arg = call_args[0][1]
        assert topic_create_arg.source_type == TopicSourceType.BASIC

    @patch("app.routers.topics._background_generate_report")
    def test_tc_010_generate_template_source_type_with_valid_template(
        self, mock_background, client, auth_headers, test_db, create_test_user
    ):
        """TC-010: Generate API allows source_type='template' with valid template_id"""
        # Given: Topic with source_type='template' and template_id
        user = create_test_user
        template = TemplateDB.create_template(
            user.id,
            TemplateCreate(
                title="Test Template",
                filename="test.hwpx",
                file_path="/tmp/test.hwpx",
                file_size=100,
                sha256="test_sha256",
                prompt_system="Test system prompt"
            )
        )
        topic_data = TopicCreate(
            input_prompt="Test topic",
            source_type=TopicSourceType.TEMPLATE,
            template_id=template.id
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # When: POST /topics/{id}/generate
        response = client.post(
            f"/api/topics/{topic.id}/generate",
            json={"topic": "Test topic", "plan": "# 계획"},
            headers=auth_headers
        )

        # Then: Request must be accepted (202)
        assert response.status_code == 202
        assert response.json()["success"] is True

    @patch("app.routers.topics._background_generate_report")
    def test_tc_011_generate_basic_source_type_without_template(
        self, mock_background, client, auth_headers, test_db, create_test_user
    ):
        """TC-011: Generate API allows source_type='basic' without template_id"""
        # Given: Topic with source_type='basic' and no template_id
        user = create_test_user
        topic_data = TopicCreate(
            input_prompt="Test topic",
            source_type=TopicSourceType.BASIC,
            template_id=None
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # When: POST /topics/{id}/generate
        response = client.post(
            f"/api/topics/{topic.id}/generate",
            json={"topic": "Test topic", "plan": "# 계획"},
            headers=auth_headers
        )

        # Then: Request must be accepted (202)
        assert response.status_code == 202
        assert response.json()["success"] is True

    @patch("app.routers.topics._background_generate_report")
    def test_tc_012_generate_template_source_type_without_template_fails(
        self, mock_background, client, auth_headers, test_db, create_test_user
    ):
        """TC-012: Generate API rejects source_type='template' with null template_id"""
        # Given: Topic with source_type='template' but no template_id
        user = create_test_user
        topic_data = TopicCreate(
            input_prompt="Test topic",
            source_type=TopicSourceType.TEMPLATE,
            template_id=None
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # When: POST /topics/{id}/generate
        response = client.post(
            f"/api/topics/{topic.id}/generate",
            json={"topic": "Test topic", "plan": "# 계획"},
            headers=auth_headers
        )

        # Then: Request must be rejected with 404 error
        assert response.status_code == 404
        response_json = response.json()
        assert response_json["success"] is False
        assert "TEMPLATE_NOT_FOUND" in response_json.get("code", "")

    @patch("app.routers.topics._background_generate_report")
    def test_tc_013_generate_basic_source_type_with_optional_template(
        self, mock_background, client, auth_headers, test_db, create_test_user
    ):
        """TC-013: Generate API allows source_type='basic' with optional template_id"""
        # Given: Topic with source_type='basic' and optional template_id
        user = create_test_user
        template = TemplateDB.create_template(
            user.id,
            TemplateCreate(
                title="Test Template",
                filename="test.hwpx",
                file_path="/tmp/test.hwpx",
                file_size=100,
                sha256="test_sha256",
                prompt_system="Test system prompt"
            )
        )
        topic_data = TopicCreate(
            input_prompt="Test topic",
            source_type=TopicSourceType.BASIC,
            template_id=template.id
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # When: POST /topics/{id}/generate
        response = client.post(
            f"/api/topics/{topic.id}/generate",
            json={"topic": "Test topic", "plan": "# 계획"},
            headers=auth_headers
        )

        # Then: Request must be accepted (202)
        assert response.status_code == 202
        assert response.json()["success"] is True

    def test_tc_014_source_type_is_immutable(self, create_test_user, test_db):
        """TC-014: source_type must be immutable after topic creation"""
        # Given: Created topic
        user = create_test_user
        topic_data = TopicCreate(
            input_prompt="Test topic",
            source_type=TopicSourceType.TEMPLATE
        )
        topic = TopicDB.create_topic(user.id, topic_data)

        # When: Try to update topic (source_type should NOT be in TopicUpdate model)
        # TopicUpdate should not include source_type field
        from app.models.topic import TopicUpdate
        update_data = TopicUpdate(generated_title="New Title")

        # Verify that TopicUpdate does not have source_type field
        assert not hasattr(update_data, 'source_type') or update_data.source_type is None

        # Then: source_type field should not exist in TopicUpdate model definition
        import inspect
        topic_update_fields = TopicUpdate.model_fields
        assert 'source_type' not in topic_update_fields, "source_type must not be updatable"
