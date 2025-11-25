import type { TokenUsage } from "@/models/TokenUsageModel";
import type { AllTokenUsage } from "@/models/ui/TokenUsageUI";

// Mapper: Domain 모델 → UI 모델
export const mapTokenUsageToUI = (usage: TokenUsage): AllTokenUsage => ({
  total_input_tokens: usage.total_input_tokens,
  total_output_tokens: usage.total_output_tokens,
  total_tokens: usage.total_tokens,
  report_count: usage.report_count
})