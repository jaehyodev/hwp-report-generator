# SSE 기반 보고서 생성 흐름 가이드

## 개요

보고서 생성은 **백그라운드 비동기 방식**으로 동작합니다. 사용자가 "생성" 버튼을 클릭하면 서버에서 즉시 202 응답을 반환하고, 실제 보고서는 백그라운드에서 생성됩니다. 클라이언트는 **SSE(Server-Sent Events)**를 통해 실시간으로 진행 상태를 받아 UI를 업데이트합니다.

---

## 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              사용자 흐름                                      │
└─────────────────────────────────────────────────────────────────────────────┘

[1] 사용자가 주제 입력
        │
        ▼
[2] POST /api/topics/plan  ───────────────────►  계획(Plan) 생성
        │                                         (Claude Sequential Planning)
        │
        ▼
[3] 사용자가 "생성" 버튼 클릭
        │
        ▼
[4] POST /api/topics/{id}/generate  ──────────►  202 Accepted (즉시 반환)
        │                                         백그라운드 Task 시작
        │
        ▼
[5] GET /api/topics/{id}/status/stream  ──────►  SSE 연결 수립
        │
        │  ┌─────────────────────────────────┐
        │  │  SSE 이벤트 수신 (실시간)        │
        │  │  - status_update: 진행 중       │
        │  │  - completion: 완료/실패        │
        │  └─────────────────────────────────┘
        │
        ▼
[6] 완료 시: 토스트 메시지 + 사이드바 토픽 추가
```

---

## API 상세

### 1. 계획 생성 API

| 항목 | 내용 |
|------|------|
| **엔드포인트** | `POST /api/topics/plan` |
| **백엔드 파일** | `backend/app/routers/topics.py` |
| **프론트엔드 API** | `topicApi.generateTopicPlan()` |
| **프론트엔드 파일** | `frontend/src/services/topicApi.ts` |

**요청:**
```typescript
{
  template_id: number,
  topic: string
}
```

**응답:**
```typescript
{
  topic_id: number,
  plan: string,        // 마크다운 형식 계획
  sections: string[]   // 섹션 목록
}
```

---

### 2. 백그라운드 보고서 생성 API

| 항목 | 내용 |
|------|------|
| **엔드포인트** | `POST /api/topics/{topic_id}/generate` |
| **백엔드 파일** | `backend/app/routers/topics.py` |
| **백엔드 함수** | `generate_report_background()` |
| **프론트엔드 API** | `topicApi.generateTopicBackground()` |
| **프론트엔드 파일** | `frontend/src/services/topicApi.ts` |

**요청:**
```typescript
{
  topic: string,
  plan: string,
  template_id?: number
}
```

**응답 (202 Accepted):**
```typescript
{
  topic_id: number,
  status: "generating",
  message: "Report generation started in background",
  status_check_url: "/api/topics/{topic_id}/status"
}
```

> ⚠️ **중요**: 이 API는 즉시 반환됩니다. 실제 보고서 생성은 `asyncio.create_task()`로 백그라운드에서 진행됩니다.

---

### 3. SSE 상태 스트림 API

| 항목 | 내용 |
|------|------|
| **엔드포인트** | `GET /api/topics/{topic_id}/status/stream` |
| **백엔드 파일** | `backend/app/routers/topics.py` |
| **백엔드 함수** | `stream_generation_status()` |
| **프론트엔드 API** | `topicApi.getGenerationStatusStream()` |
| **프론트엔드 파일** | `frontend/src/services/topicApi.ts` |
| **라이브러리** | `@microsoft/fetch-event-source` |

**SSE 이벤트 형식:**
```typescript
// 진행 중
{
  event: "status_update",
  artifact_id: number,
  status: "generating",
  progress_percent: number  // 0-100
}

// 완료
{
  event: "completion",
  artifact_id: number,
  status: "completed",
  progress_percent: 100,
  file_path: string
}

// 실패
{
  event: "completion",
  artifact_id: number,
  status: "failed",
  error_message: string
}
```

---

## 프론트엔드 코드 상세

### 파일 구조

```
frontend/src/
├── services/
│   └── topicApi.ts          # API 호출 함수들
├── stores/
│   └── useTopicStore.ts     # Zustand 상태 관리 + SSE 처리
└── pages/
    └── MainPage.tsx         # UI 컴포넌트
```

---

### 1. topicApi.ts - SSE 연결 함수

**파일 경로:** `frontend/src/services/topicApi.ts`

**함수:** `getGenerationStatusStream()`

```typescript
getGenerationStatusStream: (
    topicId: number,
    onMessage: (status: TopicGenerationStatus) => void,
    onError?: (error: any) => void
) => {
    const token = storage.getToken()
    const controller = new AbortController()

    fetchEventSource(`http://localhost:8000/api/topics/${topicId}/status/stream`, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${token}`,
        },
        signal: controller.signal,        // 연결 종료용
        openWhenHidden: true,             // 탭 전환 시 재연결 방지
        onmessage: (event) => {
            const data = JSON.parse(event.data)
            console.log('topicApi >> sse >> ', data)  // 디버그 로그

            if (data.event === 'status_update' || data.event === 'completion') {
                onMessage({
                    topic_id: topicId,
                    status: data.status,
                    progress_percent: data.progress_percent ?? 0,
                    artifact_id: data.artifact_id,
                    error_message: data.error_message
                })
            }
        },
        onerror: (error) => {
            console.error('SSE connection error:', error)
            if (onError) onError(error)
            throw error  // 재연결 방지
        },
    })

    // 구독 취소 함수 반환
    return () => {
        controller.abort()
    }
}
```

**주요 옵션:**
| 옵션 | 설명 |
|------|------|
| `signal` | `AbortController`의 signal. `unsubscribe()` 호출 시 연결 종료 |
| `openWhenHidden` | `true`로 설정하면 탭이 숨겨져도 연결 유지 (불필요한 재연결 방지) |
| `throw error` | onerror에서 throw하면 자동 재연결 비활성화 |

---

### 2. useTopicStore.ts - SSE 이벤트 처리

**파일 경로:** `frontend/src/stores/useTopicStore.ts`

**함수:** `generateReportFromPlan()`

```typescript
generateReportFromPlan: async () => {
    const { plan } = get()
    const realTopicId = plan.topic_id
    const messageStore = useMessageStore.getState()

    // 1. 백그라운드 생성 요청
    const response = await topicApi.generateTopicBackground(realTopicId, {...})

    if (response.status === 'generating') {
        // 2. 로딩 토스트 표시
        antdMessage.loading({ content: '보고서 생성 중...', key: 'generating' })

        // 3. 중복 처리 방지 플래그
        let isCompleted = false

        // 4. SSE 구독 시작
        const unsubscribe = topicApi.getGenerationStatusStream(
            realTopicId,
            async (status) => {
                // 이미 처리됐으면 무시
                if (isCompleted) return

                // 진행 상태 UI 업데이트
                messageStore.setGeneratingReportStatus({
                    topicId: realTopicId,
                    status: status.status,
                    progressPercent: status.progress_percent ?? 0,
                    artifactId: status.artifact_id
                })

                if (status.status === 'completed') {
                    // 즉시 플래그 설정 + 연결 종료
                    isCompleted = true
                    unsubscribe()

                    // 성공 처리
                    antdMessage.destroy('generating')
                    antdMessage.success('보고서가 생성되었습니다.')

                    // 메시지 및 토픽 업데이트
                    // ... (상세 코드 생략)

                } else if (status.status === 'failed') {
                    isCompleted = true
                    unsubscribe()

                    antdMessage.destroy('generating')
                    antdMessage.error('보고서 생성에 실패했습니다.')
                }
            },
            (error) => {
                // 에러 처리
                if (isCompleted) return
                isCompleted = true
                unsubscribe()

                antdMessage.error('보고서 상태 확인 중 오류가 발생했습니다.')
            }
        )
    }
}
```

---

### 3. 중복 처리 방지 패턴

백엔드에서 `completion` 이벤트가 2번 발송될 수 있어서, 프론트엔드에서 방어 로직을 추가했습니다.

```typescript
// 플래그 선언
let isCompleted = false

const unsubscribe = topicApi.getGenerationStatusStream(
    realTopicId,
    async (status) => {
        // 1. 이미 처리됐으면 무시
        if (isCompleted) return

        if (status.status === 'completed') {
            // 2. 즉시 플래그 설정 (다음 이벤트 차단)
            isCompleted = true

            // 3. 즉시 연결 종료 (추가 이벤트 방지)
            unsubscribe()

            // 4. 나머지 로직 실행 (토스트, API 호출 등)
            // ...
        }
    }
)
```

**동작 흐름:**
```
첫 번째 completion 도착
  → isCompleted = false (통과)
  → isCompleted = true 설정
  → unsubscribe() 호출 → SSE 연결 종료
  → 토스트/토픽 추가 실행

두 번째 completion 도착 (만약 큐에 있었다면)
  → isCompleted = true → return으로 무시
  → 아무것도 실행 안 됨
```

---

## 이벤트 흐름 다이어그램

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   MainPage   │     │ useTopicStore│     │   topicApi   │
│    (UI)      │     │   (Store)    │     │   (API)      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ "생성" 버튼 클릭    │                    │
       │───────────────────>│                    │
       │                    │                    │
       │                    │ generateTopicBackground()
       │                    │───────────────────>│
       │                    │                    │──── POST /generate ────>
       │                    │                    │<─── 202 Accepted ───────
       │                    │<───────────────────│
       │                    │                    │
       │                    │ getGenerationStatusStream()
       │                    │───────────────────>│
       │                    │                    │──── GET /status/stream ─>
       │                    │                    │     (SSE 연결 수립)
       │                    │                    │
       │                    │     ┌──────────────┴──────────────┐
       │                    │     │  SSE 이벤트 루프             │
       │                    │     │  - status_update 수신       │
       │                    │     │  - completion 수신          │
       │                    │     └──────────────┬──────────────┘
       │                    │                    │
       │                    │<── onMessage(status) ──│
       │                    │                    │
       │                    │ (status === 'completed')
       │                    │ isCompleted = true
       │                    │ unsubscribe()
       │                    │                    │
       │<── 토스트 표시 ────│                    │
       │<── 사이드바 업데이트│                    │
       │                    │                    │
```

---

## 관련 타입 정의

**파일:** `frontend/src/types/topic.ts`

```typescript
export interface TopicGenerationStatus {
    topic_id: number
    status: 'generating' | 'completed' | 'failed'
    progress_percent: number
    artifact_id?: number
    error_message?: string
}
```

---

## 디버깅 팁

### 콘솔에서 SSE 이벤트 확인

브라우저 개발자 도구 콘솔에서 다음 로그를 확인할 수 있습니다:

```
topicApi >> sse >>  {event: 'status_update', artifact_id: 6, status: 'generating', progress_percent: 50}
topicApi >> sse >>  {event: 'completion', artifact_id: 6, status: 'completed', progress_percent: 100}
```

### 네트워크 탭에서 SSE 확인

1. 개발자 도구 > Network 탭
2. 필터: `EventStream` 또는 `status/stream`
3. 해당 요청 클릭 > EventStream 탭에서 실시간 이벤트 확인

---

## 참고 문서

- [backend/doc/specs/20251112_sequential_planning_with_sse_progress.md](../../backend/doc/specs/20251112_sequential_planning_with_sse_progress.md) - 백엔드 SSE 구현 스펙
- [@microsoft/fetch-event-source](https://www.npmjs.com/package/@microsoft/fetch-event-source) - SSE 라이브러리 문서
