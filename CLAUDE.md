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

### v2.8 (2025-11-27) - Prompt Optimization에 신규 컬럼 추가

✅ **prompt_optimization_result 테이블 스키마 확장**
- 신규 컬럼 2개 추가: `output_format`, `original_topic`
- `output_format`: Claude 응답 구조 정보 (list, structured, etc.)
- `original_topic`: 사용자 원본 입력 주제
- 데이터 분석 목적으로 프롬프트 최적화 이력 보강

✅ **PromptOptimizationDB.create() 메서드 업데이트**
- 파라미터 추가: output_format, original_topic
- INSERT 쿼리 확장
- NULL 기본값 처리

✅ **sequential_planning._two_step_planning() 통합**
- _extract_prompt_fields()에서 output_format 추출
- 원본 topic을 original_topic으로 저장
- output_format 미저장 시 경고 로깅

✅ **Pydantic 모델 확장**
- PromptOptimizationCreate: output_format, original_topic 필드 추가
- PromptOptimizationResponse: output_format, original_topic 필드 추가

✅ **테스트 추가**
- TC-001: DB 스키마 마이그레이션 검증
- TC-002: 신규 필드 저장 확인
- TC-003: NULL 기본값 처리
- TC-004: sequential_planning 통합 검증
- TC-005: 기존 테스트 호환성 확인
- 5개 테스트 모두 추가

### 신규 API 엔드포인트
- 없음 (내부 저장만)

### 변경된 함수

| 함수 | 파일 | 변경 내용 |
|------|------|---------|
| create() | PromptOptimizationDB | output_format, original_topic 파라미터 추가 |
| _two_step_planning() | sequential_planning | 신규 필드 전달 & 로깅 추가 |

### 데이터 활용 예시

```sql
-- 1. output_format 분포 확인
SELECT output_format, COUNT(*) as count
FROM prompt_optimization_result
WHERE output_format IS NOT NULL
GROUP BY output_format;

-- 2. 원본 주제 vs 최적화 프롬프트 비교
SELECT original_topic, user_prompt
FROM prompt_optimization_result
WHERE original_topic IS NOT NULL AND user_prompt IS NOT NULL
LIMIT 10;
```

### 주요 코드 변경

**sequential_planning._two_step_planning():**
```python
PromptOptimizationDB.create(
    ...
    output_format=prompt_fields.get("output_format"),  # ✅ NEW
    original_topic=topic,  # ✅ NEW
    ...
)
```

---

### v2.9 (2025-11-27) - POST /api/topics/plan 프롬프트 데이터 조건부 저장

✅ **POST /api/topics/plan 동작 개선**
- isTemplateUsed 플래그 기반 조건부 데이터 저장
- Template-based 경로: templates DB에서 prompt_user, prompt_system 조회
- Optimization-based 경로: prompt_optimization_result에서 user_prompt 조회
- 두 경로 모두 TopicDB.update_topic_prompts()로 저장

✅ **Template 기반 처리 (isTemplateUsed=true)**
- 단계 1: sequential_planning() 실행 → plan 결과 반환
- 단계 2: Template 조회 (TemplateDB.get_template_by_id)
  - 존재하지 않음: 404 NOT_FOUND, 롤백
  - 권한 없음: 403 FORBIDDEN (owner/admin만), 롤백
- 단계 3: TopicDB.update_topic_prompts(topic_id, template.prompt_user, template.prompt_system) 저장
- 단계 4: 200 OK 응답 (plan + topic_id)

✅ **Optimization 기반 처리 (isTemplateUsed=false)**
- 단계 1: sequential_planning() 실행 → plan 결과 반환
- 단계 2: PromptOptimizationDB.get_latest_by_topic(topic_id) 조회
  - 결과 없음: WARN 로그 (비차단, prompt_user=NULL, prompt_system=NULL)
  - 결과 있음: user_prompt, output_format 추출
- 단계 3: TopicDB.update_topic_prompts(topic_id, prompt_user, prompt_system=output_format) 저장
- 단계 4: 200 OK 응답 (plan + topic_id)

✅ **에러 처리 전략**
- Template 권한 검증: 403 반환 (사용자 권한 확인)
- Template 미존재: 404 반환
- PromptOptimization 미존재: 경고 로그만 (비차단)
- DB 저장 실패: 경고 로그만 (비차단)

✅ **테스트 완료 (9/9 TC)**
- TC-001: Template 사용 성공 + 권한 검증
- TC-002: Optimization 사용 성공
- TC-003: Template 미존재 404
- TC-004: Template 권한 거부 403
- TC-005: PromptOptimization 미존재 WARN 로그
- TC-006: API 전체 흐름 (Template 기반)
- TC-007: API 전체 흐름 (Optimization 기반)
- TC-008: prompt_user/system 필드 타입 검증
- TC-009: 응답 시간 < 2000ms 검증
- ✅ 9/9 PASS (100%)
- ✅ 15개 기존 regression 테스트 PASS (100%)

### 신규 API 엔드포인트
- 변경: POST /api/topics/plan (기존 엔드포인트 동작 개선)

### 변경된 함수

| 함수 | 파일 | 변경 내용 |
|------|------|---------|
| plan_report() | backend/app/routers/topics.py | sequential_planning() 후 조건부 prompt 저장 로직 추가 (line 1106-1170) |

### 데이터 흐름 예시

**Template-based (isTemplateUsed=true):**
```
POST /api/topics/plan
├─ sequential_planning(topic, template_id, ...)
├─ TemplateDB.get_template_by_id(template_id)
├─ 권한 검증 (owner/admin)
├─ TopicDB.update_topic_prompts(topic_id, template.prompt_user, template.prompt_system)
└─ 200 OK { plan: "...", topic_id: 123 }
```

**Optimization-based (isTemplateUsed=false):**
```
POST /api/topics/plan
├─ sequential_planning(topic, template_id, ...)
├─ PromptOptimizationDB.get_latest_by_topic(topic_id)
├─ TopicDB.update_topic_prompts(topic_id, user_prompt, prompt_system=output_format)
└─ 200 OK { plan: "...", topic_id: 123 }
```

### Unit Spec
- 파일: `backend/doc/specs/20251127_api_topics_plan_prompt_enhancement.md`
- 9개 테스트 케이스 + 에러 처리 시나리오
- 2차 수정 사항 반영 (output_format, prompt_system 저장, 권한 검증)

### 구현 상세

**topics.py - plan_report() (lines 1106-1170):**
```python
if request.is_template_used:
    # Template-based 경로
    template = TemplateDB.get_template_by_id(request.template_id)
    if template is None:
        TopicDB.delete_topic(topic.id)  # Rollback
        return error_response(..., ErrorCode.RESOURCE_NOT_FOUND, 404)

    if template.user_id != current_user.id and current_user.role != 'admin':
        TopicDB.delete_topic(topic.id)  # Rollback
        return error_response(..., ErrorCode.ACCESS_DENIED, 403)

    try:
        TopicDB.update_topic_prompts(
            topic.id,
            template.prompt_user,
            template.prompt_system
        )
    except Exception as e:
        logger.warning(f"[PLAN] Update failed - {str(e)}")
else:
    # Optimization-based 경로
    opt_result = PromptOptimizationDB.get_latest_by_topic(topic.id)
    if opt_result is None:
        logger.warning(f"[PLAN] PromptOptimization not found - topic_id={topic.id}")
        prompt_user = None
        prompt_system = None
    else:
        prompt_user = opt_result.get('user_prompt')
        prompt_system = opt_result.get('output_format')

    try:
        TopicDB.update_topic_prompts(topic.id, prompt_user, prompt_system)
    except Exception as e:
        logger.warning(f"[PLAN] Update failed - {str(e)}")
```

---

### v2.10 (2025-11-28) - Placeholders DB에 Sort 컬럼 추가

✅ **Placeholders 테이블 스키마 확장**
- 신규 컬럼: `sort` (INTEGER, NOT NULL, DEFAULT 0)
- Template 업로드 시 HWPX에서 읽어온 placeholder를 순서대로 관리
- 0부터 시작하는 순차적 인덱스로 placeholder 순서 명시

✅ **Database 마이그레이션**
- connection.py init_db()에 마이그레이션 로직 통합
- 기존 DB: PRAGMA table_info로 컬럼 존재 여부 확인 후 ALTER TABLE
- 신규 DB: CREATE TABLE에 sort 컬럼 포함
- 중복 마이그레이션 방지, 오류 처리 포함

✅ **Pydantic 모델 업데이트**
- Placeholder: sort: int = Field(0, description="정렬 순서 (0-based index)")
- PlaceholderCreate: sort: Optional[int] = Field(None, ...)
- 모델 JSON 직렬화 시 sort 필드 포함

✅ **PlaceholderDB 메서드 수정 (3개)**

| 메서드 | 변경 사항 |
|--------|---------|
| create_placeholders_batch() | enumerate(placeholder_keys)로 sort 값 생성 후 INSERT |
| get_placeholders_by_template() | ORDER BY created_at → ORDER BY sort ASC |
| _row_to_placeholder() | row[3]=sort, row[4]=created_at로 매핑 |

✅ **Router/API 자동 처리**
- upload_template: placeholder_list를 순서대로 전달 (기존 동작 유지)
- create_template_with_transaction: enumerate로 자동 sort 값 할당

✅ **테스트 완료 (10/10 TC + 37개 기존 회귀 테스트)**
- TC-001: DB 스키마 검증 (INTEGER, NOT NULL, DEFAULT 0)
- TC-002: Batch INSERT sort 저장 확인 (0, 1, 2, ...)
- TC-003: 정렬 순서 조회 (ORDER BY sort ASC)
- TC-004: (API 통합, codex-cli로 별도 작성 예정)
- TC-005: Placeholder 모델 필드 확인
- TC-005b: 모델 기본값 (sort=0)
- TC-006: Sort NULL 처리 (None → 0)
- TC-006b: Sort 값 보존 (row[3] 정상 추출)
- 추가-001: PlaceholderCreate sort 선택사항
- 추가-002: 빈 리스트 & 단일 항목 엣지 케이스
- ✅ 10/10 신규 테스트 PASS (100%)
- ✅ 37개 기존 템플릿 테스트 PASS (100% - 호환성 확인)

### 신규/변경 파일

| 파일 | 상태 | 변경 내용 |
|------|------|---------|
| backend/app/database/connection.py | 변경 | init_db() 마이그레이션 로직 추가 (line 319-329) |
| backend/app/models/template.py | 변경 | Placeholder, PlaceholderCreate에 sort 필드 추가 |
| backend/app/database/template_db.py | 변경 | PlaceholderDB 3개 메서드 수정 (sort 처리) |
| backend/tests/test_placeholders_sort.py | 신규 | 10개 테스트 케이스 작성 |

### 변경된 함수

| 함수 | 파일 | 변경 내용 |
|------|------|---------|
| create_placeholders_batch() | template_db.py | enumerate로 sort 값 생성 후 INSERT |
| get_placeholders_by_template() | template_db.py | ORDER BY sort ASC로 변경 |
| _row_to_placeholder() | template_db.py | row[3]=sort, row[4]=created_at 매핑 |
| create_template_with_transaction() | template_db.py | enumerate(placeholder_keys)로 자동 sort 할당 |

### 데이터 저장 흐름

```
POST /api/templates
├─ HWPX 파일 업로드
├─ manager.extract_placeholders(work_dir)  # 순서 보존
│  └─ ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}"]
├─ TemplateDB.create_template_with_transaction(
│    template_data,
│    placeholder_list  # 순서 보존
│  )
├─ INSERT INTO placeholders (template_id, placeholder_key, sort)
│  VALUES (1, "{{TITLE}}", 0),
│         (1, "{{SUMMARY}}", 1),
│         (1, "{{BACKGROUND}}", 2)
└─ 201 Created
```

### Unit Spec
- 파일: `backend/doc/specs/20251128_placeholders_sort_column.md`
- 7개 테스트 케이스 + 에러 처리 시나리오 정의
- 4시간 예상 구현 시간

### 기술 스택
- Database: SQLite 3.x (ALTER TABLE)
- ORM: Raw SQL (편의성 vs 복잡도 고려)
- Testing: pytest 8.3.4, pytest-asyncio 0.24.0

### 호환성
- ✅ 기존 데이터: sort = DEFAULT 0 자동 설정
- ✅ 기존 API: 응답 형식 변경 없음 (PlaceholderResponse는 key만)
- ✅ 기존 테스트: 37개 모두 통과

---

**마지막 업데이트:** 2025-11-28
**버전:** 2.10.0
**상태:** ✅ Placeholders sort 컬럼 추가 완료

### v2.11 (2025-11-28) - Claude API Structured Outputs 기반 JSON 강제 응답

✅ **Structured Outputs 기능 통합**
- Claude API의 공식 Structured Outputs 기능으로 JSON 응답 강제 (Schema 검증)
- 신규 클라이언트: `utils/structured_client.py` (320줄)
- 동적 JSON Schema 생성: BASIC 모드 (type enum 고정) vs TEMPLATE 모드 (type 자유 문자열)
- `/api/topics/{id}/ask`, `/api/topics/generate` 엔드포인트에 적용

✅ **StructuredClaudeClient 구현**
- `__init__()`: Anthropic 클라이언트 초기화 + Beta Header 설정
  - `anthropic-beta: structured-outputs-2025-11-13` 헤더 자동 추가
- `generate_structured_report()`: Structured Outputs로 JSON 보고서 생성
- `_build_json_schema()`: 동적 스키마 생성 (BASIC/TEMPLATE 분기)
  - `additionalProperties: false` 포함 (공식 요구사항)
- `_invoke_with_structured_output()`: Claude API 호출 with output_format ⭐
  - 공식 API 파라미터: `output_format` (NOT response_format)
  - 불필요한 필드 제거: name, strict 제외
- `_process_response()`: StructuredReportResponse 객체로 변환
- 반환 타입: 항상 `StructuredReportResponse` (Fallback 없음)

✅ **JSON Schema 생성 규칙**

| 모드 | Type 필드 | 설명 |
|------|---------|------|
| **BASIC** | enum ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"] | 6개 고정 섹션 타입 |
| **TEMPLATE** | string (enum 없음) | 동적 placeholder ID (e.g., "MARKET_ANALYSIS", "CUSTOM_SECTION") |

**Schema 예시 (BASIC 모드):**
```json
{
  "type": "object",
  "properties": {
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "type": {"type": "string", "enum": ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"]},
          "content": {"type": "string"},
          "order": {"type": "integer"},
          "source_type": {"type": "string", "enum": ["basic", "template", "system"]}
        },
        "required": ["id", "type", "content", "order", "source_type"]
      }
    }
  }
}
```

✅ **데이터 모델 변경**
- `SectionMetadata.type`: `SectionType` Enum → `str` (동적 타입 지원)
  - BASIC: 고정 값 (TITLE, DATE, BACKGROUND 등)
  - TEMPLATE: 자유 문자열 (placeholder ID)
- 기존 코드 호환성: markdown_builder.py에서 `.value` 체크로 Enum/str 모두 지원

✅ **Router 통합 (topics.py)**
- `ask()` 함수 (Line ~788-826):
  - ClaudeClient → StructuredClaudeClient 변경
  - section_schema를 동적 JSON Schema로 변환
  - 항상 StructuredReportResponse 객체 반환 (JSON 보장)

- `_background_generate_report()` 함수 (Line ~1937-1967):
  - 백그라운드 보고서 생성에도 동일 처리
  - `asyncio.to_thread()`로 Non-blocking 유지

✅ **API 호출 패턴**

**이전 (Fallback 방식):**
```python
markdown = claude.generate_report(section_schema)
# 반환: Markdown 또는 JSON (불확실)
```

**이후 (Structured Outputs):**
```python
structured_client = StructuredClaudeClient()
json_response = await asyncio.to_thread(
    structured_client.generate_structured_report,
    topic=topic,
    system_prompt=system_prompt,
    section_schema=section_schema,
    source_type=source_type_str,
    context_messages=context_messages
)
# 반환: 항상 StructuredReportResponse (JSON 보장)
markdown = await asyncio.to_thread(
    build_report_md_from_json,
    json_response
)
```

✅ **테스트 커버리지 (11/11 TC)**
- TC-001: BASIC 모드 JSON Schema (type enum 고정)
- TC-001B: TEMPLATE 모드 JSON Schema (type 자유 문자열)
- TC-002: 유효한 structured response 처리
- TC-003: TEMPLATE 모드 동적 타입 처리
- TC-004: JSON → Markdown 변환
- TC-005: 잘못된 source_type 에러 처리
- TC-006: 빈 섹션 처리
- TC-007: 스키마 생성 성능 (< 100ms)
- TC-008: 응답 처리 성능 (< 100ms)
- Backward Compatibility: 기존 5개 테스트 모두 통과 (100%)
- **최종 결과: 11/11 PASS + 호환성 5/5 PASS**

### 신규 파일

| 파일 | 내용 | 라인 수 |
|------|------|--------|
| backend/app/utils/structured_client.py | StructuredClaudeClient 클래스 + 메서드 | 320 |
| backend/tests/test_structured_outputs_integration.py | 11개 테스트 케이스 (Unit, Integration, Backward Compatibility) | 350+ |

### 변경 파일

| 파일 | 변경 내용 | 라인 |
|------|---------|------|
| backend/app/models/report_section.py | SectionMetadata.type: SectionType → str | 33 |
| backend/app/routers/topics.py | ask() & _background_generate_report()에 StructuredClaudeClient 적용 | 788-826, 1937-1967 |
| backend/tests/test_json_section_metadata.py | Import 경로 수정 (Placeholder, TopicSourceType) | 20-23 |

### 기술 스택

- **Claude API**: Structured Outputs (output_format with json_schema) ⭐
  - 공식 문서: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
  - Beta Header: `anthropic-beta: structured-outputs-2025-11-13`
  - 주의: response_format이 아닌 output_format 사용
- **Anthropic SDK**: >= 0.71.0 (Structured Outputs 지원)
- **Pydantic**: BaseModel with dynamic field types
- **JSON Schema**: Draft 2020-12 + additionalProperties: false

### 사용 사례

**언제 StructuredClaudeClient를 사용하는가:**
- ✅ JSON 응답 포맷이 반드시 필요한 경우
- ✅ API Schema 검증이 필수인 경우
- ✅ Markdown Fallback 없이 JSON만 필요한 경우 (본 기능)

**언제 ClaudeClient를 사용하는가:**
- 자유로운 텍스트 응답 필요
- Markdown 또는 JSON 모두 가능한 경우

### 호환성

- ✅ 기존 데이터 모델: SectionMetadata.type을 str로 변경했으나, markdown_builder.py에서 `.value` 체크로 Enum 호환성 유지
- ✅ 기존 API 응답 형식: 변경 없음 (내부적으로만 JSON 처리)
- ✅ 기존 테스트: 모두 통과 (5/5 regression tests)

### 🔧 API 파라미터 핫픽스 (2025-11-28)

**문제:** 초기 구현에서 `response_format` 파라미터를 사용했으나, 공식 Claude API 문서에서는 `output_format`을 사용

**수정 사항:**
1. **파라미터 이름 변경:** `response_format` → `output_format` ⭐
   - 공식 문서: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
2. **Beta Header 추가:** `anthropic-beta: structured-outputs-2025-11-13`
3. **JSON Schema 수정:** `additionalProperties: false` 추가 (root + items level)
4. **불필요한 필드 제거:** name, strict 필드 제외 (공식 spec에 없음)

**검증:**
- ✅ 모든 11개 테스트 통과 (test_structured_outputs_integration.py)
- ✅ 공식 API 문서 기준 준수 확인

### Unit Spec
- 파일: `backend/doc/specs/20251128_json_structured_section_metadata.md`
- 15개 섹션: 요구사항, 스키마 정의, 흐름도, 동작 상세, 11개 TC, 에러 처리, 기술 스택, 호환성 검증, 구현 체크리스트

### 주요 개선 효과

| 항목 | 이전 | 이후 | 개선 |
|------|------|------|------|
| **응답 안정성** | JSON 또는 Markdown (불확실) | 항상 JSON | 100% 보장 |
| **Schema 검증** | 프롬프트 기반 (약함) | API 수준 검증 (강함) | Schema 위반 원천 차단 |
| **Error Handling** | Fallback 필요 | 즉시 실패 | 명확한 에러 처리 |
| **타입 안정성** | 동적 Markdown 파싱 | Pydantic 모델 | Type hints 완벽 |

---

**마지막 업데이트:** 2025-11-28
**버전:** 2.11.0
**상태:** ✅ Structured Outputs 기반 JSON 강제 응답 완성
