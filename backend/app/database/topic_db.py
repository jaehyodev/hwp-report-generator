"""
Topic database operations.

Handles CRUD operations for topics (conversation threads).
"""
from typing import Optional, List, Tuple
from datetime import datetime
from .connection import get_db_connection
from app.models.topic import Topic, TopicCreate, TopicUpdate
from shared.types.enums import TopicStatus


class TopicDB:
    """Topic database class for CRUD operations."""

    @staticmethod
    def create_topic(user_id: int, topic_data: TopicCreate) -> Topic:
        """Creates a new topic.

        Args:
            user_id: ID of the user creating the topic
            topic_data: Topic creation data

        Returns:
            Created topic entity

        Examples:
            >>> topic_data = TopicCreate(input_prompt="Digital banking trends")
            >>> topic = TopicDB.create_topic(user_id=1, topic_data=topic_data)
            >>> print(topic.id)
            1
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        cursor.execute(
            """
            INSERT INTO topics (user_id, input_prompt, language, status, template_id, prompt_user, prompt_system, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, topic_data.input_prompt, topic_data.language,
             TopicStatus.ACTIVE.value, topic_data.template_id, topic_data.prompt_user, topic_data.prompt_system, now, now)
        )

        conn.commit()
        topic_id = cursor.lastrowid

        # Retrieve created topic
        cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()
        conn.close()

        return TopicDB._row_to_topic(row)

    @staticmethod
    def get_topic_by_id(topic_id: int) -> Optional[Topic]:
        """Retrieves topic by ID.

        Args:
            topic_id: Topic ID

        Returns:
            Topic entity or None if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()
        conn.close()

        return TopicDB._row_to_topic(row) if row else None

    @staticmethod
    def get_topics_by_user(
        user_id: int,
        status: Optional[TopicStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Topic], int]:
        """Retrieves topics for a user with pagination.

        Args:
            user_id: User ID
            status: Filter by topic status (optional)
            limit: Maximum number of topics to return
            offset: Number of topics to skip

        Returns:
            Tuple of (list of topics, total count)

        Examples:
            >>> topics, total = TopicDB.get_topics_by_user(user_id=1, limit=10, offset=0)
            >>> print(f"Found {total} topics, showing {len(topics)}")
            Found 25 topics, showing 10
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with optional status filter
        query = "SELECT * FROM topics WHERE user_id = ?"
        count_query = "SELECT COUNT(*) FROM topics WHERE user_id = ?"
        params = [user_id]

        if status:
            query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        # Get total count
        cursor.execute(count_query, params[:-2])
        total = cursor.fetchone()[0]

        # Get topics
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        topics = [TopicDB._row_to_topic(row) for row in rows]
        return topics, total

    @staticmethod
    def update_topic(topic_id: int, update_data: TopicUpdate) -> Optional[Topic]:
        """Updates topic information.

        Args:
            topic_id: Topic ID
            update_data: Fields to update

        Returns:
            Updated topic entity or None if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build dynamic query
        update_fields = []
        params = []

        if update_data.generated_title is not None:
            update_fields.append("generated_title = ?")
            params.append(update_data.generated_title)

        if update_data.status is not None:
            update_fields.append("status = ?")
            params.append(update_data.status.value)

        if not update_fields:
            conn.close()
            return TopicDB.get_topic_by_id(topic_id)

        # Always update updated_at
        update_fields.append("updated_at = ?")
        params.append(datetime.now())

        params.append(topic_id)

        query = f"UPDATE topics SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()

        # Retrieve updated topic
        cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()
        conn.close()

        return TopicDB._row_to_topic(row) if row else None

    @staticmethod
    def update_topic_prompts(topic_id: int, prompt_user: Optional[str], prompt_system: Optional[str]) -> bool:
        """Updates prompt fields for a topic."""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE topics
            SET prompt_user = ?, prompt_system = ?, updated_at = ?
            WHERE id = ?
            """,
            (prompt_user, prompt_system, datetime.now(), topic_id)
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()

        return updated

    @staticmethod
    def delete_topic(topic_id: int) -> bool:
        """Deletes a topic (hard delete, cascades to messages/artifacts).

        Args:
            topic_id: Topic ID

        Returns:
            True if deleted, False if not found
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()

        deleted = cursor.rowcount > 0
        conn.close()

        return deleted

    @staticmethod
    def _row_to_topic(row) -> Topic:
        """Converts database row to Topic model.

        Args:
            row: SQLite row object

        Returns:
            Topic entity
        """
        try:
            prompt_user = row["prompt_user"]
        except IndexError:
            prompt_user = None

        try:
            prompt_system = row["prompt_system"]
        except IndexError:
            prompt_system = None

        return Topic(
            id=row["id"],
            user_id=row["user_id"],
            input_prompt=row["input_prompt"],
            generated_title=row["generated_title"],
            language=row["language"],
            status=TopicStatus(row["status"]),
            template_id=row["template_id"],
            prompt_user=prompt_user,
            prompt_system=prompt_system,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
