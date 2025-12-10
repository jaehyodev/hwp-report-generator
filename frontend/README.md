# HWP Report Generator - Frontend

Claude AI를 활용하여 한글(HWP) 형식의 금융 보고서를 자동 생성하는 React 기반 웹 애플리케이션입니다.

## 🌐 배포

- **프로덕션 서버**: [https://hwpreportgen.netlify.app](https://hwpreportgen.netlify.app)
- **배포 플랫폼**: Netlify
- **백엔드 API**: FastAPI (별도 서버)

## 🚀 기술 스택

- **React 19** - UI 라이브러리
- **TypeScript** - 타입 안정성
- **Vite 7** - 빌드 도구
- **React Router v7** - 라우팅
- **Ant Design 5** - UI 컴포넌트 라이브러리
- **Axios** - HTTP 클라이언트
- **Zustand** - 상태 관리
- **React Markdown** - 마크다운 렌더링

## ✨ 주요 기능

### 1. 대화형 보고서 생성 시스템
- **워크플로우**
  - (Template 선택) → Topic 생성 → Plan 생성 → (Plan 편집) → 백그라운드 보고서 생성 → (보고서 수정 요청) → 다운로드
- **Plan 미리보기 및 수정** - AI가 생성한 계획을 검토/편집 후 보고서 생성
- **실시간 진행 상황 추적** (SSE/폴링, 현재 SSE만 사용!)
- **메시지 스레드 관리** - 토픽별 대화 이력 유지

### 2. 템플릿 관리 시스템
- **템플릿 업로드** - HWPX 파일 업로드 시 자동 플레이스홀더 추출
- **템플릿 기반 생성** - 템플릿을 선택하여 일관된 형식의 보고서 생성
- **사용자/관리자 템플릿 관리** - 개인 템플릿 관리 및 전체 템플릿 관리
- **프롬프트 편집** - 템플릿별 System/User 프롬프트 커스터마이징

### 3. 보고서 관리
- **미리보기 기능** - 사이드바에서 즉시 확인
- **HWPX 다운로드** - 한글 문서로 즉시 다운로드

### 4. 사용자 인증 및 권한 관리
- **JWT 기반 인증** - 자동 토큰 갱신 및 로그아웃
- **회원가입/로그인** - 신규 사용자 등록 및 인증
- **비밀번호 변경** - 사용자 비밀번호 관리
- **Private/Public Route** - 페이지별 접근 권한 제어

### 5. 관리자 대시보드
- **사용자 관리** - 회원 승인/거부, 활성화/비활성화, 비밀번호 초기화
- **템플릿 관리** - 전체 템플릿 조회/편집/삭제
- **토큰 사용량 분석** - AI API 호출 비용 및 사용량 모니터링
- **프롬프트 관리** - 시스템 전체 프롬프트 편집 및 검증

## 📁 프로젝트 구조

```
src/
├── components/         # 재사용 가능한 컴포넌트 (~50개)
│   ├── auth/           # 인증 (PrivateRoute, PublicRoute)
│   ├── chat/           # 채팅 (ChatInput, ChatMessage, ChatLoading)
│   ├── layout/         # 레이아웃 (MainLayout, Sidebar, Header)
│   ├── report/         # 보고서 (ReportPreview, PlanPreview)
│   ├── admin/          # 관리자 (AdminDashboard, PromptManagement)
│   └── common/         # 공통 (템플릿 선택, 업로드 모달)
├── pages/              # 페이지 컴포넌트 (7개)
├── services/           # API 서비스 (6개 - auth, topic, message, artifact, template, admin)
├── stores/             # Zustand 상태 관리 (3개 - topic, message, artifact)
├── hooks/              # 커스텀 훅 (8개 - chat, artifact, auth 등)
├── context/            # React Context (AuthContext, ThemeContext)
├── types/              # TypeScript 타입 정의
├── utils/              # 유틸리티 함수
└── constants/          # 상수 (API 엔드포인트)
```

## 🎨 상태 관리 아키텍처

- **Zustand Stores**
  - `useTopicStore` - 토픽 목록, 선택된 토픽, Plan/보고서 생성 상태
  - `useMessageStore` - 토픽별 메시지 캐싱 (Map 기반)
  - `useArtifactStore` - Artifact 캐싱 및 자동 선택
- **Context Providers**
  - `AuthContext` - 전역 인증 상태 (JWT, 사용자 정보)
  - `ThemeContext` - 다크/라이트 모드 전환
  - `MessageContext` - Toast 알림 (Ant Design message)

## 🛠️ 설치 및 실행

### 1. 의존성 설치

```bash
npm install
```

### 2. 환경변수 설정

`.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
VITE_API_BASE_URL=
```

### 3. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 http://localhost:5173 으로 접속

### 4. 프로덕션 빌드

```bash
npm run build
```

빌드된 파일은 `dist/` 폴더에 생성됩니다.

## 📄 주요 페이지

| 라우트 | 페이지 | 기능 | 접근 권한 |
|--------|--------|------|----------|
| `/login` | 로그인 | 사용자 인증 | 비로그인 사용자 |
| `/register` | 회원가입 | 신규 회원 등록 | 비로그인 사용자 |
| `/` | 메인 페이지 | 대화형 보고서 생성 인터페이스 | 로그인 사용자 |
| `/topics` | 토픽 목록 | 생성한 토픽 이력 및 관리 | 로그인 사용자 |
| `/templates` | 템플릿 관리 | 개인 템플릿 업로드/편집/삭제 | 로그인 사용자 |
| `/change-password` | 비밀번호 변경 | 사용자 비밀번호 관리 | 로그인 사용자 |
| `/admin` | 관리자 대시보드 | 사용자/템플릿/토큰 관리 | 관리자 전용 |

## 🔐 인증 흐름

1. **로그인** - JWT 토큰을 localStorage에 저장
2. **자동 인증** - Axios interceptor를 통해 모든 요청에 자동으로 토큰 추가
3. **세션 복구** - 페이지 새로고침 시 토큰으로 사용자 정보 복구
4. **에러 처리** - 401 에러 발생 시 자동으로 로그인 페이지로 리다이렉트
5. **라우트 보호**
   - `PrivateRoute` - 인증 필요 페이지 보호 (메인, 토픽, 템플릿, 관리자)
   - `PublicRoute` - 로그인 후 접근 불가 페이지 처리 (로그인, 회원가입)

## 🔄 보고서 생성 워크플로우

```
1. Topic 생성
   ↓ (사용자 주제 입력 + 템플릿 선택)
2. Plan 생성 (Sequential Planning)
   ↓ (Claude AI가 보고서 구조 자동 생성, < 2초)
3. Plan 미리보기 & 편집
   ↓ (사용자 검토 및 수정)
4. 백그라운드 보고서 생성
   ↓ (비동기 처리, SSE로 실시간 진행 상황 추적)
5. Report 다운로드
   └─ (HWPX 파일 다운로드, 미리보기 가능)
```

## 🎨 스타일링 및 UX

- **Ant Design 5** - 전문적인 UI 컴포넌트 라이브러리
- **한국어 locale** - koKR 적용
- **반응형 디자인** - 모바일/태블릿/데스크톱 지원
- **다크 모드** - 라이트/다크 테마 전환 지원 (배포 버전은 오류)
- **실시간 피드백** - Toast 알림 (성공/에러/경고)

## 🔌 API 통합

### API 서비스 구조

| 서비스 | 파일 | 주요 엔드포인트 |
|--------|------|----------------|
| **인증** | `authApi.ts` | POST /login, POST /register, POST /logout |
| **토픽** | `topicApi.ts` | POST /plan, POST /generate, GET /status, GET /topics |
| **메시지** | `messageApi.ts` | GET /messages, POST /messages, DELETE /messages/:id |
| **Artifact** | `artifactApi.ts` | GET /artifacts, GET /artifacts/:id/download |
| **템플릿** | `templateApi.ts` | POST /templates, GET /templates, DELETE /templates/:id |
| **관리자** | `adminApi.ts` | GET /users, PATCH /users/:id, GET /token-usage |

### 주요 API 기능

- **SSE (Server-Sent Events)** - 실시간 보고서 생성 진행 상황 스트리밍
- **Polling** - 백그라운드 작업 상태 폴링 (SSE 미지원 시 Fallback)
- **파일 업로드** - FormData 기반 HWPX 템플릿 업로드
- **파일 다운로드** - Blob 응답으로 HWPX 파일 다운로드
- **JWT 인증** - Authorization 헤더 자동 추가 (Axios Interceptor)

## 🧪 개발 가이드

### 새로운 페이지 추가

1. `src/pages/` 폴더에 새 페이지 컴포넌트 생성
2. `src/App.tsx`에 라우트 추가
3. 필요시 `PrivateRoute` 또는 `PublicRoute`로 감싸기

### 새로운 API 엔드포인트 추가

1. `src/constants/index.ts`에 엔드포인트 상수 추가
2. `src/services/`에 API 함수 추가 (예: `topicApi.ts`)
3. 필요시 `src/hooks/`에 커스텀 훅 생성 (예: `useChatActions.ts`)
4. `src/types/`에 타입 정의 추가

### 상태 관리 추가

1. **Zustand Store** - `src/stores/`에 새 스토어 생성
2. **Context** - `src/context/`에 새 Context Provider 생성
3. **Hook** - `src/hooks/`에 커스텀 훅 생성

## 📝 코드 컨벤션

- **함수형 컴포넌트** - 모든 컴포넌트는 함수형 컴포넌트로 작성
- **TypeScript strict mode** - 타입 안정성 엄격히 준수
- **ESLint/Prettier** - 코드 포맷팅 규칙 준수
- **명확한 네이밍** - 변수/함수/컴포넌트 이름 명확히
- **컴포넌트 구조**
  - Props 인터페이스 정의 (타입 안정성)
  - Hook 사용 (상단에 배치)
  - Event Handler (handle* prefix)
  - JSX 반환 (명확한 구조)

## 🏗️ 주요 기술적 특징

### 비동기 처리 및 실시간 업데이트

- **백그라운드 작업** - 보고서 생성 중에도 UI 반응성 유지
- **SSE (Server-Sent Events)** - 실시간 진행 상황 스트리밍 (완료 알림)
- **Polling Fallback** - SSE 미지원 환경에서 자동 폴링 (500ms 간격)
- **Optimistic UI** - 사용자 액션 즉시 반영 (네트워크 지연 최소화)

### 성능 최적화

- **Zustand 기반 상태 관리** - Redux 대비 경량화 (번들 사이즈 감소)
- **Map 기반 메시지 캐싱** - 토픽별 메시지 빠른 조회 (O(1))
- **Lazy Loading** - Artifact 데이터 지연 로딩 (필요 시에만 fetch)
- **React Router v7** - 최신 라우팅 성능 개선

### 타입 안정성

- **TypeScript strict mode** - 런타임 에러 사전 방지
- **86개 .ts/.tsx 파일** - 완전한 타입 커버리지
- **Pydantic 연동** - 백엔드 모델과 타입 일치성 보장

## 🔧 트러블슈팅

### CORS 에러

백엔드 FastAPI에서 CORS 설정이 올바른지 확인하세요:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hwpreportgen.netlify.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 토큰 만료

- 로그인 후 일정 시간이 지나면 JWT 토큰이 만료됩니다.
- 401 에러 발생 시 자동으로 로그인 페이지로 리다이렉트됩니다.
- `AuthContext`에서 토큰 만료 시간 체크 및 자동 로그아웃 처리.

### 환경변수 설정 오류

`.env` 파일에 `VITE_API_BASE_URL`이 올바르게 설정되었는지 확인하세요:

```env
VITE_API_BASE_URL=https://your-backend-api.com
```

- 로컬 개발: `http://localhost:8000`
- 프로덕션: 실제 백엔드 서버 URL

### SSE 연결 실패

- 브라우저 개발자 도구에서 Network 탭 확인
- SSE 엔드포인트 `/api/topics/{id}/status/stream` 연결 상태 확인
- Fallback으로 폴링 자동 전환 (500ms 간격)

## 📊 프로젝트 통계

- **총 파일 수**: 86개 (TypeScript/TSX)
- **컴포넌트**: ~50개 (재사용 가능)
- **페이지**: 7개
- **API 서비스**: 6개
- **커스텀 훅**: 8개
- **Zustand 스토어**: 3개
- **Context Provider**: 3개

## 🎯 향후 개선 사항

- [ ] React Query 통합 (서버 상태 관리 개선)
- [ ] E2E 테스트 (Playwright/Cypress)
- [ ] PWA 지원 (오프라인 모드)
- [ ] 다국어 지원 (i18n)
- [ ] 보고서 미리보기 개선 (PDF 변환)
- [ ] 실시간 협업 기능 (WebSocket)

---

**개발자:** HWP Report Generator Frontend
**마지막 업데이트:** 2025-12-09