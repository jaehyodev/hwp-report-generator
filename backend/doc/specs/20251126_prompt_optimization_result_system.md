# Unit Spec: 프롬프트 고도화 시스템 (Prompt Optimization Result)

## 1. 요구사항 요약

- **목적:** 사용자의 초기 프롬프트를 Claude AI가 분석·최적화하여 생성된 고도화 결과(역할, 맥락, 작업)를 저장하고, 보고서 생성 시 이를 활용하여 Claude API 입력 파라미터를 자동 생성하는 시스템 구축
- **유형:** ☑️ 신규
- **핵심 요구사항:**
  - **입력:** user_prompt (사용자가 입력한 원문), topic_id, template_id (선택)
  - **출력:**
    - 고도화 결과 저장 (DB: prompt_optimization_result 테이블)
    - Claude API 호출용 payload 자동 생성 (system + user 메시지)
  - **예외/제약:**
    - 고도화 결과는 **불변**이며, role/context/task만 수동 보정 가능
    - 관리용 조회 API 필요 (최신 결과 + 이력)
    - 토픽 삭제 시 고도화 결과도 자동 삭제 (CASCADE)
    - 성능: 고도화 호출 < 30초, 조회 < 500ms
  - **처리흐름 요약:**
    1. 사용자 초기 입력 → Claude "프롬프트 고도화" 호출 (새로운 엔드포인트)
    2. Claude 응답 파싱 (hidden_intent, underlying_purpose, role, context, task)
    3. 고도화 결과 저장 (prompt_optimization_result 테이블)
    4. 향후 보고서 생성 시 고도화 결과 조회 및 활용
    5. 파라미터 맵핑 함수로 Claude API payload 자동 생성

---

## 2. 구현 대상 파일

| 구분 | 경로                                       | 설명                                      |
| ---- | ------------------------------------------ | ----------------------------------------- |
| 신규 | backend/app/models/prompt_optimization.py | Pydantic 모델 (생성/응답/업데이트)        |
| 신규 | backend/app/database/prompt_optimization_db.py | DB CRUD 모듈                             |
| 신규 | backend/app/utils/prompt_optimizer.py     | 고도화 로직 (Claude 호출, 파싱, 파라미터 맵핑) |
| 신규 | backend/tests/test_prompt_optimization.py | 단위/통합/API 테스트                      |
| 변경 | backend/app/database/connection.py        | 새 테이블 생성 (init_db())                 |
| 변경 | backend/app/routers/topics.py             | 신규 엔드포인트 (POST, GET 최적화 결과)   |
| 변경 | backend/app/utils/prompts.py              | 고도화 프롬프트 상수 추가                  |
| 참조 | backend/app/utils/claude_client.py        | Claude API 호출 구조 참고                 |
| 참조 | backend/app/utils/response_helper.py      | ErrorCode, response 형식 참고             |

---

## 3. 동작 플로우 (Mermaid)

### 3.1 고도화 결과 생성 흐름

```mermaid
flowchart TD
    A[Client] -->|POST /api/topics/[id]/optimize-prompt<br/>Body: user_prompt| B{Topic 존재?}
    B -- No --> C["404 NOT_FOUND<br/>(TOPIC.NOT_FOUND)"]
    B -- Yes --> D{권한 확인<br/>topic.user_id == current_user.id?}
    D -- No --> E["403 FORBIDDEN<br/>(TOPIC.UNAUTHORIZED)"]
    D -- Yes --> F["Claude API 호출<br/>(프롬프트 고도화)"]
    F --> G{응답 파싱<br/>유효한 JSON?}
    G -- No --> H["504 GATEWAY_TIMEOUT<br/>또는 500 ERROR"]
    G -- Yes --> I["필드 추출<br/>(hidden_intent, role, context, task 등)"]
    I --> J["DB 저장<br/>(prompt_optimization_result 테이블)"]
    J --> K["200 OK<br/>+ PromptOptimizationResponse"]

    style A fill:#e1f5ff
    style K fill:#c8e6c9
    style C fill:#ffcdd2
    style E fill:#ffcdd2
    style H fill:#ffcdd2
```

### 3.2 고도화 결과 활용 흐름 (보고서 생성)

```mermaid
flowchart TD
    A[Client] -->|POST /api/topics/[id]/generate<br/>또는 POST /api/topics/[id]/ask| B["generate_topic_report()"]
    B --> C["고도화 결과 조회<br/>prompt_optimization_db.get_latest()"]
    C --> D{결과 존재?}
    D -- No --> E["기본 프롬프트 사용<br/>(현재 동작)"]
    D -- Yes --> F["파라미터 맵핑<br/>map_optimized_to_claude_payload()"]
    F --> G["Claude API Payload 생성<br/>system = role + context<br/>user = task + original_user_prompt"]
    G --> H["Claude API 호출<br/>(구조화된 payload 사용)"]
    H --> I["보고서 생성<br/>(마크다운)"]
    E --> H

    style A fill:#e1f5ff
    style I fill:#c8e6c9
    style F fill:#fff9c4
```

### 3.3 조회 흐름 (이력)

```mermaid
flowchart TD
    A[Client] -->|GET /api/topics/[id]/optimization-result| B{Topic 존재?}
    B -- No --> C["404 NOT_FOUND"]
    B -- Yes --> D{권한 확인?}
    D -- No --> E["403 FORBIDDEN"]
    D -- Yes --> F["최신 고도화 결과 조회<br/>(created_at DESC LIMIT 1)"]
    F --> G["200 OK<br/>+ PromptOptimizationResponse"]

    style A fill:#e1f5ff
    style G fill:#c8e6c9
```

---

## 4. 데이터 모델 정의

### 4.1 DB 테이블 스키마

```sql
CREATE TABLE IF NOT EXISTS prompt_optimization_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,

    -- 입력값 (사용자 요청)
    user_prompt TEXT NOT NULL,

    -- 분석 결과 (숨겨진 의도)
    hidden_intent TEXT,
    emotional_needs JSON,
    underlying_purpose TEXT,

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
);

-- 성능: topic_id + created_at DESC로 최신 결과 빠르게 조회
CREATE INDEX idx_optimization_topic_date
    ON prompt_optimization_result(topic_id, created_at DESC);
```

### 4.2 Pydantic 모델

```python
# 생성 요청
class PromptOptimizationCreate(BaseModel):
    user_prompt: str = Field(..., min_length=10, max_length=5000, description="고도화 요청 사용자 입력")
    # template_id, model_name 등은 선택 사항 (향후 확장)

# 응답 (조회)
class PromptOptimizationResponse(BaseModel):
    id: int
    topic_id: int
    user_prompt: str

    hidden_intent: Optional[str] = None
    emotional_needs: Optional[Dict[str, Any]] = None
    underlying_purpose: Optional[str] = None

    role: str
    context: str
    task: str

    model_name: str
    latency_ms: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 업데이트 (부분 수정)
class PromptOptimizationUpdate(BaseModel):
    role: Optional[str] = None
    context: Optional[str] = None
    task: Optional[str] = None
    model_name: Optional[str] = None

# Claude API Payload 생성용 (내부)
class ClaudePayload(BaseModel):
    model: str
    system: str
    messages: List[Dict[str, str]]
    temperature: float = 0.1
    max_tokens: int = 4096
```

---

## 5. API 엔드포인트 정의

### 5.1 POST /api/topics/{topic_id}/optimize-prompt

**프롬프트 고도화 실행 (새로운 엔드포인트)**

#### 요청 (Request)
```http
POST /api/topics/123/optimize-prompt
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "user_prompt": "우리 회사의 2025년 재무 상황을 분석한 보고서를 작성해줄 수 있을까?"
}
```

#### 응답 - 성공 (200 OK)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "topic_id": 123,
    "user_prompt": "우리 회사의 2025년 재무 상황을 분석한 보고서...",
    "hidden_intent": "경영진 보고용 신뢰성 있는 재무 분석",
    "emotional_needs": {
      "formality": "professional",
      "confidence_level": "high",
      "decision_focus": "investment_strategy"
    },
    "underlying_purpose": "투자 의사결정을 위한 객관적 재무 현황 파악",
    "role": "금융 전문가이자 재무분석 컨설턴트",
    "context": "회사의 2025년 상반기 재무제표, 산업 동향, 경쟁사 현황을 고려하여...",
    "task": "다음 단계를 따라 보고서를 작성하세요:\n1. 현재 재무상태 분석\n2. 주요 지표 해석\n3. 리스크 요인 평가\n4. 개선 방안 제시",
    "model_name": "claude-sonnet-4-5-20250929",
    "latency_ms": 2450,
    "created_at": "2025-11-26T10:30:00Z",
    "updated_at": "2025-11-26T10:30:00Z"
  },
  "error": null,
  "meta": {"requestId": "req_abc123"}
}
```

#### 응답 - 오류 (4xx/5xx)
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "TOPIC.NOT_FOUND",
    "message": "토픽을 찾을 수 없습니다."
  },
  "meta": {"requestId": "req_def456"}
}
```

#### 상태 코드 및 에러

| 상태 | 에러코드 | 설명 |
|-----|---------|------|
| 200 | (성공) | 고도화 완료 |
| 400 | VALIDATION_ERROR | user_prompt 필드 누락 또는 형식 오류 |
| 401 | AUTH.UNAUTHORIZED | 인증 토큰 없음 또는 유효하지 않음 |
| 403 | TOPIC.UNAUTHORIZED | 사용자가 토픽의 소유자가 아님 |
| 404 | TOPIC.NOT_FOUND | 토픽 ID 존재하지 않음 |
| 504 | OPTIMIZATION.TIMEOUT | Claude API 호출 30초 이상 소요 |
| 500 | OPTIMIZATION.ERROR | Claude 응답 파싱 실패 또는 내부 오류 |

---

### 5.2 GET /api/topics/{topic_id}/optimization-result

**최신 고도화 결과 조회**

#### 요청 (Request)
```http
GET /api/topics/123/optimization-result
Authorization: Bearer <JWT_TOKEN>
```

#### 응답 - 성공 (200 OK)
```json
{
  "success": true,
  "data": {
    "id": 1,
    "topic_id": 123,
    "user_prompt": "우리 회사의 2025년...",
    "hidden_intent": "경영진 보고용 신뢰성 있는 재무 분석",
    ...
  },
  "error": null,
  "meta": {"requestId": "req_xyz789"}
}
```

#### 응답 - 결과 없음 (200 OK, data: null)
```json
{
  "success": true,
  "data": null,
  "error": null,
  "meta": {"requestId": "req_xyz790"}
}
```

#### 응답 - 오류 (4xx)
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "TOPIC.UNAUTHORIZED",
    "message": "이 토픽에 대한 접근 권한이 없습니다."
  },
  "meta": {"requestId": "req_xyz791"}
}
```

---

## 6. 함수 설계

### 6.1 prompt_optimizer.py (신규 유틸)

```python
# Claude 고도화 호출
async def optimize_prompt_with_claude(
    user_prompt: str,
    topic_id: int,
    model: str = "claude-sonnet-4-5-20250929"
) -> Dict[str, Any]:
    """
    사용자 프롬프트를 Claude로 고도화합니다.

    Returns:
        {
            "hidden_intent": str,
            "emotional_needs": Dict,
            "underlying_purpose": str,
            "role": str,
            "context": str,
            "task": str
        }

    Raises:
        TimeoutError: 30초 초과
        ValueError: JSON 파싱 실패
    """

# 파라미터 맵핑
def map_optimized_to_claude_payload(
    optimization_result: PromptOptimizationResponse,
    original_user_prompt: str,
    model: Optional[str] = None
) -> ClaudePayload:
    """
    고도화 결과를 Claude API Payload로 변환합니다.

    규칙:
    - system = "{role}\n\n# CONTEXT\n{context}"
    - user = "아래 작업을 수행하세요:\n\n{task}\n\n---\n\n원래 요청: {original_user_prompt}"
    - model = optimization_result.model_name 또는 입력값 override
    - temperature = 0.1 (구조적 안정성)
    - max_tokens = 4096 (기본값)

    Raises:
        ValueError: role, context, task 필드 누락
    """

# 로깅 헬퍼 (개인정보 보호)
def mask_sensitive_prompt(prompt: str, max_chars: int = 100) -> str:
    """프롬프트를 로깅 시 마스킹합니다."""
```

### 6.2 prompt_optimization_db.py (신규 CRUD)

```python
class PromptOptimizationDB:
    @staticmethod
    def create(
        topic_id: int,
        user_id: int,
        user_prompt: str,
        hidden_intent: Optional[str],
        emotional_needs: Optional[Dict],
        underlying_purpose: Optional[str],
        role: str,
        context: str,
        task: str,
        model_name: str,
        latency_ms: int
    ) -> int:
        """새 고도화 결과 저장. 반환: id"""

    @staticmethod
    def get_latest_by_topic(topic_id: int) -> Optional[Dict]:
        """최신 고도화 결과 조회 (created_at DESC LIMIT 1)"""

    @staticmethod
    def update(
        id: int,
        role: Optional[str] = None,
        context: Optional[str] = None,
        task: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> bool:
        """고도화 결과 부분 수정. 반환: 성공 여부"""

    @staticmethod
    def delete_by_topic(topic_id: int) -> int:
        """토픽의 모든 고도화 결과 삭제. 반환: 삭제된 행 수"""
```

---

## 7. 테스트 계획

### 7.1 테스트 원칙

- **TDD**: 본 섹션의 모든 TC를 코드 작성 전에 먼저 구현
- **계층별**: Unit (함수) → Integration (DB) → API (E2E-lite)
- **독립성**: Claude 호출은 Mock 사용
- **커버리지**: 최소 80% 이상

### 7.2 테스트 케이스

| TC ID | 계층 | 시나리오 | 목적 | 입력/사전조건 | 기대결과 |
|-------|------|---------|------|-------------|---------|
| **TC-API-001** | API | 고도화 성공 | POST 엔드포인트 계약 검증 | topic_id=123, user_prompt="재무분석..." | 200, PromptOptimizationResponse 스키마 일치 |
| **TC-API-002** | API | 입력 누락 (Validation) | 필드 검증 | user_prompt 필드 없음 | 400, code="VALIDATION_ERROR" |
| **TC-API-003** | API | Topic 미존재 | 404 처리 | topic_id=99999 (없는 ID) | 404, code="TOPIC.NOT_FOUND" |
| **TC-API-004** | API | 권한 없음 | 403 처리 (다른 사용자 토픽) | 다른 user의 topic_id | 403, code="TOPIC.UNAUTHORIZED" |
| **TC-API-005** | API | GET 최신 결과 조회 | 조회 엔드포인트 계약 | topic_id=123 (고도화 결과 존재) | 200, PromptOptimizationResponse 포함 |
| **TC-API-006** | API | GET 결과 없음 | 조회 시 데이터 없음 | topic_id=456 (고도화 아직 안 함) | 200, data=null |
| **TC-UNIT-007** | Unit | Claude 응답 파싱 성공 | JSON 파싱 로직 | Claude 응답 (정상 JSON) | 역할, 맥락, 작업 필드 추출 성공 |
| **TC-UNIT-008** | Unit | Claude 응답 파싱 실패 | 오류 처리 | Claude 응답 (잘못된 JSON) | ValueError 발생 |
| **TC-UNIT-009** | Unit | 파라미터 맵핑 성공 | system/user 메시지 조합 | PromptOptimizationResponse + original_prompt | system="role\n\n# CONTEXT\ncontext", user="아래 작업...\ntask" |
| **TC-UNIT-010** | Unit | 파라미터 맵핑 실패 | role/context/task 누락 시 | optimization 객체에서 필드 제거 | ValueError 발생 |
| **TC-INT-011** | Integration | DB 저장 및 조회 | CRUD 일관성 | create → get_latest | 저장된 값과 조회된 값 일치 |
| **TC-INT-012** | Integration | 부분 수정 | UPDATE 로직 | create 후 role/context 수정 | updated_at 갱신됨, 수정된 값 확인 |
| **TC-INT-013** | Integration | CASCADE 삭제 | Topic 삭제 시 고도화 결과도 삭제 | topic 삭제 | 고도화 결과 테이블에서 해당 레코드 없음 |
| **TC-PERF-014** | 성능 | 고도화 호출 타임아웃 | 30초 초과 처리 | Claude 호출이 30초 이상 소요 | 504 GATEWAY_TIMEOUT |
| **TC-PERF-015** | 성능 | 조회 응답시간 | < 500ms 달성 | 인덱스 활용 (topic_id + created_at DESC) | 응답시간 < 500ms (10회 반복 평균) |

---

## 8. 에러 처리 시나리오

### 8.1 입력 검증

| 시나리오 | 입력 | 응답 | 처리 |
|---------|------|------|------|
| user_prompt 누락 | `{}` | 400 VALIDATION_ERROR | Pydantic validation 자동 처리 |
| user_prompt 너무 짧음 | `{"user_prompt": "AI"}` | 400 VALIDATION_ERROR | min_length=10 |
| user_prompt 너무 김 | 5000자 초과 | 400 VALIDATION_ERROR | max_length=5000 |
| topic_id 존재 안 함 | topic_id=99999 | 404 TOPIC.NOT_FOUND | DB 쿼리 확인 후 None 반환 |

### 8.2 권한 검증

| 시나리오 | 조건 | 응답 | 처리 |
|---------|------|------|------|
| 다른 사용자의 토픽 | topic.user_id != current_user.id | 403 TOPIC.UNAUTHORIZED | guard 함수 검사 |
| 인증 토큰 없음 | 헤더에 Authorization 없음 | 401 AUTH.UNAUTHORIZED | Depends(get_current_user) |

### 8.3 Claude API 오류

| 시나리오 | 원인 | 응답 | 처리 |
|---------|------|------|------|
| 응답 파싱 실패 | 잘못된 JSON | 500 OPTIMIZATION.ERROR | try-except + 로그 |
| 30초 초과 | 네트워크 지연 | 504 GATEWAY_TIMEOUT | asyncio.wait_for(timeout=30) |
| Rate Limiting | API 제한 | 429 (Claude API) | 재시도 로직 (선택) |

### 8.4 로깅 및 개인정보

- ✅ 고도화 요청/응답은 **마스킹하여 로깅**
  ```python
  logger.info(f"Optimization requested for topic {topic_id}, prompt: {mask_sensitive_prompt(user_prompt, 50)}")
  ```
- ❌ raw payload는 로그에 출력 금지
- ⚠️ error 로그에만 민감정보 포함 가능 (단, exc_info 로그는 제한)

---

## 9. 구현 체크리스트

### Phase 1: 데이터베이스 및 모델
- [ ] DB 테이블 생성 (connection.py의 init_db())
- [ ] Pydantic 모델 정의 (prompt_optimization.py)
- [ ] 인덱스 추가 (topic_id + created_at DESC)

### Phase 2: DB CRUD
- [ ] prompt_optimization_db.py 구현 (create, get_latest, update, delete)
- [ ] 테스트 TC-INT-011, TC-INT-012, TC-INT-013

### Phase 3: 고도화 로직
- [ ] Claude 호출 함수 (prompt_optimizer.py)
- [ ] JSON 파싱 로직
- [ ] 파라미터 맵핑 함수
- [ ] 테스트 TC-UNIT-007~010, TC-PERF-014~015

### Phase 4: API 엔드포인트
- [ ] POST /api/topics/{id}/optimize-prompt 구현
- [ ] GET /api/topics/{id}/optimization-result 구현
- [ ] 에러 처리 (400, 403, 404, 504)
- [ ] 테스트 TC-API-001~006

### Phase 5: 통합
- [ ] generate_topic_report()에서 고도화 결과 조회 로직 추가
- [ ] 보고서 생성 시 Claude payload 자동 생성
- [ ] 기존 테스트 영향도 확인

### Phase 6: 최종 검증
- [ ] 모든 TC 통과 확인
- [ ] CLAUDE.md 업데이트 (신규 엔드포인트, 모델, DB 추가)
- [ ] 기존 테스트 회귀 확인 (no broken tests)
- [ ] 커밋: Spec + 코드 + 테스트 함께

---

## 10. 기술 상세 사항

### 10.1 Claude 고도화 프롬프트 (prompts.py에 추가)

```python
PROMPT_OPTIMIZATION_PROMPT = """당신은 전문 심리학자이자 고급 프롬프트 엔지니어입니다.
사용자가 제시한 요청을 분석하여 숨겨진 의도, 감정적 니즈, 궁극적 목적을 파악하고,
이를 바탕으로 AI 어시스턴트가 가장 효과적으로 대응할 수 있는 역할, 맥락, 작업을 정의합니다.

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "hidden_intent": "사용자가 명시하지 않은 실제 의도 (1-2줄)",
    "emotional_needs": {
        "formality": "professional|casual|formal",
        "confidence_level": "high|medium|low",
        "decision_focus": "strategic|tactical|informational"
    },
    "underlying_purpose": "상위 목적 (1-2줄)",
    "role": "AI가 맡아야 할 역할 (전문가 설명)",
    "context": "고려해야 할 배경/맥락 (3-5줄)",
    "task": "수행해야 할 구체적 작업 (단계별, 구조화)"
}

---

## 사용자 요청 (분석 대상)
{USER_PROMPT}
"""
```

### 10.2 파라미터 맵핑 규칙

```python
def map_optimized_to_claude_payload(
    optimization_result: PromptOptimizationResponse,
    original_user_prompt: str,
    model: Optional[str] = None
) -> ClaudePayload:
    """
    고도화 결과 → Claude API Payload 변환

    System 메시지:
        {role}

        # CONTEXT
        {context}

    User 메시지:
        아래 작업을 수행하세요:

        {task}

        ---

        원래 요청: {original_user_prompt}

    Payload:
        - model: optimization_result.model_name (또는 입력값 override)
        - temperature: 0.1 (구조적 안정성)
        - max_tokens: 4096 (기본값)
    """
```

### 10.3 성능 최적화

1. **DB 인덱스:**
   - `idx_optimization_topic_date`: (topic_id, created_at DESC)
   - 목표: 최신 결과 조회 < 100ms

2. **캐싱 (향후 확장):**
   - 동일 topic_id 반복 조회 시 메모리 캐시 활용
   - TTL: 1시간

3. **타임아웃:**
   - Claude 호출: 30초 (asyncio.wait_for)
   - DB 조회: 5초

---

## 11. 사용자 요청 기록

### 5.1 Original User Request

```
사용자가 제출한 "FastAPI 기반 프롬프트 고도화 시스템 요구사항 요청서"를 기반으로
다음 두 가지 기능을 구현하기를 요청:

1. prompt_optimization_result 모델 생성 및 DB 저장
   - 필드: id, topic_id, user_prompt, hidden_intent, emotional_needs, underlying_purpose,
           role, context, task, model_name, created_at, updated_at
   - 동작: 고도화 결과는 불변이며, role/context/task만 수동 보정 가능
   - 조회: topic_id 기반 최신 결과 조회, 이력 조회 가능

2. Claude API 파라미터 맵핑 함수 개발
   - 입력: optimized_prompt (role, context, task), original_user_prompt, model_name
   - 출력: Claude Messages API Payload (system + user 메시지)
   - 규칙:
     * system = {role} + "\n# CONTEXT\n" + {context}
     * user = "아래 작업을 수행하세요:\n\n" + {task}
     * temperature = 0.1, max_tokens = 4096
```

### 5.2 Claude 응답 (분석)

```
종합 분석 결과:
- 적용 가능성: 7/10 (인프라 기반 O, 설계 충돌 주의 필요)
- 기존 코드 영향도: 6/10 (많은 수정 필요)
- 구현 복잡도: 6/10 (새 테이블, 새 로직, 트랜잭션 처리 필요)

문제점 6가지:
1. 개념 충돌: 현재 prompt_user는 Sequential Planning 결과, 요구사항은 고도화 입력
2. "고도화" 프로세스 부재: Sequential Planning만 있음
3. 기존 코드 통합 복잡성: generate_report 함수 대폭 수정 필요
4. 성능/지연: Claude API 호출 증가 (+10~20초)
5. 데이터 마이그레이션: 기존 테이블 구조 변경 필요
6. 프롬프트 템플릿화: role/context/task 구조화된 저장 필요

권장사항: 시나리오 1 (신규 분리 테이블) 선택
```

### 5.3 User Clarification/Modification

```
사용자: "시나리오 1번(신규 분리 테이블)을 선택할게. 이걸로 unit spec을 만들어줘."
```

### 최종 명확화 (통합)

- ✅ 신규 테이블 `prompt_optimization_result` 생성 (분리 설계)
- ✅ Pydantic 모델: PromptOptimizationCreate, PromptOptimizationResponse, PromptOptimizationUpdate
- ✅ DB CRUD: create, get_latest, update, delete
- ✅ 신규 유틸: prompt_optimizer.py (Claude 호출, 파싱, 파라미터 맵핑)
- ✅ 신규 엔드포인트:
  - POST /api/topics/{id}/optimize-prompt (고도화 실행)
  - GET /api/topics/{id}/optimization-result (최신 결과 조회)
- ✅ 에러 처리: 400 (Validation), 403 (Unauthorized), 404 (NotFound), 504 (Timeout), 500 (Error)
- ✅ 테스트: 15개 TC (API 6개, Unit 4개, Integration 3개, 성능 2개)
- ✅ 문서화: Google 스타일 Docstring, 모든 함수 주석
- ✅ 로깅: 민감정보 마스킹, exc_info=True 사용
- ✅ 성능: 고도화 호출 < 30초, 조회 < 500ms

**요청 일시:** 2025-11-26

**컨텍스트/배경:**
- HWP Report Generator v2.6.0 (Markdown to HWPX 변환 기능 완성)
- 기존: Sequential Planning (보고서 구조 계획), Custom System Prompt (템플릿 기반)
- 신규: 프롬프트 고도화 시스템 추가 (사용자 의도 분석 → role/context/task 생성)
- 우선순위: Unit Spec 우선 작성 → 사용자 승인 → TDD 구현

---

## 12. 비기능 요구사항

### 12.1 성능

| 항목 | 목표 | 검증 방법 |
|-----|------|---------|
| 고도화 호출 | < 30초 | TC-PERF-014 (타임아웃) |
| 조회 응답 | < 500ms | TC-PERF-015 (10회 반복) |
| DB 인덱스 | (topic_id, created_at DESC) | EXPLAIN QUERY PLAN |

### 12.2 보안/개인정보

| 항목 | 규칙 | 구현 |
|-----|------|------|
| 접근 제어 | 자신의 토픽만 조회/수정 | topic.user_id == current_user.id |
| 로그 마스킹 | 민감정보는 마스킹 | mask_sensitive_prompt() |
| CASCADE 삭제 | 토픽 삭제 시 고도화 결과도 삭제 | FOREIGN KEY ... ON DELETE CASCADE |

### 12.3 데이터 일관성

| 항목 | 규칙 | 검증 |
|-----|------|------|
| 불변성 | 고도화 결과는 읽기 전용 (role/context/task만 수정) | UPDATE에서 user_prompt 제외 |
| 타임스탬프 | created_at은 변경 안 함, updated_at만 갱신 | 부분 수정 시 TC-INT-012 |
| 외래키 | topic_id 삭제 시 자동 삭제 | TC-INT-013 |

---

## 13. 의존성 및 외부 라이브러리

- **anthropic**: Claude API 호출 (이미 설치)
- **pydantic**: 데이터 검증 (이미 설치)
- **fastapi**: 라우터 및 응답 (이미 설치)
- **sqlite3**: DB (Python 표준 라이브러리)

**추가 설치 필요:** 없음

---

## 14. 참고자료

- 요구사항 원본: "FastAPI 기반 프롬프트 고도화 시스템 요구사항 요청서"
- 분석 보고서: "프롬프트 고도화 시스템 - 프로젝트 적용 가능성 분석" (2025-11-26)
- CLAUDE.md: Backend 개발 가이드라인
- BACKEND_TEST.md: 테스트 작성 가이드
- Backend_UnitSpec.md: Unit Spec 템플릿

---

**작성:** Claude Code
**날짜:** 2025-11-26
**버전:** 1.0
**상태:** 📋 검토 대기 중 (사용자 승인 필요)
