import { useState, useEffect, useCallback } from 'react'
import { adminApi } from '@/services/adminApi'
import type { TokenUsageModel } from '@/models/TokenUsageModel'
import type { TokenUsageUI } from '@/models/ui/TokenUsageUI'
import { mapAllTokenUsageResponseToModel, mapUserTokenUsageResponseToModel, mapTokenUsageToUI } from '@/mapper/tokenUsageMapper'
import type { UserData } from '../types/user'

export const useTokenUsage = () => {
  // 1. 전체 토큰 사용량 상태
  const [totalTokenUsage, setTotalTokenUsage] = useState<TokenUsageUI>()
  const [isTotalUsageLoading, setIsTotalUsageLoading] = useState(false)
  const [totalUsageError, setTotalUsageError] = useState<string | null>(null)

  // 2. 사용자 목록 상태
  const [users, setUsers] = useState<UserData[]>()
  const [isUserListLoading, setIsUserListLoading] = useState(false)
  const [userListError, setUserListError] = useState<string | null>(null)

  // 3. 사용자별 토큰 사용량 상태
  const [userTokenUsageList, setUserTokenUsageList] = useState<TokenUsageUI[]>()
  const [isUserUsageLoading, setIsUserUsageLoading] = useState(false)
  const [userUsageError, setUserUsageError] = useState<string | null>(null)

  // 전체 토큰 사용량 조회 함수
  const fetchTotalTokenUsage = useCallback(async () => {
    setIsTotalUsageLoading(true)
    setTotalUsageError(null)
    try {
      const response = await adminApi.getAllTokenUsage()
      const tokenUsageModel = mapAllTokenUsageResponseToModel(response)
      const tokenUsageUI = mapTokenUsageToUI(tokenUsageModel)
      setTotalTokenUsage(tokenUsageUI)
    } catch (error: any) {
      setTotalUsageError('전체 토큰 사용량 조회 실패')
    } finally {
      setIsTotalUsageLoading(false)
    }
  }, [])

  // 사용자 목록 조회
  const fetchUsers = useCallback(async () => {
    setIsUserListLoading(true)
    setUserListError(null)
    try {
        const userList = await adminApi.listUsers()
        setUsers(userList)
    } catch (error: any) {
        setUserListError('사용자 목록 조회 실패')
        setUsers([])
    } finally {
        setIsUserListLoading(false)
    }
  }, [])

  // 사용자별 토큰 사용량 조회 함수
  const fetchUserTokenUsageList = useCallback(async (userList: UserData[]) => {
    if (!userList || userList.length === 0) {
        setUserTokenUsageList([])
        return
    }

    setIsUserUsageLoading(true)
    setUserUsageError(null)

    try {
        const usagePromises = userList.map(async (user) => {
            try {
                const response = await adminApi.getUserTokenUsage(user.id)
    
                const tokenUsageModel = mapUserTokenUsageResponseToModel(response)
                const tokenUsageUI = mapTokenUsageToUI(tokenUsageModel)

                return tokenUsageUI
            } catch (error: any) {
                console.error(`사용자 ID ${user.id}의 토큰 사용량 조회 실패:`, error)
                // 실패하더라도 기본값과 함께 사용자 데이터를 반환
                const tokenUsageUI = {
                  userId: user.id,
                  username: user.username,
                  totalInputTokens: 0,
                  totalOutputTokens: 0,
                  totalTokens: 0,
                  reportCount: 0,
                  lastUsage: ''
                }
                return tokenUsageUI
            }
        })

        const results = await Promise.all(usagePromises)
        setUserTokenUsageList(results)

    } catch (error: any) {
        setUserUsageError('사용자별 토큰 사용량 목록 조회 실패')
    } finally {
        setIsUserUsageLoading(false)
    }
}, [])

  const refetchAllTokenUsage = useCallback(() => {
      // 1. 전체 사용량 조회
      fetchTotalTokenUsage()
      // 2. 사용자 목록 조회 (이후 useEffect에서 목록 기반 사용량 조회 트리거)
      fetchUsers() 
  }, [fetchTotalTokenUsage, fetchUsers])
  
  // 초기 로드: 전체 새로고침 실행
  useEffect(() => {
      refetchAllTokenUsage()
  }, [refetchAllTokenUsage])

  // 사용자 목록이 로드되면: 사용자별 토큰 사용량 조회 시작
  useEffect(() => {
    if (users && !userListError) {
        fetchUserTokenUsageList(users)
    } else if (userListError) {
          // 사용자 목록 조회 실패 시, 사용자별 사용량도 실패 처리
        setUserUsageError('사용자 목록을 가져오지 못해 토큰 사용량을 조회할 수 없습니다.')
        setUserTokenUsageList([])
    }
  }, [users, fetchUserTokenUsageList, userListError])

  return {
    // 전체 사용량 상태
    totalTokenUsage,
    isTotalUsageLoading,
    totalUsageError,
    
    // 사용자별 사용량 상태
    userTokenUsageList,
    isUserUsageLoading,
    userUsageError,
    
    // 전체 새로고침 함수
    refetch: refetchAllTokenUsage 
  }
}