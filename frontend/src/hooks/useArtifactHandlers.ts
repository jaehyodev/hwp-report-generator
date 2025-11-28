import {useState} from 'react'
import {artifactApi} from '../services/artifactApi'
import {useArtifactStore, type Artifact} from '../stores/useArtifactStore'

/**
 * useArtifactHandlers.ts
 *
 * 아티팩트 관련 핸들러 및 상태 관리 커스텀 훅
 * - 토스트는 호출하는 컴포넌트에서 처리
 */

interface ArtifactResult {
    ok: boolean
    error?: string
}

interface UseArtifactHandlersReturn {
    // Dropdown 상태
    isReportsDropdownOpen: boolean
    setIsReportsDropdownOpen: (isOpen: boolean) => void

    // Store actions
    loadArtifacts: (topicId: number) => Promise<Artifact[]>             // 아티팩트 목록 불러오기
    refreshArtifacts: (topicId: number) => Promise<Artifact[]>          // 아티팩트 목록 갱신
    getMarkdownArtifacts: (topicId: number) => Artifact[]               // MD 아티팩트 리스트만 반환
    getSelectedArtifactId: (topicId: number) => number | null           // 선택된 아티팩트 ID 반환
    selectArtifact: (topicId: number, artifactId: number) => void       // 아티팩트 선택
    autoSelectLatest: (topicId: number, artifacts: Artifact[]) => void  // MD 아티팩트 중 최신 것을 자동 선택
    loadingTopics: Set<number>                                          // 로딩 중인 토픽 ID 집합

    // Handlers
    handleReportsClick: (topicId: number | null) => Promise<ArtifactResult>                                   // 보고서 버튼 클릭 (Dropdown 열기)
    handleArtifactSelect: (topicId: number | null, artifactId: number) => void                                // 보고서 선택
    handleArtifactDownload: (artifact: Artifact, topicId: number | null) => Promise<ArtifactResult>           // 보고서 다운로드
    handleArtifactPreview: (artifact: Artifact, onSuccess: (data: any) => void) => Promise<ArtifactResult>    // 보고서 미리보기
}

export const useArtifactHandlers = (): UseArtifactHandlersReturn => {
    const [isReportsDropdownOpen, setIsReportsDropdownOpen] = useState(false)
    
    const {
        loadArtifacts,
        refreshArtifacts,
        getMarkdownArtifacts,
        getSelectedArtifactId,
        selectArtifact,
        autoSelectLatest,
        loadingTopics
    } = useArtifactStore()

    /**
     * 보고서 버튼 클릭 (Dropdown 열기)
     */
    const handleReportsClick = async (topicId: number | null): Promise<ArtifactResult> => {
        if (!topicId) {
            return {ok: false, error: 'ARTIFACT_NEW_TOPIC_FIRST'}
        }

        setIsReportsDropdownOpen(true)

        try {
            const artifacts = await loadArtifacts(topicId)

            console.log('useArtifiactHandlers > loadArtifacts >', artifacts)

            // 아직 선택된 아티팩트가 없으면 자동으로 마지막 선택 (MD 파일만)
            const markdownArtifacts = artifacts.filter((art) => art.kind === 'md')
            if (!getSelectedArtifactId(topicId) && markdownArtifacts.length > 0) {
                autoSelectLatest(topicId, markdownArtifacts)
            }
            return {ok: true}
        } catch (error: any) {
            console.error('Failed to load artifacts:', error)
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return {ok: false, error: serverMessage || 'ARTIFACT_LOAD_FAILED'}
        }
    }

    /**
     * 아티팩트 선택
     */
    const handleArtifactSelect = (topicId: number | null, artifactId: number) => {
        if (topicId) {
            selectArtifact(topicId, artifactId)
        }
    }

    /**
     * 아티팩트 다운로드 (HWPX 변환)
     * @returns {ArtifactResult} 성공 시 ok: true, 실패 시 error 코드 반환
     */
    const handleArtifactDownload = async (artifact: Artifact, topicId: number | null): Promise<ArtifactResult> => {
        try {
            // message_id가 있으면 메시지 기반 HWPX 다운로드 사용
            if (artifact.message_id) {
                const hwpxFilename = artifact.filename.replace('.md', '.hwpx')
                await artifactApi.downloadMessageHwpx(artifact.message_id, hwpxFilename)

                // HWPX 다운로드 후 artifact 목록 갱신 (새로운 hwpx artifact가 생성됨)
                if (topicId) {
                    await refreshArtifacts(topicId)
                }
                return {ok: true}
            } else {
                return {ok: false, error: 'HWPX_DOWNLOAD_FAILED'}
            }
        } catch (error: any) {
            console.error('Download failed:', error)
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return {ok: false, error: serverMessage || 'HWPX_DOWNLOAD_FAILED'}
        }
    }

    /**
     * 아티팩트 미리보기
     */
    const handleArtifactPreview = async (
        artifact: Artifact,
        onSuccess: (data: any) => void
    ): Promise<ArtifactResult> => {
        try {
            const contentResponse = await artifactApi.getArtifactContent(artifact.id)

            onSuccess({
                filename: artifact.filename,
                content: contentResponse.content,
                messageId: artifact.message_id,
                reportId: artifact.id
            })

            setIsReportsDropdownOpen(false)
            return {ok: true}
        } catch (error: any) {
            console.error('Failed to preview artifact:', error)
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return {ok: false, error: serverMessage || 'PREVIEW_LOAD_FAILED'}
        }
    }

    return {
        isReportsDropdownOpen,
        setIsReportsDropdownOpen,
        loadArtifacts,
        refreshArtifacts,
        getMarkdownArtifacts,
        getSelectedArtifactId,
        selectArtifact,
        autoSelectLatest,
        loadingTopics,
        handleReportsClick,
        handleArtifactSelect,
        handleArtifactDownload,
        handleArtifactPreview
    }
}
