import api from './api'
import {API_BASE_URL, API_ENDPOINTS} from '@/constants/'
import type {TopicUpdate, Topic, TopicListResponse, AskRequest, AskResponse, PlanRequest, PlanResponse, TopicGenerationStatus, ReportGenerationRequest, ReportGenerationResponse} from '@/types/topic'
import type {ApiResponse} from '@/types/api'
import { storage } from '@/utils/storage'
import { fetchEventSource } from '@microsoft/fetch-event-source'

/**
 * topicApi.ts
 *
 * 토픽(대화 스레드) 관련 API 함수 모음
 */

export const topicApi = {
    /**
     * 토픽 목록 조회
     * GET /api/topics
     * @param status 토픽 상태 필터 (optional)
     * @param page 페이지 번호
     * @param pageSize 페이지 크기
     * @returns 토픽 목록
     */
    listTopics: async (status?: string, page: number = 1, pageSize: number = 20): Promise<TopicListResponse> => {
        const params = new URLSearchParams()
        if (status) params.append('status', status)
        params.append('page', page.toString())
        params.append('page_size', pageSize.toString())

        console.log('/api/topics >> request(status, page, pageSize): ', status, page, pageSize) 

        const response = await api.get<ApiResponse<TopicListResponse>>(`${API_ENDPOINTS.LIST_TOPICS}?${params.toString()}`)

        if (!response.data.success || !response.data.data) {
            console.log('/api/topics >> failed >> response.data: ', response.data)

            throw new Error(response.data.error?.message || '토픽 목록 조회에 실패했습니다.')
        }

        console.log('/api/topics >> success >> response.data: ', response.data)

        return response.data.data
    },

    /**
     * 특정 토픽 조회
     * GET /api/topics/{topicId}
     * @param topicId 토픽 ID
     * @returns 토픽 정보
     */
    getTopic: async (topicId: number): Promise<Topic> => {
        console.log(`/api/topics/${topicId} >> request(topicId): `, topicId)

        const response = await api.get<ApiResponse<Topic>>(API_ENDPOINTS.GET_TOPIC(topicId))

        if (!response.data.success || !response.data.data) {
            console.log(`/api/topics/${topicId} >> failed >> response.data: `, response.data)

            throw new Error(response.data.error?.message || '토픽 조회에 실패했습니다.')
        }

        console.log(`/api/topics/${topicId} >> success >> response.data: `, response.data)

        return response.data.data
    },

    /**
     * 토픽 업데이트
     * PATCH /api/topics/{topicId}
     * @param topicId 토픽 ID
     * @param data 업데이트 데이터
     * @returns 업데이트된 토픽
     */
    updateTopic: async (topicId: number, data: TopicUpdate): Promise<Topic> => {
        console.log(`/api/topics/${topicId} >> request(topicId, data): `, topicId, data)

        const response = await api.patch<ApiResponse<Topic>>(API_ENDPOINTS.UPDATE_TOPIC(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log(`/api/topics/${topicId} >> failed >> response.data: `, response.data)

            throw new Error(response.data.error?.message || '토픽 업데이트에 실패했습니다.')
        }

        console.log(`/api/topics/${topicId} >> success >> response.data: `, response.data)

        return response.data.data
    },

    /**
     * 토픽 삭제
     * DELETE /api/topics/{topicId}
     * @param topicId 토픽 ID
     */
    deleteTopic: async (topicId: number): Promise<void> => {
        console.log(`/api/topics/${topicId} >> request(topicId): `, topicId)

        const response = await api.delete<ApiResponse<void>>(API_ENDPOINTS.DELETE_TOPIC(topicId))

        if (!response.data.success) {
            console.log(`/api/topics/${topicId} >> failed >> response.data: `, response.data)

            throw new Error(response.data.error?.message || '토픽 삭제에 실패했습니다.')
        }

        console.log(`/api/topics/${topicId} >> success >> response.data: `, response.data)
    },

    /**
     * 메시지 체이닝 (대화 이어가기)
     * POST /api/topics/{topicId}/ask
     * @param topicId 토픽 ID
     * @param data Ask 요청 데이터
     * @returns AskResponse
     */
    ask: async (topicId: number, data: AskRequest): Promise<AskResponse> => {
        console.log(`/api/ask/topics/${topicId}/ask >> request(topicId, data): `, topicId, data)

        const response = await api.post<ApiResponse<AskResponse>>(API_ENDPOINTS.ASK(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log(`/api/ask/topics/${topicId}/ask >> failed >> response.data: `, response.data)

            throw new Error(response.data.error?.message || '질문 전송에 실패했습니다.')
        }

        console.log(`/api/ask/topics/${topicId}/ask >> success >> response.data: `, response.data)

        return response.data.data
    },

    /**
     * 보고서 계획 생성
     * POST /api/topics/plan
     * @param data Plan 요청 데이터 (template_id, custom_prompt)
     * @returns 보고서 작성 계획 (plan, sections)
     */
    generateTopicPlan: async (data: PlanRequest): Promise<PlanResponse> => {
        console.log('/api/topics/plan >> request(data): ', data)

        const response = await api.post<ApiResponse<PlanResponse>>(API_ENDPOINTS.TOPIC_PLAN, data)

        if (!response.data.success || !response.data.data) {
            console.log('/api/topics/plan >> failed >> response.data: ', response.data)

            throw new Error(response.data.error?.message || '보고서 계획 생성에 실패했습니다.')
        }

        console.log('/api/topics/plan >> success >> response.data: ', response.data)

        return response.data.data
    },

    /**
     * 보고서 생성
     * POST /api/topics/:topicId/generate
     * @param topicId 토픽 ID
     * @param data
     * @returns 생성 상태 정보 (202 Accepted)
     */
    generateReport: async (topicId: number, data: ReportGenerationRequest
    ): Promise<ReportGenerationResponse> => {
        console.log(`/api/topics/${topicId}/generate >> request(data): `, data)

        const response = await api.post<ApiResponse<ReportGenerationResponse>>(API_ENDPOINTS.GENERATE_TOPIC_BACKGROUND(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log(`/api/topics/${topicId}/generate >> failed >> response.data: `, response.data)
            throw new Error(response.data.error?.message || '보고서 생성 요청에 실패했습니다.')
        }

        console.log(`/api/topics/${topicId}/generate >> success >> response.data: `, response.data)
        return response.data.data
    },

    /**
     * 보고서 생성 상태 조회 - 미사용
     * GET /api/topics/:topicId/status
     * @param topicId 토픽 ID
     * @returns 생성 상태 정보
     */
    getGenerationStatus: async (
        topicId: number
    ): Promise<{
        topic_id: number
        status: 'generating' | 'completed' | 'failed'
        progress_percent: number
        current_step?: string
        artifact_id?: number
        started_at?: string
        completed_at?: string
        error_message?: string
    }> => {
        const response = await api.get<
            ApiResponse<{
                topic_id: number
                status: 'generating' | 'completed' | 'failed'
                progress_percent: number
                current_step?: string
                artifact_id?: number
                started_at?: string
                completed_at?: string
                error_message?: string
            }>
        >(API_ENDPOINTS.GET_GENERATION_STATUS(topicId))

        if (!response.data.success || !response.data.data) {
            console.log('getGenerationStatus > failed >', response.data)
            throw new Error(response.data.error?.message || '상태 조회에 실패했습니다.')
        }

        return response.data.data
    },

    /**
     * 보고서 생성 상태(SSE) 실시간 구독
     * GET /api/topics/:topicId/status/stream
     *
     * 서버에서 보내는 SSE(EventStream)를 구독하여
     * 생성 진행률, 완료 여부, 에러 상태 등을 실시간으로 전달받는다.
     *
     * @param topicId 조회할 토픽 ID
     * @param onMessage 서버로부터 상태 이벤트를 받을 때 실행되는 콜백
     * @param onError SSE 연결 오류가 발생했을 때 실행되는 콜백(선택)
     * @returns SSE 연결을 중단하는 unsubscribe 함수
     */
    getGenerationStatusStream: (
        topicId: number,
        onMessage: (status: TopicGenerationStatus) => void,
        onError?: (error: any) => void
    ) => {
        // 토큰 추출
        const token = storage.getToken()
        const controller = new AbortController()

        // EventSource 생성
        fetchEventSource(`${API_BASE_URL}${API_ENDPOINTS.GET_GENERATION_STATUS_STREAM(topicId)}`, {
            method: 'GET',
            // axios가 아니라 token을 따로 붙여야함.
            headers: {
                Authorization: `Bearer ${token}`,
            },
            signal: controller.signal, // AbortController signal 추가
            openWhenHidden: true, // 탭이 숨겨져도 연결 유지 (재연결 방지)
            onmessage: (event) => {
                try {
                    const data = JSON.parse(event.data)
                    
                    console.log(`/api/topics/${topicId}/status/stream >> request(data): `, data)
                    
                    // event 타입에 따라 처리
                    if (data.event === 'status_update' || data.event === 'completion') {
                        onMessage({
                            topic_id: topicId,
                            status: data.status,
                            progress_percent: data.progress_percent ?? 0,
                            artifact_id: data.artifact_id,
                            error_message: data.error_message
                        })
                    }
                } catch (error) {
                    console.error(`/api/topics/${topicId}/status/stream >> error: `, error)
                }
            },
            onerror: (error) => {
                console.error(`/api/topics/${topicId}/status/stream >> error: `, error)
                if (onError) onError(error)
                // 에러 시 재연결 하지 않도록 throw
                throw error
            },
        })

        // 반환: 구독 취소용
        return () => {
            controller.abort()
        }
    }
}
