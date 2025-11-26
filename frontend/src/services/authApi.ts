import api from './api'
import {API_ENDPOINTS} from '../constants/'
import type {LoginRequest, LoginResponse, RegisterRequest, ChangePasswordRequest} from '../types/auth'
import type {UserData} from '../types/user'
import type {ApiResponse} from '../types/api'

/**
 * authApi.ts
 *
 * 인증 관련 API 함수 모음
 * - 로그인, 회원가입, 비밀번호 변경
 */

export const authApi = {
    /**
     * 로그인
     * POST /api/auth/login
     * @param data 이메일, 비밀번호
     * @returns 토큰, 사용자 정보
     */
    login: async (data: LoginRequest): Promise<LoginResponse> => {
        const response = await api.post<ApiResponse<LoginResponse>>(API_ENDPOINTS.LOGIN, data)
        
        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '로그인에 실패했습니다.')
        }

        return response.data.data
    },

    /**
     * 회원가입
     * POST /api/auth/register
     * @param data 이메일, 사용자명, 비밀번호
     */
    register: async (data: RegisterRequest): Promise<void> => {
        const response = await api.post<ApiResponse<void>>(API_ENDPOINTS.REGISTER, data)

        if (!response.data.success) {
            throw new Error(response.data.error?.message || '회원가입에 실패했습니다.')
        }
    },

    /**
     * 로그아웃
     * POST /api/auth/logout
     * 서버에 로그아웃 요청 후 로컬 스토리지의 토큰 제거
     */
    logout: async (): Promise<void> => {
        try {
            const response = await api.post<ApiResponse<void>>(API_ENDPOINTS.LOGOUT)

            if (!response.data.success) {
                throw new Error(response.data.error?.message || '로그아웃에 실패했습니다.')
            }
        } finally {
            // 성공/실패 여부와 관계없이 로컬 토큰 제거
            localStorage.removeItem('access_token')
        }
    },

    /**
     * 비밀번호 변경
     * POST /api/auth/change-password
     * @param data 현재 비밀번호, 새 비밀번호
     */
    changePassword: async (data: ChangePasswordRequest): Promise<void> => {
        const response = await api.post<ApiResponse<void>>(API_ENDPOINTS.CHANGE_PASSWORD, data)

        if (!response.data.success) {
            throw new Error(response.data.error?.message || '비밀번호 변경에 실패했습니다.')
        }
    },

    /**
     * 내 정보 조회
     * GET /api/auth/me
     * @returns 현재 로그인한 사용자 정보
     */
    getMyInfo: async (): Promise<UserData> => {
        const response = await api.get<ApiResponse<UserData>>(API_ENDPOINTS.ME)

        if (!response.data.success || !response.data.data) {
            throw new Error(response.data.error?.message || '사용자 정보를 불러올 수 없습니다.')
        }

        return response.data.data
    }
}
