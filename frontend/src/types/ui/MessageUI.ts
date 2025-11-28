import type {MessageRole} from '@/types/domain/MessageModel'
import type {Artifact} from '@/types/artifact'

/**
 * UI 표시용 메시지 모델
 */
export interface MessageUI {
    id: number | undefined // 보고서 생성 전에는 id가 없을 수 있음
    role: MessageRole
    content: string
    // seqNo: number | undefined // 보고서 생성 전에는 seqNo가 없을 수 있음
    // artifacts?: Artifact[] // 메시지와 연관된 아티팩트 목록 (MD, HWPX 등)
    isPlan?: boolean // 계획 메시지인지 여부 (true: OutlineMessage, false/undefined: ChatMessage)
    clientId: number // UI 렌더링용 고유 ID (React key로 사용)
    timestamp: Date
    isOutline?: boolean // Outline 모드 여부 (개요 버튼 표시용)
    reportData?: {
        // md 아티팩트 내용
        reportId: number
        filename: string
        content: string
    }
}
