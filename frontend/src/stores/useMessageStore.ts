import {create} from 'zustand'
import {message as antdMessage} from 'antd'
import {messageApi} from '../services/messageApi'
import {artifactApi} from '../services/artifactApi'
import {mapMessageResponsesToModels, mapMessageModelsToUI} from '../mapper/messageMapper'
import {enrichMessagesWithArtifacts} from '../utils/messageHelpers'
import type {MessageModel} from '../models/MessageModel'
import type {MessageUI} from '../models/ui/MessageUI'

/**
 * useMessageStore.ts
 *
 * 메시지 관련 상태 관리 (전역)
 * - 메시지 데이터 (topicId별)
 * - UI 상태 (생성/삭제 중)
 * - API 호출 로직 (fetchMessages, refreshMessages)
 */

interface MessageStore {
    // 메시지 데이터 (topicId별로 관리)
    messagesByTopic: Map<number, MessageModel[]>

    // UI 상태
    isGeneratingMessage: boolean
    isDeletingMessage: boolean
    isLoadingMessages: boolean

    generatingReportStatus?: {
        topicId: number
        status: 'pending' | 'generating' | 'completed' | 'failed'
        progressPercent: number
        artifactId?: number
        errorMessage?: string
    }

    // 메시지 데이터 Actions
    setMessages: (topicId: number, messages: MessageModel[]) => void
    addMessages: (topicId: number, messages: MessageModel[]) => void
    clearMessages: (topicId: number) => void
    getMessages: (topicId: number) => MessageModel[]
    getMessagesUI: (topicId: number) => MessageUI[]
    setGeneratingReportStatus: (status?: MessageStore['generatingReportStatus']) => void

    // UI 상태 Actions
    setIsGeneratingMessage: (generating: boolean) => void
    setIsDeletingMessage: (deleting: boolean) => void
    setIsLoadingMessages: (loading: boolean) => void

    // API Actions
    loadMessages: (topicId: number) => Promise<void>
    refreshMessages: (topicId: number) => Promise<void>
    mergeNewMessages: (topicId: number) => Promise<void>
    fetchMessages: (topicId: number) => Promise<void> // Deprecated: use loadMessages instead
}

export const useMessageStore = create<MessageStore>((set, get) => {
    // 개발 환경에서 MSW가 접근할 수 있도록 window 객체에 노출
    if (typeof window !== 'undefined') {
        // @ts-ignore
        window.__messageStore = {getState: get}
    }

    return {
        // 초기 상태
        messagesByTopic: new Map(),
        isGeneratingMessage: false,
        isDeletingMessage: false,
        isLoadingMessages: false,

        // 메시지 데이터 Actions
        setMessages: (topicId, messages) =>
            set((state) => {
                const newMap = new Map(state.messagesByTopic)
                newMap.set(topicId, messages)
                return {messagesByTopic: newMap}
            }),

        addMessages: (topicId, newMessages) =>
            set((state) => {
                const newMap = new Map(state.messagesByTopic)
                const existing = newMap.get(topicId) || []
                newMap.set(topicId, [...existing, ...newMessages])
                return {messagesByTopic: newMap}
            }),

        clearMessages: (topicId) =>
            set((state) => {
                const newMap = new Map(state.messagesByTopic)
                newMap.delete(topicId)
                return {messagesByTopic: newMap}
            }),

        getMessages: (topicId) => {
            const state = get()
            return state.messagesByTopic.get(topicId) || []
        },

        getMessagesUI: (topicId) => {
            const messages = get().messagesByTopic.get(topicId) || []
            return mapMessageModelsToUI(messages)
        },

        // UI 상태 Actions
        setIsGeneratingMessage: (generating) => set({isGeneratingMessage: generating}),
        setIsDeletingMessage: (deleting) => set({isDeletingMessage: deleting}),
        setIsLoadingMessages: (loading) => set({isLoadingMessages: loading}),

        // API Actions
        /**
         * 특정 주제의 메시지 리스트 조회 (아티팩트 포함)
         * - 실제 topicId에 대해 백엔드에서 메시지 조회
         * - 임시 topicId(-1)의 메시지와 병합하지 않음 (MSW가 처리)
         */
        fetchMessages: async (topicId: number) => {
            set({isLoadingMessages: true})
            try {
                // ✅ 임시 topicId(음수)인 경우 백엔드 호출하지 않음
                if (topicId < 0) {
                    // 이미 addOutlineMessage로 저장된 메시지 사용
                    set({isLoadingMessages: false})
                    return
                }

                // 1. 메시지 리스트 조회
                const messagesResponse = await messageApi.listMessages(topicId)

                // 2. Response → Model 변환
                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)

                // 3. 아티팩트 리스트 불러오기
                try {
                    const artifactsResponse = await artifactApi.listArtifactsByTopic(topicId)

                    // 4. 아티팩트가 있으면 메시지에 연결
                    if (artifactsResponse.artifacts.length > 0) {
                        const messagesWithArtifacts = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)
                        get().setMessages(topicId, messagesWithArtifacts)
                    } else {
                        get().setMessages(topicId, messageModels)
                    }
                } catch (error) {
                    console.error('Failed to load artifacts:', error)
                    // 아티팩트 로드 실패 시에도 메시지는 표시
                    get().setMessages(topicId, messageModels)
                }
            } catch (error: any) {
                console.error('Failed to load messages:', error)
                antdMessage.error('메시지를 불러오는데 실패했습니다.')
            } finally {
                set({isLoadingMessages: false})
            }
        },

        /**
         * 토픽 전환 시 메시지 로드 (전체 교체)
         * 사이드바 클릭, 토픽 리스트에서 선택 시 사용
         */
        loadMessages: async (topicId: number) => {
            set({isLoadingMessages: true})
            try {
                // 임시 topicId(음수)인 경우 백엔드 호출하지 않음
                if (topicId < 0) {
                    set({isLoadingMessages: false})
                    return
                }

                // 1. 메시지 리스트 조회
                const messagesResponse = await messageApi.listMessages(topicId)
                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)

                // 2. 아티팩트 리스트 조회 및 연결
                try {
                    const artifactsResponse = await artifactApi.listArtifactsByTopic(topicId)

                    if (artifactsResponse.artifacts.length > 0) {
                        const messagesWithArtifacts = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)
                        get().setMessages(topicId, messagesWithArtifacts)
                    } else {
                        get().setMessages(topicId, messageModels)
                    }
                } catch (error) {
                    console.error('Failed to load artifacts:', error)
                    // 아티팩트 로드 실패 시에도 메시지는 표시
                    get().setMessages(topicId, messageModels)
                }
            } catch (error: any) {
                console.error('Failed to load messages:', error)
                antdMessage.error('메시지를 불러오는데 실패했습니다.')
            } finally {
                set({isLoadingMessages: false})
            }
        },

        /**
         * 메시지 리스트 재조회 (AI 응답 후, 삭제 후)
         * 전체 교체 방식
         */
        refreshMessages: async (topicId: number) => {
            try {
                // 1. 메시지 리스트 조회
                const messagesResponse = await messageApi.listMessages(topicId)

                // 2. Response → Model 변환
                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)

                // 3. 아티팩트 강제 갱신
                const artifactsResponse = await artifactApi.listArtifactsByTopic(topicId)

                if (artifactsResponse.artifacts.length > 0) {
                    const messagesWithArtifacts = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)
                    get().setMessages(topicId, messagesWithArtifacts)
                } else {
                    get().setMessages(topicId, messageModels)
                }
            } catch (error) {
                console.error('Failed to reload messages:', error)
                antdMessage.error('메시지를 불러오는데 실패했습니다.')
                throw error
            }
        },

        /**
         * 서버에서 새 메시지를 가져와 기존 메시지와 병합 (중복 제거)
         * generateReportFromPlan 후 사용 - 계획 메시지 유지하면서 서버 메시지 추가
         * handleSendMessage 후 사용 - 임시 사용자 메시지를 서버 메시지로 교체
         */
        mergeNewMessages: async (topicId: number) => {
            try {
                // 1. 서버에서 메시지 + Artifact 조회
                const messagesResponse = await messageApi.listMessages(topicId)
                console.log('mergeNewMessages: fetched messages', messagesResponse.messages)
                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)

                const artifactsResponse = await artifactApi.listArtifactsByTopic(topicId)
                const serverMessages = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)

                // 2. 기존 메시지 가져오기 (계획 메시지 포함)
                const existingMessages = get().getMessages(topicId)

                // 3. 임시 사용자 메시지 제거 (첫 번째 메시지는 제외)
                const permanentMessages = existingMessages.filter((msg, index) => {
                    // 첫 번째 메시지(index=0)는 무조건 유지 (계획 요청 메시지)
                    if (index === 0) {
                        return true
                    }

                    // 두 번째 메시지부터: ID가 없는 사용자 메시지는 임시이므로 제거
                    if (msg.role === 'user' && !msg.id) {
                        console.log(`[${index}] 임시 메시지 제거:`, msg.content.substring(0, 50))
                        return false
                    }
                    return true
                })

                // 4. 중복 제거: 영구 메시지의 ID 기반으로 중복 체크
                const existingIds = new Set(permanentMessages.filter((m) => m.id).map((m) => m.id))

                const newMessages = serverMessages.filter((m) => {
                    // ID가 없으면 무조건 추가 (서버에서 온 임시 메시지)
                    if (!m.id) return true
                    // ID가 있으면 중복 체크
                    return !existingIds.has(m.id)
                })

                // 5. 병합 (영구 메시지 + 새 서버 메시지)
                get().setMessages(topicId, [...permanentMessages, ...newMessages])

                console.log('✅ mergeNewMessages 완료:', {
                    topicId,
                    removedTemp: existingMessages.length - permanentMessages.length,
                    existing: permanentMessages.length,
                    new: newMessages.length,
                    total: permanentMessages.length + newMessages.length
                })
            } catch (error) {
                console.error('Failed to merge messages:', error)
                // 에러 시에도 기존 메시지 유지 (아무 작업 안 함)
            }
        },

        setGeneratingReportStatus: (status) => set({ generatingReportStatus: status }),
    }
})
