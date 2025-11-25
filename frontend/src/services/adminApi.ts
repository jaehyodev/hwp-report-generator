import api from './api'
import {API_ENDPOINTS} from '../constants/'
import type {UserData} from '../types/user'
import type {ApiResponse} from '../types/api'
import type { TokenUsage } from '@/models/TokenUsageModel'

interface MessageResponse {
    message: string
}

interface PasswordResetResponse {
    message: string
    temporary_password: string
}

interface UsersListResponse {
    users: UserData[]
    total: number
}

interface TokenUsageResponse {
    stats: TokenUsage[]
}

export const adminApi = {
    listUsers: async (): Promise<UserData[]> => {
        const response = await api.get<ApiResponse<UsersListResponse>>(API_ENDPOINTS.LIST_USERS)

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '사용자 목록 조회에 실패했습니다.')
        }

        return response.data.data.users
    },

    approveUser: async (userId: number): Promise<MessageResponse> => {
        const response = await api.patch<ApiResponse<MessageResponse>>(API_ENDPOINTS.APPROVE_USER(userId))

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '사용자 승인에 실패했습니다.')
        }

        return response.data.data
    },

    rejectUser: async (userId: number): Promise<MessageResponse> => {
        const response = await api.patch<ApiResponse<MessageResponse>>(API_ENDPOINTS.REJECT_USER(userId))

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '사용자 거부에 실패했습니다.')
        }

        return response.data.data
    },

    resetPassword: async (userId: number): Promise<PasswordResetResponse> => {
        const response = await api.post<ApiResponse<PasswordResetResponse>>(API_ENDPOINTS.RESET_PASSWORD(userId))

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '비밀번호 초기화에 실패했습니다.')
        }

        return response.data.data
    },

    getAllTokenUsage: async (): Promise<TokenUsageResponse> => {
        const response = await api.get<ApiResponse<TokenUsageResponse>>(API_ENDPOINTS.GET_ALL_TOKEN_USAGE)

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '모든 사용자의 토큰 사용량 조회에 실패했습니다.')
        }

        return response.data.data
    },

    getUserTokenUsage: async (userId: number): Promise<TokenUsageResponse> => {
        const response = await api.get<ApiResponse<TokenUsageResponse>>(API_ENDPOINTS.GET_USER_TOKEN_USAGE(userId))

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '해당 사용자의 토큰 사용량 조회에 실패했습니다.')
        }

        return response.data.data
    }
}
