import {useMessageStore} from '../stores/useMessageStore'
import {mapMessageModelsToUI} from '../mapper/messageMapper'
import type {MessageUI} from '../types/ui/MessageUI'

/**
 * useMessages 커스텀 훅
 *
 * 선택된 토픽의 메시지를 구독하고 UI 변환을 수행합니다.
 *
 * @param selectedTopicId - 선택된 토픽 ID (null이면 빈 배열 반환)
 * @returns MessageUI[] - UI 표시용 메시지 배열
 */
export const useMessages = (selectedTopicId: number | null): MessageUI[] => {
    // ✅ messagesByTopic을 직접 구독
    const messagesByTopic = useMessageStore((state) => state.messagesByTopic)

    // selectedTopicId의 메시지만 추출 + UI 변환 (messagesByTopic 변경 시 자동 재계산)
    if (selectedTopicId === null) {
        return []
    }

    const messages = messagesByTopic.get(selectedTopicId) || []
    return mapMessageModelsToUI(messages)
}
