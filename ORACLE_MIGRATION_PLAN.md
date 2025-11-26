# HWP Report Generator - Oracle DB 마이그레이션 계획

**문서 작성일:** 2025-11-16
**대상 버전:** v2.5+
**예상 기간:** 6-7주
**난이도:** 중상(Medium-High)

---

## 📋 Executive Summary

현재 **SQLite** 기반 백엔드를 **Oracle Database**로 마이그레이션하기 위한 종합 계획입니다.

### 핵심 내용
- **현재 상태:** SQLite 3, Raw SQL, 11개 테이블, 10개 CRUD 모듈
- **목표 상태:** Oracle Database (Enterprise/Express), 동일 비즈니스 로직
- **전략:** Raw SQL 유지 + cx_Oracle 드라이버 도입 (최소 변경 범위)
- **일정:** 6-7주 (개발 4주 + 테스트 2주 + 배포 1주)
- **리소스:** 개발자 1-2명, DB 관리자 1명, QA 1명

---

## 🎯 마이그레이션 목표

### 기능 목표
- ✅ 모든 데이터 100% 마이그레이션 (11개 테이블)
- ✅ API 호환성 유지 (엔드포인트 변경 없음)
- ✅ 성능 동등 이상 (응답시간 ±10% 이내)
- ✅ 테스트 커버리지 70%+ 유지
- ✅ 장기 운영 안정성 확보

### 비즈니스 목표
- 확장성 향상 (SQLite 동시성 제한 해결)
- 대규모 데이터 처리 능력 강화
- 엔터프라이즈 DB 지원 (보안, 백업, 감사)
- 향후 클라우드 마이그레이션 기반 마련

---

## 📊 현황 분석

### 현재 데이터베이스 구조

```
SQLite Database (11 tables)
├── Core Tables (5)
│   ├── users (사용자 계정)
│   ├── topics (대화 주제)
│   ├── messages (메시지)
│   ├── artifacts (생성 파일)
│   └── ai_usage (AI 사용량)
├── v2.2+ Tables (2)
│   ├── templates (보고서 템플릿)
│   └── placeholders (템플릿 플레이스홀더)
├── Tracking Tables (1)
│   └── transformations (파일 변환 이력)
└── Legacy Tables (3) - Deprecated
    ├── reports
    ├── token_usage
    └── (1 reserved)
```

### 기술 스택 현황

| 영역 | 현재 | 변경 예정 |
|------|------|---------|
| DB | SQLite 3 | Oracle DB (19c+) |
| 드라이버 | sqlite3 (내장) | cx_Oracle 또는 oracledb |
| ORM | None (Raw SQL) | None (유지) |
| 연결 관리 | 직접 연결 | 연결 풀 도입 검토 |
| 파라미터 바인딩 | ? 위치 기반 | :name 또는 %s |

### 파일 변경 범위

```
수정할 파일 (15개)
├── 핵심 변경 (3개)
│   ├── backend/app/database/connection.py (완전 재작성)
│   ├── backend/requirements.txt (라이브러리 추가)
│   └── backend/.env (환경 변수 변경)
├── CRUD 모듈 (10개)
│   ├── user_db.py
│   ├── topic_db.py
│   ├── message_db.py
│   ├── artifact_db.py
│   ├── ai_usage_db.py
│   ├── template_db.py
│   ├── transformation_db.py
│   ├── report_db.py
│   ├── token_usage_db.py
│   └── (예약)
└── 테스트 (2개)
    ├── conftest.py (테스트 DB 설정)
    └── test_*.py (SQL 호환성 재검증)
```

---

## 🏗️ 상세 마이그레이션 계획

### Phase 1: 준비 단계 (1-2주)

#### 1.1 Oracle 환경 구성
```
작업 항목:
- [ ] Oracle Database 설치 (Express Edition 또는 Enterprise)
  선택지:
  ✅ Oracle Express Edition 21c (무료, 제한 있음: 4GB 메모리, 1개 테넌트)
  ✅ Oracle Cloud Free Tier (무료, 1년)
  ✅ Docker: oracledb:23-free (개발 환경)

- [ ] 테이블스페이스 생성
  ```sql
  CREATE TABLESPACE hwp_reports_data
    DATAFILE '/u01/oradata/hwp_reports01.dbf' SIZE 500M;

  CREATE TEMPORARY TABLESPACE hwp_reports_temp
    TEMPFILE '/u01/oradata/hwp_reports_temp.dbf' SIZE 100M;
  ```

- [ ] 사용자/계정 생성
  ```sql
  CREATE USER hwp_app IDENTIFIED BY <password>
    DEFAULT TABLESPACE hwp_reports_data
    TEMPORARY TABLESPACE hwp_reports_temp;

  GRANT CONNECT, RESOURCE, CREATE TABLE, CREATE SEQUENCE TO hwp_app;
  ```

- [ ] 개발/스테이징용 테이블스페이스 생성 (동일)
```

**담당:** DB 관리자 (1명)
**기간:** 3-5일
**산출물:** Oracle DB 접속 정보, 스키마 준비 완료

---

#### 1.2 개발 환경 준비
```
작업 항목:
- [ ] cx_Oracle 또는 oracledb 라이브러리 평가

  비교:
  ┌─────────────┬──────────────────┬─────────────────┐
  │ 항목        │ cx_Oracle        │ oracledb        │
  ├─────────────┼──────────────────┼─────────────────┤
  │ 라이선스    │ Apache 2.0       │ Apache 2.0      │
  │ 활발성      │ 중간             │ 높음 (신규)     │
  │ Python 버전 │ 3.6+             │ 3.7+            │
  │ 설치        │ C++ 컴파일 필요  │ Pure Python     │
  │ 성능        │ 약간 더 빠름     │ 동등 수준       │
  └─────────────┴──────────────────┴─────────────────┘

  ✅ 권장: oracledb (설치 용이, 순수 Python)

- [ ] 로컬 개발 환경 구성
  ```bash
  # requirements.txt 추가
  oracledb>=2.0.0
  python-dotenv

  # 설치
  pip install oracledb

  # 테스트
  python -c "import oracledb; print(oracledb.__version__)"
  ```

- [ ] 환경 변수 설정
  ```env
  # 기존 (SQLite)
  # DATABASE_PATH=/path/to/hwp_reports.db

  # 신규 (Oracle)
  ORACLE_HOST=localhost
  ORACLE_PORT=1521
  ORACLE_SERVICE=XE  # Express Edition 기본값
  ORACLE_USER=hwp_app
  ORACLE_PASSWORD=<password>
  ```

- [ ] connection.py 프로토타입 작성
  - oracledb 기본 연결 테스트
  - 트랜잭션 관리 테스트
  - 바인딩 파라미터 형식 검증
```

**담당:** 백엔드 개발자 (1명)
**기간:** 3-5일
**산출물:** 동작하는 connection.py 프로토타입

---

#### 1.3 스키마 설계
```
작업 항목:
- [ ] SQLite → Oracle 데이터 타입 매핑표 작성

  매핑 규칙:
  ┌──────────────────────────┬─────────────────┬─────────────────┐
  │ SQLite Type              │ Oracle Type     │ 크기/제약        │
  ├──────────────────────────┼─────────────────┼─────────────────┤
  │ INTEGER PK AUTOINCREMENT │ NUMBER(*)       │ Sequence + trigger│
  │ TEXT (일반)              │ VARCHAR2(1000)  │ 최대 1000자      │
  │ TEXT (큰 데이터)         │ CLOB            │ artifact.content │
  │ BOOLEAN                  │ CHAR(1)         │ 'Y' / 'N'        │
  │ TIMESTAMP                │ TIMESTAMP       │ SYSDATE 이용     │
  │ UNIQUE                   │ UNIQUE          │ 동일             │
  │ FOREIGN KEY              │ FOREIGN KEY     │ ON DELETE CASCADE │
  └──────────────────────────┴─────────────────┴─────────────────┘

- [ ] DDL 스크립트 작성 (oracle_schema.sql)
  ```sql
  -- 1. 시퀀스 생성
  CREATE SEQUENCE seq_users START WITH 1 INCREMENT BY 1;
  CREATE SEQUENCE seq_topics START WITH 1 INCREMENT BY 1;
  -- ... (총 11개)

  -- 2. 테이블 생성
  CREATE TABLE users (
    id NUMBER PRIMARY KEY,
    email VARCHAR2(255) UNIQUE NOT NULL,
    username VARCHAR2(100) NOT NULL,
    hashed_password VARCHAR2(255) NOT NULL,
    is_active CHAR(1) DEFAULT '0' CHECK (is_active IN ('0', '1')),
    is_admin CHAR(1) DEFAULT '0' CHECK (is_admin IN ('0', '1')),
    password_reset_required CHAR(1) DEFAULT '0',
    created_at TIMESTAMP DEFAULT SYSDATE,
    updated_at TIMESTAMP DEFAULT SYSDATE
  );

  -- 3. 트리거 생성 (AUTOINCREMENT 대체)
  CREATE OR REPLACE TRIGGER trg_users_before_insert
  BEFORE INSERT ON users
  FOR EACH ROW
  BEGIN
    SELECT seq_users.NEXTVAL INTO :NEW.id FROM DUAL;
  END;
  /

  -- 4. 인덱스 생성
  CREATE INDEX idx_users_email ON users(email);
  -- ... (다른 인덱스)

  -- 5. 외래 키 제약
  ALTER TABLE topics
  ADD CONSTRAINT fk_topics_user_id
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
  -- ... (다른 FK)
  ```

- [ ] 각 테이블별 상세 정의서 작성
  - 컬럼 설명 + 제약조건
  - 예상 데이터 크기
  - 인덱스 전략
```

**담당:** DB 관리자 + 백엔드 리드
**기간:** 5-7일
**산출물:** oracle_schema.sql (완성), 타입 매핑표, 테이블 정의서

---

### Phase 2: 스키마 생성 (1주)

#### 2.1 Oracle에 스키마 생성
```
작업 항목:
- [ ] oracle_schema.sql 실행
  ```bash
  # SQLPlus 또는 SQL Developer에서
  @oracle_schema.sql
  ```

- [ ] 스키마 검증
  ```sql
  -- 테이블 존재 확인
  SELECT table_name FROM user_tables WHERE table_name IN (
    'USERS', 'TOPICS', 'MESSAGES', 'ARTIFACTS', 'AI_USAGE',
    'TEMPLATES', 'PLACEHOLDERS', 'TRANSFORMATIONS'
  );

  -- 시퀀스 확인
  SELECT sequence_name FROM user_sequences;

  -- 인덱스 확인
  SELECT index_name FROM user_indexes;
  ```

- [ ] 제약조건 검증
  ```sql
  SELECT constraint_name, constraint_type FROM user_constraints;
  ```

- [ ] 샘플 데이터 INSERT 테스트
  ```sql
  -- users 테이블 샘플 입력
  INSERT INTO users (id, email, username, hashed_password)
  VALUES (seq_users.NEXTVAL, 'test@example.com', 'testuser', 'hash123');
  COMMIT;

  -- 시퀀스 작동 확인
  SELECT seq_users.CURRVAL FROM DUAL;
  ```
```

**담당:** DB 관리자
**기간:** 2-3일
**산출물:** 검증된 Oracle 스키마

---

#### 2.2 개발 환경 스키마 자동 초기화 코드 작성
```python
# backend/database/oracle_init.py (신규)

import oracledb
from pathlib import Path

def init_oracle_schema():
    """
    Oracle 스키마 자동 초기화
    (프로덕션 배포 시 DB 관리자가 수동 실행)
    """
    conn = oracledb.connect(
        user="hwp_app",
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=f"{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}/{os.getenv('ORACLE_SERVICE')}"
    )

    cursor = conn.cursor()

    # oracle_schema.sql 읽어서 실행
    schema_file = Path(__file__).parent / "oracle_schema.sql"
    sql_script = schema_file.read_text()

    # SQL 문을 ; 기준으로 분리하여 실행
    statements = sql_script.split(";")
    for statement in statements:
        if statement.strip():
            cursor.execute(statement)

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    init_oracle_schema()
    print("✅ Oracle schema initialized successfully")
```

**담당:** 백엔드 개발자
**기간:** 1-2일
**산출물:** oracle_init.py 스크립트

---

### Phase 3: 데이터 마이그레이션 (1-2주)

#### 3.1 마이그레이션 도구 개발
```python
# backend/scripts/migrate_sqlite_to_oracle.py (신규)

"""
SQLite → Oracle 데이터 마이그레이션 도구

사용법:
  python migrate_sqlite_to_oracle.py --source /path/to/hwp_reports.db --target oracle

기능:
  1. SQLite에서 각 테이블 읽기
  2. 데이터 타입 변환 (BOOLEAN → CHAR, timestamp 등)
  3. Oracle에 INSERT
  4. 검증 (row count, 데이터 무결성)
  5. 롤백 가능
"""

import sqlite3
import oracledb
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any

class SQLiteToOracleMigrator:
    def __init__(self, sqlite_path: str, oracle_config: Dict[str, str]):
        self.sqlite_path = sqlite_path
        self.oracle_config = oracle_config
        self.logger = logging.getLogger(__name__)

        # 마이그레이션 통계
        self.stats = {
            "tables_processed": 0,
            "rows_migrated": 0,
            "errors": []
        }

    def connect_sqlite(self) -> sqlite3.Connection:
        """SQLite 연결"""
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def connect_oracle(self) -> oracledb.Connection:
        """Oracle 연결"""
        return oracledb.connect(
            user=self.oracle_config['user'],
            password=self.oracle_config['password'],
            dsn=f"{self.oracle_config['host']}:{self.oracle_config['port']}/{self.oracle_config['service']}"
        )

    def convert_value(self, value: Any, column_type: str) -> Any:
        """SQLite 값을 Oracle 형식으로 변환"""
        if value is None:
            return None

        # BOOLEAN (SQLite: 0/1) → Oracle: 'Y'/'N'
        if column_type == "CHAR(1)" and isinstance(value, int):
            return 'Y' if value else 'N'

        # TIMESTAMP 문자열 처리
        if column_type == "TIMESTAMP" and isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except:
                return None

        return value

    def migrate_table(self, table_name: str, sqlite_conn: sqlite3.Connection,
                     oracle_conn: oracledb.Connection):
        """특정 테이블 마이그레이션"""
        sqlite_cursor = sqlite_conn.cursor()
        oracle_cursor = oracle_conn.cursor()

        # SQLite에서 데이터 읽기
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

        if not rows:
            self.logger.info(f"{table_name}: no data to migrate")
            return

        # 컬럼명 가져오기
        columns = [desc[0] for desc in sqlite_cursor.description]

        # 데이터 변환 및 INSERT
        for row in rows:
            values = []
            for col, val in zip(columns, row):
                # 타입 변환 로직 (필요에 따라 확장)
                converted_val = self.convert_value(val, "VARCHAR2")
                values.append(converted_val)

            # Oracle INSERT (시퀀스 자동 사용)
            placeholders = ", ".join([f":{i+1}" for i in range(len(values))])
            cols_str = ", ".join(columns)

            # ID 컬럼 제외 (시퀀스로 자동 생성)
            if 'id' in columns:
                cols = [c for c in columns if c != 'id']
                vals = values[1:]
                placeholders = ", ".join([f":{i+1}" for i in range(len(vals))])
                sql = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
            else:
                sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

            try:
                oracle_cursor.execute(sql, values)
            except Exception as e:
                self.logger.error(f"Error inserting into {table_name}: {str(e)}")
                self.stats["errors"].append({
                    "table": table_name,
                    "row": row,
                    "error": str(e)
                })

        oracle_conn.commit()
        self.stats["rows_migrated"] += len(rows)
        self.logger.info(f"{table_name}: {len(rows)} rows migrated")

    def validate_migration(self, sqlite_conn: sqlite3.Connection,
                          oracle_conn: oracledb.Connection):
        """마이그레이션 검증 (row count 비교)"""
        tables = [
            'users', 'topics', 'messages', 'artifacts', 'ai_usage',
            'templates', 'placeholders', 'transformations', 'reports', 'token_usage'
        ]

        validation_result = {}

        for table in tables:
            # SQLite row count
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = sqlite_cursor.fetchone()[0]

            # Oracle row count
            oracle_cursor = oracle_conn.cursor()
            oracle_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            oracle_count = oracle_cursor.fetchone()[0]

            match = sqlite_count == oracle_count
            validation_result[table] = {
                "sqlite": sqlite_count,
                "oracle": oracle_count,
                "match": match
            }

            status = "✅" if match else "❌"
            print(f"{status} {table}: SQLite={sqlite_count}, Oracle={oracle_count}")

        return validation_result

    def run(self, skip_tables: List[str] = None):
        """전체 마이그레이션 실행"""
        tables = [
            'users', 'reports', 'token_usage', 'topics', 'messages',
            'artifacts', 'ai_usage', 'templates', 'placeholders', 'transformations'
        ]

        if skip_tables:
            tables = [t for t in tables if t not in skip_tables]

        try:
            sqlite_conn = self.connect_sqlite()
            oracle_conn = self.connect_oracle()

            print(f"\n🔄 Starting migration from SQLite to Oracle...")
            print(f"📊 Tables to migrate: {', '.join(tables)}\n")

            for table in tables:
                try:
                    self.migrate_table(table, sqlite_conn, oracle_conn)
                    self.stats["tables_processed"] += 1
                except Exception as e:
                    self.logger.error(f"Failed to migrate {table}: {str(e)}")
                    self.stats["errors"].append({
                        "table": table,
                        "error": str(e)
                    })

            # 검증
            print(f"\n🔍 Validating migration...")
            validation = self.validate_migration(sqlite_conn, oracle_conn)

            # 결과 출력
            print(f"\n📈 Migration Summary:")
            print(f"  Tables processed: {self.stats['tables_processed']}")
            print(f"  Rows migrated: {self.stats['rows_migrated']}")
            print(f"  Errors: {len(self.stats['errors'])}")

            if self.stats["errors"]:
                print(f"\n⚠️ Errors encountered:")
                for err in self.stats["errors"]:
                    print(f"  - {err}")

            sqlite_conn.close()
            oracle_conn.close()

            return validation

        except Exception as e:
            self.logger.error(f"Migration failed: {str(e)}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite to Oracle migration tool")
    parser.add_argument("--source", required=True, help="SQLite database path")
    parser.add_argument("--host", default="localhost", help="Oracle host")
    parser.add_argument("--port", default="1521", help="Oracle port")
    parser.add_argument("--service", default="XE", help="Oracle service/SID")
    parser.add_argument("--user", default="hwp_app", help="Oracle username")
    parser.add_argument("--password", required=True, help="Oracle password")
    parser.add_argument("--skip-tables", help="Comma-separated table names to skip")

    args = parser.parse_args()

    oracle_config = {
        'host': args.host,
        'port': args.port,
        'service': args.service,
        'user': args.user,
        'password': args.password
    }

    migrator = SQLiteToOracleMigrator(args.source, oracle_config)
    migrator.run(skip_tables=args.skip_tables.split(',') if args.skip_tables else None)
```

**담당:** 백엔드 개발자
**기간:** 3-5일
**산출물:** migrate_sqlite_to_oracle.py (검증 완료)

---

#### 3.2 마이그레이션 실행 및 검증
```bash
# 1. 백업
cp data/hwp_reports.db data/hwp_reports.db.backup

# 2. 마이그레이션 실행 (드라이 런)
python scripts/migrate_sqlite_to_oracle.py \
  --source data/hwp_reports.db \
  --host oracle.example.com \
  --port 1521 \
  --service hwp_prod \
  --user hwp_app \
  --password <password> \
  --skip-tables reports,token_usage  # deprecated 테이블 스킵

# 3. 검증 결과
# ✅ users: SQLite=5, Oracle=5
# ✅ topics: SQLite=12, Oracle=12
# ✅ messages: SQLite=48, Oracle=48
# ... (모든 테이블 일치)

# 4. Oracle에서 수동 검증
sqlplus hwp_app/<password>@hwp_prod
SQL> SELECT COUNT(*) FROM users;
SQL> SELECT COUNT(*) FROM topics;
SQL> SELECT * FROM users LIMIT 1;
```

**담당:** DB 관리자 + 백엔드 개발자
**기간:** 2-3일
**산출물:** Oracle에 마이그레이션된 완전한 데이터

---

### Phase 4: 백엔드 코드 변경 (2주)

#### 4.1 connection.py 전면 재작성
```python
# backend/app/database/connection.py (전체 변경)

"""
Oracle Database 연결 및 초기화
"""
import oracledb
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Oracle 연결 풀 설정
_connection_pool: Optional[oracledb.ConnectionPool] = None

def init_connection_pool():
    """
    Oracle 연결 풀 초기화
    (애플리케이션 시작 시 호출)
    """
    global _connection_pool

    if _connection_pool is not None:
        return

    try:
        _connection_pool = oracledb.create_pool(
            user=os.getenv("ORACLE_USER"),
            password=os.getenv("ORACLE_PASSWORD"),
            dsn=f"{os.getenv('ORACLE_HOST')}:{os.getenv('ORACLE_PORT')}/{os.getenv('ORACLE_SERVICE')}",
            min=2,
            max=10,
            increment=1,
            threaded=True,
            encoding="UTF-8"
        )
        logger.info("Oracle connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Oracle connection pool: {str(e)}")
        raise

def get_db_connection() -> oracledb.Connection:
    """
    데이터베이스 연결 획득
    (연결 풀에서 자동 관리)
    """
    global _connection_pool

    if _connection_pool is None:
        init_connection_pool()

    try:
        conn = _connection_pool.acquire()
        conn.autocommit = False  # 명시적 COMMIT 필요
        return conn
    except Exception as e:
        logger.error(f"Failed to acquire database connection: {str(e)}")
        raise

def close_connection(conn: oracledb.Connection):
    """연결 반환"""
    try:
        if conn:
            conn.close()
    except Exception as e:
        logger.error(f"Error closing connection: {str(e)}")

def init_db():
    """
    데이터베이스 초기화
    (프로덕션에서는 DBA가 수동 실행)
    """
    logger.info("Oracle database initialization skipped - manual schema creation required")
    # Oracle 스키마는 별도의 oracle_schema.sql로 관리
    # init_oracle_schema() 참고

# FastAPI 시작/종료 시 호출할 함수
async def startup():
    """애플리케이션 시작"""
    try:
        init_connection_pool()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database startup failed: {str(e)}")
        raise

async def shutdown():
    """애플리케이션 종료"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.close()
        logger.info("Connection pool closed")
```

**main.py에 추가:**
```python
# backend/app/main.py

from app.database.connection import startup, shutdown

app = FastAPI()

# 앱 시작/종료 훅
@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()
```

**담당:** 백엔드 개발자
**기간:** 2-3일
**산출물:** 검증된 connection.py

---

#### 4.2 CRUD 모듈 SQL 변환 (10개 파일)

각 CRUD 파일에서 다음과 같이 변경:

```python
# 예시: backend/app/database/user_db.py

# ❌ 변경 전 (SQLite)
cursor.execute(
    """
    INSERT INTO users (email, username, hashed_password)
    VALUES (?, ?, ?)
    """,
    (user.email, user.username, hashed_password)
)
user_id = cursor.lastrowid

# ✅ 변경 후 (Oracle)
cursor.execute(
    """
    INSERT INTO users (id, email, username, hashed_password)
    VALUES (seq_users.NEXTVAL, :email, :username, :hashed_password)
    RETURNING id INTO :user_id
    """,
    email=user.email,
    username=user.username,
    hashed_password=hashed_password,
    user_id=None  # OUT 바인딩
)

# RETURNING 절에서 ID 획득
user_id = cursor.var(oracledb.Number).getvalue()
```

**변경 대상 파일 목록:**

| 파일 | SQL 문 수 | 변경 예상 난이도 |
|------|---------|---------------|
| user_db.py | 15 | ⭐⭐ (중간) |
| topic_db.py | 20 | ⭐⭐⭐ (높음) |
| message_db.py | 12 | ⭐⭐ (중간) |
| artifact_db.py | 15 | ⭐⭐⭐ (높음) |
| ai_usage_db.py | 8 | ⭐ (낮음) |
| template_db.py | 12 | ⭐⭐ (중간) |
| transformation_db.py | 8 | ⭐ (낮음) |
| report_db.py (deprecated) | 10 | ⭐ (낮음) |
| token_usage_db.py (deprecated) | 8 | ⭐ (낮음) |
| | **총 108** | |

**주요 변경 사항 요약:**

```
변경 항목                  개수  파급 범위
────────────────────────────────────
? → :param 바인딩           ~100  모든 CRUD
cursor.lastrowid → RETURNING  ~10  INSERT 메서드
CURRENT_TIMESTAMP → SYSDATE   ~20  timestamp 컬럼
BOOLEAN (0/1) → CHAR('Y'/'N')  ~5  boolean 컬럼
LIMIT/OFFSET → FETCH          ~15  페이징 쿼리
```

**예상 작업 시간:**
- user_db.py: 4시간
- topic_db.py: 6시간
- message_db.py: 4시간
- artifact_db.py: 6시간
- 나머지 6개: 8시간
- **소계: 28시간 (1주)**

**담당:** 백엔드 개발자 2명
**기간:** 1주
**산출물:** 모든 CRUD 파일 Oracle 호환 완료

---

#### 4.3 테스트 코드 수정
```python
# backend/tests/conftest.py

# ❌ 변경 전
@pytest.fixture
def test_db():
    """임시 SQLite 테스트 DB"""
    db_path = ":memory:"
    init_db_sqlite(db_path)
    yield db_path

# ✅ 변경 후
@pytest.fixture
def test_db():
    """테스트 Oracle DB (또는 메모리 SQLite 유지)"""
    # 옵션 1: 메모리 SQLite 유지 (빠른 테스트)
    db_path = ":memory:"
    init_db_sqlite(db_path)
    yield db_path

    # 옵션 2: Oracle 테스트 스키마 사용
    # oracle_test_schema = create_oracle_test_schema()
    # yield oracle_test_schema
    # drop_oracle_test_schema(oracle_test_schema)
```

**권장:** 테스트는 메모리 SQLite 유지 (빠른 반복)
실제 Oracle은 스테이징 환경에서 테스트

**담당:** QA + 백엔드 개발자
**기간:** 2-3일
**산출물:** 테스트 커버리지 70%+ 유지

---

### Phase 5: 통합 테스트 (1주)

#### 5.1 단위 테스트 (Unit Tests)
```bash
cd backend

# 모든 테스트 실행
pytest tests/ -v

# CRUD 모듈별 테스트
pytest tests/test_database_user_db.py -v
pytest tests/test_database_topic_db.py -v
# ... (모든 DB 모듈)

# 결과: 모든 테스트 통과 ✅
```

**담당:** QA
**기간:** 2-3일
**목표:** 100% 통과율

---

#### 5.2 API 통합 테스트 (Integration Tests)
```bash
# 실제 Oracle 환경에서 API 테스트

# 1. Auth API
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPassword123!"
  }'

# 2. Topics API
curl -X GET http://localhost:8000/api/topics \
  -H "Authorization: Bearer <token>"

# 3. Messages API
curl -X POST http://localhost:8000/api/topics/1/messages \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Test message"
  }'

# 4. Artifacts API (다운로드)
curl -X GET http://localhost:8000/api/artifacts/1/download \
  -H "Authorization: Bearer <token>" \
  -o artifact.md

# 예상 응답 시간: < 500ms (SQLite와 동등)
```

**담당:** QA + 백엔드 개발자
**기간:** 2-3일
**목표:** 모든 주요 엔드포인트 통과

---

#### 5.3 성능 테스트 (Performance Testing)
```python
# backend/tests/test_performance.py

import time
from locust import HttpUser, task, between

class APILoadTest(HttpUser):
    wait_time = between(1, 3)

    @task
    def get_topics(self):
        """토픽 목록 조회 성능 테스트"""
        start = time.time()
        response = self.client.get(
            "/api/topics?limit=20&offset=0",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 500  # 500ms 이내

        print(f"GET /api/topics: {duration:.2f}ms")

# 실행: locust -f test_performance.py --host=http://localhost:8000
```

**목표:**
- 평균 응답 시간: ≤ 500ms
- P99 응답 시간: ≤ 2s
- 동시 사용자 100명 기준

**담당:** QA 성능 엔지니어
**기간:** 1-2일

---

### Phase 6: 배포 준비 (1주)

#### 6.1 배포 전 체크리스트
```
배포 전 검사 목록:

DATABASE
  ✅ Oracle 스키마 확인
  ✅ 시퀀스 작동 확인
  ✅ 모든 테이블 데이터 마이그레이션 완료
  ✅ 외래 키 제약 조건 검증
  ✅ 인덱스 생성 확인

BACKEND CODE
  ✅ connection.py 최종 테스트
  ✅ 모든 CRUD 모듈 Oracle 호환 완료
  ✅ 테스트 커버리지 70%+ 달성
  ✅ 코드 리뷰 완료

DOCUMENTATION
  ✅ Oracle 연결 정보 문서화
  ✅ 마이그레이션 절차 가이드 작성
  ✅ 롤백 절차 문서화
  ✅ 팀 교육 자료 준비

MONITORING & LOGGING
  ✅ 애플리케이션 로깅 설정
  ✅ Oracle 성능 모니터링 도구 설정
  ✅ 에러 알림 설정
  ✅ 데이터 검증 스크립트 준비

BACKUP & RECOVERY
  ✅ SQLite 백업 (최종)
  ✅ Oracle 백업 정책 수립
  ✅ 복구 테스트 완료
```

**담당:** 배포 리드
**기간:** 2-3일

---

#### 6.2 롤백 계획
```
롤백 절차 (필요시):

1. SQLite 백업에서 복원
   - data/hwp_reports.db.backup → data/hwp_reports.db
   - git checkout backend/app/database/connection.py (SQLite 버전)

2. 환경 변수 변경
   - .env에서 Oracle 설정 제거
   - DATABASE_PATH 복구

3. 의존성 변경
   - requirements.txt에서 oracledb 제거
   - pip install -r requirements.txt

4. 애플리케이션 재시작
   - uvicorn app.main:app --reload

5. 검증
   - API 정상 작동 확인
   - 기본 기능 테스트

예상 소요 시간: 15-20분
```

---

### Phase 7: 배포 (1주)

#### 7.1 Blue-Green 배포 전략
```
시간대         Blue (현재)          Green (신규)        상태
─────────────────────────────────────────────────────
Day 1 ~ Day 6  SQLite 운영         Oracle 준비        병렬 준비
Day 7 00:00    SQLite 운영         Oracle 스키마 생성 스키마 준비
Day 7 01:00    SQLite 운영         데이터 마이그레이션  데이터 이관
Day 7 02:00    SQLite 운영         API 코드 배포      검증 시작
Day 7 03:00    SQLite 운영         헬스 체크 통과     준비 완료
Day 7 03:30    트래픽 전환 시작
Day 7 04:00    트래픽 10% → Green
Day 7 04:30    모니터링 + 문제 없음
Day 7 05:00    트래픽 50% → Green
Day 7 06:00    트래픽 100% → Green
Day 7 07:00    Blue 제거 (최종)

롤백 시간대:
- T+1시간 이내: 즉시 Blue로 복구 (30초)
- T+6시간 이후: 신중한 롤백 검토 필요
```

**담당:** DevOps 엔지니어 + 백엔드 리드
**모니터링:**
- CPU 사용률
- 메모리 사용률
- 응답 시간
- 에러율
- DB 연결 풀 상태

---

#### 7.2 배포 후 모니터링 (72시간)
```
배포 후 72시간 모니터링 항목:

실시간 모니터링 (0-24시간)
  - 각 API 엔드포인트 응답 시간
  - 데이터베이스 연결 풀 상태
  - 에러 로그 분석
  - 사용자 신고 사항

일일 검증 (Day 1-3)
  - 일일 활성 사용자 기준 성능
  - 데이터 일관성 검사
  - 백업 상태 확인
  - 로그 분석 및 이상 탐지

최종 검증 (Day 4)
  - 성능 기준선 대비 비교 (±10% 이내)
  - SQLite 백업 보관 종료 결정
  - 팀 회고 및 개선점 정리
```

---

## 📈 상세 마이그레이션 로드맵

```
주차    Phase          세부 항목                    담당 리소스    상태
────────────────────────────────────────────────────────────────
Week 1  준비           Oracle 환경 + 스키마 설계    DB Admin       📋 계획 수립
        (3-5일)       개발 환경 구성              Backend 1명

Week 2  스키마         DDL 작성 + Oracle 적용     DB Admin       📋 준비 중
        (5-7일)       검증 및 샘플 데이터 INSERT  Backend 1명

Week 3  마이그레이션   마이그레이션 도구 개발      Backend 1명    🔄 진행 중
        (7-10일)      SQLite → Oracle 데이터 이관 QA 1명
                      검증 및 보고서

Week 4  백엔드 코드    connection.py 재작성       Backend 2명    🔄 진행 중
        (10-14일)     CRUD 모듈 변환 (110 SQL)
                      테스트 코드 수정

Week 5  통합 테스트    Unit / Integration / Perf   QA 1명        📋 예정
        (14-21일)     API 엔드포인트 검증        Backend 1명
                      성능 기준 달성 확인

Week 6  배포 준비      체크리스트 + 롤백 계획    DevOps 1명     📋 예정
        (21-28일)     팀 교육 + 문서화           Backend 1명
                      모니터링 도구 설정

Week 7  본 배포 및     Blue-Green 배포           전원           📋 예정
        모니터링      트래픽 전환 + 모니터링
        (72시간)

총 기간: 6-7주 (28-35일)
```

---

## 🔑 핵심 성공 요소

### 1. 데이터 무결성
- ✅ 마이그레이션 전후 row count 일치
- ✅ 샘플 데이터 checksum 검증
- ✅ 외래 키 제약 조건 검증
- ✅ 데이터 타입 변환 정확성

### 2. 성능 검증
- ✅ 주요 쿼리 실행 계획 분석
- ✅ 응답 시간 기준선 설정 (±10%)
- ✅ 연결 풀 크기 최적화
- ✅ 인덱스 전략 수립

### 3. 운영 연속성
- ✅ 다운타임 최소화 (< 1시간)
- ✅ 빠른 롤백 가능성 (< 30분)
- ✅ 사용자 영향 최소화
- ✅ 투명한 커뮤니케이션

### 4. 팀 역량
- ✅ Oracle 기본 지식 교육
- ✅ oracledb 라이브러리 이해
- ✅ SQL 호환성 인식
- ✅ 운영 절차 숙지

---

## 📝 상세 체크리스트

### Pre-Migration (Week 1-2)
```
준비 단계
- [ ] Oracle Database 설치
- [ ] 테이블스페이스 생성
- [ ] 사용자/권한 설정
- [ ] oracledb 라이브러리 설치 및 테스트
- [ ] connection.py 프로토타입 작성
- [ ] oracle_schema.sql 작성 (11개 테이블 + 시퀀스 + 트리거)
- [ ] 타입 매핑표 작성
- [ ] 마이그레이션 도구 개발 (migrate_sqlite_to_oracle.py)
```

### Migration (Week 3)
```
데이터 이관
- [ ] SQLite 최종 백업
- [ ] Oracle 스키마 생성 실행
- [ ] 마이그레이션 도구 드라이 런
- [ ] 데이터 검증 (row count, checksum)
- [ ] 외래 키 검증
- [ ] 샘플 데이터 수동 검증
```

### Code Change (Week 4)
```
백엔드 코드 수정
- [ ] connection.py 최종 작성
- [ ] user_db.py SQL 변환
- [ ] topic_db.py SQL 변환
- [ ] message_db.py SQL 변환
- [ ] artifact_db.py SQL 변환
- [ ] ai_usage_db.py SQL 변환
- [ ] template_db.py SQL 변환
- [ ] transformation_db.py SQL 변환
- [ ] report_db.py SQL 변환 (deprecated)
- [ ] token_usage_db.py SQL 변환 (deprecated)
- [ ] conftest.py 테스트 환경 수정
- [ ] requirements.txt 라이브러리 업데이트
- [ ] .env 샘플 업데이트
```

### Testing (Week 5)
```
통합 테스트
- [ ] Unit 테스트 모두 통과 (100%)
- [ ] Auth API 테스트
- [ ] Topics API 테스트
- [ ] Messages API 테스트
- [ ] Artifacts API 테스트
- [ ] Admin API 테스트
- [ ] 응답 시간 측정 (±10% 기준)
- [ ] 동시 사용자 100명 부하 테스트
- [ ] 데이터 일관성 재검증
```

### Pre-Deployment (Week 6)
```
배포 준비
- [ ] 배포 전 체크리스트 검증
- [ ] 롤백 절차 문서화
- [ ] 배포 스크립트 작성
- [ ] 모니터링 도구 설정
- [ ] 팀 교육 실시
- [ ] 야간 배포 스케줄 확정
- [ ] 긴급 대응 연락처 확보
```

### Deployment (Week 7)
```
본 배포
- [ ] 배포 전 최종 확인
- [ ] Blue 환경 확인 (SQLite 정상)
- [ ] Green 환경 준비 (Oracle 스키마)
- [ ] 마이그레이션 실행
- [ ] API 헬스 체크
- [ ] 트래픽 10% 전환 + 모니터링
- [ ] 트래픽 50% 전환 + 모니터링
- [ ] 트래픽 100% 전환
- [ ] 72시간 모니터링
- [ ] 최종 완료 보고
```

---

## 💰 예상 비용 및 리소스

### 인프라 비용
| 항목 | 단가 | 기간 | 소계 |
|------|------|------|------|
| Oracle Enterprise | $40K/년 | 12개월 | $40,000 |
| 또는 Express Edition | 무료 | 12개월 | $0 |
| 또는 Oracle Cloud Free | 무료 | 12개월 | $0 |

### 개발 인력
| 역할 | 인원 | 주당 시간 | 기간 | 소계 |
|------|------|---------|------|------|
| 백엔드 개발 | 2명 | 40h | 4주 | 320h |
| DB 관리자 | 1명 | 20h | 2주 | 40h |
| QA 엔지니어 | 1명 | 30h | 2주 | 60h |
| DevOps | 1명 | 10h | 1주 | 10h |
| **합계** | | | | **430h** |

### 총 비용 (내부 인력 기준, 시급 $100)
```
인력 비용: 430h × $100/h = $43,000
인프라 비용: $0 - $40,000 (선택)
────────────────────────────────
총 비용: $43,000 - $83,000 (1회)
```

---

## ⚠️ 위험 요소 및 대응책

| 위험 | 영향도 | 확률 | 대응책 |
|------|--------|------|--------|
| **데이터 손실** | 🔴 극심 | 낮음 | - 마이그레이션 3회 검증<br>- SQLite 원본 보관<br>- row count 일치 확인 |
| **성능 저하** | 🟡 중간 | 중간 | - 인덱스 전략 수립<br>- 쿼리 최적화<br>- 연결 풀 튜닝 |
| **호환성 문제** | 🟡 중간 | 중간 | - 철저한 SQL 변환<br>- 로컬 테스트 후 배포<br>- 롤백 계획 |
| **배포 중 장애** | 🔴 극심 | 낮음 | - Blue-Green 배포<br>- 빠른 롤백 (< 30분)<br>- 모니터링 24/7 |
| **팀 숙련도 부족** | 🟡 중간 | 중간 | - 사전 교육 프로그램<br>- 상세 문서 작성<br>- 외부 컨설턴트 검토 |

---

## 🎯 성공 기준

### 기능 기준
- ✅ 모든 API 엔드포인트 정상 작동
- ✅ 데이터 100% 정확성
- ✅ 외래 키 무결성 보장
- ✅ 비즈니스 로직 변화 없음

### 성능 기준
- ✅ 평균 응답 시간: ≤ 500ms (기존 ±10%)
- ✅ P99 응답 시간: ≤ 2s
- ✅ 동시 사용자 100명 지원
- ✅ 데이터베이스 연결 안정성

### 운영 기준
- ✅ 다운타임 < 1시간
- ✅ 배포 후 72시간 무장애
- ✅ 에러율 < 0.1%
- ✅ 데이터 백업 자동화

---

## 📚 참고 문서

### Oracle 관련
- [Oracle Database Documentation](https://docs.oracle.com/en/database/)
- [oracledb Python Documentation](https://python-oracledb.readthedocs.io/)
- [Oracle SQL Reference](https://docs.oracle.com/en/database/oracle/oracle-database/21/sqlrf/)

### 마이그레이션 가이드
- SQLite → Oracle 타입 매핑
- 시퀀스 및 트리거 설정
- 성능 최적화 가이드
- 트러블슈팅 가이드

### 프로젝트 문서
- [BACKEND_ONBOARDING.md](./BACKEND_ONBOARDING.md) - 현재 SQLite 구조
- [CLAUDE.md](./CLAUDE.md) - 개발 가이드라인

---

## 🚀 다음 단계

### 즉시 실행 (Week 1)
1. ✅ 이 계획 리뷰 및 승인
2. ✅ 리소스 할당 (DB Admin, 개발자 2명, QA)
3. ✅ Oracle DB 환경 설정 시작
4. ✅ 스키마 설계 시작

### 1개월 내 (Week 2-4)
- 마이그레이션 도구 개발 및 테스트
- 백엔드 코드 변환
- 통합 테스트 준비

### 6주차 (Week 6)
- 배포 준비 완료
- 팀 교육
- 모니터링 설정

### 7주차 (Week 7)
- **본 배포 실행**

---

**문서 버전:** 1.0
**작성자:** Backend Architecture Team
**상태:** 📋 검토 대기
**마지막 수정:** 2025-11-16
