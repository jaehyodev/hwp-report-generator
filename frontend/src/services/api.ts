import axios from 'axios'
import type {AxiosInstance, InternalAxiosRequestConfig} from 'axios'
import {API_BASE_URL} from '../constants/'
import {storage} from '../utils/storage'

/**
 * api.ts
 *
 * ⭐ Axios 기본 설정 및 공통 API 인스턴스
 *
 * Axios란?
 * - 서버와 HTTP 통신(API 호출)을 쉽게 해주는 라이브러리
 * - fetch보다 편리한 기능 제공 (자동 JSON 변환, 인터셉터 등)
 *
 * 이 파일의 역할:
 * 1. Axios 인스턴스 생성 (기본 URL, 헤더 설정)
 * 2. 요청 인터셉터: 모든 요청에 자동으로 토큰 추가
 * 3. 응답 인터셉터: 401 에러 시 자동 로그아웃
 *
 * Interceptor(인터셉터)란?
 * - 요청/응답을 가로채서 공통 작업을 수행하는 기능
 * - 예: 모든 요청에 토큰 자동 추가, 에러 공통 처리
 *
 * 사용 방법:
 * import api from './services/api';
 * const response = await api.get('/users');
 * const response = await api.post('/login', { email, password });
 */

/**
 * Axios 인스턴스 생성
 * - baseURL: 모든 요청의 기본 URL (예: http://localhost:8000)
 * - headers: 모든 요청에 포함될 기본 헤더
 */
const api: AxiosInstance = axios.create({
    baseURL: API_BASE_URL, // 환경변수 또는 기본값
    headers: {
        'Content-Type': 'application/json' // JSON 형식으로 데이터 전송
    }
})

/**
 * JWT 인증이 필요 없는 Public 엔드포인트 목록
 * - 로그인/회원가입 시에는 토큰이 없으므로 헤더에 추가하지 않음
 */
const PUBLIC_ENDPOINTS = ['/api/auth/login', '/api/auth/register']

/**
 * 주어진 URL이 Public 엔드포인트인지 확인
 * @param url 요청 URL
 * @returns Public 엔드포인트 여부
 */
const isPublicEndpoint = (url?: string): boolean => {
    if (!url) return false
    return PUBLIC_ENDPOINTS.some((endpoint) => url.includes(endpoint))
}

/**
 * 요청 인터셉터 (Request Interceptor)
 *
 * 역할: 모든 API 요청이 서버로 가기 전에 실행
 * - 로컬스토리지에서 토큰을 가져와서 Authorization 헤더에 자동 추가
 * - Public 엔드포인트(로그인/회원가입)는 토큰 추가 제외
 * - 이렇게 하면 매번 요청마다 토큰을 수동으로 추가할 필요 없음
 *
 * 동작:
 * 1. 요청 직전에 실행
 * 2. Public 엔드포인트가 아니고 토큰이 있으면 헤더에 "Bearer 토큰값" 추가
 * 3. 수정된 요청을 서버로 전송
 */
api.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // Public 엔드포인트는 토큰 추가 안 함
        if (isPublicEndpoint(config.url)) {
            return config
        }

        // Protected 엔드포인트는 토큰 추가
        const token = storage.getToken()
        if (token && config.headers) {
            // Authorization: Bearer eyJhbGc... 형태로 추가
            config.headers.Authorization = `Bearer ${token}`
        }
        return config // 수정된 설정 반환
    },
    (error) => {
        // 요청 설정 중 에러 발생 시
        return Promise.reject(error)
    }
)

/**
 * 응답 인터셉터 (Response Interceptor)
 *
 * 역할: 모든 API 응답을 받은 후 처리하기 전에 실행
 * - 401 Unauthorized 에러(인증 실패) 발생 시 자동 로그아웃
 * - 토큰 만료, 잘못된 토큰 등의 경우 자동으로 로그인 페이지로 이동
 *
 * 동작:
 * 1. 정상 응답(200~299): 그대로 통과
 * 2. 401 에러: 로컬스토리지 삭제 + 로그인 페이지로 이동
 * 3. 기타 에러: 그대로 에러 반환
 */
api.interceptors.response.use(
    (response) => response, // 정상 응답은 그대로 통과
    (error) => {
        const status = error.response?.status
        const url = error.config?.url

        const isLoginAPI = url?.includes('/api/auth/login')
        const isRegisterAPI = url?.includes('/api/auth/register')

        // 401 에러 = 인증 실패 (토큰 없음/만료/잘못됨)
        // 회원가입 및 로그인을 제외한 인증 실패는 로그인 화면으로 이동
        if (status === 401 && !isRegisterAPI && !isLoginAPI) {
            storage.clear()
            window.location.href = '/login'
            return
        }
        return Promise.reject(error)
    }
)

export default api
