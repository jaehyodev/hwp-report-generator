# MESSAGE_FLOW.md - 메시지 흐름 문서

이 문서는 프론트엔드에서 메시지 생성 및 삭제 흐름을 정리합니다.

---

## 목차

1. [메시지 삭제 흐름](#1-메시지-삭제-흐름)
2. [메시지 생성 흐름](#2-메시지-생성-흐름) *(작성 예정)*

---

## 1. 메시지 삭제 흐름

### 1.1 전체 흐름 다이어그램

```mermaid
flowchart TD
    subgraph UI["UI 계층"]
        A[ChatMessage 컴포넌트<br/>마우스 호버]
        B{삭제 버튼 표시 조건}
        C[삭제 버튼 클릭]
        D[DeleteChatMessageModal<br/>삭제 확인 모달]
        E{사용자 선택}
    end

    subgraph Logic["비즈니스 로직 계층"]
        F[MainPage.handleDeleteMessage]
        G[useChatActions.handleDeleteMessage]
        H{selectedTopicId<br/>존재 여부}
        I{마지막 메시지<br/>여부 확인}
    end

    subgraph API["API 계층"]
        J[messageApi.deleteMessage<br/>DELETE /api/topics/topicId/messages/messageId]
        K{API 응답}
    end

    subgraph State["상태 관리 계층"]
        L[useTopicStore.deleteTopicById]
        M[useMessageStore.clearMessages]
        N[selectedTopicId = null]
        O[useMessageStore.refreshMessages]
        P[messageApi.listMessages]
        Q[artifactApi.listArtifactsByTopic]
        R[메시지 목록 업데이트]
    end

    subgraph Result["결과"]
        S[성공 메시지 표시]
        T[에러 메시지 표시]
        U[UI 상태 복구<br/>isDeletingMessage = false]
    end

    %% UI 흐름
    A --> B
    B -->|clientId > 1<br/>AND !isGenerating<br/>AND isHovered| C
    B -->|조건 미충족| A
    C --> D
    D --> E
    E -->|취소| A
    E -->|확인| F

    %% 비즈니스 로직 흐름
    F --> G
    G --> H
    H -->|없음| T
    H -->|있음| J

    %% API 흐름
    J --> K
    K -->|실패| T
    K -->|성공| I

    %% 분기 처리
    I -->|마지막 메시지<br/>clientId = 2| L
    I -->|일반 메시지| O

    %% 마지막 메시지 삭제 흐름
    L --> M
    M --> N
    N --> S

    %% 일반 메시지 삭제 흐름
    O --> P
    P --> Q
    Q --> R
    R --> S

    %% 최종 처리
    S --> U
    T --> U

    %% 스타일링
    style A fill:#e1f5fe
    style D fill:#fff3e0
    style G fill:#f3e5f5
    style J fill:#e8f5e9
    style L fill:#fce4ec
    style O fill:#fce4ec
    style S fill:#c8e6c9
    style T fill:#ffcdd2
```

### 1.2 단계별 상세 설명

#### Step 1: UI 진입점 - 삭제 버튼 표시

| 파일 | 함수 | 설명 |
|------|------|------|
| [MainPage.tsx](../src/pages/MainPage.tsx#L256-L258) | `handleDeleteMessage` | 삭제 핸들러 정의 |
| [ChatMessage.tsx](../src/components/chat/ChatMessage.tsx#L77-L81) | `ChatMessage` | 호버 시 삭제 버튼 표시 |

```typescript
// MainPage.tsx:256-258
const handleDeleteMessage = async (messageId: number, messageClientId: number) => {
    await deleteMessage(messageId, messageClientId, setSelectedReport, selectedReport)
}

// MainPage.tsx:361 - 삭제 버튼 조건부 전달
onDelete={message.clientId > 1 ? handleDeleteMessage : undefined}
```

**분기 조건:**
- `clientId > 1` → 삭제 가능 (첫 2개 메시지는 삭제 불가)
- `isGenerating = false` → 생성 중이 아닐 때만 표시
- `isHovered = true` → 마우스 호버 상태일 때만 표시

#### Step 2: 삭제 확인 모달

| 파일 | 함수 | 설명 |
|------|------|------|
| [ChatMessage.tsx](../src/components/chat/ChatMessage.tsx#L29-L32) | `handleDeleteClick` | 모달 열기 |
| [DeleteChatMessageModal.tsx](../src/components/chat/DeleteChatMessageModal.tsx#L34-L38) | `handleConfirmDelete` | 삭제 확인 |

```mermaid
flowchart LR
    A[삭제 버튼 클릭] --> B[showDeleteModal = true]
    B --> C[DeleteChatMessageModal 표시]
    C --> D{사용자 선택}
    D -->|취소| E[showDeleteModal = false]
    D -->|확인| F[onDelete 콜백 호출]
```

**모달 상태 제어:**
- `loading = true` → OK 버튼 로딩, 취소/닫기 비활성화
- `message.id` 없으면 삭제 중단

#### Step 3: 비즈니스 로직 - useChatActions

| 파일 | 함수 | 설명 |
|------|------|------|
| [useChatActions.ts](../src/hooks/useChatActions.ts#L100-L160) | `handleDeleteMessage` | 삭제 메인 로직 |

```mermaid
flowchart TD
    A[handleDeleteMessage 시작] --> B[isDeletingMessage = true]
    B --> C{selectedTopicId 존재?}
    C -->|없음| D[에러: 주제가 선택되지 않았습니다]
    C -->|있음| E[messageApi.deleteMessage 호출]
    E --> F{API 성공?}
    F -->|실패| G[에러: 메시지 삭제에 실패했습니다]
    F -->|성공| H{selectedReport가<br/>삭제 메시지?}
    H -->|예| I[setSelectedReport = null]
    H -->|아니오| J{마지막 메시지?<br/>clientId === 2}
    I --> J
    J -->|예| K[토픽 삭제 + 상태 초기화]
    J -->|아니오| L[refreshMessages 호출]
    K --> M[성공: 대화가 종료되었습니다]
    L --> N[성공: 메시지가 삭제되었습니다]
    D --> O[isDeletingMessage = false]
    G --> O
    M --> O
    N --> O

    style D fill:#ffcdd2
    style G fill:#ffcdd2
    style M fill:#c8e6c9
    style N fill:#c8e6c9
```

**핵심 분기:**

| 분기 조건 | 참일 때 | 거짓일 때 |
|----------|--------|----------|
| `!selectedTopicId` | 에러 반환 | 계속 진행 |
| `clientId === 2` | 토픽 삭제 | 메시지만 삭제 |
| `selectedReport.messageId === messageId` | 미리보기 닫기 | 유지 |

#### Step 4: API 호출

| 파일 | 함수 | 설명 |
|------|------|------|
| [messageApi.ts](../src/services/messageApi.ts#L66-L76) | `deleteMessage` | DELETE API 호출 |

```typescript
// messageApi.ts:66-76
deleteMessage: async (topicId: number, messageId: number): Promise<void> => {
    const response = await api.delete<ApiResponse<{message: string}>>(
        API_ENDPOINTS.DELETE_MESSAGE(topicId, messageId)
    )

    if (!response.data.success) {
        throw new Error(response.data.error?.message || '메시지 삭제에 실패했습니다.')
    }
}
```

**API 엔드포인트:** `DELETE /api/topics/{topicId}/messages/{messageId}`

#### Step 5: 상태 업데이트 (분기별 처리)

##### 5-A: 마지막 메시지 삭제 시 (clientId === 2)

| 파일 | 함수 | 설명 |
|------|------|------|
| [useTopicStore.ts](../src/stores/useTopicStore.ts#L276-L284) | `deleteTopicById` | 토픽 삭제 |
| [useMessageStore.ts](../src/stores/useMessageStore.ts) | `clearMessages` | 메시지 정리 |

```mermaid
sequenceDiagram
    participant Logic as useChatActions
    participant TopicStore as useTopicStore
    participant MsgStore as useMessageStore
    participant API as topicApi

    Logic->>TopicStore: deleteTopicById(topicId)
    TopicStore->>API: DELETE /api/topics/{topicId}
    API-->>TopicStore: 성공
    TopicStore->>TopicStore: removeTopicFromBothLists(topicId)
    Logic->>MsgStore: clearMessages(topicId)
    Logic->>Logic: setSelectedTopicId(null)
    Logic->>Logic: setSelectedTemplateId(null)
```

##### 5-B: 일반 메시지 삭제 시

| 파일 | 함수 | 설명 |
|------|------|------|
| [useMessageStore.ts](../src/stores/useMessageStore.ts#L215-L237) | `refreshMessages` | 메시지 재조회 |
| [messageMapper.ts](../src/mapper/messageMapper.ts) | `mapMessageResponsesToModels` | 데이터 변환 |
| [messageHelpers.ts](../src/utils/messageHelpers.ts) | `enrichMessagesWithArtifacts` | 아티팩트 연결 |

```mermaid
sequenceDiagram
    participant Logic as useChatActions
    participant MsgStore as useMessageStore
    participant MsgAPI as messageApi
    participant ArtAPI as artifactApi
    participant Mapper as messageMapper
    participant Helper as messageHelpers

    Logic->>MsgStore: refreshMessages(topicId)
    MsgStore->>MsgAPI: listMessages(topicId)
    MsgAPI-->>MsgStore: MessagesResponse
    MsgStore->>Mapper: mapMessageResponsesToModels(messages)
    Mapper-->>MsgStore: MessageModel[]
    MsgStore->>ArtAPI: listArtifactsByTopic(topicId)
    ArtAPI-->>MsgStore: ArtifactsResponse

    alt 아티팩트 존재
        MsgStore->>Helper: enrichMessagesWithArtifacts(messages, artifacts)
        Helper-->>MsgStore: MessageModel[] with artifacts
    end

    MsgStore->>MsgStore: setMessages(topicId, messages)
```

### 1.3 상태 관리 요약

| 스토어 | 상태 변수 | 변경 시점 | 목적 |
|--------|----------|----------|------|
| `useMessageStore` | `isDeletingMessage` | 삭제 시작/완료 | 버튼 비활성화 |
| `useMessageStore` | `messagesByTopic` | refreshMessages 완료 | UI 목록 업데이트 |
| `useTopicStore` | `selectedTopicId` | 마지막 메시지 삭제 | 화면 초기화 |
| `useTopicStore` | `sidebarTopics` | deleteTopicById | 사이드바 업데이트 |
| `useTopicStore` | `pageTopics` | deleteTopicById | 리스트 업데이트 |
| `MainPage` | `selectedReport` | 삭제된 메시지 보고서 | 미리보기 닫기 |

### 1.4 에러 처리 흐름

```mermaid
flowchart TD
    A[메시지 삭제 시작] --> B{selectedTopicId?}
    B -->|없음| C["antdMessage.error<br/>'주제가 선택되지 않았습니다.'"]
    B -->|있음| D[messageApi.deleteMessage]
    D --> E{API 성공?}
    E -->|실패| F["console.error<br/>antdMessage.error<br/>'메시지 삭제에 실패했습니다.'"]
    E -->|성공| G{마지막 메시지?}
    G -->|예| H[deleteTopicById]
    H --> I{토픽 삭제 성공?}
    I -->|실패| J["console.error<br/>throw error (상위 catch)"]
    I -->|성공| K["antdMessage.success<br/>'대화가 종료되었습니다.'"]
    G -->|아니오| L[refreshMessages]
    L --> M{재조회 성공?}
    M -->|실패| N["console.error<br/>throw error"]
    M -->|성공| O["antdMessage.success<br/>'메시지가 삭제되었습니다.'"]

    C --> P[return false]
    F --> P
    J --> P
    N --> P
    K --> Q[return true]
    O --> Q

    P --> R[finally: isDeletingMessage = false]
    Q --> R

    style C fill:#ffcdd2
    style F fill:#ffcdd2
    style J fill:#ffcdd2
    style N fill:#ffcdd2
    style K fill:#c8e6c9
    style O fill:#c8e6c9
```

### 1.5 관련 파일 목록

| 용도 | 파일 경로 |
|------|---------|
| 메시지 카드 | [ChatMessage.tsx](../src/components/chat/ChatMessage.tsx) |
| 삭제 확인 모달 | [DeleteChatMessageModal.tsx](../src/components/chat/DeleteChatMessageModal.tsx) |
| 페이지 핸들러 | [MainPage.tsx](../src/pages/MainPage.tsx) |
| 비즈니스 로직 | [useChatActions.ts](../src/hooks/useChatActions.ts) |
| 메시지 API | [messageApi.ts](../src/services/messageApi.ts) |
| 토픽 API | [topicApi.ts](../src/services/topicApi.ts) |
| 메시지 스토어 | [useMessageStore.ts](../src/stores/useMessageStore.ts) |
| 토픽 스토어 | [useTopicStore.ts](../src/stores/useTopicStore.ts) |
| 메시지 매퍼 | [messageMapper.ts](../src/mapper/messageMapper.ts) |
| 메시지 헬퍼 | [messageHelpers.ts](../src/utils/messageHelpers.ts) |
| API 엔드포인트 | [constants/index.ts](../src/constants/index.ts) |

---

## 2. 메시지 생성 흐름

> **작성 예정**

### 2.1 전체 흐름 다이어그램

*(추후 작성)*

### 2.2 단계별 상세 설명

*(추후 작성)*

### 2.3 상태 관리 요약

*(추후 작성)*

### 2.4 에러 처리 흐름

*(추후 작성)*

### 2.5 관련 파일 목록

*(추후 작성)*

---

### 마지막 메시지 조건 ###
#### 메시지 id
id와 clientId 2가지 필드가 있다. 
id는 서버에서 생성, clientId는 클라이언트에서 생성한다.
서버는 세번째 메시지부터 저장한다.
그러므로 화면에 보이는 세번째 메시지가 마지막 메시지로 삭제될 시 토픽도 삭제된다.

#### 메시지 종류
첫번째 메시지는 사용자의 계획 생성 요청 메시지.
두번째 메시지는 어시스턴트의 계획 생성 응답 메시지.
세번째 메시지는 어시스턴트의 보고서 응답 메시지.
네번째 메시지는 사용자의 보고서 수정 요청 메시지.
다섯번째 메시지는 어시스턴트의 보고서 응답 메시지.
... 이후 네번쨰 ~ 다섯번째 메시지 반복

**마지막 업데이트:** 2025-11-28
