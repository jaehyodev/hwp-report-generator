import type {MessageRole} from '@/types/domain/MessageModel'

// 메시지 응답
export interface MessageResponse {
    id: number
    topic_id: number
    role: MessageRole
    content: string
    seq_no: number
    created_at: string
}

// 메시지 목록 응답
export interface MessageListResponse {
    messages: MessageResponse[]
    total: number
    topic_id: number
}

// 새 메시지 생성 요청
export interface CreateMessageRequest {
    role: MessageRole
    content: string
}