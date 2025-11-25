import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '@/services/adminApi'
import type { TokenUsage } from '@/models/TokenUsageModel'
import type { AllTokenUsage } from '@/models/ui/TokenUsageUI'
import { mapTokenUsageToUI } from '@/mapper/tokenUsageMapper'

export const useAllTokenUsage = () => {
  const [usageList, setUsageList] = useState<AllTokenUsage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchUsage = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await adminApi.getAllTokenUsage() // stats 배열 반환
      const mapped = response.stats.map((item: TokenUsage) => mapTokenUsageToUI(item))
      setUsageList(mapped)
    } catch (error: any) {
      setError(error.message || '전체 토큰 사용량 조회 실패')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsage()
  }, [fetchUsage])

  return { usageList, isLoading, error, refetch: fetchUsage }
}
