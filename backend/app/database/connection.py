"""
SQLite 데이터베이스 연결 및 초기화
"""
import sqlite3
import os
from pathlib import Path
from shared.constants import ProjectPath

# PATH_PROJECT_HOME 기반 데이터베이스 경로
DB_PATH = str(ProjectPath.DATABASE_FILE)


def get_db_connection():
    """데이터베이스 연결 가져오기"""
    # 데이터베이스 디렉토리 생성
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
    return conn


def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # SQLite 외래 키 제약 활성화
    cursor.execute("PRAGMA foreign_keys = ON")

    # 사용자 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            is_admin BOOLEAN DEFAULT 0,
            password_reset_required BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 보고서 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # 토큰 사용량 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            report_id INTEGER,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE SET NULL
        )
    """)

    # 토픽 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            input_prompt TEXT NOT NULL,
            generated_title TEXT,
            language TEXT NOT NULL DEFAULT 'ko',
            status TEXT NOT NULL DEFAULT 'active',
            template_id INTEGER,
            prompt_user TEXT,
            prompt_system TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # 메시지 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            seq_no INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
            UNIQUE (topic_id, seq_no)
        )
    """)

    # 아티팩트 테이블
    # v2.5+: file_path는 NULL 가능 (작업 중에는 파일이 없을 수 있음)
    # v2.5+: message_id는 NULL 가능 (백그라운드 생성 시 메시지 생성 이후에 추가됨)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            message_id INTEGER,
            kind TEXT NOT NULL,
            locale TEXT NOT NULL DEFAULT 'ko',
            version INTEGER NOT NULL DEFAULT 1,
            filename TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
        )
    """)

    # AI 사용량 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
            FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
        )
    """)

    # 템플릿 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)

    # 플레이스홀더 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS placeholders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            placeholder_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE
        )
    """)

    # Templates 테이블 마이그레이션: Dynamic Prompt 컬럼 추가 (v2.2)
    try:
        cursor.execute("""
            ALTER TABLE templates ADD COLUMN prompt_user TEXT DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    try:
        cursor.execute("""
            ALTER TABLE templates ADD COLUMN prompt_system TEXT DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    # Topics 테이블 마이그레이션: template_id 컬럼 추가 (v2.4)
    try:
        cursor.execute("""
            ALTER TABLE topics ADD COLUMN template_id INTEGER DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    # Topics 테이블 마이그레이션: prompt_user 컬럼 추가 (v2.7 Sequential Planning)
    try:
        cursor.execute("""
            ALTER TABLE topics ADD COLUMN prompt_user TEXT DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    # Topics 테이블 마이그레이션: prompt_system 컬럼 추가 (v2.7 Sequential Planning)
    try:
        cursor.execute("""
            ALTER TABLE topics ADD COLUMN prompt_system TEXT DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    # Artifacts 테이블 마이그레이션: 상태 관리 컬럼 추가 (v2.5, Option A)
    try:
        cursor.execute("""
            ALTER TABLE artifacts ADD COLUMN status TEXT DEFAULT 'completed'
        """)
    except sqlite3.OperationalError:
        pass  # 컬럼이 이미 존재하면 무시

    try:
        cursor.execute("""
            ALTER TABLE artifacts ADD COLUMN progress_percent INTEGER DEFAULT 100
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE artifacts ADD COLUMN started_at TIMESTAMP DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE artifacts ADD COLUMN completed_at TIMESTAMP DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            ALTER TABLE artifacts ADD COLUMN error_message TEXT DEFAULT NULL
        """)
    except sqlite3.OperationalError:
        pass

    # 프롬프트 고도화 결과 테이블 (v2.7+)
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_optimization_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,

                -- 입력값 (사용자 요청)
                user_prompt TEXT NOT NULL,

                -- 분석 결과 (숨겨진 의도)
                hidden_intent TEXT,
                emotional_needs TEXT,  -- JSON 문자열
                underlying_purpose TEXT,
                formality TEXT,  -- 형식: formal, professional, casual
                confidence_level TEXT,  -- 형식: low, medium, high
                decision_focus TEXT,  -- 형식: strategic, tactical, operational

                -- 최적화된 프롬프트 (Claude 정제)
                role TEXT NOT NULL,
                context TEXT NOT NULL,
                task TEXT NOT NULL,

                -- 메타데이터
                model_name TEXT NOT NULL DEFAULT 'claude-sonnet-4-5-20250929',
                latency_ms INTEGER DEFAULT 0,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
    except sqlite3.OperationalError:
        pass  # 테이블이 이미 존재하면 무시

    # prompt_optimization_result 컬럼 마이그레이션 (v2.8+)
    for column_def in (
        "emotional_needs TEXT DEFAULT NULL",
        "formality TEXT DEFAULT NULL",
        "confidence_level TEXT DEFAULT NULL",
        "decision_focus TEXT DEFAULT NULL",
    ):
        try:
            cursor.execute(f"ALTER TABLE prompt_optimization_result ADD COLUMN {column_def}")
        except sqlite3.OperationalError:
            pass  # 컬럼이 이미 존재하면 무시

    # prompt_optimization_result 테이블 마이그레이션: output_format, original_topic 컬럼 추가 (v2.8+)
    for column_def in (
        "output_format TEXT DEFAULT NULL",
        "original_topic TEXT DEFAULT NULL",
    ):
        try:
            cursor.execute(f"ALTER TABLE prompt_optimization_result ADD COLUMN {column_def}")
        except sqlite3.OperationalError:
            pass  # 컬럼이 이미 존재하면 무시

    # 인덱스 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_user_id ON token_usage(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_user_id ON topics(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_template_id ON topics(template_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_topic_id ON messages(topic_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_topic_id ON artifacts(topic_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_message_id ON artifacts(message_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_started_at ON artifacts(started_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_topic_id ON ai_usage(topic_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_message_id ON ai_usage(message_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_templates_user_id ON templates(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_placeholders_template_id ON placeholders(template_id)")
    # prompt_optimization_result 테이블 인덱스 (v2.7+)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimization_topic_date ON prompt_optimization_result(topic_id, created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimization_user_id ON prompt_optimization_result(user_id)")

    conn.commit()
    conn.close()
