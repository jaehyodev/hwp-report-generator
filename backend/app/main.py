"""
HWP 보고서 자동 생성 시스템 - FastAPI 메인 애플리케이션
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# 현재 위치에서 상위로 올라가며 .env 파일 자동 검색
env_file_path = find_dotenv()
print(f"DEBUG: 찾은 .env 파일 경로: {env_file_path}")

load_dotenv(env_file_path)

# 환경 변수에서 프로젝트 홈 읽기
path_project_home = os.getenv("PATH_PROJECT_HOME")
print(f"DEBUG: PATH_PROJECT_HOME 값: {path_project_home}")

if not path_project_home:
    print("=" * 80)
    print("ERROR: PATH_PROJECT_HOME 환경 변수가 설정되지 않았습니다.")
    print("=" * 80)
    print()
    print(f".env 파일에 다음 항목을 추가해주세요:")
    print(f"위치: {env_file_path}")
    print()
    print("PATH_PROJECT_HOME=D:\\WorkSpace\\hwp-report\\hwp-report-generator")
    print()
    print("(위 경로를 실제 프로젝트 경로로 수정하세요)")
    print("=" * 80)
    sys.exit(1)

# 프로젝트 루트를 sys.path에 추가 (shared 모듈 import를 위해)
project_root = Path(path_project_home)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

from app.utils.claude_client import ClaudeClient
from app.utils.hwp_handler import HWPHandler
from app.utils.auth import hash_password
from app.utils.markdown_parser import parse_markdown_to_content
from app.database import init_db, UserDB
from app.routers import (
    auth_router,
    reports_router,
    admin_router,
    topics_router,
    messages_router,
    artifacts_router,
    templates_router,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="HWP 보고서 자동 생성 시스템",
    description="Claude AI를 사용하여 금융 업무보고서를 자동 생성하는 시스템",
    version="1.0.0"
)

# Backend 디렉토리 설정 (PATH_PROJECT_HOME 기반)
BACKEND_DIR = project_root / "backend"

# 앱 시작 시 실행
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 실행"""
    logger.info("애플리케이션 시작 중...")

    # 필요한 디렉토리 생성
    os.makedirs(BACKEND_DIR / "templates", exist_ok=True)
    os.makedirs(BACKEND_DIR / "output", exist_ok=True)  # Legacy (deprecated)
    os.makedirs(BACKEND_DIR / "temp", exist_ok=True)
    os.makedirs(BACKEND_DIR / "data", exist_ok=True)
    os.makedirs(BACKEND_DIR / "artifacts", exist_ok=True)  # New: chat-based artifacts

    # 데이터베이스 초기화
    logger.info("데이터베이스를 초기화합니다...")
    init_db()
    logger.info("데이터베이스 초기화 완료")

    # 관리자 계정 생성
    logger.info("관리자 계정을 확인/생성합니다...")
    init_admin_user()
    logger.info("애플리케이션 시작 완료")

# CORS 설정 - 환경별 프론트엔드 주소 지정
FRONTEND_URLS = os.getenv("FRONTEND_URLS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    max_age=3600,
)

# 정적 파일 및 템플릿 설정
# Get the project root directory for legacy static/templates
PROJECT_ROOT = BACKEND_DIR.parent
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))

# 라우터 등록
app.include_router(auth_router)
app.include_router(reports_router)  # Legacy (deprecated)
app.include_router(admin_router)

# New chat-based API routers
app.include_router(topics_router)
app.include_router(messages_router)
app.include_router(artifacts_router)

# Template management routers
app.include_router(templates_router)

# 템플릿 파일 경로 (HWP 템플릿)
TEMPLATE_PATH = str(BACKEND_DIR / "templates" / "report_template.hwpx")


class ReportRequest(BaseModel):
    """보고서 생성 요청 모델"""
    topic: str


class ReportResponse(BaseModel):
    """보고서 생성 응답 모델"""
    success: bool
    message: str
    file_path: str = None
    filename: str = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """관리자 페이지"""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    """비밀번호 변경 페이지"""
    return templates.TemplateResponse("change-password.html", {"request": request})


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "HWP Report Generator",
        "version": "1.0.0"
    }


@app.post("/api/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """
    보고서 생성 API

    Args:
        request: 보고서 주제를 포함한 요청

    Returns:
        ReportResponse: 생성 결과
    """
    try:
        logger.info(f"보고서 생성 요청: {request.topic}")

        # 입력 검증
        if not request.topic or len(request.topic.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="보고서 주제는 최소 3자 이상이어야 합니다."
            )

        # Claude 클라이언트 초기화
        claude_client = ClaudeClient()

        # 보고서 내용 생성
        logger.info("Claude AI로 보고서 내용 생성 중...")
        md_content = claude_client.generate_report(request.topic)
        logger.info("보고서 내용 생성 완료 (Markdown)")

        # Markdown을 파싱하여 content dict로 변환
        content = parse_markdown_to_content(md_content)
        logger.info("Markdown 파싱 완료")

        # HWP 파일 생성
        logger.info("HWPX 파일 생성 중...")

        # 템플릿이 없으면 간단한 템플릿 생성
        if not os.path.exists(TEMPLATE_PATH):
            logger.warning("템플릿 파일이 없습니다. 기본 템플릿을 생성합니다.")
            os.makedirs(BACKEND_DIR / "templates", exist_ok=True)
            os.makedirs(BACKEND_DIR / "temp", exist_ok=True)

            # 간단한 HWPX 템플릿 직접 생성
            import zipfile
            work_dir = str(BACKEND_DIR / "temp" / "template_creation")
            os.makedirs(work_dir, exist_ok=True)
            os.makedirs(f"{work_dir}/Contents", exist_ok=True)

            # section0.xml 생성
            section_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<section>
    <p><text>제목: {{TITLE}}</text></p>
    <p><text>작성일: {{DATE}}</text></p>
    <p><text>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</text></p>
    <p><text>1. 요약</text></p>
    <p><text>{{SUMMARY}}</text></p>
    <p><text>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</text></p>
    <p><text>2. 배경 및 목적</text></p>
    <p><text>{{BACKGROUND}}</text></p>
    <p><text>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</text></p>
    <p><text>3. 주요 내용</text></p>
    <p><text>{{MAIN_CONTENT}}</text></p>
    <p><text>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</text></p>
    <p><text>4. 결론 및 제언</text></p>
    <p><text>{{CONCLUSION}}</text></p>
</section>"""

            with open(f"{work_dir}/Contents/section0.xml", 'w', encoding='utf-8') as f:
                f.write(section_content)

            # version.xml 생성
            with open(f"{work_dir}/version.xml", 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<version>5.0.0.0</version>')

            # HWPX 압축
            with zipfile.ZipFile(TEMPLATE_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(work_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, work_dir)
                        zipf.write(file_path, arcname)

            # 임시 디렉토리 정리
            import shutil
            shutil.rmtree(work_dir)
            logger.info("기본 템플릿이 생성되었습니다.")

        # HWP 핸들러 초기화 및 보고서 생성
        hwp_handler = HWPHandler(
            template_path=TEMPLATE_PATH,
            temp_dir=str(BACKEND_DIR / "temp"),
            output_dir=str(BACKEND_DIR / "output")
        )

        output_path = hwp_handler.generate_report(content)
        filename = os.path.basename(output_path)

        logger.info(f"보고서 생성 완료: {filename}")

        return ReportResponse(
            success=True,
            message="보고서가 성공적으로 생성되었습니다.",
            file_path=output_path,
            filename=filename
        )

    except ValueError as e:
        logger.error(f"설정 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"설정 오류: {str(e)}")

    except FileNotFoundError as e:
        logger.error(f"파일 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 오류: {str(e)}")

    except Exception as e:
        logger.error(f"보고서 생성 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"보고서 생성 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/api/download/{filename}")
async def download_report(filename: str):
    """
    생성된 보고서 다운로드

    Args:
        filename: 다운로드할 파일명

    Returns:
        FileResponse: 파일 다운로드 응답
    """
    try:
        file_path = str(BACKEND_DIR / "output" / filename)

        # 파일 존재 확인
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        # 보안: 파일명 검증 (디렉토리 탐색 방지)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

        logger.info(f"파일 다운로드: {filename}")

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 다운로드 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"파일 다운로드 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/api/reports")
async def list_reports():
    """
    생성된 보고서 목록 조회

    Returns:
        dict: 보고서 파일 목록
    """
    try:
        output_dir = str(BACKEND_DIR / "output")
        if not os.path.exists(output_dir):
            return {"reports": []}

        files = [
            {
                "filename": f,
                "size": os.path.getsize(os.path.join(output_dir, f)),
                "created": os.path.getctime(os.path.join(output_dir, f))
            }
            for f in os.listdir(output_dir)
            if f.endswith(".hwpx")
        ]

        # 생성 시간 기준 내림차순 정렬
        files.sort(key=lambda x: x["created"], reverse=True)

        return {"reports": files}

    except Exception as e:
        logger.error(f"보고서 목록 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"보고서 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


def init_admin_user():
    """관리자 계정 자동 생성"""
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123!@#")
        admin_username = os.getenv("ADMIN_USERNAME", "관리자")

        # 관리자 계정이 이미 있는지 확인
        existing_admin = UserDB.get_user_by_email(admin_email)
        if existing_admin:
            logger.info("관리자 계정이 이미 존재합니다.")
            return

        # 관리자 계정 생성
        from app.models.user import UserCreate, UserUpdate
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

        logger.info(f"관리자 계정이 생성되었습니다. 이메일: {admin_email}")

    except Exception as e:
        logger.error(f"관리자 계정 생성 중 오류: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # 필요한 디렉토리 생성
    os.makedirs(BACKEND_DIR / "templates", exist_ok=True)
    os.makedirs(BACKEND_DIR / "output", exist_ok=True)
    os.makedirs(BACKEND_DIR / "temp", exist_ok=True)
    os.makedirs(BACKEND_DIR / "data", exist_ok=True)

    # 데이터베이스 초기화
    logger.info("데이터베이스를 초기화합니다...")
    init_db()
    logger.info("데이터베이스 초기화 완료")

    # 관리자 계정 생성
    logger.info("관리자 계정을 확인/생성합니다...")
    init_admin_user()

    logger.info("HWP 보고서 생성 시스템을 시작합니다...")
    logger.info("서버 주소: http://localhost:8000")
    logger.info("API 문서: http://localhost:8000/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
