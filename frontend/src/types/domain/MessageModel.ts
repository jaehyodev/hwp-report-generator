import type {Artifact} from '@/types/artifact'

export type MessageRole = 'user' | 'assistant' | 'system'

/**
 * 메시지 도메인 모델
 * - 백엔드 데이터의 순수한 표현
 * - artifacts: 메시지와 연관된 모든 아티팩트 (content 포함 가능)
 */
export interface MessageModel {
    id: number | undefined // 보고서 생성 전에는 id가 없을 수 있음
    topicId: number
    role: MessageRole
    content: string
    seqNo: number | undefined // 보고서 생성 전에는 seqNo가 없을 수 있음
    createdAt: string
    artifacts?: Artifact[] // 메시지와 연관된 아티팩트 목록 (MD, HWPX 등)
    isPlan?: boolean // 계획 메시지인지 여부 (true: OutlineMessage, false/undefined: ChatMessage)
}
