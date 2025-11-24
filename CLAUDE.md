# CLAUDE.md - HWP Report Generator 개발 가이드

이 파일은 Claude Code (claude.ai/code)가 이 저장소의 코드 작업 시 참고하는 종합 개발 가이드입니다.

---

## ⚠️ CRITICAL: 백엔드 개발 시 Unit Spec 우선 규칙

### 🔴 의무 규칙 (반드시 따라야 함)

**Rule #1: 반드시 Unit Spec부터 작성**
- 모든 신규 기능, 버그 수정, 리팩토링은 **코드 작성 전에 반드시 Unit Spec을 먼저 작성**
- 규모가 작아도, 간단해 보여도 **예외 없음**
- Unit Spec 없이 코드 작성은 거절됨

**Rule #2: 사용자 승인 후에만 구현**
- Unit Spec 작성 후 사용자의 검토 및 승인을 받을 때까지 대기
- 사용자가 수정을 요청하면 스펙을 수정
- 승인이 나면 그제서야 구현 시작

**Rule #3: Spec을 100% 준수하여 구현**
- 승인된 Spec에서 정의한 테스트 케이스를 모두 통과시켜야 함
- Spec의 파일 변경, 엔드포인트, 로직을 정확히 따름
- 사용자 승인 없이 Spec 변경 금지

**Rule #4: 모든 문서와 테스트 함께 제출**
- 코드 + 테스트 + Unit Spec 문서를 함께 커밋
- CLAUDE.md 업데이트 포함

### 🎯 Claude Code가 따를 프롬프트 지시

> **백엔드 코드 작업을 시작하기 전에 반드시 이를 읽으세요.**

**Step 1: 사용자 요청 분석**
- 사용자가 백엔드 기능을 요청하면, **절대로 코드를 먼저 작성하지 마세요**
- 신규 기능, 버그 수정, 리팩토링 모두 동일하게 적용

**Step 2: Unit Spec 작성 (90% 이상의 시간을 여기에)**
```
// 생성할 Spec 파일 경로
backend/doc/specs/YYYYMMDD_feature_name.md

// 사용할 템플릿
backend/doc/Backend_UnitSpec.md

// 포함할 항목 (모두 필수):
1. 요구사항 요약 (Purpose, Type, Core Requirements)
2. 구현 대상 파일 (New/Change/Reference 표)
3. 흐름도 (Mermaid flowchart 또는 sequence diagram)
4. 테스트 계획 (최소 3개 이상의 TC, Layer별 분류)
5. 에러 처리 시나리오
```

**Step 3: 사용자 검토 대기**
- Spec을 사용자에게 제시하고 승인을 받을 때까지 대기
- "이 Spec이 맞나요? 수정할 부분이 있나요?" 물어보기
- 사용자 의견 반영하여 Spec 수정

**Step 4: 승인 후 구현**
- 사용자 승인 이후에만 코드 작성 시작
- Spec에서 정의한 테스트 케이스를 먼저 작성 (TDD)
- 테스트가 모두 통과할 때까지 구현

**Step 5: 최종 검증 및 커밋**
- 모든 테스트 통과 확인
- CLAUDE.md 업데이트
- Unit Spec 문서 + 코드 + 테스트 함께 커밋

---

## 프로젝트 개요

**HWP Report Generator**: Claude AI를 활용하여 한글(HWP) 형식의 금융 보고서를 자동 생성하는 FastAPI 기반 웹 시스템입니다.

- 사용자가 주제를 입력 → Claude AI로 보고서 내용 자동 생성 → HWPX 형식 파일 생성
- **v2.0+**: 대화형 시스템 (토픽 기반 스레드, 메시지 체이닝)
- **v2.2**: Template 기반 동적 System Prompt 지원
- **v2.3**: 통합 문서화 및 아키텍처 정리

---

## 기술 스택

| 영역 | 스택 | 버전 |
|------|------|------|
| **Backend** | FastAPI | 0.104.1 |
| **Runtime** | Python | 3.12 |
| **패키지 관리** | uv / pip | - |
| **AI** | Anthropic Claude API | anthropic==0.71.0 |
| **Model** | Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 |
| **DB** | SQLite | 3.x |
| **HWPX 처리** | olefile, zipfile | olefile==0.47 |
| **인증** | JWT | python-jose==3.3.0 |
| **해싱** | bcrypt | bcrypt==4.1.2 |
| **Frontend** | React + TypeScript | 18.x / 5.x |

---

## Backend Architecture (Detailed Documentation)

**📖 For comprehensive backend documentation including:**
- Complete architecture overview (routers, models, database schemas)
- Core functions with step-by-step flows (generate_topic_report 9 steps, ask 12 steps, upload_template 9 steps)
- Database design (11 tables with SQL schemas)
- API endpoints (6 routers)
- E2E workflows (2 scenarios)
- Development checklist (Step 0, 1, 2)
- Environment setup & folder structure

**→ See [backend/CLAUDE.md](backend/CLAUDE.md)**

---

## 주요 개선사항 (v2.0 → v2.4)

### v2.4 (2025-11-12) - Sequential Planning + Real-time Progress Tracking

✅ **Sequential Planning 기반 보고서 계획 수립**
- Template의 prompt_system을 활용하여 Claude Sequential Planning으로 보고서 계획 생성
- 신규 엔드포인트: POST /api/topics/plan (< 2초 제약)
- 신규 유틸: `utils/sequential_planning.py` (219줄)
- 응답: 마크다운 형식 계획 + 섹션 목록

✅ **백그라운드 보고서 생성 + 실시간 진행 추적**
- 기존 POST /generate를 백그라운드 asyncio.create_task()로 리팩토링
- 응답시간 제약: < 1초 (202 Accepted)
- 메모리 기반 상태 관리: `utils/generation_status.py` (298줄)
- 신규 엔드포인트:
  - GET /api/topics/{id}/status (폴링, < 500ms)
  - GET /api/topics/{id}/status/stream (SSE, 실시간 완료 알림)

✅ **Pydantic 모델 추가**
- `PlanRequest`, `PlanResponse`, `PlanSection` 모델
- `GenerateRequest`, `GenerateResponse` 모델
- `StatusResponse` 모델

✅ **테스트 추가**
- `test_generation_status.py`: 35개 unit tests (100% 통과)
- generation_status 모듈 커버리지 97%

✅ **Unit Spec 문서화**
- `backend/doc/specs/20251112_sequential_planning_with_sse_progress.md`
- 완전한 API 정의, 테스트 계획, 구현 체크리스트 포함

### v2.3 (2025-11-11) - /ask 응답 형태 자동 판별 + 통합 문서화

✅ **/ask 응답 형태 자동 판별 (질문 vs 보고서)**
- Claude API 응답을 자동으로 분류 (3단계 감지 알고리즘)
- 보고서: 마크다운 H2 섹션 + 충분한 내용 → artifact 생성
- 질문: 추가 정보 요청 또는 사용자 입력 필요 → artifact 없이 응답만 반환
- 신규 util: `response_detector.py` (231줄)
- 테스트: 40개 단위 테스트 (100% 통과)

✅ **백엔드 CLAUDE.md 완전 갱신**
- 주요 함수 E2E 플로우 상세 분석
- 모든 라우터, 모델, DB 구조 문서화
- 환경 변수 설정 가이드
- 12단계 ask() 플로우 도식화

✅ **아키텍처 정리**
- 라우터 6개, 모델 9개, DB 11개, Utils 13개 분류
- 각 컴포넌트의 역할 명확화
- 의존성 관계 정의

### v2.2 (2025-11-10) - 동적 Prompt + 마크다운 파싱 수정

✅ **Template 기반 동적 System Prompt**
- 템플릿 업로드 시 Placeholder 추출 → System Prompt 자동 생성
- POST /api/topics/generate, POST /api/topics/{id}/ask에서 template_id 지원
- 우선순위: custom > template_id > default

✅ **/ask 아티팩트 마크다운 파싱 수정**
- 문제: Claude 응답 전체가 artifact로 저장됨
- 해결: parse_markdown_to_content() + build_report_md() 적용
- /generate와 /ask의 일관성 확보

✅ **테스트 추가**
- /ask 마크다운 파싱 3개 신규 테스트
- 전체 topics 테스트 28/28 통과 (100%)
- topics.py 커버리지 39% → 78%

### v2.1 (2025-11-04) - 프롬프트 통합

✅ **System Prompt 중앙 관리** (utils/prompts.py)
- FINANCIAL_REPORT_SYSTEM_PROMPT 상수화
- create_dynamic_system_prompt() 함수
- create_topic_context_message() 함수

✅ **동적 섹션 추출** (markdown_parser.py)
- H2 섹션 자동 분류 (요약, 배경, 주요내용, 결론)
- 동적 제목 추출 (title_summary, title_background, ...)
- 키워드 우선순위 조정

✅ **ClaudeClient 반환 타입 변경**
- Dict[str, str] → str (Markdown만 반환)
- 파싱 책임을 호출자로 이전 (관심사 분리)

### v2.0 (2025-10-31) - 대화형 시스템

✅ **Topics + Messages 아키텍처**
- 단일 요청 → 대화형 시스템 (토픽 스레드)
- 메시지 seq_no 기반 순서 관리
- 컨텍스트 유지 (이전 메시지 참조)

✅ **Artifacts 버전 관리**
- MD (Markdown), HWPX, PDF 지원
- 버전 번호로 변경사항 추적
- Transformation 이력 (MD→HWPX 변환)

✅ **API 표준화**
- success_response(), error_response() 헬퍼
- ErrorCode 클래스 (DOMAIN.DETAIL 형식)
- 모든 엔드포인트 100% 준수

---

## 개발 체크리스트 (백엔드)

### ✅ Step 0: Unit Spec 작성 (필수, 가장 먼저)

**이 단계를 완료하지 않으면 다음 단계로 진행할 수 없습니다.**

```
사용자 요청
    ↓
Claude: Unit Spec 작성
    ↓
[생성 위치] backend/doc/specs/YYYYMMDD_feature_name.md
[템플릿] backend/doc/Backend_UnitSpec.md
    ↓
사용자: 스펙 검토 및 승인
    ↓
승인 ✅ → Step 1로 진행
또는
수정 요청 → 스펙 수정 후 재제출
```

**Unit Spec에 포함되어야 할 항목:**
- [ ] 요구사항 요약 (Purpose, Type, Core Requirements)
- [ ] 구현 대상 파일 (New/Change/Reference)
- [ ] 흐름도 (Mermaid)
- [ ] 테스트 계획 (최소 3개 이상 TC)
- [ ] 에러 처리 시나리오

---

### ✅ Step 1: 구현 (Unit Spec 승인 후)

**Step 0의 승인을 받았을 때만 진행**

#### 1-1. 데이터 모델 정의
- [ ] Pydantic 모델 정의 (`models/*.py`)
- [ ] 필드 타입 힌트 완벽
- [ ] 선택/필수 필드 명확히

#### 1-2. 데이터베이스 로직
- [ ] DB CRUD 메서드 구현 (`database/*.py`)
- [ ] 트랜잭션 처리 (필요시)
- [ ] SQL 쿼리 파라미터화 (SQL Injection 방지)
- [ ] 인덱스 고려

#### 1-3. 라우터/API 구현
- [ ] 라우터 함수 구현 (`routers/*.py`)
- [ ] API 응답: **반드시** `success_response()` / `error_response()` 사용
- [ ] 에러 코드: **반드시** `ErrorCode` 상수 사용
- [ ] HTTP 상태 코드 정확히

#### 1-4. 로깅 및 문서화
- [ ] 로깅 추가 (`logger.info()`, `logger.warning()`, `logger.error()`)
- [ ] DocString 작성 (Google 스타일, 모든 함수)
- [ ] 파라미터, 반환값, 예외 명시

#### 1-5. 테스트 작성
- [ ] 테스트 작성 (`tests/test_*.py`)
- [ ] Unit Spec의 모든 TC 구현
- [ ] 성공 케이스 + 에러 케이스 모두
- [ ] 모든 테스트 **반드시 통과**

---

### ✅ Step 2: 검증 및 최종 확인 (구현 후)

#### 2-1. 기존 코드 영향 확인
- [ ] 기존 테스트 실행 (새 에러 없는지 확인)
- [ ] 호환성 검증 (breaking change 없는지)
- [ ] 의존성 충돌 확인

#### 2-2. 문서 업데이트
- [ ] CLAUDE.md 업데이트 (새 엔드포인트, 모델, DB 등)
- [ ] 필요시 README.md 업데이트

#### 2-3. 깃 커밋
- [ ] Unit Spec 문서 포함 (`backend/doc/specs/YYYYMMDD_*.md`)
- [ ] 깃 커밋 메시지: feat/fix/refactor 명확히
- [ ] 커밋 메시지에 Unit Spec 파일 명시

---

### 🚫 주의사항

**다음은 절대 하면 안 됨:**
- ❌ Unit Spec 없이 코드 작성 시작
- ❌ Unit Spec 미승인 상태에서 구현
- ❌ 승인된 Spec에서 임의로 변경
- ❌ 테스트 없이 구현 완료했다고 간주
- ❌ HTTPException 직접 사용 (response_helper 사용)
- ❌ 에러 코드 하드코딩 (ErrorCode 상수 사용)

---

### 버그 수정 / 리팩토링 시

**중요: 규모가 작아도 Unit Spec 필수**

- [ ] Unit Spec 작성 (버그/리팩토링 계획)
- [ ] 사용자 승인 (큰 변경사항일 경우)
- [ ] 기존 테스트 확인 (모두 통과해야 함)
- [ ] 새 테스트 추가 (버그 재발 방지)
- [ ] CLAUDE.md 업데이트

---

## 참고 자료

- `backend/CLAUDE.md` - 백엔드 개발 가이드라인 (DocString, 파일 관리)
- `backend/BACKEND_TEST.md` - 테스트 작성 가이드
- `backend/doc/Backend_UnitSpec.md` - Unit Spec 템플릿
- `backend/doc/specs/` - 구현된 스펙 문서들
- `backend/doc/07.PromptIntegrate.md` - 프롬프트 통합 가이드
- `backend/doc/04.messageChaining.md` - 메시지 체이닝 설계

---

### v2.5 (2025-11-14) - Event Loop Non-Blocking + Task Exception Handling

✅ **Event Loop Blocking 문제 해결**
- 백그라운드 보고서 생성 중 모든 동기 작업을 `asyncio.to_thread()` 감싸기
- Claude API, DB 작업, 파일 I/O 모두 별도 스레드에서 실행
- 응답: POST `/generate` < 1초, GET `/status` < 100ms 달성

✅ **Task 예외 처리 강화**
- `asyncio.create_task()` 후 `add_done_callback()` 추가
- Task 실패 시 `mark_failed()` 자동 호출
- 예외 로그 명확하게 기록

✅ **개발 환경 설정**
- `main.py`의 `uvicorn.run(..., reload=False)` 변경
- 메모리 상태 손실 문제 해결

✅ **테스트 추가**
- TC-001: Event Loop Non-Blocking (응답 시간 < 100ms)
- TC-002: Task 예외 처리 (실패 시 상태 업데이트)
- TC-003: 동시 다중 생성 (3개 Topic 동시 생성)
- TC-004: 로그 검증 (예외 발생 시 ERROR 로그)
- TC-005: 응답 시간 검증 (10회 반복 조회 < 100ms)
- **5/5 테스트 통과** (100%)

### 주요 코드 변경

**topics.py의 _background_generate_report():**
```python
# ❌ 이전 (blocking)
markdown = claude.generate_report(topic=topic)

# ✅ 이후 (non-blocking)
markdown = await asyncio.to_thread(
    claude.generate_report,
    topic=topic
)
```

**generate_report_background()의 예외 처리:**
```python
# ✅ Task 예외 처리 추가
task = asyncio.create_task(_background_generate_report(...))

def handle_task_result(t: asyncio.Task):
    try:
        t.result()
    except Exception as e:
        logger.error(f"Task failed: {str(e)}", exc_info=True)

task.add_done_callback(handle_task_result)
```

### Unit Spec
- 파일: `backend/doc/specs/20251114_fix_background_generation_event_loop_blocking.md`
- 8개 섹션: 요구사항, 흐름도, 5개 테스트 케이스, 에러 처리, 체크리스트

---

**마지막 업데이트:** 2025-11-14
**버전:** 2.5.0
**상태:** ✅ Event Loop Non-Blocking + Task Exception Handling 완성

### v2.6 (2025-11-20) - Markdown to HWPX 변환 기능

✅ **신규 엔드포인트: POST /api/artifacts/{artifact_id}/convert-hwpx**
- Artifact ID 기반 직접 HWPX 변환 다운로드
- 기존 GET /api/messages/{message_id}/hwpx/download와 차별화 (직접 경로)
- 권한 검증, artifact 종류 검증, 30초 타임아웃 포함

✅ **마크다운 파싱 엔진 (parse_markdown_to_md_elements)**
- 마크다운을 MdElement 리스트로 구조화
- FilterContext 기반 필터링 (코드블록, 테이블, 이미지, 링크, 체크박스, HTML 태그)
- 타입 분류: TITLE, SECTION, ORDERED_LIST_DEP1/DEP2, UNORDERED_LIST_DEP1/DEP2, QUOTATION, NORMAL_TEXT, HORIZON_LINE, NO_CONVERT
- 깊이 감지: 들여쓰기 칸 수로 DEP1(0칸) vs DEP2(>=2칸) 판별

✅ **HWPX 변환 유틸리티 (md_to_hwpx_converter.py)**
- escape_xml(): XML 특수문자 이스케이프 (&, <, >, ", ')
- load_template(): HWPX 템플릿 로드 & 압축해제 (tempfile 사용)
- apply_markdown_to_hwpx(): MD 요소 → section0.xml 적용
  - ⭐ Ref 파일은 읽기만 (원본 수정 금지)
  - HTML 주석 보존, 내부 값만 교체
  - <!-- Content Start --> ~ <!-- Content End --> 사이에 순차 추가
- create_hwpx_file(): HWPX 재압축 (HWPX 표준: mimetype ZIP_STORED)
- convert_markdown_to_hwpx(): 통합 변환 함수

✅ **데이터 모델 (convert_models.py)**
- MdType Enum: 10개 마크다운 요소 타입
- MdElement: 파싱된 마크다운 요소
- FilterContext: 필터링 컨텍스트
- ConvertResponse: HWPX 변환 응답

✅ **테스트 커버리지 (13개 TC)**
- Unit 테스트 (7개): 파싱, 플레이스홀더, 특수문자, 오탐 방지
- Integration 테스트 (1개): 전체 변환 프로세스
- API 테스트 (5개): 권한, 종류, 필터링, 성능, 404

### 신규 API 엔드포인트

**POST /api/artifacts/{artifact_id}/convert-hwpx**
```
요청:
- Path: artifact_id (정수)
- Headers: Authorization (JWT)

응답 (성공):
- 200 OK: HWPX 파일 (FileResponse, application/x-hwpx)
- Body: 바이너리 파일 (다운로드)

응답 (오류):
- 404 NOT_FOUND: artifact_id 유효하지 않음
- 403 FORBIDDEN: 사용자 권한 없음 (topic 소유자/관리자 아님)
- 400 BAD_REQUEST: artifact 종류가 MD 아님
- 504 GATEWAY_TIMEOUT: 변환 시간 > 30초
```

### 신규 파일

| 파일 | 내용 | 라인 수 |
|------|------|--------|
| backend/app/models/convert_models.py | MdType, MdElement, FilterContext, ConvertResponse | 76 |
| backend/app/utils/markdown_parser.py | parse_markdown_to_md_elements() + 필터링 함수들 | 600+ |
| backend/app/utils/md_to_hwpx_converter.py | escape_xml, load_template, apply_markdown_to_hwpx, create_hwpx_file, convert_markdown_to_hwpx | 400+ |
| backend/tests/test_convert.py | 13개 테스트 케이스 (Unit, Integration, API) | 550+ |

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| backend/app/routers/artifacts.py | 신규 엔드포인트 추가: POST /api/artifacts/{artifact_id}/convert-hwpx (Line 441+) |

### 구현 상세 (스펙 준수)

**마크다운 필터링 전략** (필터링 보고서 기반):
- 필터링 대상 (NO_CONVERT): 코드블록(```/~~~), 테이블(|...|), 이미지(![...]()), 링크([...]()), 체크박스(- [ ]), HTML 위험 태그(<script>, <style> 등)
- 필터링 안 함: 인용(>), 수평선(---) → 파싱되어 artifact에 포함

**Ref 파일 처리** (⭐ 핵심):
- 각 타입별 Ref 파일은 읽기만 수행 (원본 수정 금지)
- Ref 파일 내용을 메모리에 로드
- 메모리에서만 플레이스홀더 교체 (예: <!-- XXX_Start -->값<!-- XXX_End -->)
- 교체된 내용만 section0.xml에 저장
- 다른 한글 문서 작성 시 Ref 파일 재사용 가능

**타입별 Ref 파일 매핑**:
- SECTION → Ref_01_Section
- ORDERED_LIST_DEP1 → Ref07_OrderedList_dep1
- ORDERED_LIST_DEP2 → Ref08_OrderedList_dep2
- UNORDERED_LIST_DEP1 → Ref05_UnOrderedList_dep1
- UNORDERED_LIST_DEP2 → Ref06_UnOrderedList_dep2
- QUOTATION → Ref04_Quotation
- NORMAL_TEXT → Ref02_NormalText
- HORIZON_LINE → Ref03_HorizonLine

### Unit Spec
- 파일: `backend/doc/specs/20251120_md_to_hwpx_conversion.md`
- 11개 섹션: 요구사항, 흐름도, 동작 상세, 13개 TC, 에러 처리, 기술 스택, 함수 설계, 사용자 요청 기록, 구현 체크리스트, 가정사항, 참고자료
- 누적 수정 내용: 9차 (API 엔드포인트 위치 변경) - backend/app/routers/artifacts.py에 직접 추가

---

**마지막 업데이트:** 2025-11-20
**버전:** 2.6.0
**상태:** ✅ Markdown to HWPX 변환 기능 완성
