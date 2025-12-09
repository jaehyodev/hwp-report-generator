import api from './api'
import {API_BASE_URL, API_ENDPOINTS} from '@/constants/'
import type {TopicCreate, TopicUpdate, Topic, TopicListResponse, AskRequest, AskResponse, PlanRequest, PlanResponse, TopicGenerationStatus} from '../types/topic'
import type {ApiResponse} from '../types/api'
import { storage } from '@/utils/storage'
import { fetchEventSource } from '@microsoft/fetch-event-source'

/**
 * topicApi.ts
 *
 * 토픽(대화 스레드) 관련 API 함수 모음
 */

// Generate Topic 응답 타입
interface GenerateTopicResponse {
    topic_id: number
    md_path: string
}

export const topicApi = {
    /**
     * 토픽 생성 + AI 보고서 자동 생성
     * POST /api/topics/generate
     * @param data 토픽 생성 데이터 (input_prompt, language)
     * @returns 토픽 ID와 생성된 MD 파일 경로
     */
    generateTopic: async (data: TopicCreate): Promise<GenerateTopicResponse> => {
        const response = await api.post<ApiResponse<GenerateTopicResponse>>(API_ENDPOINTS.GENERATE_TOPIC, data)

        if (!response.data.success || !response.data.data) {
            console.log('generateTopic > failed >', response.data)

            throw new Error(response.data.error?.message || '보고서 생성에 실패했습니다.')
        }

        console.log('generateTopic > success >', response.data)

        return response.data.data
    },

    /**
     * 새 토픽 생성 (미사용)
     * POST /api/topics
     * @param data 토픽 생성 데이터
     * @returns 생성된 토픽
     */
    createTopic: async (data: TopicCreate): Promise<Topic> => {
        const response = await api.post<ApiResponse<Topic>>(API_ENDPOINTS.CREATE_TOPIC, data)

        if (!response.data.success || !response.data.data) {
            console.log('createTopic > failed >', response.data)

            throw new Error(response.data.error?.message || '토픽 생성에 실패했습니다.')
        }

        console.log('createTopic > success >', response.data)

        return response.data.data
    },

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

        const response = await api.get<ApiResponse<TopicListResponse>>(`${API_ENDPOINTS.LIST_TOPICS}?${params.toString()}`)

        if (!response.data.success || !response.data.data) {
            console.log('listTopics > failed >', response.data)

            throw new Error(response.data.error?.message || '토픽 목록 조회에 실패했습니다.')
        }

        console.log('listTopics > success >', response.data)

        return response.data.data
    },

    /**
     * 특정 토픽 조회
     * GET /api/topics/{topicId}
     * @param topicId 토픽 ID
     * @returns 토픽 정보
     */
    getTopic: async (topicId: number): Promise<Topic> => {
        const response = await api.get<ApiResponse<Topic>>(API_ENDPOINTS.GET_TOPIC(topicId))

        if (!response.data.success || !response.data.data) {
            console.log('getTopic > failed >', response.data)

            throw new Error(response.data.error?.message || '토픽 조회에 실패했습니다.')
        }

        console.log('getTopic > success >', response.data)

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
        const response = await api.patch<ApiResponse<Topic>>(API_ENDPOINTS.UPDATE_TOPIC(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log('updateTopic > failed >', response.data)

            throw new Error(response.data.error?.message || '토픽 업데이트에 실패했습니다.')
        }

        console.log('updateTopic > success >', response.data)

        return response.data.data
    },

    /**
     * 토픽 삭제
     * DELETE /api/topics/{topicId}
     * @param topicId 토픽 ID
     */
    deleteTopic: async (topicId: number): Promise<void> => {
        const response = await api.delete<ApiResponse<void>>(API_ENDPOINTS.DELETE_TOPIC(topicId))

        if (!response.data.success) {
            console.log('deleteTopic > failed >', response.data)

            throw new Error(response.data.error?.message || '토픽 삭제에 실패했습니다.')
        }

        console.log('deleteTopic > success >', response.data)
    },

    /**
     * 메시지 체이닝 (대화 이어가기)
     * POST /api/topics/{topicId}/ask
     * @param topicId 토픽 ID
     * @param data Ask 요청 데이터
     * @returns AskResponse
     */
    ask: async (topicId: number, data: AskRequest): Promise<AskResponse> => {
        // 요청 데이터 확인
        console.log('ask >> request >> ', topicId, data)

        const response = await api.post<ApiResponse<AskResponse>>(API_ENDPOINTS.ASK(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log('ask >> failed >> response.data: ', response.data)

            throw new Error(response.data.error?.message || '질문 전송에 실패했습니다.')
        }

        console.log('ask >> success >> response.data: ', response.data)

        return response.data.data
    },

    /**
     * 보고서 작성 계획 생성
     * POST /api/topics/plan
     * @param data Plan 요청 데이터 (template_id, custom_prompt)
     * @returns 보고서 작성 계획 (plan, sections)
     */
    generateTopicPlan: async (data: PlanRequest): Promise<PlanResponse> => {
        console.log('generateTopicPlan > request data >', data)

        const response = await api.post<ApiResponse<PlanResponse>>(API_ENDPOINTS.TOPIC_PLAN, data)

        if (!response.data.success || !response.data.data) {
            console.log('generateTopicPlan > failed >', response.data)

            throw new Error(response.data.error?.message || '보고서 계획 생성에 실패했습니다.')
        }

        console.log('generateTopicPlan > success >', response.data)

        return response.data.data
    },

    /**
     * 백그라운드 보고서 생성 (v2.4+)
     * POST /api/topics/:topicId/generate
     * @param topicId 토픽 ID
     * @param data 생성 요청 데이터 (topic, plan, template_id)
     * @returns 생성 상태 정보 (202 Accepted)
     */
    generateTopicBackground: async (
        topicId: number,
        data: {topic: string; plan: string; template_id?: number}
    ): Promise<{
        topic_id: number
        status: string
        message: string
        status_check_url: string
    }> => {
        console.log('generateTopicBackground > request >', topicId, data)

        const response = await api.post<
            ApiResponse<{
                topic_id: number
                status: string
                message: string
                status_check_url: string
            }>
        >(API_ENDPOINTS.GENERATE_TOPIC_BACKGROUND(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log('generateTopicBackground > failed >', response.data)
            throw new Error(response.data.error?.message || '보고서 생성 요청에 실패했습니다.')
        }

        console.log('generateTopicBackground > success >', response.data)
        return response.data.data
    },

    /**
     * 보고서 생성 상태 조회 (v2.4+)
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
                    console.log('topicApi >> sse >> ', data)
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
                    console.error('SSE parsing error:', error)
                }
            },
            onerror: (error) => {
                console.error('SSE connection error:', error)
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
