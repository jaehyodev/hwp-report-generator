import {CloseOutlined, DownloadOutlined} from '@ant-design/icons'
import {useMessage} from '@/contexts/MessageContext'
import ReactMarkdown from 'react-markdown'
import styles from './ReportPreview.module.css'
import { TOAST_MESSAGES } from '@/constants'

interface DownloadResult {
    ok: boolean
    error?: string    
}
interface ReportPreviewProps {
    report: {
        filename: string
        content: string
        messageId: number
        reportId: number
    }
    onClose: () => void
    onDownload: () => Promise<DownloadResult>
}

const ReportPreview = ({report, onClose, onDownload}: ReportPreviewProps) => {
    const {antdMessage} = useMessage()

    // hwpx 아티팩트 다운로드 결과에 따른 토스트 출력
    const handleDownload = async () => {
        try {
            const result = await onDownload()
            
            if (result.ok) {
                antdMessage.success(TOAST_MESSAGES.HWPX_DOWNLOAD_SUCCESS)
            } else {
                antdMessage.error(result.error)
            }
        } catch (error)  {
            antdMessage.error(TOAST_MESSAGES.HWPX_DOWNLOAD_FAILED)
        }
    }

    return (
        <div className={styles.reportPreviewSidebar}>
            <div className={styles.previewHeader}>
                <div className={styles.previewTitle}>
                    <span>보고서 미리보기</span>
                </div>
                <div className={styles.previewActions}>
                    <button className={`${styles.previewActionBtn} ${styles.download}`} onClick={handleDownload} title="다운로드">
                        <DownloadOutlined />
                    </button>
                    <button className={`${styles.previewActionBtn} ${styles.close}`} onClick={onClose} title="닫기">
                        <CloseOutlined />
                    </button>
                </div>
            </div>
            <div className={styles.previewContent}>
                <div className={styles.previewFilename}>{report.filename}</div>
                <div className={styles.previewText}>
                    <div className={styles.markdown}>
                        <ReactMarkdown>{report.content}</ReactMarkdown>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default ReportPreview
