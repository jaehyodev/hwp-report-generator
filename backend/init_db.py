#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 초기화 스크립트
"""
import os
import sys
from dotenv import load_dotenv, find_dotenv

# 프로젝트 루트의 .env 파일 자동 탐색 및 로드
load_dotenv(find_dotenv())

# PATH_PROJECT_HOME 환경 변수 확인 및 sys.path 설정
path_project_home = os.getenv("PATH_PROJECT_HOME")
if not path_project_home:
    print("ERROR: PATH_PROJECT_HOME 환경 변수가 설정되지 않았습니다.")
    print(".env 파일에 PATH_PROJECT_HOME을 설정해주세요.")
    sys.exit(1)

# 프로젝트 루트를 sys.path에 추가
if path_project_home not in sys.path:
    sys.path.insert(0, path_project_home)

from app.database import init_db
from app.database.user_db import UserDB
from app.models.user import UserCreate, UserUpdate
from app.utils.auth import hash_password
from shared.constants import ProjectPath

def main():
    print("데이터베이스를 초기화합니다...")

    # 필요한 디렉토리 생성 (PATH_PROJECT_HOME 기반)
    os.makedirs(ProjectPath.DATABASE_DIR, exist_ok=True)

    # === 기존 테이블 삭제 (완전한 초기화) ===
    from app.database.connection import get_db_connection
    import time

    # max_retries = 3
    # for attempt in range(max_retries):
    #     try:
    #         conn = get_db_connection()
    #         cursor = conn.cursor()
    #         cursor.execute("PRAGMA foreign_keys = OFF")  # 외래키 제약 일시 비활성화

    #         # 모든 테이블 삭제
    #         cursor.execute("DROP TABLE IF EXISTS transformations")
    #         cursor.execute("DROP TABLE IF EXISTS artifacts")
    #         cursor.execute("DROP TABLE IF EXISTS messages")
    #         cursor.execute("DROP TABLE IF EXISTS topics")
    #         cursor.execute("DROP TABLE IF EXISTS ai_usage")
    #         cursor.execute("DROP TABLE IF EXISTS token_usage")
    #         cursor.execute("DROP TABLE IF EXISTS placeholders")
    #         cursor.execute("DROP TABLE IF EXISTS templates")
    #         cursor.execute("DROP TABLE IF EXISTS reports")
    #         cursor.execute("DROP TABLE IF EXISTS users")

    #         cursor.execute("PRAGMA foreign_keys = ON")  # 외래키 제약 재활성화
    #         conn.commit()
    #         conn.close()
    #         print("[OK] 기존 테이블이 삭제되었습니다.")
    #         break
    #     except Exception as e:
    #         if attempt < max_retries - 1:
    #             print(f"[RETRY] 테이블 삭제 실패 (시도 {attempt + 1}/{max_retries}): {e}")
    #             time.sleep(1)  # 1초 대기 후 재시도
    #         else:
    #             print(f"[WARNING] 기존 테이블 삭제 실패 (최종): {e}")
    #             print("[INFO] 기존 테이블이 없거나 서버가 데이터베이스를 사용 중입니다.")
    #             print("[INFO] 계속 진행합니다...")

    # 데이터베이스 초기화 (새로운 테이블 생성)
    init_db()
    print("[OK] 데이터베이스 테이블이 생성되었습니다.")

    # 관리자 계정 생성
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_username = os.getenv("ADMIN_USERNAME")

    if not admin_email:
        raise ValueError("ADMIN_EMAIL 환경 변수가 설정되지 않았습니다.")
    if not admin_password:
        raise ValueError("ADMIN_PASSWORD 환경 변수가 설정되지 않았습니다.")
    if not admin_username:
        raise ValueError("ADMIN_USERNAME 환경 변수가 설정되지 않았습니다.")

    # 기존 관리자 확인
    existing_admin = UserDB.get_user_by_email(admin_email)
    if existing_admin:
        print(f"[OK] 관리자 계정이 이미 존재합니다: {admin_email}")
    else:
        # 관리자 계정 생성
        admin_data = UserCreate(
            email=admin_email,
            username=admin_username,
            password=admin_password
        )

        hashed_password = hash_password(admin_password)
        admin_user = UserDB.create_user(admin_data, hashed_password)

        # 관리자 권한 및 활성화
        update = UserUpdate(is_active=True, is_admin=True)
        UserDB.update_user(admin_user.id, update)

        print(f"[OK] 관리자 계정이 생성되었습니다:")
        print(f"   이메일: {admin_email}")
        print(f"   비밀번호: {admin_password}")

    print("\n데이터베이스 초기화가 완료되었습니다!")

if __name__ == "__main__":
    main()
