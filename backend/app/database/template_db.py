"""Template database operations.

Handles CRUD operations for user custom templates and their placeholders.
"""

from datetime import datetime
from typing import List, Optional

from .connection import get_db_connection
from app.models.template import Template, TemplateCreate, Placeholder, PlaceholderCreate


class TemplateDB:
    """Template database class for CRUD operations."""

    @staticmethod
    def create_template(user_id: int, template_data: TemplateCreate) -> Template:
        """Creates a new template.

        Args:
            user_id: User ID who owns this template
            template_data: Template creation data

        Returns:
            Created template entity

        Raises:
            Exception: Database insertion error

        Examples:
            >>> template_data = TemplateCreate(
            ...     title="재무보고서 템플릿",
            ...     filename="template.hwpx",
            ...     file_path="backend/templates/user_1/template_1/template.hwpx",
            ...     file_size=45678,
            ...     sha256="abc123..."
            ... )
            >>> template = TemplateDB.create_template(1, template_data)
            >>> print(template.title)
            재무보고서 템플릿
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        try:
            cursor.execute(
                """
                INSERT INTO templates (
                    user_id, title, description, filename,
                    file_path, file_size, sha256, is_active,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    template_data.title,
                    template_data.description,
                    template_data.filename,
                    template_data.file_path,
                    template_data.file_size,
                    template_data.sha256,
                    True,  # is_active
                    now,
                    now
                )
            )
            conn.commit()
            template_id = cursor.lastrowid

            # Retrieve created template
            cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            conn.close()

            return TemplateDB._row_to_template(row)
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def create_template_with_transaction(
        user_id: int,
        template_data: TemplateCreate,
        placeholder_keys: List[str]
    ) -> Template:
        """Creates a new template and its placeholders in a single transaction.

        이 메서드는 Template과 Placeholder를 원자적(Atomically)으로 저장합니다.
        Template INSERT 또는 Placeholder INSERT 중 하나라도 실패하면 전체 롤백됩니다.

        Args:
            user_id: User ID who owns this template
            template_data: Template creation data (prompt_user, prompt_system 포함)
            placeholder_keys: List of placeholder keys (e.g., ["{{TITLE}}", "{{SUMMARY}}"])

        Returns:
            Created template entity

        Raises:
            Exception: Database transaction error (자동 롤백)

        Examples:
            >>> template_data = TemplateCreate(
            ...     title="재무보고서 템플릿",
            ...     filename="template.hwpx",
            ...     file_path="backend/templates/user_1/template_1/template.hwpx",
            ...     file_size=45678,
            ...     sha256="abc123...",
            ...     prompt_user="{{TITLE}}, {{SUMMARY}}",
            ...     prompt_system="당신은 금융 기관의 전문 보고서..."
            ... )
            >>> placeholders = ["{{TITLE}}", "{{SUMMARY}}"]
            >>> template = TemplateDB.create_template_with_transaction(1, template_data, placeholders)
            >>> print(template.prompt_system[:50])
            당신은 금융 기관의 전문 보고서...
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        try:
            # Step 1: 트랜잭션 시작
            cursor.execute("BEGIN TRANSACTION")

            # Step 2: Template INSERT
            cursor.execute(
                """
                INSERT INTO templates (
                    user_id, title, description, filename,
                    file_path, file_size, sha256, is_active,
                    prompt_user, prompt_system,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    template_data.title,
                    template_data.description,
                    template_data.filename,
                    template_data.file_path,
                    template_data.file_size,
                    template_data.sha256,
                    True,  # is_active
                    template_data.prompt_user,
                    template_data.prompt_system,
                    now,
                    now
                )
            )
            template_id = cursor.lastrowid

            # Step 3: Placeholders 배치 INSERT
            if placeholder_keys:
                data = [(template_id, key, sort_idx, now) for sort_idx, key in enumerate(placeholder_keys)]
                cursor.executemany(
                    """
                    INSERT INTO placeholders (template_id, placeholder_key, sort, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    data
                )

            # Step 4: 커밋 (모든 INSERT 성공 시)
            conn.commit()

            # Step 5: 생성된 Template 조회 및 반환
            cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            row = cursor.fetchone()
            conn.close()

            return TemplateDB._row_to_template(row)

        except Exception as e:
            # 에러 발생 시 자동 롤백
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def get_template_by_id(template_id: int, user_id: Optional[int] = None) -> Optional[Template]:
        """Retrieves an active template by ID.

        Args:
            template_id: Template ID to retrieve
            user_id: User ID for permission check (optional)

        Returns:
            Template entity or None if not found or inactive

        Examples:
            >>> template = TemplateDB.get_template_by_id(1)
            >>> if template:
            ...     print(template.title)
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        if user_id is not None:
            cursor.execute(
                "SELECT * FROM templates WHERE id = ? AND user_id = ? AND is_active = 1",
                (template_id, user_id)
            )
        else:
            cursor.execute("SELECT * FROM templates WHERE id = ? AND is_active = 1", (template_id,))

        row = cursor.fetchone()
        conn.close()

        return TemplateDB._row_to_template(row) if row else None

    @staticmethod
    def list_templates_by_user(user_id: int) -> List[Template]:
        """Lists all templates owned by a user.

        Args:
            user_id: User ID

        Returns:
            List of template entities

        Examples:
            >>> templates = TemplateDB.list_templates_by_user(1)
            >>> print(len(templates))
            3
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM templates WHERE user_id = ? AND is_active = ? ORDER BY created_at DESC",
            (user_id, True)
        )
        rows = cursor.fetchall()
        conn.close()

        return [TemplateDB._row_to_template(row) for row in rows]

    @staticmethod
    def list_all_templates() -> List[Template]:
        """Lists all active templates (admin only).

        Returns:
            List of all template entities

        Examples:
            >>> all_templates = TemplateDB.list_all_templates()
            >>> print(len(all_templates))
            10
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM templates WHERE is_active = ? ORDER BY created_at DESC",
            (True,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [TemplateDB._row_to_template(row) for row in rows]

    @staticmethod
    def delete_template(template_id: int, user_id: int) -> bool:
        """Soft deletes a template (marks as inactive).

        Args:
            template_id: Template ID to delete
            user_id: User ID for permission check

        Returns:
            True if deleted successfully, False if not found

        Examples:
            >>> success = TemplateDB.delete_template(1, 1)
            >>> print(success)
            True
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE templates
                SET is_active = 0, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (datetime.now(), template_id, user_id)
            )
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def update_prompt_system(template_id: int, new_prompt_system: str) -> Optional[Template]:
        """Updates the prompt_system field of a template.

        Args:
            template_id: Template ID to update
            new_prompt_system: New system prompt text

        Returns:
            Updated template entity or None if not found

        Raises:
            Exception: Database update error

        Examples:
            >>> template = TemplateDB.update_prompt_system(1, "새로운 시스템 프롬프트")
            >>> if template:
            ...     print(template.prompt_system)
            새로운 시스템 프롬프트
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE templates
                SET prompt_system = ?, updated_at = ?
                WHERE id = ? AND is_active = 1
                """,
                (new_prompt_system, datetime.now(), template_id)
            )
            conn.commit()

            # Retrieve updated template
            if cursor.rowcount > 0:
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                row = cursor.fetchone()
                conn.close()
                return TemplateDB._row_to_template(row)
            else:
                conn.close()
                return None
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def update_prompt_user(template_id: int, new_prompt_user: str) -> Optional[Template]:
        """Updates the prompt_user field of a template.

        Args:
            template_id: Template ID to update
            new_prompt_user: New user prompt text

        Returns:
            Updated template entity or None if not found

        Raises:
            Exception: Database update error

        Examples:
            >>> template = TemplateDB.update_prompt_user(1, "새로운 사용자 프롬프트")
            >>> if template:
            ...     print(template.prompt_user)
            새로운 사용자 프롬프트
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE templates
                SET prompt_user = ?, updated_at = ?
                WHERE id = ? AND is_active = 1
                """,
                (new_prompt_user, datetime.now(), template_id)
            )
            conn.commit()

            # Retrieve updated template
            if cursor.rowcount > 0:
                cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
                row = cursor.fetchone()
                conn.close()
                return TemplateDB._row_to_template(row)
            else:
                conn.close()
                return None
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def _row_to_template(row) -> Optional[Template]:
        """Converts database row to Template entity.

        Args:
            row: Database row tuple

        Returns:
            Template entity or None if row is None
        """
        if not row:
            return None

        return Template(
            id=row[0],
            user_id=row[1],
            title=row[2],
            description=row[3],
            filename=row[4],
            file_path=row[5],
            file_size=row[6],
            sha256=row[7],
            is_active=row[8],
            created_at=datetime.fromisoformat(row[9]),
            updated_at=datetime.fromisoformat(row[10]),
            prompt_user=row[11] if len(row) > 11 else None,
            prompt_system=row[12] if len(row) > 12 else None
        )


class PlaceholderDB:
    """Placeholder database class for CRUD operations."""

    @staticmethod
    def create_placeholder(placeholder_data_or_template_id, placeholder_key=None) -> Placeholder:
        """Creates a new placeholder.

        Supports two calling conventions:
        1. create_placeholder(placeholder_data: PlaceholderCreate)
        2. create_placeholder(template_id: int, placeholder_key: str)

        Args:
            placeholder_data_or_template_id: Either PlaceholderCreate object or template_id (int)
            placeholder_key: Placeholder key string (optional, required if first arg is int)

        Returns:
            Created placeholder entity

        Raises:
            Exception: Database insertion error

        Examples:
            >>> # Method 1: PlaceholderCreate object
            >>> placeholder_data = PlaceholderCreate(
            ...     template_id=1,
            ...     placeholder_key="{{TITLE}}"
            ... )
            >>> placeholder = PlaceholderDB.create_placeholder(placeholder_data)
            
            >>> # Method 2: Direct arguments
            >>> placeholder = PlaceholderDB.create_placeholder(1, "{{TITLE}}")
        """
        # Handle both calling conventions
        if isinstance(placeholder_data_or_template_id, int):
            # Method 2: create_placeholder(template_id, placeholder_key)
            template_id = placeholder_data_or_template_id
            if placeholder_key is None:
                raise ValueError("placeholder_key is required when passing template_id")
            placeholder_data = PlaceholderCreate(
                template_id=template_id,
                placeholder_key=placeholder_key
            )
        else:
            # Method 1: create_placeholder(placeholder_data)
            placeholder_data = placeholder_data_or_template_id

        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        try:
            cursor.execute(
                """
                INSERT INTO placeholders (template_id, placeholder_key, created_at)
                VALUES (?, ?, ?)
                """,
                (placeholder_data.template_id, placeholder_data.placeholder_key, now)
            )
            conn.commit()
            placeholder_id = cursor.lastrowid

            # Retrieve created placeholder
            cursor.execute("SELECT * FROM placeholders WHERE id = ?", (placeholder_id,))
            row = cursor.fetchone()
            conn.close()

            return PlaceholderDB._row_to_placeholder(row)
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def create_placeholders_batch(template_id: int, placeholder_keys: List[str]) -> List[Placeholder]:
        """Creates multiple placeholders in batch.

        Args:
            template_id: Template ID
            placeholder_keys: List of placeholder keys (e.g., ["{{TITLE}}", "{{SUMMARY}}"])

        Returns:
            List of created placeholder entities

        Raises:
            Exception: Database insertion error

        Examples:
            >>> placeholders = PlaceholderDB.create_placeholders_batch(
            ...     1,
            ...     ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"]
            ... )
            >>> print(len(placeholders))
            3
        """
        if not placeholder_keys:
            return []

        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        try:
            # Prepare data for batch insert with sort index
            data = [(template_id, key, sort_idx, now) for sort_idx, key in enumerate(placeholder_keys)]

            cursor.executemany(
                """
                INSERT INTO placeholders (template_id, placeholder_key, sort, created_at)
                VALUES (?, ?, ?, ?)
                """,
                data
            )
            conn.commit()

            # Retrieve all created placeholders ordered by sort
            cursor.execute(
                "SELECT * FROM placeholders WHERE template_id = ? ORDER BY sort ASC",
                (template_id,)
            )
            rows = cursor.fetchall()
            conn.close()

            return [PlaceholderDB._row_to_placeholder(row) for row in rows]
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def get_placeholders_by_template(template_id: int) -> List[Placeholder]:
        """Gets all placeholders for a template.

        Args:
            template_id: Template ID

        Returns:
            List of placeholder entities ordered by sort

        Examples:
            >>> placeholders = PlaceholderDB.get_placeholders_by_template(1)
            >>> for p in placeholders:
            ...     print(p.placeholder_key)
            {{TITLE}}
            {{SUMMARY}}
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM placeholders WHERE template_id = ? ORDER BY sort ASC",
            (template_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [PlaceholderDB._row_to_placeholder(row) for row in rows]

    @staticmethod
    def delete_placeholders_by_template(template_id: int) -> bool:
        """Deletes all placeholders for a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted successfully

        Examples:
            >>> success = PlaceholderDB.delete_placeholders_by_template(1)
            >>> print(success)
            True
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM placeholders WHERE template_id = ?", (template_id,))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            conn.rollback()
            conn.close()
            raise e

    @staticmethod
    def _row_to_placeholder(row) -> Optional[Placeholder]:
        """Converts database row to Placeholder entity.

        Args:
            row: Database row tuple (id, template_id, placeholder_key, sort, created_at)

        Returns:
            Placeholder entity or None if row is None
        """
        if not row:
            return None

        return Placeholder(
            id=row[0],
            template_id=row[1],
            placeholder_key=row[2],
            sort=row[3] if len(row) > 3 and row[3] is not None else 0,
            created_at=datetime.fromisoformat(row[4]) if len(row) > 4 else datetime.now()
        )
