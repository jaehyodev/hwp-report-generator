/**
 * constants/index.ts
 *
 * ⭐ 앱 전체에서 사용하는 상수 정의
 *
 * 상수(Constant)란?
 * - 변하지 않는 값
 * - 코드 여러 곳에서 같은 값을 사용할 때, 한 곳에서 관리
 *
 * 왜 상수를 사용하나?
 * 1. 중복 방지: '/api/auth/login'을 10곳에서 쓰면, URL 변경 시 10곳 모두 수정
 * 2. 오타 방지: 'LOGIN' 타이핑 실수 시 에디터가 경고
 * 3. 유지보수: 한 곳만 수정하면 전체 반영
 *
 * 이 파일이 관리하는 것:
 * 1. API_BASE_URL: 서버 주소
 * 2. API_ENDPOINTS: 모든 API 엔드포인트 URL
 * 3. STORAGE_KEYS: 로컬스토리지 키 이름
 *
 * 사용 방법:
 * import { API_ENDPOINTS } from './constants';
 * await api.post(API_ENDPOINTS.LOGIN, data);
 */

/**
 * API 서버 기본 URL
 * - Vite 개발 서버의 프록시 기능을 사용하므로 빈 문자열
 * - vite.config.ts에서 '/api' 경로를 'http://localhost:8000'으로 프록시 설정
 * - 프로덕션에서는 환경변수 VITE_API_BASE_URL 사용
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

/**
 * API 엔드포인트 URL 모음
 *
 * as const란?
 * - TypeScript에게 "이 값들은 절대 변경 안 됨"을 알려줌
 * - 더 정확한 타입 체크 가능
 *
 * 함수형 엔드포인트:
 * - DOWNLOAD_REPORT: (filename) => `/api/download/${filename}`
 * - 동적으로 URL을 만들어야 할 때 사용
 * - 예: DOWNLOAD_REPORT('report.hwpx') → '/api/download/report.hwpx'
 */
export const API_ENDPOINTS = {
    // 인증 API
    REGISTER: '/api/auth/register', // 회원가입
    LOGIN: '/api/auth/login', // 로그인
    ME: '/api/auth/me', // 내 정보 조회 (미구현)
    LOGOUT: '/api/auth/logout', // 로그아웃
    CHANGE_PASSWORD: '/api/auth/change-password', // 비밀번호 변경

    // 주제 API (v2.0)
    CREATE_TOPIC: '/api/topics', // 새 토픽 생성
    GENERATE_TOPIC: '/api/topics/generate', // 입력 한 번에 MD 산출 (토픽/메시지/아티팩트 동시 생성) - DEPRECATED
    GENERATE_TOPIC_BACKGROUND: (topicId: number) => `/api/topics/${topicId}/generate`, // 백그라운드 보고서 생성 (v2.4+)
    GET_GENERATION_STATUS: (topicId: number) => `/api/topics/${topicId}/status`, // 보고서 생성 상태 조회 (v2.4+)
    LIST_TOPICS: '/api/topics', // 내 토픽 목록 (페이징)
    GET_TOPIC: (topicId: number) => `/api/topics/${topicId}`, // 특정 토픽 조회
    UPDATE_TOPIC: (topicId: number) => `/api/topics/${topicId}`, // 토픽 업데이트
    DELETE_TOPIC: (topicId: number) => `/api/topics/${topicId}`, // 토픽 삭제
    ASK_TOPIC: (topicId: number) => `/api/topics/${topicId}/ask`, // 메시지 체이닝 (대화 이어가기)
    TOPIC_PLAN: '/api/topics/plan', // 보고서 작성 계획 생성
    GET_GENERATION_STATUS_STREAM: (topicId: number) => `/api/topics/${topicId}/status/stream`, // 보고서 생성 완료 알림

    // 보고서 관련 API
    GENERATE_REPORT: '/api/generate', // 보고서 생성
    LIST_REPORTS: '/api/reports', // 보고서 목록
    DOWNLOAD_REPORT: (filename: string) => `/api/download/${filename}`, // 보고서 다운로드 (동적 URL)

    // 관리자 API
    LIST_USERS: '/api/admin/users', // 사용자 목록
    APPROVE_USER: (userId: number) => `/api/admin/users/${userId}/approve`, // 사용자 승인
    REJECT_USER: (userId: number) => `/api/admin/users/${userId}/reject`, // 사용자 거부
    RESET_PASSWORD: (userId: number) => `/api/admin/users/${userId}/reset-password`, // 비밀번호 초기화
    GET_ALL_TOKEN_USAGE: '/api/admin/token-usage', // 모든 사용자의 토큰 사용량 조회
    GET_USER_TOKEN_USAGE: (userId: number) => `/api/admin/token-usage/${userId}`, // 사용자 토큰 사용량 조회

    // 메시지 API
    LIST_MESSAGES: (topicId: number) => `/api/topics/${topicId}/messages`, // 토픽의 메시지 목록
    CREATE_MESSAGE: (topicId: number) => `/api/topics/${topicId}/messages`, // 새 메시지 생성 (AI 응답 자동)
    DELETE_MESSAGE: (topicId: number, messageId: number) => `/api/topics/${topicId}/messages/${messageId}`, // 메시지 삭제

    // 아티팩트 API
    GET_ARTIFACT: (artifactId: number) => `/api/artifacts/${artifactId}`, // 아티팩트 메타데이터 조회
    GET_ARTIFACT_CONTENT: (artifactId: number) => `/api/artifacts/${artifactId}/content`, // MD 파일 내용 조회
    DOWNLOAD_ARTIFACT: (artifactId: number) => `/api/artifacts/${artifactId}/download`, // 파일 다운로드
    DOWNLOAD_MESSAGE_HWPX: (messageId: number, locale: string = 'ko') => `/api/artifacts/messages/${messageId}/hwpx/download?locale=${locale}`, // 메시지 기반 HWPX 다운로드 (자동 생성)
    LIST_ARTIFACTS_BY_TOPIC: (topicId: number) => `/api/artifacts/topics/${topicId}`, // 토픽의 아티팩트 목록
    CONVERT_ARTIFACT: (artifactId: number) => `/api/artifacts/${artifactId}/convert`, // MD to HWPX 변환

    // 템플릿 API
    LIST_TEMPLATES: '/api/templates', // 내 템플릿 목록
    GET_TEMPLATE: (templateId: number) => `/api/templates/${templateId}`, // 템플릿 상세 조회
    UPLOAD_TEMPLATE: '/api/templates', // 템플릿 업로드
    DELETE_TEMPLATE: (templateId: number) => `/api/templates/${templateId}`, // 템플릿 삭제
    UPDATE_PROMPT_USER: (templateId: number) => `/api/templates/${templateId}/prompt-user`, // User Prompt 업데이트
    UPDATE_PROMPT_SYSTEM: (templateId: number) => `/api/templates/${templateId}/prompt-system`, // System Prompt 업데이트
    REGENERATE_PROMPT_SYSTEM: (templateId: number) => `/api/templates/${templateId}/regenerate-prompt-system`, // System Prompt 재생성
    ADMIN_LIST_TEMPLATES: '/api/templates/admin/templates' // 관리자: 전체 템플릿 조회
}

/**
 * 로컬스토리지 키 이름
 * - 로컬스토리지에 저장할 때 사용하는 키
 * - 'access_token' 같은 문자열을 직접 쓰지 않고 상수로 관리
 */
export const STORAGE_KEYS = {
    ACCESS_TOKEN: 'access_token', // JWT 토큰 저장 키
    USER: 'user' // 사용자 정보 저장 키
}

/**
 * UI 설정 상수
 */
export const UI_CONFIG = {
    /**
     * 페이지네이션 설정
     */
    PAGINATION: {
        /**
         * TopicListPage에서 한 페이지당 표시할 토픽 개수
         */
        TOPICS_PER_PAGE: 5,
        /**
         * Sidebar에 표시할 최대 토픽 개수
         * - 이 개수 이상의 토픽이 있으면 "모든 대화" 버튼이 표시됨
         */
        SIDEBAR_TOPICS_PER_PAGE: 5
    }
}

/**
 * 토스트 메시지 상수
 * - 서버에서 받아오지 않는 클라이언트 측 메시지
 */
export const TOAST_MESSAGES = {
    // 공통
    LOADING: '로딩 중...',

    // 토픽/계획
    EMPTY_MESSAGE: '메시지를 입력해주세요.',
    NO_PLAN: '계획 정보가 없습니다.',
    PLAN_FAILED: '개요 생성에 실패했습니다.',
    PLAN_GENERATION_FAILED: '보고서 계획 생성에 실패했습니다.',

    // 보고서 생성
    REPORT_REQUESTING: '보고서 생성 요청 중...',
    REPORT_GENERATING: '보고서 생성 중...',
    REPORT_SUCCESS: '보고서가 생성되었습니다.',
    REPORT_FAILED: '보고서 생성에 실패했습니다.',
    REPORT_STATUS_ERROR: '보고서 상태 확인 중 오류가 발생했습니다.',

    // 메시지
    MESSAGE_LOAD_FAILED: '메시지를 불러오는데 실패했습니다.',
    MESSAGE_SEND_FAILED: '메시지 전송에 실패했습니다.',
    MESSAGE_DELETE_SUCCESS: '메시지가 삭제되었습니다.',
    MESSAGE_DELETE_FAILED: '메시지 삭제에 실패했습니다.',
    LAST_MESSAGE_DELETE_SUCCESS: '마지막 메시지가 삭제되어 대화가 종료되었습니다.',

    // 토픽
    TOPIC_NOT_SELECTED: '주제가 선택되지 않았습니다.',
    TOPIC_SELECT_FIRST: '대화를 시작하려면 먼저 주제를 선택하세요.',
    TOPIC_LOAD_FAILED: '토픽 목록을 불러오는데 실패했습니다.',
    TOPIC_DELETE_SUCCESS: '토픽이 삭제되었습니다.',
    TOPIC_DELETE_FAILED: '토픽 삭제에 실패했습니다.',
    TOPIC_TITLE_EMPTY: '제목을 입력해주세요.',
    TOPIC_TITLE_NO_CHANGE: '변경사항이 없습니다.',
    TOPIC_TITLE_UPDATE_SUCCESS: '제목이 수정되었습니다.',
    TOPIC_TITLE_UPDATE_FAILED: '제목 수정에 실패했습니다.',

    // 아티팩트/다운로드
    ARTIFACT_NEW_TOPIC_FIRST: '새로운 주제를 먼저 입력하세요.',
    ARTIFACT_LOAD_FAILED: '보고서 목록을 불러오는데 실패했습니다.',
    HWPX_DOWNLOADING: 'HWPX 파일 다운로드 중...',
    HWPX_DOWNLOAD_SUCCESS: 'HWPX 파일이 다운로드되었습니다.',
    HWPX_DOWNLOAD_FAILED: 'HWPX 파일 다운로드에 실패했습니다.',
    PREVIEW_LOAD_FAILED: '미리보기를 불러오는데 실패했습니다.',

    // 템플릿
    TEMPLATE_LOAD_FAILED: '템플릿 목록을 불러오는데 실패했습니다.',
    TEMPLATE_SELECT_REQUIRED: '템플릿을 선택해주세요.',
    TEMPLATE_DELETE_SUCCESS: '템플릿이 삭제되었습니다.',
    TEMPLATE_DELETE_FAILED: '템플릿 삭제에 실패했습니다.',
    TEMPLATE_UPLOAD_SUCCESS: '템플릿이 업로드되었습니다.',
    TEMPLATE_UPLOAD_FAILED: '템플릿 업로드에 실패했습니다.',
    TEMPLATE_FILE_REQUIRED: '파일을 선택해주세요.',
    TEMPLATE_FILE_INVALID: '파일 정보가 올바르지 않습니다.',
    TEMPLATE_HWPX_ONLY: 'HWPX 파일만 업로드 가능합니다.',
    TEMPLATE_SIZE_LIMIT: '파일 크기는 10MB 이하여야 합니다.',
    TEMPLATE_PROMPT_NO_CHANGE: '변경된 내용이 없습니다.',
    TEMPLATE_PROMPT_SAVE_SUCCESS: '프롬프트가 저장되었습니다.',
    TEMPLATE_PROMPT_SAVE_FAILED: '프롬프트 저장에 실패했습니다.',

    // 인증
    LOGIN_SUCCESS: '로그인 성공!',
    LOGOUT_SUCCESS: '로그아웃되었습니다.',
    LOGOUT_FAILED: '로그아웃 중 오류가 발생했습니다.',
    PASSWORD_CHANGE_SUCCESS: '비밀번호가 변경되었습니다.',
    PASSWORD_CHANGE_FAILED: '비밀번호 변경에 실패했습니다.',
    REGISTER_SUCCESS: '회원가입이 완료되었습니다. 관리자 승인 후 로그인 가능합니다.',
    REGISTER_FAILED: '회원가입에 실패했습니다.',

    // 관리자
    USER_DEACTIVATED: '사용자가 비활성화되었습니다.',
    USER_ACTIVATED: '사용자가 활성화되었습니다.',
    USER_STATUS_CHANGE_FAILED: '상태 변경에 실패했습니다.',
    PASSWORD_RESET_FAILED: '비밀번호 초기화에 실패했습니다.',
    USER_INFO_LOAD_FAILED: '사용자 정보를 불러올 수 없습니다.',
    PROMPT_LOAD_FAILED: '프롬프트를 불러오는데 실패했습니다.',
    PROMPT_SAVE_SUCCESS: '프롬프트가 저장되었습니다.',
    PROMPT_SAVE_FAILED: '프롬프트 저장에 실패했습니다.',
    PROMPT_RESET: '기본 프롬프트로 초기화되었습니다.'
}
