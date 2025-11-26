import type { AllTokenUsageResponse } from "@/services/adminApi";
import type { UserTokenUsageResponse } from "@/services/adminApi";
import type { TokenUsageModel } from "@/models/TokenUsageModel";
import type { TokenUsageUI } from "@/models/ui/TokenUsageUI";
import { isoStringToDate, formatDateToString } from "@/utils/formatters";
import type { To } from "react-router-dom";

// Mapper: DTO -> Domain 모델
export const mapAllTokenUsageResponseToModel = (response: AllTokenUsageResponse): TokenUsageModel => ({
  userId: response.stats[0].user_id,
  username: response.stats[0].username,
  email: response.stats[0].email,
  totalInputTokens: response.stats[0].total_input_tokens,
  totalOutputTokens: response.stats[0].total_output_tokens,
  totalTokens: response.stats[0].total_tokens,
  reportCount: response.stats[0].report_count,
  lastUsage: isoStringToDate(response.stats[0].last_usage)
})

// Mapper: DTO -> Domain 모델
export const mapUserTokenUsageResponseToModel = (response: UserTokenUsageResponse): TokenUsageModel => ({
  userId: response.user_id,
  username: response.username,
  email: response.email,
  totalInputTokens: response.total_input_tokens,
  totalOutputTokens: response.total_output_tokens,
  totalTokens: response.total_tokens,
  reportCount: response.report_count,
  lastUsage: isoStringToDate(response.last_usage)
})

// Mapper: Domain 모델 → UI 모델
export const mapTokenUsageToUI = (usage: TokenUsageModel): TokenUsageUI => ({
  userId: usage.userId,
  username: usage.username,
  totalInputTokens: usage.totalInputTokens,
  totalOutputTokens: usage.totalOutputTokens,
  totalTokens: usage.totalTokens,
  reportCount: usage.reportCount,
  lastUsage: usage.lastUsage !== null ? formatDateToString(usage.lastUsage) : '-'
})