# Bug Report: 전역 UI 상태를 토픽별 상태로 분리

**날짜**: 2025-11-26
**상태**: ✅ 해결됨
**영향 범위**: MainPage, useTopicStore, useMessageStore, useChatActions

---

## 문제 설명

### 증상 1: GeneratingIndicator가 모든 화면에서 표시됨
- **재현 경로**: 새 대화에서 보고서 생성 시작 → 다른 대화 화면으로 이동
- **기대 동작**: GeneratingIndicator는 보고서 생성 중인 대화 화면에서만 표시
- **실제 동작**: 모든 대화 화면에서 GeneratingIndicator가 표시됨

### 증상 2: ChatLoading이 모든 화면에서 표시됨
- **재현 경로**: 보고서 생성 중인 대화에서 다른 대화로 이동
- **기대 동작**: "대화 내용을 불러오는 중..." 메시지는 해당 토픽 메시지 로딩 중일 때만 표시
- **실제 동작**: 다른 대화 화면에서도 로딩 메시지가 표시됨

### 증상 3: antd.message 충돌
- **문제**: 여러 대화에서 동시에 보고서 생성 시 동일한 메시지 키('generating')로 인해 메시지가 덮어쓰기됨
- **영향**: 첫 번째 생성 완료 시 두 번째 생성 진행 중인데도 메시지가 사라짐

---

## 근본 원인

### 전역 boolean 상태 사용
```typescript
// 문제: 전역 상태로 관리됨
isGeneratingMessage: boolean  // 모든 토픽에서 공유
isLoadingMessages: boolean    // 모든 토픽에서 공유
```

여러 대화 화면에서 동시에 다른 작업이 진행될 수 있으므로, 전역 boolean으로는 각 토픽의 상태를 독립적으로 관리할 수 없음.

---

## 해결 방법

### 1. 토픽별 상태 관리를 위한 Set 사용

**useTopicStore.ts** - AI 응답 생성 상태
```typescript
// Before
isGeneratingMessage: boolean

// After
messageGeneratingTopicIds: Set<number>

// Actions
addGeneratingTopicId: (topicId: number) => void
removeGeneratingTopicId: (topicId: number) => void
isTopicGenerating: (topicId: number | null) => boolean
```

**useMessageStore.ts** - 메시지 로딩 상태
```typescript
// Before
isLoadingMessages: boolean

// After
messageLoadingTopicIds: Set<number>

// Actions
addMessageLoadingTopicId: (topicId: number) => void
removeMessageLoadingTopicId: (topicId: number) => void
isTopicMessagesLoading: (topicId: number | null) => boolean
```

### 2. MainPage에서 토픽별 상태 구독

```typescript
// Before
const {isGeneratingMessage, isLoadingMessages} = useMessageStore()

// After
const isGeneratingMessage = useTopicStore((state) => state.isTopicGenerating(selectedTopicId))
const isLoadingMessages = useMessageStore((state) => state.isTopicMessagesLoading(selectedTopicId))
```

### 3. antd.message 키에 topicId 추가

```typescript
// Before
antdMessage.loading({content: '보고서 생성 중...', key: 'generating', duration: 0})
antdMessage.destroy('generating')

// After
antdMessage.loading({content: '보고서 생성 중...', key: `generating-${realTopicId}`, duration: 0})
antdMessage.destroy(`generating-${realTopicId}`)
```

---

## 수정된 파일

### 1. frontend/src/stores/useTopicStore.ts

**추가된 상태:**
```typescript
interface TopicStore {
    // AI 응답 생성 중인 토픽 ID 목록
    messageGeneratingTopicIds: Set<number>

    // Actions
    addGeneratingTopicId: (topicId: number) => void
    removeGeneratingTopicId: (topicId: number) => void
    isTopicGenerating: (topicId: number | null) => boolean
}
```

**구현:**
```typescript
messageGeneratingTopicIds: new Set(),

addGeneratingTopicId: (topicId: number) => {
    set((state) => {
        const newSet = new Set(state.messageGeneratingTopicIds)
        newSet.add(topicId)
        return {messageGeneratingTopicIds: newSet}
    })
},

removeGeneratingTopicId: (topicId: number) => {
    set((state) => {
        const newSet = new Set(state.messageGeneratingTopicIds)
        newSet.delete(topicId)
        return {messageGeneratingTopicIds: newSet}
    })
},

isTopicGenerating: (topicId: number | null) => {
    if (topicId === null) return false
    return get().messageGeneratingTopicIds.has(topicId)
},
```

**antd.message 키 변경:**
- `'generate'` → `\`generate-${realTopicId}\``
- `'generating'` → `\`generating-${realTopicId}\``

### 2. frontend/src/stores/useMessageStore.ts

**변경된 상태:**
```typescript
// Before
isLoadingMessages: boolean
setIsLoadingMessages: (loading: boolean) => void

// After
messageLoadingTopicIds: Set<number>
addMessageLoadingTopicId: (topicId: number) => void
removeMessageLoadingTopicId: (topicId: number) => void
isTopicMessagesLoading: (topicId: number | null) => boolean
```

**fetchMessages, loadMessages 수정:**
```typescript
loadMessages: async (topicId: number) => {
    get().addMessageLoadingTopicId(topicId)  // 시작 시 추가
    try {
        // ... API 호출
    } finally {
        get().removeMessageLoadingTopicId(topicId)  // 완료 시 제거
    }
},
```

### 3. frontend/src/pages/MainPage.tsx

**상태 구독 변경:**
```typescript
// 현재 토픽에서 AI 응답 생성 중인지 확인 (토픽별로 GeneratingIndicator 표시 제어)
const isGeneratingMessage = useTopicStore((state) => state.isTopicGenerating(selectedTopicId))

// 현재 토픽의 메시지가 로딩 중인지 확인 (토픽별로 ChatLoading 표시 제어)
const isLoadingMessages = useMessageStore((state) => state.isTopicMessagesLoading(selectedTopicId))
```

### 4. frontend/src/hooks/useChatActions.ts

**생성 상태 관리 위치 변경:**
```typescript
// Before (MessageStore 사용)
useMessageStore.getState().setIsGeneratingMessage(true)
// ... finally
useMessageStore.getState().setIsGeneratingMessage(false)

// After (TopicStore 사용)
const topicStore = useTopicStore.getState()
topicStore.addGeneratingTopicId(selectedTopicId)
// ... finally
useTopicStore.getState().removeGeneratingTopicId(selectedTopicId)
```

---

## 설계 결정 사항

### 1. 상태 저장 위치 결정

| 상태 | 저장소 | 이유 |
|------|--------|------|
| messageGeneratingTopicIds | TopicStore | 보고서 생성은 토픽 레벨의 비즈니스 로직 |
| messageLoadingTopicIds | MessageStore | 메시지 데이터 로딩과 직접 연관 |

### 2. 변수명 선정

| 초기 제안 | 최종 선택 | 변경 이유 |
|-----------|-----------|-----------|
| generatingTopicId | - | "토픽 ID를 생성 중"으로 오해 가능 |
| activeGenerationTopicId | - | 동시에 여러 토픽 생성 불가능한 구조 |
| generatingTopicIds | messageGeneratingTopicIds | 어떤 생성인지 명확히 표현 |
| loadingTopicIds | messageLoadingTopicIds | 어떤 로딩인지 명확히 표현 |

### 3. Set 자료구조 선택
- 여러 토픽에서 동시에 작업 가능
- O(1) 조회/추가/삭제 성능
- 중복 방지 자동 처리

---

## 테스트 시나리오

### 시나리오 1: 단일 대화 보고서 생성
1. 새 대화에서 보고서 생성 시작
2. GeneratingIndicator 표시 확인
3. 생성 완료 후 GeneratingIndicator 사라짐 확인

### 시나리오 2: 대화 전환 시 상태 분리
1. 대화 A에서 보고서 생성 시작
2. 대화 B로 이동
3. 대화 B에서 GeneratingIndicator 미표시 확인
4. 대화 A로 복귀 시 GeneratingIndicator 표시 확인

### 시나리오 3: 동시 보고서 생성
1. 대화 A에서 보고서 생성 시작
2. 대화 B에서 보고서 생성 시작
3. 각 대화에서 독립적으로 GeneratingIndicator 표시 확인
4. 대화 A 완료 시 대화 A만 GeneratingIndicator 사라짐 확인

### 시나리오 4: 메시지 로딩 상태 분리
1. 대화 A에서 보고서 생성 중
2. 대화 B로 이동
3. 대화 B 메시지 로딩 중 ChatLoading 표시 확인
4. 로딩 완료 후 ChatLoading 사라짐 확인
5. 대화 A로 복귀 시 GeneratingIndicator만 표시 (ChatLoading 미표시)

---

## 관련 컴포넌트

- `GeneratingIndicator`: AI 응답 생성 중 표시
- `ChatLoading`: 메시지 로딩 중 표시
- `antd.message`: 토스트 알림 메시지

---

## 향후 고려사항

1. **에러 상태**: 토픽별 에러 상태 관리 패턴 적용 가능
2. **성능 최적화**: Set 크기가 커질 경우 정리 로직 필요 (현재는 생성/로딩 완료 시 자동 제거됨)

> **참고**: SSE 연결은 이미 토픽별로 독립적으로 관리됩니다 (`topicApi.getGenerationStatusStream`에서 `topicId`별 연결 생성)
