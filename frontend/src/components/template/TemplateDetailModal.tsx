import {useState, useEffect} from 'react'
import {Modal, Button, Tag} from 'antd'
import {TagsOutlined} from '@ant-design/icons'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import {templateApi} from '../../services/templateApi'
import type {TemplateDetail} from '../../types/template'
import {formatFileSize, formatDate} from '../../utils/formatters'
import styles from './TemplateDetailModal.module.css'

/**
 * TemplateDetailModal.tsx
 *
 * ⭐ 템플릿 상세 정보 모달
 *
 * 역할:
 * 1. 템플릿 상세 정보 표시 (제목, 파일명, 파일 크기, 플레이스홀더 목록, 생성일)
 * 2. 모달 열기/닫기
 *
 * 표시 정보:
 * - 기본 정보: 제목, 파일명, 파일 크기, 생성일
 * - 플레이스홀더 목록: {{KEY}} 형태로 표시
 */

interface TemplateDetailModalProps {
    open: boolean
    templateId: number | null
    onClose: () => void
}

const TemplateDetailModal: React.FC<TemplateDetailModalProps> = ({open, templateId, onClose}) => {
    const {antdMessage} = useMessage()
    const [template, setTemplate] = useState<TemplateDetail | null>(null)
    const [loading, setLoading] = useState(false)

    // 프롬프트 상태 관리
    const [promptUser, setPromptUser] = useState<string>('')
    const [promptSystem, setPromptSystem] = useState<string>('')
    const [initialPromptUser, setInitialPromptUser] = useState<string>('')
    const [initialPromptSystem, setInitialPromptSystem] = useState<string>('')
    const [isSaving, setIsSaving] = useState(false)

    // 템플릿 상세 정보 로드
    const loadTemplate = async () => {
        if (!templateId) return

        setLoading(true)
        try {
            const data = await templateApi.getTemplate(templateId)
            setTemplate(data)
        } catch (error: any) {
            console.log('TemplateDetailModal > loadTemplate', error)
            onClose()
        } finally {
            setLoading(false)
        }
    }

    // 모달 열릴 때 데이터 로드
    useEffect(() => {
        if (open && templateId) {
            loadTemplate()
        }
    }, [open, templateId])

    // 템플릿 로드 시 프롬프트 초기값 설정
    useEffect(() => {
        if (template) {
            const userPrompt = template.prompt_user || ''
            const systemPrompt = template.prompt_system || ''

            setPromptUser(userPrompt)
            setPromptSystem(systemPrompt)
            setInitialPromptUser(userPrompt)
            setInitialPromptSystem(systemPrompt)
        }
    }, [template])

    // 변경 감지 함수
    const hasUserPromptChanged = (): boolean => {
        return promptUser !== initialPromptUser
    }

    const hasSystemPromptChanged = (): boolean => {
        return promptSystem !== initialPromptSystem
    }

    const hasAnyChanges = (): boolean => {
        return hasUserPromptChanged() || hasSystemPromptChanged()
    }

    // 저장 핸들러
    const handleSave = async () => {
        if (!templateId) return

        if (!hasAnyChanges()) {
            antdMessage.info(TOAST_MESSAGES.TEMPLATE_PROMPT_NO_CHANGE)
            return
        }

        setIsSaving(true)

        try {
            // User Prompt 업데이트
            if (hasUserPromptChanged()) {
                await templateApi.updatePromptUser(templateId, promptUser)
            }

            // System Prompt 업데이트 또는 재생성
            if (hasSystemPromptChanged()) {
                const trimmedSystemPrompt = promptSystem.trim()

                if (trimmedSystemPrompt === '') {
                    // 재생성 확인
                    const confirmed = await new Promise<boolean>((resolve) => {
                        Modal.confirm({
                            title: 'System Prompt 재생성',
                            content: '빈 값으로 저장하면 System Prompt가 자동으로 재생성됩니다. 계속하시겠습니까?',
                            onOk: () => resolve(true),
                            onCancel: () => resolve(false)
                        })
                    })

                    if (!confirmed) {
                        setIsSaving(false)
                        return
                    }

                    await templateApi.regeneratePromptSystem(templateId)
                } else {
                    await templateApi.updatePromptSystem(templateId, promptSystem)
                }
            }

            antdMessage.success(TOAST_MESSAGES.TEMPLATE_PROMPT_SAVE_SUCCESS)
            onClose()
        } catch (error: any) {
            console.error('TemplateDetailModal > handleSave', error)
            antdMessage.error(TOAST_MESSAGES.TEMPLATE_PROMPT_SAVE_FAILED)
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <Modal
            title="템플릿 상세"
            open={open}
            onCancel={onClose}
            width={700}
            closable={!isSaving}
            maskClosable={!isSaving}
            keyboard={!isSaving}
            footer={[
                <Button key="close" onClick={onClose} disabled={isSaving}>
                    닫기
                </Button>,
                <Button key="save" type="primary" loading={isSaving} disabled={!hasAnyChanges()} onClick={handleSave}>
                    저장
                </Button>
            ]}>
            {loading ? (
                <div className={styles.loadingContainer}>
                    <p>템플릿 정보를 불러오는 중...</p>
                </div>
            ) : template ? (
                <div className={styles.content}>
                    <div className={styles.section}>
                        <h3 className={styles.sectionTitle}>기본 정보</h3>
                        <table className={styles.infoTable}>
                            <tbody>
                                <tr>
                                    <td className={styles.infoLabel}>제목</td>
                                    <td className={styles.infoValue}>{template.title}</td>
                                </tr>
                                <tr>
                                    <td className={styles.infoLabel}>파일명</td>
                                    <td className={styles.infoValue}>{template.filename}</td>
                                </tr>
                                <tr>
                                    <td className={styles.infoLabel}>파일 크기</td>
                                    <td className={styles.infoValue}>{formatFileSize(template.file_size)}</td>
                                </tr>
                                <tr>
                                    <td className={styles.infoLabel}>생성일</td>
                                    <td className={styles.infoValue}>{formatDate(new Date(template.created_at).getTime() / 1000)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div className={styles.section}>
                        <h3 className={styles.sectionTitle}>플레이스홀더</h3>
                        {template.placeholders.length > 0 ? (
                            <div className={styles.tagContainer}>
                                {template.placeholders.map((ph, index) => (
                                    <Tag key={index}>{`${ph.key}`}</Tag>
                                ))}
                            </div>
                        ) : (
                            <p className={styles.emptyText}>플레이스홀더가 없습니다.</p>
                        )}
                    </div>

                    {/* User Prompt 섹션 */}
                    <div className={styles.section}>
                        <h3 className={styles.sectionTitle}>User Prompt</h3>
                        <textarea
                            className={styles.promptTextarea}
                            value={promptUser}
                            onChange={(e) => setPromptUser(e.target.value)}
                            placeholder="사용자 프롬프트를 입력하세요 (선택사항)"
                            rows={3}
                            disabled={isSaving}
                        />
                        <p className={styles.promptHint}>보고서 생성 시 사용자가 추가로 정의하는 프롬프트입니다.</p>
                    </div>

                    {/* System Prompt 섹션 */}
                    <div className={styles.section}>
                        <h3 className={styles.sectionTitle}>System Prompt</h3>
                        <textarea
                            className={styles.promptTextarea}
                            value={promptSystem}
                            onChange={(e) => setPromptSystem(e.target.value)}
                            placeholder="시스템 프롬프트를 입력하세요"
                            rows={3}
                            disabled={isSaving}
                        />
                        <p className={styles.promptHint}>빈 값으로 저장 시 자동으로 재생성됩니다.</p>
                    </div>

                    <div className={styles.notice}>
                        <p className={styles.noticeText}>
                            이 템플릿은 보고서 생성 시 사용할 수 있습니다. 플레이스홀더는 자동으로 실제 내용으로 대체됩니다.
                        </p>
                    </div>
                </div>
            ) : (
                <div className={styles.emptyContainer}>템플릿 정보를 찾을 수 없습니다.</div>
            )}
        </Modal>
    )
}

export default TemplateDetailModal
