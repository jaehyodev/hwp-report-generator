/**
 * 토큰 사용량 도메인 모델
 */

export interface TokenUsage {
    user_id: string
    username: string
    email: string
    total_input_tokens: number
    total_output_tokens: number
    total_tokens: number
    report_count: number
    last_usage: null
}