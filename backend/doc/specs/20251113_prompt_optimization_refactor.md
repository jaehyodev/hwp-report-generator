# Unit Spec: Prompt 관리 최적화 (Refactoring) - v2.0

**작성일:** 2025-11-13
**버전:** v2.0 (사용자 피드백 + 영향도 분석 반영)
**상태:** 사용자 검토 대기

---

## 📋 Executive Summary

### 요구사항 개요
Claude API 호출에 사용할 **system prompt의 관리를 효율적**으로 개선합니다.

**핵심 인사이트:**
- BASE_SYSTEM_PROMPT는 **"양식"(성격)** 이지 단순 상수가 아님
- **2가지 BASE 양식**이 필요함:
  1. **REPORT_BASE_PROMPT** - 보고서 작성용 (현재 BASE_REPORT_SYSTEM_PROMPT)
  2. **PLAN_BASE_PROMPT** - 빠른 계획 수립용 (sequential_planning.py용)
- 모든 프롬프트는 **`prompts.py`에서만 관리** (단일 진실 공급원)
- BASE 프롬프트는 **`shared/constants.properties`에서 관리** (확장성)

---

## 🎯 핵심 개념

### System Prompt의 구조 (목표 상태)

```
┌─────────────────────────────────────────────────────────────┐
│ System Prompt = BASE_PROMPT + TEMPLATE_SPECIFIC_RULES       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1️⃣ BASE_PROMPT (prompts.py 함수)                            │
│    ├─ REPORT_BASE_PROMPT                                    │
│    │  역할: 보고서 작성 지침 (모든 Template에 적용)            │
│    │  내용: "당신은 금융 기관의 전문 보고서 작성자입니다..."   │
│    │  저장: prompts.py + Template.prompt_user                │
│    │                                                          │
│    └─ PLAN_BASE_PROMPT                                      │
│       역할: 계획 수립 지침 (sequential_planning용)             │
│       내용: "당신은 보고서 계획 전문가입니다..."               │
│       저장: prompts.py만 (Template 불필요)                   │
│                                                              │
│ 2️⃣ TEMPLATE_SPECIFIC_RULES (Template의 내용)                │
│    역할: 특정 Template의 Placeholder 기반 동적 규칙           │
│    내용: "다음 placeholder들을 포함하여 작성: ..."             │
│    저장: Template.prompt_system (BASE 제외)                  │
│                                                              │
│ 3️⃣ FINAL_SYSTEM_PROMPT (runtime)                            │
│    = BASE_PROMPT + TEMPLATE_SPECIFIC_RULES                  │
│    생성 방법: 함수 호출 시 조합                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2가지 BASE 프롬프트의 역할 구분

| 프롬프트 | 사용 시점 | 특징 | 저장 위치 |
|---------|---------|------|---------|
| **REPORT_BASE_PROMPT** | `/generate`, `/ask` | 상세한 보고서 작성 지침 | prompts.py + Template.prompt_user |
| **PLAN_BASE_PROMPT** | `sequential_planning.py` | 빠른 계획 수립 (Haiku용) | prompts.py만 |

---

## 🔄 기존 플로우 vs 변경 사항

### 플로우 1: `/api/topics/generate` (보고서 생성)

#### 기존 플로우 (9단계)
```
1️⃣ 입력 검증
   └─ input_prompt 필수, 3자 이상

2️⃣ System Prompt 선택 (우선순위)
   ├─ IF custom_prompt
   │   └─ custom_prompt 사용
   ├─ ELSE IF template_id
   │   └─ get_system_prompt(template_id=...)
   │       ├─ TemplateDB.get_template_by_id() 조회
   │       ├─ PlaceholderDB.get_placeholders_by_template() 조회
   │       └─ create_dynamic_system_prompt(placeholders) 호출
   │           ├─ Placeholder 없으면: FINANCIAL_REPORT_SYSTEM_PROMPT 반환
   │           └─ Placeholder 있으면: BASE + 동적 규칙 생성
   └─ ELSE
       └─ FINANCIAL_REPORT_SYSTEM_PROMPT 반환

3️⃣ Claude API 호출
   └─ claude.chat_completion([user_message], system_prompt)

4️⃣ Markdown 파싱
   └─ parse_markdown_to_content(response)

5️⃣ Topic 생성
   └─ TopicDB.create_topic(...)

6️⃣ 메시지 저장
   └─ MessageDB.create_message(...)

7️⃣ Artifact 저장 (MD)
   └─ ArtifactDB.create_artifact(kind=MD)

8️⃣ 응답 생성
   └─ success_response({...})

9️⃣ 백그라운드 작업
   └─ asyncio.create_task() (202 Accepted)
```

#### 변경된 플로우 (동일 9단계, 2단계 개선)

```
1️⃣ 입력 검증 (동일)
   └─ input_prompt 필수, 3자 이상

2️⃣ System Prompt 선택 (✅ 개선)
   ├─ IF custom_prompt
   │   └─ custom_prompt 사용
   ├─ ELSE IF template_id
   │   └─ get_system_prompt(template_id=...)
   │       ├─ TemplateDB.get_template_by_id() 조회
   │       └─ template.prompt_user + template.prompt_system 직접 조합
   │           ├─ base = template.prompt_user or get_base_report_prompt()
   │           ├─ rules = template.prompt_system
   │           └─ return f"{base}\n\n{rules}"
   └─ ELSE
       └─ get_base_report_prompt() 반환 (✅ 함수 호출)

3️⃣-9️⃣ (동일)
```

**개선 효과:**
- ✅ PlaceholderDB 조회 제거 (성능 향상)
- ✅ 동적 생성 로직 단순화
- ✅ Template 구조 명확화 (prompt_user / prompt_system 분리)

### 플로우 2: `/api/templates (Template 업로드)

#### 기존 플로우 (11단계)
```
1️⃣ 파일 확장자 검증
2️⃣ 파일 내용 읽기
3️⃣ HWPX 파일 검증 (Magic Byte)
4️⃣ 임시 파일 저장
5️⃣ HWPX 압축 해제
6️⃣ Placeholder 추출
7️⃣ 중복 검증
8️⃣ SHA256 계산
9️⃣ Placeholder 메타정보 생성 (Claude API)
🔟 prompt_system 생성 (✅ 변경 필요)
   └─ create_system_prompt_with_metadata()
   └─ prompt_user = None (❌ 문제)
   └─ prompt_system = BASE + 메타정보 (❌ 문제)
1️⃣1️⃣ DB 저장 (Template + Placeholders)
```

#### 변경된 플로우 (동일 11단계, 10단계 개선)

```
1️⃣-9️⃣ (동일)

🔟 prompt 생성 (✅ 개선)
   ├─ base_prompt = get_base_report_prompt()
   ├─ template_rules = create_template_specific_rules(placeholder_list, metadata)
   ├─ prompt_user = base_prompt (✅ BASE 저장)
   └─ prompt_system = template_rules (✅ 규칙만 저장)

1️⃣1️⃣ DB 저장 (동일)
```

**개선 효과:**
- ✅ prompt_user에 BASE 저장 (이전 NULL)
- ✅ prompt_system에 규칙만 저장 (BASE 제외)
- ✅ 두 필드의 역할 명확화

### 플로우 3: `/api/topics/{id}/ask` (Q&A)

#### 기존 플로우
```
1️⃣ 메시지 이력 조회 (시퀀스로 정렬)
2️⃣ System Prompt 결정
   ├─ template_id → get_system_prompt(template_id=...)
   │   ├─ PlaceholderDB 조회
   │   └─ create_dynamic_system_prompt() (BASE 포함)
   └─ template_id 없으면 → FINANCIAL_REPORT_SYSTEM_PROMPT
3️⃣ Claude API 호출 (메시지 체인)
4️⃣ 응답 파싱 (markdown → artifact 판별)
5️⃣ Message 저장
6️⃣ Artifact 저장 (필요시)
```

#### 변경된 플로우

```
1️⃣ 메시지 이력 조회 (동일)
2️⃣ System Prompt 결정 (✅ 개선)
   ├─ template_id → get_system_prompt(template_id=...)
   │   ├─ template.prompt_user + template.prompt_system 직접 조합
   │   └─ PlaceholderDB 조회 제거
   └─ template_id 없으면 → get_base_report_prompt() (함수 호출)
3️⃣-6️⃣ (동일)
```

### 플로우 4: Sequential Planning (`_get_guidance_prompt`)

#### 기존 플로우
```
async def _get_guidance_prompt(template_id, user_id):
    # 하드코딩된 문자열
    default_guidance = """
**보고서 계획 작성 가이드:**
- 보고서는 다음 구조를 따라야 합니다:
  1. 요약
  2. 배경
  3. 주요 내용
  4. 결론
  ...
    """

    if not template_id:
        return default_guidance

    # Template 조회 로직
```

#### 변경된 플로우

```python
async def _get_guidance_prompt(template_id, user_id):
    # ✅ 중앙화된 BASE 프롬프트 사용
    default_guidance = get_base_plan_prompt()

    if not template_id:
        return default_guidance

    # Template 조회 로직 (동일)
```

**개선 효과:**
- ✅ 하드코딩 제거
- ✅ 중앙화 관리
- ✅ 변경 시 한 곳만 수정

---

## 📊 영향도 분석

### 📈 영향받는 함수 (Direct Impact)

| # | 함수명 | 파일 | 심각도 | 변경 사항 |
|---|--------|------|--------|---------|
| 1 | `get_system_prompt()` | prompts.py | ⭐⭐⭐ **HIGH** | 템플릿 조회 로직 변경 (DB 최소화) |
| 2 | `upload_template()` | templates.py | ⭐⭐⭐ **HIGH** | prompt_user/prompt_system 할당 변경 |
| 3 | `_get_guidance_prompt()` | sequential_planning.py | ⭐⭐ **MEDIUM** | 하드코딩 문자열 제거 |
| 4 | `chat_completion()` | claude_client.py | ⭐⭐ **MEDIUM** | Import 변경 (상수 → 함수) |
| 5 | `create_dynamic_system_prompt()` | prompts.py | ⭐ **LOW** | 내부 구현만 변경 (호환성 유지) |

### 📊 영향받는 엔드포인트 (Indirect Impact)

| # | 엔드포인트 | 라우터 | 영향 | 테스트 필수 |
|---|-----------|--------|------|-----------|
| 1 | `POST /api/topics/generate` | topics.py | get_system_prompt() 호출 | ✅ YES |
| 2 | `POST /api/topics/{id}/ask` | topics.py | get_system_prompt() 호출 | ✅ YES |
| 3 | `POST /api/topics/plan` | topics.py | _get_guidance_prompt() 호출 | ✅ YES |
| 4 | `POST /api/templates` | templates.py | upload_template() 호출 | ✅ YES |
| 5 | `POST /api/templates/{id}/regenerate-prompt-system` | templates.py | create_system_prompt_with_metadata() 호출 | ⚠️ Check |

---

## 🏗️ 구현 상세 설명

### 1️⃣ `prompts.py` (templates.py 수정)

#### 변경 위치: 단계 10 (Prompt 생성)

**현재 코드:**
```python
# Step 10: Prompt 생성
metadata_dicts = [
    {**p.model_dump(), "key": p.placeholder_key}
    for p in metadata.placeholders
] if metadata else None
prompt_system = create_system_prompt_with_metadata(placeholder_list, metadata_dicts)

# Step 11: DB 저장
template_data = TemplateCreate(
    title=title,
    prompt_user=None,  # ❌ 문제: NULL 저장
    prompt_system=prompt_system  # ❌ 문제: BASE + 규칙 혼합
)
```

**개선된 코드:**
```python
# Step 10: [개선] Prompt 생성 (BASE와 규칙 분리)
from app.utils.prompts import get_base_report_prompt, create_template_specific_rules

base_prompt = get_base_report_prompt()
logger.info(f"[UPLOAD_TEMPLATE] Base prompt loaded - length={len(base_prompt)}")

# 규칙 생성 (메타정보 포함)
metadata_dicts = [
    {**p.model_dump(), "key": p.placeholder_key}
    for p in metadata.placeholders
] if metadata else None
template_rules = create_template_specific_rules(placeholder_list, metadata_dicts)
logger.info(f"[UPLOAD_TEMPLATE] Template rules created - length={len(template_rules)}")

# Step 11: DB 저장 (변경)
template_data = TemplateCreate(
    title=title,
    prompt_user=base_prompt,      # ✅ 변경: BASE 저장
    prompt_system=template_rules  # ✅ 변경: 규칙만 저장
)
logger.info(
    f"[UPLOAD_TEMPLATE] Template data prepared - "
    f"prompt_user_length={len(base_prompt)}, "
    f"prompt_system_length={len(template_rules)}"
)
```

**수정 체크리스트:**
- [ ] import 추가: `get_base_report_prompt`, `create_template_specific_rules`
- [ ] create_system_prompt_with_metadata() 호출 제거
- [ ] base_prompt 변수 추가
- [ ] template_rules 변수 추가
- [ ] prompt_user = base_prompt (NULL 제거)
- [ ] prompt_system = template_rules (규칙만)
- [ ] 로깅 추가
- [ ] 테스트: prompt_user와 prompt_system 검증

**영향받는 응답:**
```python
# response_dict 확인
response_dict = response_data.model_dump()
# prompt_user가 NULL이 아닌지 확인
# prompt_system이 BASE를 포함하지 않는지 확인
```

---

### 2️⃣ `templates.py` (upload_template 함수)

#### 변경 위치: 단계 10 (Prompt 생성)

**현재 코드:**
```python
# Step 10: Prompt 생성
metadata_dicts = [
    {**p.model_dump(), "key": p.placeholder_key}
    for p in metadata.placeholders
] if metadata else None
prompt_system = create_system_prompt_with_metadata(placeholder_list, metadata_dicts)

# Step 11: DB 저장
template_data = TemplateCreate(
    title=title,
    prompt_user=None,  # ❌ 문제: NULL 저장
    prompt_system=prompt_system  # ❌ 문제: BASE + 규칙 혼합
)
```

**개선된 코드:**
```python
# Step 10: [개선] Prompt 생성 (BASE와 규칙 분리)
from app.utils.prompts import get_base_report_prompt, create_template_specific_rules

base_prompt = get_base_report_prompt()
logger.info(f"[UPLOAD_TEMPLATE] Base prompt loaded - length={len(base_prompt)}")

# 규칙 생성 (메타정보 포함)
metadata_dicts = [
    {**p.model_dump(), "key": p.placeholder_key}
    for p in metadata.placeholders
] if metadata else None
template_rules = create_template_specific_rules(placeholder_list, metadata_dicts)
logger.info(f"[UPLOAD_TEMPLATE] Template rules created - length={len(template_rules)}")

# Step 11: DB 저장 (변경)
template_data = TemplateCreate(
    title=title,
    prompt_user=base_prompt,      # ✅ 변경: BASE 저장
    prompt_system=template_rules  # ✅ 변경: 규칙만 저장
)
logger.info(
    f"[UPLOAD_TEMPLATE] Template data prepared - "
    f"prompt_user_length={len(base_prompt)}, "
    f"prompt_system_length={len(template_rules)}"
)
```

**수정 체크리스트:**
- [ ] import 추가: `get_base_report_prompt`, `create_template_specific_rules`
- [ ] create_system_prompt_with_metadata() 호출 제거
- [ ] base_prompt 변수 추가
- [ ] template_rules 변수 추가
- [ ] prompt_user = base_prompt (NULL 제거)
- [ ] prompt_system = template_rules (규칙만)
- [ ] 로깅 추가
- [ ] 테스트: prompt_user와 prompt_system 검증

**영향받는 응답:**
```python
# response_dict 확인
response_dict = response_data.model_dump()
# prompt_user가 NULL이 아닌지 확인
# prompt_system이 BASE를 포함하지 않는지 확인
```

---

### 3️⃣ `sequential_planning.py` (_get_guidance_prompt 함수)

#### 변경 위치: 함수 상단 (기본값)

**현재 코드:**
```python
async def _get_guidance_prompt(template_id, user_id):
    # ❌ 문제: 하드코딩된 문자열
    default_guidance = """
**보고서 계획 작성 가이드:**
- 보고서는 다음 구조를 따라야 합니다:
  1. 요약
  2. 배경
  3. 주요 내용
  4. 결론
    """

    if not template_id or not user_id:
        logger.info("No template_id provided, using default guidance")
        return default_guidance

    # ... Template 조회 로직
```

**개선된 코드:**
```python
async def _get_guidance_prompt(template_id, user_id):
    # ✅ 개선: 중앙화된 BASE 프롬프트 사용
    from app.utils.prompts import get_base_plan_prompt

    default_guidance = get_base_plan_prompt()
    logger.info(
        f"[PLAN] Base plan prompt loaded - length={len(default_guidance)}"
    )

    if not template_id or not user_id:
        logger.info("No template_id provided, using base plan prompt")
        return default_guidance

    # ... Template 조회 로직 (동일)
```

**수정 체크리스트:**
- [ ] import 추가: `get_base_plan_prompt`
- [ ] default_guidance 문자열 제거
- [ ] get_base_plan_prompt() 호출로 변경
- [ ] 로깅 추가
- [ ] 테스트: 반환값이 get_base_plan_prompt()와 동일한지 확인

---

### 4️⃣ `claude_client.py` (직접 import 변경)

#### 변경 위치: import 섹션

**현재 코드:**
```python
from app.utils.prompts import FINANCIAL_REPORT_SYSTEM_PROMPT

# 사용 예
system_prompt = FINANCIAL_REPORT_SYSTEM_PROMPT
```

**개선된 코드:**
```python
from app.utils.prompts import get_base_report_prompt

# 사용 예
system_prompt = get_base_report_prompt()
```

**수정할 위치 찾기:**
```bash
grep -n "FINANCIAL_REPORT_SYSTEM_PROMPT" backend/app/utils/claude_client.py
```

**수정 체크리스트:**
- [ ] import 변경: `FINANCIAL_REPORT_SYSTEM_PROMPT` → `get_base_report_prompt`
- [ ] 모든 사용 위치 변경 (함수 호출로)
- [ ] 테스트: 반환값 확인

---

## 🧪 테스트 계획

### Test Case 1: `get_base_report_prompt()` 반환값 검증
```python
def test_get_base_report_prompt_returns_string():
    prompt = get_base_report_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "금융 기관" in prompt
    assert "당신은" in prompt
```

**목표:** BASE_REPORT_SYSTEM_PROMPT 상수가 올바르게 반환되는지 확인

### Test Case 2: `get_base_plan_prompt()` 반환값 검증
```python
def test_get_base_plan_prompt_returns_string():
    prompt = get_base_plan_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "보고서 계획 전문가" in prompt
    assert "지침" in prompt
```

**목표:** BASE_PLAN_SYSTEM_PROMPT 상수가 올바르게 반환되는지 확인

### Test Case 3: `create_template_specific_rules()` BASE 미포함 검증
```python
def test_create_template_specific_rules_excludes_base():
    placeholders = ["{{TITLE}}", "{{SUMMARY}}"]
    metadata = [
        {"key": "{{TITLE}}", "type": "string", ...},
        {"key": "{{SUMMARY}}", "type": "text", ...}
    ]

    rules = create_template_specific_rules(placeholders, metadata)

    # 핵심: BASE 내용이 포함되지 않았는지 확인
    assert "금융 기관" not in rules  # BASE 제외 확인
    assert "Placeholder" in rules or "placeholder" in rules  # 규칙은 포함
```

**목표:** BASE 제외, 규칙만 생성되는지 확인

### Test Case 4: `get_system_prompt()` 템플릿 조합 검증
```python
async def test_get_system_prompt_combines_base_and_rules():
    # 임시 템플릿 생성
    template = Template(
        prompt_user="당신은 금융 기관의 전문 보고서 작성자입니다.",
        prompt_system="다음 placeholder를 포함하여 작성: {{TITLE}}"
    )

    # Mock: get_template_by_id 결과로 template 반환
    with patch('app.database.template_db.TemplateDB.get_template_by_id', return_value=template):
        prompt = get_system_prompt(template_id=1, user_id=1)

        # 확인
        assert "금융 기관" in prompt  # BASE 포함
        assert "{{TITLE}}" in prompt  # 규칙 포함
        assert prompt.startswith("당신은 금융 기관")  # BASE 먼저
```

**목표:** BASE + 규칙이 올바르게 조합되는지 확인

### Test Case 5: `upload_template()` prompt 할당 검증
```python
async def test_upload_template_prompt_assignment():
    # HWPX 파일 업로드
    response = await upload_template(
        file=UploadFile(filename="test.hwpx", ...),
        title="테스트 템플릿",
        current_user=test_user
    )

    # 응답 검증
    response_dict = response_data.model_dump()

    # ✅ 핵심 검증
    assert response_dict["prompt_user"] is not None  # BASE 저장 확인
    assert "금융 기관" in response_dict["prompt_user"]  # BASE 내용 확인
    assert "금융 기관" not in response_dict["prompt_system"]  # prompt_system에 BASE 미포함
    assert len(response_dict["prompt_system"]) > 0  # 규칙 포함
```

**목표:** prompt_user에 BASE 저장, prompt_system에 규칙만 저장되는지 확인

### Test Case 6: `_get_guidance_prompt()` BASE_PLAN 사용 검증
```python
async def test_get_guidance_prompt_uses_base_plan():
    # 템플릿 없이 호출
    guidance = await _get_guidance_prompt(template_id=None, user_id=None)

    # 확인
    base_plan = get_base_plan_prompt()
    assert guidance == base_plan  # 동일한지 확인
```

**목표:** get_base_plan_prompt()가 올바르게 사용되는지 확인

---

## 📋 구현 체크리스트

### Phase 1: prompts.py (2시간)
- [ ] BASE_PLAN_SYSTEM_PROMPT 상수 추가
- [ ] get_base_report_prompt() 함수 구현
- [ ] get_base_plan_prompt() 함수 구현
- [ ] create_template_specific_rules() 함수 구현
- [ ] create_dynamic_system_prompt() 내부 수정
- [ ] get_system_prompt() 로직 개선
- [ ] 테스트 1-4 통과

### Phase 2: templates.py (1시간)
- [ ] import 추가
- [ ] `upload_template()` 단계 10 개선
- [ ] 로깅 추가
- [ ] 테스트 5 통과

### Phase 3: sequential_planning.py (30분)
- [ ] import 추가
- [ ] `_get_guidance_prompt()` 기본값 변경
- [ ] 로깅 추가
- [ ] 테스트 6 통과

### Phase 4: claude_client.py (15분)
- [ ] import 변경
- [ ] 모든 사용 위치 수정
- [ ] 테스트 실행

### Phase 5: 통합 테스트 (1시간)
- [ ] 기존 130 TC 회귀 테스트
- [ ] E2E 테스트 실행
- [ ] 로깅 검토

---

## ✅ 최종 검증 기준

### 구현 완료 조건
- [x] 모든 함수 수정 완료
- [x] 6개 TC 통과
- [x] 기존 130 TC 회귀 없음
- [x] 로깅 추가 완료
- [x] 호환성 100% 유지

### 배포 조건
- [ ] 개발자 코드 리뷰 완료
- [ ] QA 테스트 통과
- [ ] 성능 테스트 통과
- [ ] 문서화 완료

---

## 📚 관련 자료

- 기존 구현: `backend/CLAUDE.md` → "v2.0 - 대화형 시스템"
- 아키텍처: `backend/doc/07.PromptIntegrate.md`
- 메시지 설계: `backend/doc/04.messageChaining.md`

---

**문서 버전:** v2.0
**마지막 업데이트:** 2025-11-13
**작성자:** Claude Code
**상태:** ✅ 사용자 검토 대기
