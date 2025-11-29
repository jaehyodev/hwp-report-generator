# Unit Spec: Structured Outputs JSON Schema additionalProperties 필수 요구사항 반영

**버전:** 1.0
**작성일:** 2025-11-29
**대상:** Claude API Structured Outputs Beta
**우선순위:** CRITICAL (API 호출 실패 상황)

---

## 1. 요구사항 요약

### Purpose
Anthropic Claude API의 **Structured Outputs** 기능에서 모든 `object` 타입 정의에 **명시적으로 `additionalProperties: false`를 요구**하는 공식 사양을 준수하여, 현재 발생하는 400 Bad Request 에러를 해결합니다.

### Type
버그 수정 (Bug Fix)

### Core Requirements

1. **metadata 필드 수정 (긴급)**
   - 현재: `type: ["object", "null"]` + `additionalProperties` 미설정
   - 수정: `type: ["object", "null"]` + `additionalProperties: false` 명시

2. **metadata 구조 상세 정의**
   - `properties` 블록 추가
   - 기본 메타데이터 필드 정의:
     - `generated_at` (string, ISO-8601): 보고서 생성 시각
     - `model` (string): 사용된 Claude 모델명
     - `topic` (string): 보고서 주제
     - `total_sections` (integer): 섹션 개수

3. **전체 JSON Schema 검증**
   - Root object: `additionalProperties: false` ✅ (이미 있음)
   - `sections.items` (object): `additionalProperties: false` ✅ (이미 있음)
   - `metadata` (object): `additionalProperties: false` ✅ (추가 필요)

4. **API 호출 패턴 유지**
   - `client.beta.messages.create()` 호출 패턴 그대로 유지
   - `betas: ["structured-outputs-2025-11-13"]` 파라미터 유지
   - `output_format` 파라미터 사용 (response_format 아님)

### Error Context
```
HTTP 400 Bad Request
error message: "output_format.schema: For 'object' type, 'additionalProperties' must be explicitly set to false"
```

---

## 2. 구현 대상 파일

| 파일명 | 상태 | 변경 내용 |
|--------|------|---------|
| `backend/app/utils/structured_client.py` | **Change** | `_build_json_schema()` 메서드 수정 (Line 204-247) |

### 상세 변경 위치

**함수:** `StructuredClaudeClient._build_json_schema()`
**라인:** 126-247

**변경 구간:**
```python
# Line 204-207 (현재 - ❌ 불완전)
"metadata": {
    "type": ["object", "null"],
    "description": "메타데이터 (생성일, 모델 등)"
}

# Line 204-220 (변경 후 - ✅ 완전)
"metadata": {
    "type": ["object", "null"],
    "description": "보고서 생성 관련 메타데이터",
    "properties": {
        "generated_at": {
            "type": "string",
            "description": "보고서 생성 시각 (ISO-8601 형식)"
        },
        "model": {
            "type": "string",
            "description": "생성에 사용된 Claude 모델명"
        },
        "topic": {
            "type": "string",
            "description": "보고서 주제"
        },
        "total_sections": {
            "type": "integer",
            "description": "섹션 배열의 총 개수"
        }
    },
    "additionalProperties": false  # ⭐ 핵심 추가
}
```

---

## 3. 흐름도

### 현재 문제 (Before)
```
POST /api/topics/{id}/ask
  ├─ StructuredClaudeClient.generate_structured_report()
  ├─ _build_json_schema() 생성
  │  ├─ Root: additionalProperties: false ✅
  │  ├─ sections.items: additionalProperties: false ✅
  │  └─ metadata: ❌ additionalProperties 없음
  ├─ API 호출: client.beta.messages.create(**api_params)
  └─ Error: 400 Bad Request
     └─ "additionalProperties must be explicitly set to false"
```

### 개선된 흐름 (After)
```
POST /api/topics/{id}/ask
  ├─ StructuredClaudeClient.generate_structured_report()
  ├─ _build_json_schema() 생성
  │  ├─ Root: additionalProperties: false ✅
  │  ├─ sections.items: additionalProperties: false ✅
  │  └─ metadata: additionalProperties: false ✅ (추가)
  │     └─ properties: generated_at, model, topic, total_sections
  ├─ API 호출: client.beta.messages.create(**api_params)
  └─ Success: 200 OK
     └─ JSON Response (Schema 검증됨)
```

---

## 4. 최종 JSON Schema 구조 (BASIC 모드 예시)

```json
{
  "type": "object",
  "properties": {
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "id": {
            "type": "string",
            "description": "섹션 ID (예: TITLE, BACKGROUND)"
          },
          "type": {
            "type": "string",
            "enum": ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"],
            "description": "섹션 타입 (고정)"
          },
          "content": {
            "type": "string",
            "description": "섹션 내용"
          },
          "order": {
            "type": "integer",
            "description": "섹션 순서 (1-based)"
          },
          "source_type": {
            "type": "string",
            "enum": ["basic", "system"],
            "description": "섹션 출처"
          },
          "placeholder_key": {
            "type": ["string", "null"],
            "description": "템플릿 placeholder_key ({{KEY}} 형식)"
          }
        },
        "required": ["id", "type", "content", "order", "source_type"],
        "additionalProperties": false
      }
    },
    "metadata": {
      "type": ["object", "null"],
      "description": "보고서 생성 메타데이터",
      "properties": {
        "generated_at": {
          "type": "string",
          "description": "보고서 생성 시각 (ISO-8601 형식)"
        },
        "model": {
          "type": "string",
          "description": "생성에 사용된 Claude 모델명"
        },
        "topic": {
          "type": "string",
          "description": "보고서 주제"
        },
        "total_sections": {
          "type": "integer",
          "description": "섹션 배열의 총 개수"
        }
      },
      "additionalProperties": false
    }
  },
  "required": ["sections"],
  "additionalProperties": false
}
```

---

## 5. 테스트 계획

### TC-001: JSON Schema 빌드 - metadata additionalProperties 검증
- **Scenario:** BASIC 모드에서 JSON Schema 생성
- **Expected:**
  - `schema["properties"]["metadata"]` 존재
  - `schema["properties"]["metadata"]["additionalProperties"]` = `false`
  - `schema["properties"]["metadata"]["properties"]` 존재
  - `properties`에는 `generated_at`, `model`, `topic`, `total_sections` 필드만 정의
- **Files:** `backend/tests/test_structured_outputs_integration.py`

### TC-002: JSON Schema 빌드 - metadata properties 정확성
- **Scenario:** BASIC 모드 metadata properties 생성
- **Expected:**
  - 4개 필드만 정의됨: `generated_at`, `model`, `topic`, `total_sections`
  - 각 필드 `type` 정의됨 (string, string, string, integer)
  - 각 필드 `description` 정의됨
  - max_length, min_length 등 비표준 필드는 포함되지 않음
- **Files:** `backend/tests/test_structured_outputs_integration.py`

### TC-003: JSON Schema 빌드 - TEMPLATE 모드에서도 적용
- **Scenario:** TEMPLATE 모드에서 JSON Schema 생성
- **Expected:**
  - `source_type` enum = `["template", "system"]` (BASIC과 다름)
  - `metadata.additionalProperties` = `false` (동일)
  - `metadata.properties` 동일 구조
- **Files:** `backend/tests/test_structured_outputs_integration.py`

### TC-004: Claude API 호출 - 400 에러 해결 확인
- **Scenario:** StructuredClaudeClient로 실제 API 호출 (Mock)
- **Expected:**
  - Claude API가 200 OK 응답 반환
  - 더 이상 `additionalProperties must be explicitly set to false` 에러 없음
  - Response JSON이 StructuredReportResponse로 파싱 가능
- **Files:** `backend/tests/test_structured_outputs_integration.py`

### TC-005: 기존 기능 회귀 테스트
- **Scenario:** 기존 generate_structured_report() 동작 유지
- **Expected:**
  - sections 배열 정상 생성
  - 각 section의 type, content, order 정상 파싱
  - metadata 필드가 응답에 포함됨
- **Files:** `backend/tests/test_structured_outputs_integration.py`

---

## 6. 에러 처리 시나리오

### Scenario A: metadata 필드가 없는 응답
- **상황:** Claude가 metadata 필드를 생략한 JSON 반환
- **처리:** 응답이 `required: ["sections"]`만 만족하면 유효
- **코드:** Line 476-482 기존 로직 유지 (metadata를 자동으로 생성)

### Scenario B: metadata 필드에 추가 프로퍼티가 있는 응답
- **상황:** Claude가 예상 밖의 필드를 metadata에 추가한 경우
- **처리:** JSON Schema 검증 단계에서 Claude API가 거부 (Structured Outputs)
- **결과:** 400 에러로 명확한 실패 신호 (예측 가능)

### Scenario C: 빈 metadata 또는 null
- **상황:** metadata가 null 또는 빈 객체
- **처리:** 응답 객체에서 적절히 처리 (Line 476-482에서 기본값 사용)
- **결과:** 정상 작동

---

## 7. 코드 변경 상세

### Before (현재 - Line 204-207)
```python
"metadata": {
    "type": ["object", "null"],
    "description": "메타데이터 (생성일, 모델 등)"
}
```

### After (수정 후 - Line 204-220)
```python
"metadata": {
    "type": ["object", "null"],
    "description": "보고서 생성 관련 메타데이터",
    "properties": {
        "generated_at": {
            "type": "string",
            "description": "보고서 생성 시각 (ISO-8601 형식)"
        },
        "model": {
            "type": "string",
            "description": "생성에 사용된 Claude 모델명"
        },
        "topic": {
            "type": "string",
            "description": "보고서 주제"
        },
        "total_sections": {
            "type": "integer",
            "description": "섹션 배열의 총 개수"
        }
    },
    "additionalProperties": False  # ⭐ 핵심: Anthropic Structured Outputs 요구사항
}
```

### 추가 개선사항 (비표준 필드 제거)
sections.items의 properties에서 다음 필드들을 **제거**:
- ~~`max_length`~~ (Anthropic JSON Schema 미지원)
- ~~`min_length`~~ (Anthropic JSON Schema 미지원)
- ~~`description`~~ (섹션 메타에는 불필요)
- ~~`example`~~ (섹션 메타에는 불필요)

**유지하는 필드** (6개):
- `id`, `type`, `content`, `order`, `source_type`, `placeholder_key`

---

## 8. 호환성 검증

| 항목 | 상태 | 설명 |
|------|------|------|
| **기존 응답 형식** | ✅ 호환 | metadata 구조는 변경 없음 (properties 추가만) |
| **API 파라미터** | ✅ 호환 | `client.beta.messages.create()` 패턴 동일 |
| **SectionMetadata 모델** | ✅ 호환 | 변경 없음 |
| **_process_response() 메서드** | ✅ 호환 | metadata 처리 로직 변경 없음 |
| **기존 테스트** | ✅ 호환 | 모든 기존 테스트 통과 예상 |

---

## 9. 구현 체크리스트

- [ ] **Step 1: 코드 수정**
  - [ ] `_build_json_schema()` 메서드의 metadata 정의 업데이트 (Line 204-220)
  - [ ] 설명 주석 추가

- [ ] **Step 2: 테스트 작성**
  - [ ] TC-001: metadata additionalProperties 검증
  - [ ] TC-002: metadata properties 완전성
  - [ ] TC-003: TEMPLATE 모드 검증
  - [ ] TC-004: Claude API 호출 통합 테스트
  - [ ] TC-005: 회귀 테스트

- [ ] **Step 3: 검증**
  - [ ] 모든 테스트 통과 (5/5 TC)
  - [ ] 기존 테스트 회귀 검증
  - [ ] 실제 API 호출 테스트 (Dev 환경)

- [ ] **Step 4: 커밋**
  - [ ] 변경사항 커밋 (structured_client.py 수정)
  - [ ] 테스트 코드 커밋
  - [ ] 이 Unit Spec 문서 포함

---

## 10. 예상 영향 범위

### 영향받는 엔드포인트
- `POST /api/topics/{id}/ask` (Structured Outputs 사용)
- `POST /api/topics/generate` (배경 보고서 생성, 동일 StructuredClaudeClient 사용)

### 영향받는 함수
- `StructuredClaudeClient.generate_structured_report()`
- `StructuredClaudeClient._build_json_schema()` (직접 수정)
- `StructuredClaudeClient._invoke_with_structured_output()` (간접: API 호출 성공)

### 영향받지 않는 항목
- `ClaudeClient` (기존 클라이언트)
- `topics.py` 라우터 로직
- 데이터베이스 스키마
- 프론트엔드

---

## 11. 기술 스택

| 항목 | 값 |
|------|-----|
| **Python** | 3.12 |
| **Framework** | FastAPI |
| **API** | Anthropic Claude API (Structured Outputs Beta) |
| **SDK** | anthropic >= 0.71.0 |
| **Test Framework** | pytest, pytest-asyncio |

---

## 12. 참고 자료

- **Anthropic 공식 문서:** https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- **JSON Schema Draft 2020-12:** https://json-schema.org/
- **현재 파일:** `backend/app/utils/structured_client.py` (Line 126-247)
- **관련 모델:** `backend/app/models/report_section.py` (StructuredReportResponse)
- **관련 라우터:** `backend/app/routers/topics.py` (ask, generate)

---

## 검토 사항

### 이 Spec에 대해 사용자가 확인할 항목:

1. **요구사항이 명확한가?**
   - metadata에 additionalProperties: false 추가
   - metadata.properties에 4개 기본 필드 정의

2. **테스트 케이스가 충분한가?**
   - 5개 TC로 충분한지 (Schema 검증, API 호출, 회귀)

3. **구현 범위가 명확한가?**
   - structured_client.py 단 1개 파일만 수정
   - Line 204-220 범위

4. **호환성 영향이 없는가?**
   - 기존 응답 형식 변경 없음
   - API 패턴 변경 없음

### 수정이 필요한 부분이 있나요? 아니면 구현을 진행해도 될까요?
