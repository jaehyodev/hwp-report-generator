# Phase 2 작업 영향도 분석 및 테스트 대상 API 리스트

**작성일**: 2025-11-14
**상태**: 완료된 작업 분석 문서
**대상**: Phase 2 Task 5-8 (Artifact 기반 상태 관리 + Non-Blocking + generation_status 제거)

---

## 1. Phase 2 완료된 작업 요약

### Task 5: POST /generate → 202 Accepted + 백그라운드 작업
- **변경사항**: 동기식 생성 → 비동기 백그라운드 task
- **응답**: 200 OK (blocking) → 202 Accepted (non-blocking)
- **Artifact 상태**: 즉시 생성 (status="scheduled") → 백그라운드에서 상태 업데이트
- **영향 범위**: ⭐⭐⭐ (크기: 높음)

### Task 6: POST /ask → asyncio.to_thread() + Artifact 상태 머신
- **변경사항**: 모든 동기 작업을 비동기로 래핑
- **Artifact 생성**: MD artifact만 (HWPX는 보류)
- **응답 구조**: 변경 없음
- **영향 범위**: ⭐⭐ (중간)

### Task 7: GET /status, GET /status/stream → Artifact 테이블 직접 조회
- **변경사항**: generation_status.py 메모리 기반 → ArtifactDB 테이블 조회
- **응답 구조**: 동일
- **영향 범위**: ⭐ (낮음, 내부 구현 변경)

### Task 8: generation_status.py 의존성 제거
- **변경사항**: topics.py에서 legacy 함수 호출 제거
- **파일 보관**: generation_status.py는 유지 (Phase 1 호환성용)
- **영향 범위**: ⭐⭐ (내부 정리)

---

## 2. 영향도 분석

### 2.1 DB 스키마 변경
❌ **변경 없음** - artifacts 테이블 구조 동일

### 2.2 API 응답 구조 변경
| API | 변경 | 상세 |
|-----|------|------|
| POST /generate | ❌ No | 202 Accepted 추가, 응답 구조 동일 |
| POST /ask | ✅ Partial | artifact 구조는 동일, 저장 방식만 변경 |
| GET /status | ❌ No | 응답 구조 동일 (데이터 소스만 변경) |
| GET /status/stream | ❌ No | SSE 스트림 동일 (폴링 방식만 변경) |

### 2.3 비동기 처리 영향
| 컴포넌트 | 변경 | 영향 |
|---------|------|------|
| Event Loop | ⭐⭐ | asyncio.to_thread() 도입으로 모든 DB/File I/O가 별도 스레드 실행 |
| Response Time | ⭐⭐⭐ | POST /generate는 < 1초, POST /ask는 비슷 (스레드 풀 사용) |
| Concurrent Requests | ⭐⭐⭐ | 동시 요청 처리 능력 향상 (event loop 블로킹 제거) |

### 2.4 상태 관리 변경
| 항목 | 변경 전 | 변경 후 | 영향 |
|------|--------|--------|------|
| 상태 저장소 | generation_status.py (메모리) | ArtifactDB (DB) | ✅ 영속성 확보 |
| 상태 조회 | 메모리 dict 접근 | DB 조회 | ⚠️ 약간의 지연 가능 |
| 다중 인스턴스 | 불가능 | 가능 | ✅ 스케일링 가능 |

---

## 3. 테스트 대상 API 리스트

### 🔴 **Critical Tests** (반드시 검증)

#### 3.1.1 POST /api/topics/{id}/generate
**목적**: 보고서 생성 202 응답 + 백그라운드 작업

```
엔드포인트: POST /api/topics/{topic_id}/generate
요청 본문:
{
  "topic": "금리 인상 시장 영향",
  "plan": "1. 현황 분석\n2. 영향도 평가\n3. 미래 전망"
}

테스트 케이스:
1. TC-001: 성공 케이스 - 202 Accepted 응답 확인
   - Status Code: 202
   - Response body.status: "generating"
   - artifact_id 존재 여부

2. TC-002: Artifact 초기 상태 확인
   - status: "scheduled" 또는 "generating"
   - file_path: NULL (작업 중)
   - progress_percent: 0-10
   - started_at: 현재 시각 근처

3. TC-003: 동시 다중 생성
   - 3개 topic 동시 POST
   - 모두 202 응답 확인
   - 각각 다른 artifact_id 할당 확인

4. TC-004: 응답 시간 검증
   - 응답 < 1초 확인 (202 Accepted)
   - event loop 블로킹 없음 확인
```

---

#### 3.1.2 GET /api/topics/{id}/status
**목적**: 백그라운드 작업 상태 조회 (artifact 테이블 직접 접근)

```
엔드포인트: GET /api/topics/{topic_id}/status

테스트 케이스:
1. TC-001: 진행 중 상태 조회
   - Status Code: 200
   - data.status: "generating"
   - data.progress_percent: 10-100 범위
   - data.artifact_id: 유효한 ID

2. TC-002: 완료 상태 조회
   - POST /generate 후 약 5초 대기 (mock 사용)
   - Status Code: 200
   - data.status: "completed"
   - data.progress_percent: 100
   - data.file_path: 파일 경로
   - data.completed_at: ISO 시간

3. TC-003: 실패 상태 조회
   - Mock에서 Claude API 에러 유발
   - data.status: "failed"
   - data.error_message: 에러 내용 포함

4. TC-004: 응답 시간 검증
   - GET /status 응답 < 100ms (DB 직접 조회)
```

---

#### 3.1.3 GET /api/topics/{id}/status/stream
**목적**: SSE 스트림 기반 상태 변화 감지 (artifact 테이블 폴링)

```
엔드포인트: GET /api/topics/{topic_id}/status/stream (SSE)

테스트 케이스:
1. TC-001: SSE 연결 및 이벤트 수신
   - SSE 연결 성공 (status 200)
   - "status_update" 이벤트 수신 (generating)
   - "completion" 이벤트 수신 (completed)
   - 이벤트 데이터: artifact_id, status, progress_percent 포함

2. TC-002: 폴링 간격 확인
   - 0.5초 폴링 주기 확인
   - 상태 변화 감지 < 600ms (하나의 폴링 사이클)

3. TC-003: 스트림 정상 종료
   - completed 상태 도달 후 자동 종료
   - 정상적인 SSE 종료 (no errors)
```

---

#### 3.1.4 POST /api/topics/{id}/ask
**목적**: 대화형 질문 (Artifact 상태 머신 + asyncio.to_thread)

```
엔드포인트: POST /api/topics/{topic_id}/ask
요청 본문:
{
  "content": "위의 보고서에서 주요 리스크는 무엇인가요?",
  "template_id": null,  // or specific template ID
  "artifact_id": null   // or specific artifact ID
}

테스트 케이스:
1. TC-001: 보고서 응답
   - is_report=true 감지
   - MD artifact 생성 (status="completed")
   - artifact.file_path: 유효한 경로
   - Response artifact 포함

2. TC-002: 질문 응답
   - is_report=false 감지
   - artifact 미생성
   - Response에 artifact=null

3. TC-003: 컨텍스트 필터링
   - artifact_id 지정 시 해당 메시지 이전 메시지만 포함
   - artifact_id 미지정 시 최신 MD artifact 사용
   - max_messages 제한 적용

4. TC-004: 응답 시간 검증
   - 보통 3-5초 (Claude API + Markdown parsing + File I/O)
   - event loop 블로킹 없음

5. TC-005: 에러 처리
   - Content 길이 초과 (> 50000)
   - Context 크기 초과 (> 50000 chars)
   - Artifact not found
   - Topic unauthorized
```

---

### 🟡 **Important Tests** (주요 검증)

#### 3.2.1 GET /api/topics
**목적**: 사용자의 모든 topic 조회 (데이터 무결성)

```
엔드포인트: GET /api/topics

테스트 케이스:
1. 기존 데이터 호환성
   - 생성된 topic이 정상 조회됨
   - topic_id, language, created_at 등 필드 존재

2. Response 구조 변경 없음
   - 응답 구조 동일 확인
```

---

#### 3.2.2 POST /api/topics
**목적**: 새 topic 생성 (기존 기능 호환성)

```
엔드포인트: POST /api/topics
요청 본문:
{
  "input_prompt": "AI 시장 보고서",
  "language": "ko",
  "template_id": null
}

테스트 케이스:
1. 정상 생성
   - Status 200 또는 201
   - topic_id 반환
   - template_id가 null로 저장되는지 확인
```

---

#### 3.2.3 GET /api/topics/{id}/messages
**목적**: 대화 메시지 조회 (Artifact 연동)

```
엔드포인트: GET /api/topics/{topic_id}/messages

테스트 케이스:
1. 메시지 시퀀스 확인
   - seq_no 순서대로 반환
   - USER/ASSISTANT 역할 구분

2. Artifact와의 연동
   - artifact_id가 있는 ASSISTANT 메시지 확인
   - message_id와 artifact.message_id 매칭 확인
```

---

#### 3.2.4 GET /api/artifacts
**목적**: Artifact 목록 조회 (DB 직접 접근)

```
엔드포인트: GET /api/artifacts?topic_id={topic_id}&kind=MD

테스트 케이스:
1. 필터링 확인
   - topic_id로 필터링
   - kind로 필터링 (MD/HWPX)

2. 상태 필드 확인
   - status: "scheduled", "generating", "completed", "failed"
   - progress_percent: 0-100
   - started_at, completed_at 필드
```

---

#### 3.2.5 GET /api/artifacts/{id}/download
**목적**: MD 파일 다운로드

```
엔드포인트: GET /api/artifacts/{artifact_id}/download

테스트 케이스:
1. MD 다운로드
   - Status 200
   - Content-Type: text/markdown
   - 파일 내용 유효성

2. 비존재 artifact
   - Status 404
```

---

### 🟢 **Optional Tests** (선택적 검증)

#### 3.3.1 Plan 엔드포인트 (기존 기능)
```
엔드포인트: POST /api/topics/{id}/plan

영향도: 낮음 (독립적인 기능)
검증: 기존 동작 확인
```

---

## 4. 테스트 시나리오별 순서도

### 시나리오 A: 완전한 생성 → 상태 확인 플로우
```
1. POST /api/topics/{id}/generate
   ↓ (202 Accepted)
2. GET /api/topics/{id}/status (진행 중)
   ↓ (status="generating", progress=10-90)
3. 5초 대기 (mock 사용하면 ~100ms)
   ↓
4. GET /api/topics/{id}/status (완료)
   ↓ (status="completed", progress=100)
5. GET /api/artifacts/{artifact_id}/download
   ↓ (파일 다운로드 확인)
```

### 시나리오 B: 스트림 기반 실시간 모니터링
```
1. POST /api/topics/{id}/generate
   ↓ (202 Accepted)
2. GET /api/topics/{id}/status/stream (SSE)
   ↓ (status_update 이벤트)
   ↓ (progress 증가)
   ↓ (completion 이벤트)
```

### 시나리오 C: 대화형 흐름
```
1. POST /api/topics/{id}/generate (보고서 생성)
   ↓ (완료 대기)
2. POST /api/topics/{id}/ask (질문)
   ↓ (MD artifact 생성)
3. GET /api/topics/{id}/messages (메시지 확인)
   ↓ (artifact 연결 확인)
4. GET /api/artifacts/{id}/download (MD 다운로드)
```

---

## 5. 회귀 테스트 체크리스트

### 5.1 기존 기능 호환성
- [ ] POST /api/topics (topic 생성)
- [ ] GET /api/topics (topic 목록)
- [ ] GET /api/topics/{id} (topic 상세)
- [ ] PATCH /api/topics/{id} (topic 수정)
- [ ] DELETE /api/topics/{id} (topic 삭제)
- [ ] GET /api/topics/{id}/messages (메시지 조회)
- [ ] GET /api/artifacts (artifact 목록)
- [ ] GET /api/artifacts/{id} (artifact 상세)
- [ ] POST /api/topics/{id}/plan (계획 생성)

### 5.2 데이터 무결성
- [ ] DB 레코드 일관성 (artifact, message, topic)
- [ ] Foreign key 제약 조건 위반 없음
- [ ] 파일 시스템과 DB 동기화
- [ ] 트랜잭션 정상 처리

### 5.3 권한 및 보안
- [ ] 다른 사용자의 topic 접근 거부
- [ ] 다른 사용자의 artifact 다운로드 거부
- [ ] Admin 권한으로 다른 사용자 topic 접근 가능
- [ ] Token 만료 시 403 응답

---

## 6. 성능 벤치마크

### 예상 응답 시간
| API | 예상 시간 | 최대값 |
|-----|----------|--------|
| POST /generate | < 1초 | 1.5초 |
| GET /status | < 100ms | 200ms |
| GET /status/stream (SSE 연결) | < 100ms | 200ms |
| POST /ask (보고서) | 3-5초 | 8초 |
| POST /ask (질문) | 2-3초 | 5초 |
| GET /artifacts/download (MD) | < 100ms | 300ms |

### 동시성 테스트
```
1. 10개 동시 POST /generate
   - 모두 202 Accepted
   - 각각 다른 artifact_id
   - 병렬 처리 확인 (event loop 블로킹 없음)

2. 10개 동시 GET /status
   - 모두 200 OK
   - 응답 시간 < 200ms (캐싱 영향 최소)
```

---

## 7. 알려진 제한사항 및 주의사항

### ⚠️ 주의사항
1. **generation_status.py**: 아직 파일 유지 (미사용), Phase 3에서 제거 예정
2. **Response Detector**: POST /ask에서 is_report 판별 로직 미흡
   - 현재는 항상 is_report=True로 처리
   - 추후 개선 필요
3. **HWPX 생성**: POST /ask에서 미지원 (의도적으로 보류)

### 🐛 알려진 버그
1. `test_ask_question_response_extracts_section_content`: H2 헤더 제거 미동작
   - 원인: response_detector 모듈 이슈
   - 영향: 질문 응답에서 마크다운 포맷 유지 (부분적 영향)
   - 해결: Phase 3에서 처리 예정

---

## 8. 롤백 계획 (if needed)

### 만약 문제 발생 시
```
1. git revert [commit hash]
2. generation_status.py 사용 재개
3. topics.py에서 asyncio.to_thread() 제거
4. GET /status를 메모리 기반으로 복구
```

---

## 9. 다음 단계

### Phase 3 계획 (추천)
1. **Test Coverage 70% 달성**
   - artifacts.py: 24% → 70%
   - templates.py: 16% → 70%

2. **Response Detector 개선**
   - is_report 판별 정확도 향상
   - 질문/보고서 구분 로직 개선

3. **Generation Status 제거**
   - generation_status.py 파일 완전 삭제
   - Phase 2 최종 완성

4. **Error Recovery & Retry**
   - Task 실패 시 자동 재시도
   - Failed artifact 복구 로직

---

**작성자**: Claude Code
**마지막 업데이트**: 2025-11-14
**상태**: ✅ Phase 2 완료, 테스트 대상 API 정의 완료
