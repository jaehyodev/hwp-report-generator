"""
사용자 데이터베이스 작업
"""
from typing import Optional, List
from datetime import datetime
from .connection import get_db_connection
from app.models.user import User, UserCreate, UserUpdate


class UserDB:
    """사용자 데이터베이스 클래스"""

    @staticmethod
    def create_user(user: UserCreate, hashed_password: str) -> User:
        """사용자 생성"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users (email, username, hashed_password)
            VALUES (?, ?, ?)
            """,
            (user.email, user.username, hashed_password)
        )

        conn.commit()
        user_id = cursor.lastrowid

        # 생성된 사용자 조회
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        return UserDB._row_to_user(row)

    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """ID로 사용자 조회"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        return UserDB._row_to_user(row) if row else None

    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()

        return UserDB._row_to_user(row) if row else None

    @staticmethod
    def get_all_users() -> List[User]:
        """모든 사용자 조회"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()

        return [UserDB._row_to_user(row) for row in rows]

    @staticmethod
    def update_user(user_id: int, update) -> Optional[User]:
        """사용자 정보 수정 (딕셔너리 또는 UserUpdate 객체 지원)"""
        from app.models.user import UserUpdate
        
        # 딕셔너리를 UserUpdate 모델로 변환
        if isinstance(update, dict):
            update = UserUpdate(**update)
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # 동적 쿼리 생성
        update_fields = []
        values = []

        if update.username is not None:
            update_fields.append("username = ?")
            values.append(update.username)

        if update.is_active is not None:
            update_fields.append("is_active = ?")
            values.append(int(update.is_active))

        if update.is_admin is not None:
            update_fields.append("is_admin = ?")
            values.append(int(update.is_admin))

        if update.password_reset_required is not None:
            update_fields.append("password_reset_required = ?")
            values.append(int(update.password_reset_required))

        if not update_fields:
            return UserDB.get_user_by_id(user_id)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)

        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        conn.close()

        return UserDB.get_user_by_id(user_id)

    @staticmethod
    def update_password(user_id: int, hashed_password: str) -> bool:
        """비밀번호 업데이트"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET hashed_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (hashed_password, user_id)
        )

        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    @staticmethod
    def update_user_password(user_id: int, hashed_password: str) -> bool:
        """사용자 비밀번호 업데이트 (v2.11+ 관리자 비밀번호 동기화용)

        Args:
            user_id: 사용자 ID
            hashed_password: 해시된 비밀번호

        Returns:
            bool: 성공 여부
        """
        return UserDB.update_password(user_id, hashed_password)

    @staticmethod
    def delete_user(user_id: int) -> bool:
        """사용자 삭제"""
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()

        return affected > 0

    @staticmethod
    def _row_to_user(row) -> User:
        """데이터베이스 행을 User 객체로 변환"""
        return User(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            hashed_password=row["hashed_password"],
            is_active=bool(row["is_active"]),
            is_admin=bool(row["is_admin"]),
            password_reset_required=bool(row["password_reset_required"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )
