import {create} from 'zustand'
import {topicApi} from '../services/topicApi'
import {messageApi} from '../services/messageApi'
import {artifactApi} from '../services/artifactApi'
import type {Topic, TopicUpdate, PlanResponse} from '../types/topic'
import type {MessageModel} from '@/types/domain/MessageModel'
import type {Template} from '../types/template'
import {UI_CONFIG} from '../constants'
import {useMessageStore} from './useMessageStore'
import {mapMessageResponsesToModels} from '../mapper/messageMapper'
import {enrichMessagesWithArtifacts} from '../utils/messageHelpers'

/**
 * useTopicStore.ts
 *
 * 토픽 관리
 */

interface TopicStore {
    // State - Sidebar용 (항상 첫 페이지만 표시)
    sidebarTopics: Topic[]
    sidebarLoading: boolean

    // State - TopicListPage용 (페이지네이션)
    pageTopics: Topic[]
    pageLoading: boolean
    pageTotalTopics: number
    pageCurrentPage: number
    pagePageSize: number

    // State - 공통
    selectedTopicId: number | null
    selectedTemplateId: number | null // 선택된 토픽의 템플릿 ID
    selectedTemplate: Template | null // 선택된 템플릿 전체 정보
    useTemplate: boolean // 대화 시작 전 템플릿 사용 여부
    isTemplateSelected: boolean // 대화 시작 전 템플릿 선택 여부

    // State - 계획 생성
    plan: PlanResponse | null
    planLoading: boolean
    planError: string | null

    // State - AI 응답 생성 중인 토픽 ID 목록
    messageGeneratingTopicIds: Set<number>

    // Actions - Sidebar용
    loadSidebarTopics: () => Promise<void>

    // Actions - TopicListPage용
    loadPageTopics: (page: number, pageSize: number) => Promise<void>

    // Actions - 공통 (양쪽 리스트에 모두 반영)
    addTopic: (topic: Topic) => void
    updateTopicInBothLists: (topicId: number, updates: Partial<Topic>) => void
    removeTopicFromBothLists: (topicId: number) => Promise<void>
    setSelectedTopicId: (id: number | null, templateId?: number | null) => void
    setSelectedTemplateId: (id: number | null) => void
    setSelectedTemplate: (template: Template | null) => void
    setUseTemplate: (value: boolean) => void
    setIsTemplateSelected: (value: boolean) => void
    refreshTopic: (topicId: number) => Promise<void>
    updateTopicById: (topicId: number, data: TopicUpdate) => Promise<void>
    deleteTopicById: (topicId: number) => Promise<void>
    updateMessagesTopic: (oldTopicId: number, newTopicId: number) => void

    // Actions - 계획 생성
    generatePlan: (
        topic: string,
        isTemplateUsed: boolean,
        templateId: number | null, 
        isWebSearch: boolean
    ) => Promise<void>
    handleTopicPlanWithMessages: (
        isTemplateUsed: boolean,
        templateId: number | null,
        userMessage: string,
        addMessages: (topicId: number, messages: MessageModel[]) => void
    ) => Promise<void>
    updatePlan: (newPlan: string) => void
    clearPlan: () => void

    // Actions - 보고서 생성
    generateReportFromPlan: (isEdit: boolean) => Promise<{ ok: boolean, error?: any, topicId: number}>

    // Actions - 생성 상태 관리
    addGeneratingTopicId: (topicId: number) => void
    removeGeneratingTopicId: (topicId: number) => void
    isTopicGenerating: (topicId: number | null) => boolean
}

export const useTopicStore = create<TopicStore>((set, get) => {

    return {
        // 초기 상태 - Sidebar용
        sidebarTopics: [],
        sidebarLoading: false,

        // 초기 상태 - TopicListPage용
        pageTopics: [],
        pageLoading: false,
        pageTotalTopics: 0,
        pageCurrentPage: 1,
        pagePageSize: 20,

        // 초기 상태 - 공통
        selectedTopicId: null,
        selectedTemplateId: null,
        selectedTemplate: null,
        useTemplate: true,
        isTemplateSelected: false,

        // 초기 상태 - 계획 생성
        plan: null,
        planLoading: false,
        planError: null,
        isPlanEditByTopic: new Map<number, boolean>(),

        // 초기 상태 - AI 응답 생성 중인 토픽 ID 목록
        messageGeneratingTopicIds: new Set(),

        // Sidebar용 토픽 로드 (항상 첫 페이지만)
        loadSidebarTopics: async () => {
            set({sidebarLoading: true})
            try {
                const response = await topicApi.listTopics('active', 1, UI_CONFIG.PAGINATION.SIDEBAR_TOPICS_PER_PAGE)

                set({
                    sidebarTopics: response.topics,
                    sidebarLoading: false
                })
            } catch (error) {
                console.error('Failed to load sidebar topics:', error)
                set({sidebarLoading: false})
                throw error
            }
        },

        // TopicListPage용 토픽 로드 (페이지네이션)
        loadPageTopics: async (page, pageSize) => {
            set({pageLoading: true})
            try {
                const response = await topicApi.listTopics('active', page, pageSize)

                set({
                    pageTopics: response.topics,
                    pageTotalTopics: response.total,
                    pageCurrentPage: page,
                    pagePageSize: pageSize,
                    pageLoading: false
                })
            } catch (error) {
                console.error('Failed to load page topics:', error)
                set({pageLoading: false})
                throw error
            }
        },

        // 토픽 생성 후 양쪽 리스트에 추가 (중복 체크 포함)
        addTopic: (topic) => {
            set((state) => {
                // 중복 체크: 이미 존재하는 토픽이면 추가하지 않음
                const existsInSidebar = state.sidebarTopics.some((t) => t.id === topic.id)
                const existsInPage = state.pageTopics.some((t) => t.id === topic.id)

                // Sidebar: 중복이 아닐 경우에만 추가
                const newSidebarTopics = existsInSidebar
                    ? state.sidebarTopics
                    : [topic, ...state.sidebarTopics].slice(0, UI_CONFIG.PAGINATION.SIDEBAR_TOPICS_PER_PAGE)

                // Page: 중복이 아닐 경우에만 추가
                const newPageTopics = existsInPage
                    ? state.pageTopics
                    : [topic, ...state.pageTopics]

                return {
                    sidebarTopics: newSidebarTopics,
                    pageTopics: newPageTopics
                }
            })
        },

        // 토픽 업데이트 (양쪽 리스트에 모두 반영)
        updateTopicInBothLists: (topicId, updates) => {
            set((state) => ({
                sidebarTopics: state.sidebarTopics.map((topic) => (topic.id === topicId ? {...topic, ...updates} : topic)),
                pageTopics: state.pageTopics.map((topic) => (topic.id === topicId ? {...topic, ...updates} : topic))
            }))
        },

        // 토픽과 연관된 메시지들의 topicId 업데이트
        updateMessagesTopic: (oldTopicId: number, newTopicId: number) => {
            const messageStore = useMessageStore.getState()

            // oldTopicId의 메시지 가져오기
            const oldMessages = messageStore.getMessages(oldTopicId)

            if (!oldMessages || oldMessages.length === 0) {
                return
            }

            // topicId 변경한 새 메시지 배열 생성
            const updatedMessages = oldMessages.map((msg) => ({
                ...msg,
                topicId: newTopicId
            }))

            // 기존 임시 메시지 제거
            messageStore.clearMessages(oldTopicId)

            // 새 topicId로 메시지 세팅
            messageStore.setMessages(newTopicId, updatedMessages)
        },

        // 양쪽 리스트에서 토픽 삭제
        removeTopicFromBothLists: async (topicId) => {
            set((state) => ({
                sidebarTopics: state.sidebarTopics.filter((topic) => topic.id !== topicId),
                pageTopics: state.pageTopics.filter((topic) => topic.id !== topicId),
                selectedTopicId: state.selectedTopicId === topicId ? null : state.selectedTopicId
            }))

            // 사이드바 토픽 재로드 (삭제 후 빈 자리를 채우기 위해)
            try {
                await get().loadSidebarTopics()
            } catch (error) {
                console.error('Failed to reload sidebar topics after deletion:', error)
            }
        },

        // 선택된 토픽 ID 설정
        setSelectedTopicId: (id, templateId) => {
            const prevTopicId = get().selectedTopicId

            // 토픽 전환 시
            if (prevTopicId !== id) {
                const messageStore = useMessageStore.getState()

                // 계획 모드(topicId=0)에서 실제 토픽으로 이동 시 정리
                if (prevTopicId === 0 && id !== null && id !== 0) {
                    messageStore.clearMessages(0)
                    get().clearPlan() // plan 상태도 함께 정리
                }
            }

            // templateId가 제공되면 함께 설정
            if (templateId !== undefined) {
                set({selectedTopicId: id, selectedTemplateId: templateId})
            } else {
                set({selectedTopicId: id})
            }
        },

        // 선택된 템플릿 ID 설정
        setSelectedTemplateId: (id) => {
            set({selectedTemplateId: id})
        },

        // 선택된 템플릿 전체 정보 설정
        setSelectedTemplate: (template) => {
            set({selectedTemplate: template})
        },

        // 템플릿 사용 여부 설정
        setUseTemplate: (value) => {
            set({useTemplate: value})
        },

        // 템플릿 선택 여부 설정
        setIsTemplateSelected: (value) => {
            set({isTemplateSelected: value})
        },

        // 특정 토픽 조회 (API 호출 + 양쪽 상태 업데이트)
        refreshTopic: async (topicId) => {
            try {
                const updatedTopic = await topicApi.getTopic(topicId)
                get().updateTopicInBothLists(topicId, updatedTopic)
            } catch (error) {
                console.error('Failed to refresh topic:', error)
                throw error
            }
        },

        // 특정 토픽 수정 (API 호출 + 양쪽 상태 업데이트)
        updateTopicById: async (topicId, data) => {
            try {
                const updatedTopic = await topicApi.updateTopic(topicId, data)
                get().updateTopicInBothLists(topicId, updatedTopic)
            } catch (error) {
                console.error('Failed to update topic:', error)
                throw error
            }
        },

        // 토픽 삭제 (API 호출 + 양쪽 스토어에서 삭제)
        deleteTopicById: async (topicId) => {
            try {
                await topicApi.deleteTopic(topicId)
                get().removeTopicFromBothLists(topicId)
            } catch (error) {
                console.error('Failed to delete topic:', error)
                throw error
            }
        },

        // 보고서 작성 계획 생성
        generatePlan: async (topic, isTemplateUsed, templateId, isWebSearch) => {
            set({
                planLoading: true, 
                planError: null
            })
            
            try {
                const result = await topicApi.generateTopicPlan({
                    topic: topic,
                    isTemplateUsed: isTemplateUsed,
                    template_id: templateId || 1,
                    isWebSearch: isWebSearch
                })

                set({
                    plan: result,
                    planLoading: false,
                    planError: null
                })
            } catch (error: any) {
                // 서버 에러 메시지 우선, 없으면 기본 메시지
                const errorMessage = error.response?.data?.error?.message || '계획 생성에 실패했습니다.'
                console.error('Failed to generate plan:', error)
                set({
                    plan: null,
                    planLoading: false,
                    planError: errorMessage
                })
                throw error
            }
        },

        // 보고서 계획 요청 + 메시지 관리
        handleTopicPlanWithMessages: async (isTemplateUsed, templateId, userMessage, addMessages) => {
            if (!userMessage.trim()) {
                throw new Error('EMPTY_MESSAGE')
            }

            const topic = userMessage.trim()
            const isWebSearch = true // 임시 true
            const tempTopicId = 0 // 임시 topicId 고정

            // 1. 사용자 메시지를 UI에 즉시 표시하기위해 생성
            const userMsgModel: MessageModel = {
                id: undefined, // 임시
                topicId: tempTopicId,
                role: 'user',
                content: userMessage.trim(),
                seqNo: undefined,
                createdAt: new Date().toISOString(),
                isPlan: false
            }

            // 2. 사용자 메시지 상태에 추가
            addMessages(tempTopicId, [userMsgModel])

            // 즉시 selectedTopicId 설정 (사용자 메시지가 바로 보이도록)
            set({selectedTopicId: tempTopicId})

            // AI 응답 대기 상태 설정 (GeneratingIndicator 표시)
            get().addGeneratingTopicId(tempTopicId)

            try {
                // 3. 계획 생성 API 호출
                await get().generatePlan(topic, isTemplateUsed, templateId, isWebSearch)

                // 4. plan 상태에서 결과 가져와서 메시지로 추가,
                const currentPlan = get().plan
                if (currentPlan) {
                    const messageStore = useMessageStore.getState()

                    // 서버에서 메시지들을 먼저 가져옵니다 (selectedTopicId 변경 전에!)
                    try {
                        // 기존 메시지 및 아티팩트를 서버에서 가져와 표시합니다.
                        const messagesResponse = await messageApi.listMessages(currentPlan?.topic_id)
                        const messageModels = mapMessageResponsesToModels(messagesResponse.messages)
                        const artifactsResponse = await artifactApi.listArtifactsByTopic(currentPlan?.topic_id)
                        const serverMessages = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)

                        // 실제 토픽 ID에 메시지 먼저 설정 (화면 깜빡임 방지)
                        messageStore.setMessages(currentPlan?.topic_id, serverMessages)
                    } catch (fetchError) {
                        console.error("Failed to fetch initial messages for realTopicId:", fetchError);
                        // 메시지 로딩 실패 시 에러 처리 (예: 사용자에게 알림)
                        // return { ok: false, error: 'FAILED_TO_LOAD_MESSAGES', topicId: realTopicId };
                    }

                    // 계획 생성 시 토픽을 사이드바에 추가
                    try {
                        const newTopic = await topicApi.getTopic(currentPlan.topic_id)
                        get().addTopic(newTopic)
                    } catch (error) {
                        console.error('Failed to fetch new topic for sidebar:', error)
                        get().loadSidebarTopics()
                    }

                    // 현재 토픽을 실제 토픽으로 변경 (메시지 설정 후에!)
                    set({ selectedTopicId: currentPlan?.topic_id })

                    // 임시 토픽(0)의 메시지 제거 (selectedTopicId 변경 후에!)
                    messageStore.clearMessages(0)
                }

                // PLAN 생성 완료 - GeneratingIndicator 숨기기
                get().removeGeneratingTopicId(tempTopicId)
            } catch (error: any) {
                console.error('개요 요청 실패:', error)
                const currentError = get().planError

                // 에러 메시지 추가
                const errorMsgModel: MessageModel = {
                    id: undefined,
                    topicId: tempTopicId,
                    role: 'assistant',
                    content: currentError || '보고서 계획 생성에 실패했습니다.',
                    seqNo: undefined,
                    createdAt: new Date().toISOString(),
                    isPlan: true // 계획 메시지 표시
                }
                addMessages(tempTopicId, [errorMsgModel])

                // PLAN 생성 실패 - GeneratingIndicator 숨기기
                get().removeGeneratingTopicId(tempTopicId)

                // 에러를 다시 throw하여 호출자에서 처리하도록 함
                throw error
            }
        },

        // 계획 업데이트
        updatePlan: (newPlan) => {
            set((state) => {
                if (!state.plan) return state

                return {
                    plan: {
                        ...state.plan,
                        plan: newPlan
                    }
                }
            })
        },

        // 계획 초기화
        clearPlan: () => {
            set({
                plan: null,
                planLoading: false,
                planError: null
            })
        },

        // 생성 중인 토픽 ID 추가
        addGeneratingTopicId: (topicId: number) => {
            set((state) => {
                const newSet = new Set(state.messageGeneratingTopicIds)
                newSet.add(topicId)
                return {messageGeneratingTopicIds: newSet}
            })
        },

        // 생성 중인 토픽 ID 제거
        removeGeneratingTopicId: (topicId: number) => {
            set((state) => {
                const newSet = new Set(state.messageGeneratingTopicIds)
                newSet.delete(topicId)
                return {messageGeneratingTopicIds: newSet}
            })
        },

        // 특정 토픽이 생성 중인지 확인
        isTopicGenerating: (topicId: number | null) => {
            if (topicId === null) return false
            return get().messageGeneratingTopicIds.has(topicId)
        },

        /**
         * 계획 기반 보고서 생성
         * "예" 클릭 시 호출 - 백그라운드에서 실제 보고서 생성
         */
        generateReportFromPlan: async (isEdit: boolean) => {
            const state = get()
            const { plan } = state

            if (!plan) {
                // plan이 없는 것은 topicId가 없으므로 0 사용
                return { ok: false, error: 'NO_PLAN', topicId: 0 } 
            }

            const realTopicId = plan.topic_id
            const messageStore = useMessageStore.getState()

            try {
                // 기존 메시지 및 아티팩트를 서버에서 가져와 표시합니다.
                const messagesResponse = await messageApi.listMessages(realTopicId)
                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)
                const artifactsResponse = await artifactApi.listArtifactsByTopic(realTopicId)
                const serverMessages = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)
                messageStore.setMessages(realTopicId, serverMessages) // 실제 토픽 ID에 메시지 설정
                messageStore.clearMessages(0) // 임시 토픽(0)의 메시지 제거
            } catch (fetchError) {
                console.error("Failed to fetch initial messages for realTopicId:", fetchError);
                // 메시지 로딩 실패 시 에러 처리 (예: 사용자에게 알림)
                // return { ok: false, error: 'FAILED_TO_LOAD_MESSAGES', topicId: realTopicId };
            }

            // AI 응답 대기 상태 설정 (GeneratingIndicator 표시)
            get().addGeneratingTopicId(realTopicId) // 로딩 인디케이터를 실제 토픽 ID에 연결

            // 💡 Promise로 감싸서 최종 결과를 기다리도록 합니다. 외부 try...catch를 제거하고 Promise 내부에서 처리합니다.
            return new Promise(async (resolve) => {
                try {
                    // 1. 백그라운드 보고서 생성 API 호출
                    await topicApi.generateReport(realTopicId, {
                        topic: plan.plan.split('\n')[0].replace('# ', '').replace(' 작성 계획', ''), // 첫 줄에서 주제 추출
                        plan: plan.plan,
                        isEdit,
                        isWebSearch: true
                    })

                    // 2. 202 Accepted - 백그라운드에서 생성 중, SSE 시작
                    let isCompleted = false

                    const unsubscribe = topicApi.getGenerationStatusStream(
                        realTopicId,
                        async (status) => {
                            if (isCompleted) return // 이미 완료/실패 처리됐으면 무시
                        
                            // SSE 상태를 메시지 스토어에 반영
                            messageStore.setGeneratingReportStatus({
                                topicId: realTopicId,
                                status: status.status,
                                progressPercent: status.progress_percent ?? 0,
                                artifactId: status.artifact_id,
                                errorMessage: status.error_message
                            });

                            if (status.status === 'completed') {
                                isCompleted = true
                                unsubscribe()

                                // 3-1. GeneratingIndicator 먼저 제거 (UI 순서: indicator 제거 → 메시지 표시)
                                get().removeGeneratingTopicId(realTopicId)

                                // 3-2. 완료 시 데이터 병합 및 상태 업데이트 로직
                                const messagesResponse = await messageApi.listMessages(realTopicId)
                                const messageModels = mapMessageResponsesToModels(messagesResponse.messages)
                                const artifactsResponse = await artifactApi.listArtifactsByTopic(realTopicId)
                                const serverMessages = await enrichMessagesWithArtifacts(messageModels, artifactsResponse.artifacts)
                                messageStore.setMessages(realTopicId, serverMessages)
                                messageStore.clearMessages(0)

                                // 3-3. 보고서 생성 완료 시 토픽 정보 업데이트 (이미 사이드바에 있으므로 addTopic이 아닌 updateTopicInBothLists)
                                try {
                                    const updatedTopic = await topicApi.getTopic(realTopicId)
                                    get().updateTopicInBothLists(realTopicId, updatedTopic)
                                } catch (error) {
                                    console.error('Failed to update topic after report generation:', error)
                                }

                                // ✅ Promise resolve: 성공 상태를 반환
                                resolve({ ok: true, topicId: realTopicId })
                            } else if (status.status === 'failed') {
                                isCompleted = true
                                unsubscribe()

                                get().removeGeneratingTopicId(realTopicId)
                                messageStore.setGeneratingReportStatus(undefined)

                                // ✅ Promise resolve: 비즈니스 로직 상 ok: false를 반환하여 호출자에게 알림
                                resolve({ ok: false, error: status.error_message || '보고서 생성 실패', topicId: realTopicId })
                            }
                        },
                        // SSE 에러 핸들러
                        (error) => {
                            if (isCompleted) return
                            isCompleted = true
                            unsubscribe()

                            console.error('SSE error:', error)

                            get().removeGeneratingTopicId(realTopicId)
                            messageStore.setGeneratingReportStatus(undefined)

                            // ✅ Promise resolve: 에러 상태 반환
                            resolve({ ok: false, error: error, topicId: realTopicId})
                        }
                    )
                } catch (error: any) {
                    // 4. 최초 topicApi.generateTopicBackground 호출 실패 처리
                    console.error('보고서 생성 요청 실패:', error)
                    get().removeGeneratingTopicId(realTopicId)

                    // ✅ Promise resolve: 실패 상태 반환
                    resolve({ ok: false, error: error, topicId: realTopicId })
                }
            })
        }
    }
})