import {useState} from 'react'
import {CloseOutlined} from '@ant-design/icons'
import styles from './PlanPreview.module.css'

interface PlanPreviewProps {
    plan: string
    onClose: () => void
    onGenerate: (editedPlan: string) => void
}

/**
 * 계획 편집 사이드바 컴포넌트
 *
 * 보고서 계획을 편집하고 수정된 내용으로 보고서를 생성할 수 있습니다.
 */
const PlanPreview = ({plan, onClose, onGenerate}: PlanPreviewProps) => {
    const [editedPlan, setEditedPlan] = useState(plan)

    const handleGenerate = () => {
        if (!editedPlan.trim()) {
            alert('계획 내용을 입력해주세요.')
            return
        }
        onGenerate(editedPlan)
    }

    return (
        <div className={styles.planPreviewSidebar}>
            <div className={styles.previewHeader}>
                <div className={styles.previewTitle}>
                    <span>계획 수정</span>
                </div>
                <div className={styles.previewActions}>
                    <button className={`${styles.previewActionBtn} ${styles.generate}`} onClick={handleGenerate} title="보고서 생성">
                        보고서 생성
                    </button>
                    <button className={`${styles.previewActionBtn} ${styles.close}`} onClick={onClose} title="닫기">
                        <CloseOutlined />
                    </button>
                </div>
            </div>

            <div className={styles.previewContent}>
                <textarea
                    className={styles.editableTextarea}
                    value={editedPlan}
                    onChange={(e) => setEditedPlan(e.target.value)}
                    placeholder="보고서 계획을 입력하세요..."
                />
            </div>
        </div>
    )
}

export default PlanPreview
