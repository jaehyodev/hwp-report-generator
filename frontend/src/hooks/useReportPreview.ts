import {useState} from 'react'
import {artifactApi} from '../services/artifactApi'

interface ReportData {
    filename: string
    content: string
    messageId: number
    reportId: number
}

interface DownloadedFile {
    id: number
    filename: string
    downloadUrl: string
    size: string
    timestamp: Date
}

interface DownloadResult {
    ok: boolean
    error?: string
}

/**
 * useReportPreview 커스텀 훅
 *
 * 보고서 미리보기 및 다운로드 상태 관리
 * - 토스트는 호출하는 컴포넌트에서 처리
 *
 * @returns 보고서 미리보기 관련 상태 및 핸들러
 */
export const useReportPreview = () => {
    const [selectedReport, setSelectedReport] = useState<ReportData | null>(null)
    const [downloadedFiles, setDownloadedFiles] = useState<DownloadedFile[]>([])

    /**
     * 보고서 클릭 - 미리보기 열기
     */
    const handleReportClick = (reportData: ReportData) => {
        setSelectedReport(reportData)
    }

    /**
     * 보고서 미리보기 닫기
     */
    const handleClosePreview = () => {
        setSelectedReport(null)
    }

    /**
     * 보고서 다운로드 핸들러
     * @returns {DownloadResult} 성공/실패 결과
     */
    const handleDownload = async (reportData: ReportData): Promise<DownloadResult> => {
        try {
            const hwpxFilename = reportData.filename.replace('.md', '.hwpx')
            
            // 구버전
            // await artifactApi.downloadMessageHwpx(reportData.messageId, hwpxFilename)

            // 신버전
            console.log('useReportPreview >> handleDownload >> reportData >> ', reportData)
            await artifactApi.downloadHwpxArtifact(reportData.reportId)

            const downloadedFile: DownloadedFile = {
                id: reportData.messageId,
                filename: hwpxFilename,
                downloadUrl: `#`,
                size: '알 수 없음',
                timestamp: new Date()
            }

            setDownloadedFiles((prev) => [...prev, downloadedFile])
            return {ok: true}
        } catch (error: any) {
            console.error('Download failed:', error)
            const serverMessage = error.response?.data?.detail || error.response?.data?.error?.message
            return {ok: false, error: serverMessage || 'HWPX_DOWNLOAD_FAILED'}
        }
    }

    return {
        selectedReport,
        setSelectedReport,
        downloadedFiles,
        handleReportClick,
        handleClosePreview,
        handleDownload
    }
}
