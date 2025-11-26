/**
 * UI 표시용 토큰 사용량
 */
export interface TokenUsageUI {
  userId: number
  username: string
  totalInputTokens: number
  totalOutputTokens: number
  totalTokens: number
  reportCount: number
  lastUsage: string
}
