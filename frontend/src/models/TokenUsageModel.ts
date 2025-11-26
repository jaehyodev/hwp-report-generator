/**
 * 토큰 사용량 도메인 모델
 */

export interface TokenUsageModel {
    userId: number
    username: string
    email: string
    totalInputTokens: number
    totalOutputTokens: number
    totalTokens: number
    reportCount: number
    lastUsage: Date | null
}