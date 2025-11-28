import {topicApi} from '../services/topicApi'
import {messageApi} from '../services/messageApi'
import {useTopicStore} from '../stores/useTopicStore'
import {useMessageStore} from '../stores/useMessageStore'
import type {MessageModel} from '@/types/domain/MessageModel'

/**
 * useChatActions.ts
 *
 * 메시지 전송 및 삭제 커스텀 훅
 * - MessageModel 기반으로 리팩토링
 * - 토스트는 호출하는 컴포넌트에서 처리
 */

interface UseChatActionsOptions {
    selectedTopicId: number | null
    setSelectedTopicId: (id: number | null) => void
    setMessages: (topicId: number, messages: MessageModel[]) => void
    refreshMessages: (topicId: number) => Promise<void>
}

/**
 * 결과 타입 정의
 */
interface SendMessageResult {
    ok: boolean
    error?: string // 에러 코드 (TOAST_MESSAGES 키)
}

interface DeleteMessageResult {
    ok: boolean
    error?: string // 에러 코드 (TOAST_MESSAGES 키)
    isLastMessage?: boolean
}

export const useChatActions = ({selectedTopicId, setSelectedTopicId, refreshMessages}: UseChatActionsOptions) => {
    /**
     * 메시지 전송 핸들러
     * - MessageModel 기반으로 동작
     * @returns {SendMessageResult} 성공/실패 결과와 에러 코드
     */
    const handleSendMessage = async (message: string, files: File[], webSearchEnabled: boolean): Promise<SendMessageResult> => {
        // 주제가 없는 지 확인
        if (selectedTopicId === null) {
            return { ok: false, error: 'TOPIC_SELECT_FIRST' }
        }

        const messageStore = useMessageStore.getState()
        const topicStore = useTopicStore.getState() 
        topicStore.addGeneratingTopicId(selectedTopicId) // 메시지 생성 중인 쓰레드 목록에 쓰레드 추가

        try {
            // 보고서 생성 이후 메시지 체이닝 (ask API) (selectedTopicId는 number 타입이 보장됨)

            // 임시 사용자 메시지 생성 - UI에 즉시 표시용
            const userMessage: MessageModel = {
                id: undefined, // 임시 메시지 표시 - 서버 응답 후 메시지를 제거 후, 새로 추가
                topicId: selectedTopicId,
                role: 'user',
                content: message.trim(),
                seqNo: undefined,
                createdAt: new Date().toISOString(),
                isPlan: false
            }

            // UI에 즉시 표시 (사용자 경험 향상)
            messageStore.addMessages(selectedTopicId, [userMessage])

            /*  선택된 참조 보고서 (미사용)
                let selectedArtifactId = getSelectedArtifactId(selectedTopicId)

                // 참조 보고서 선택: 선택된 아티팩트가 없으면 자동으로 최신 선택 (MD 파일만)
                if (!selectedArtifactId) {
                    const artifacts = await loadArtifacts(selectedTopicId)
                    const markdownArtifacts = artifacts.filter((art) => art.kind === 'md')
                    if (markdownArtifacts.length > 0) {
                        autoSelectLatest(selectedTopicId, markdownArtifacts)
                        selectedArtifactId = getSelectedArtifactId(selectedTopicId)
                    }
                }
            */

            // 서버에 사용자 메시지 전달 (응답은 현재 미사용)
            await topicApi.askTopic(selectedTopicId, {
                content: message,
                artifact_id: null, // 참조 보고서 미사용으로 현재는 서버에서 가장 최신 md 파일 참조
                include_artifact_content: true
            })

            // 서버에서 새 메시지 가져와 병합 (임시 사용자 메시지는 제거 후, 서버의 정식 메시지로 추가)
            await messageStore.mergeNewMessages(selectedTopicId)

            /*
                참조 보고서 미사용
                // Artifact 갱신
                const refreshedArtifacts: Artifact[] = await refreshArtifacts(selectedTopicId)

                // 새로운 MD 파일이 생성되므로 참조 보고서를 최신 MD 파일로 선택
                autoSelectLatest(selectedTopicId, refreshedArtifacts)
            */
            return { ok: true }
        } catch (error: any) {
            console.error('Error sending message:', error)
            // 서버 에러 메시지가 있으면 전달, 없으면 기본 코드 전달
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return { ok: false, error: serverMessage || 'MESSAGE_SEND_FAILED' }
        } finally {
            // 메시지가 전송 된 후, 메시지 생성 중인 쓰레드 목록에서 현재 쓰레드 제거
            useTopicStore.getState().removeGeneratingTopicId(selectedTopicId)
        }
    }

    /**
     * 메시지 삭제 핸들러
     * - MessageModel 기반으로 동작
     * @returns {DeleteMessageResult} 성공/실패 결과와 에러 코드
     */
    const handleDeleteMessage = async (
        messageId: number,
        messageclientId: number,
        setSelectedReport: (report: any) => void,
        selectedReport: any
    ): Promise<DeleteMessageResult> => {
        // 현재 선택된 토픽이 없는 경우는 메시지 삭제 불가
        if (!selectedTopicId) {
            return { ok: false, error: 'TOPIC_NOT_SELECTED' }
        }

        // 메시지 삭제 로딩 시작
        useMessageStore.getState().setIsDeletingMessage(true)

        try {
            // 마지막 메시지인지 확인 (마지막 메시지인 경우 토픽도 삭제 필수)
            // 0은 사용자의 첫 메시지
            // 1은 어시스턴트의 계획 메시지
            // 2는 어시스턴트의 보고서 메시지
            const isLastMessage = messageclientId === 2

            // 메시지 삭제 요청
            await messageApi.deleteMessage(selectedTopicId, messageId)

            // 미리보기 중인 보고서가 삭제된 메시지의 것이면 닫기
            if (selectedReport && selectedReport.messageId === messageId) {
                setSelectedReport(null)
            }

            // 마지막 메시지였다면 토픽도 삭제
            if (isLastMessage) {
                // 토픽 삭제
                const {deleteTopicById, setSelectedTemplateId} = useTopicStore.getState()
                await deleteTopicById(selectedTopicId)

                // 메시지 스토어에서 해당 토픽의 메시지 클리어
                useMessageStore.getState().clearMessages(selectedTopicId)

                // 현재 토픽 초기화
                setSelectedTopicId(null)
                setSelectedTemplateId(null)

                return { ok: true, isLastMessage: true }
            } else {
                // 아티팩트 자동 갱신 (삭제된 메시지의 아티팩트도 함께 삭제됨)
                await refreshMessages(selectedTopicId)
                return { ok: true, isLastMessage: false }
            }
        } catch (error: any) {
            console.error('useChatActions >> handleDeleteMessage >> ', error)
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return { ok: false, error: serverMessage || 'MESSAGE_DELETE_FAILED' }
        } finally {
            // 메시지 삭제 로딩 종료
            useMessageStore.getState().setIsDeletingMessage(false)
        }
    }

    return {
        handleSendMessage,
        handleDeleteMessage
    }
}
