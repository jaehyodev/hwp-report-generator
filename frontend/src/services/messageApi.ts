import api from './api'
import {API_ENDPOINTS} from '../constants/'
import type {ApiResponse} from '../types/api'
import type { CreateMessageRequest, MessageListResponse, MessageResponse } from '@/types/api/MessageApi'

/**
 * messageApi.ts
 *
 * 메시지 관련 API 함수 모음
 */
export const messageApi = {
    /**
     * 특정 주제의 메시지 목록 조회
     * GET /api/topics/{topicId}/messages
     * @param topicId 토픽 ID
     * @param limit 최대 메시지 수 (optional)
     * @param offset 건너뛸 메시지 수 (default: 0)
     * @returns 메시지 목록 (AI 응답 포함)
     */
    listMessages: async (topicId: number, limit?: number, offset: number = 0): Promise<MessageListResponse> => {
        const params = new URLSearchParams()
        if (limit) params.append('limit', limit.toString())
        params.append('offset', offset.toString())

        const response = await api.get<ApiResponse<MessageListResponse>>(`${API_ENDPOINTS.LIST_MESSAGES(topicId)}?${params.toString()}`)

        if (!response.data.success || !response.data.data) {
            console.log('listMessages >> failed >> ', response.data)

            throw new Error(response.data.error?.message || '메시지 목록 조회에 실패했습니다.')
        }

        console.log('listMessages >> success >> ', response.data)

        return response.data.data
    },

    /**
     * 새 메시지 생성 (role이 'user'면 AI 응답 자동 생성됨, 단 응답에는 포함 안됨)
     * POST /api/topics/{topicId}/messages
     * @param topicId 토픽 ID
     * @param data 메시지 role과 content
     * @returns 생성된 메시지 (user 메시지만 반환, AI 응답은 별도 조회 필요)
     */
    createMessage: async (topicId: number, data: CreateMessageRequest): Promise<MessageResponse> => {
        const response = await api.post<ApiResponse<MessageResponse>>(API_ENDPOINTS.CREATE_MESSAGE(topicId), data)

        if (!response.data.success || !response.data.data) {
            console.log('createMessage > failed >', response.data)

            throw new Error(response.data.error?.message || '메시지 생성에 실패했습니다.')
        }

        console.log('createMessage > success >', response.data)

        return response.data.data
    },

    /**
     * 메시지 삭제
     * DELETE /api/topics/{topicId}/messages/{messageId}
     * @param topicId 토픽 ID
     * @param messageId 삭제할 메시지 ID
     * @returns void (성공 시 아무것도 반환하지 않음)
     */
    deleteMessage: async (topicId: number, messageId: number): Promise<void> => {
        const response = await api.delete<ApiResponse<{message: string}>>(API_ENDPOINTS.DELETE_MESSAGE(topicId, messageId))

        if (!response.data.success) {
            console.log('deleteMessage >> failed >> ', response.data)

            throw new Error(response.data.error?.message || '메시지 삭제에 실패했습니다.')
        }

        console.log('deleteMessage >> success >> ', response.data)
    }
}
