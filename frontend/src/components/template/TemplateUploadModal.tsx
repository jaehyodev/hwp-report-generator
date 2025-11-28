import {useState} from 'react'
import {Modal, Form, Input, Upload, Button} from 'antd'
import {FileOutlined, CloseOutlined} from '@ant-design/icons'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import type {UploadFile, RcFile} from 'antd/es/upload'
import styles from './TemplateUploadModal.module.css'

/**
 * TemplateUploadModal.tsx
 *
 * ⭐ 템플릿 업로드 모달
 *
 * 역할:
 * 1. 템플릿 파일 선택 (.hwpx)
 * 2. 템플릿 제목 입력
 * 3. 파일 업로드 및 검증
 *
 * 검증:
 * - 확장자: .hwpx만 허용
 * - 파일 크기: 10MB 이하
 * - 필수 입력: 파일, 제목
 */

interface TemplateUploadModalProps {
    open: boolean
    onClose: () => void
    uploading: boolean
    onUpload: (file: File, title: string) => Promise<boolean>
}

const TemplateUploadModal = ({open, onClose, uploading, onUpload}: TemplateUploadModalProps) => {
    const {antdMessage} = useMessage()
    const [form] = Form.useForm()
    const [fileList, setFileList] = useState<UploadFile[]>([])

    // 파일 선택 전 검증
    const beforeUpload = (file: RcFile): boolean => {
        // 확장자 검증
        const isHwpx = file.name.toLowerCase().endsWith('.hwpx')
        if (!isHwpx) {
            antdMessage.error(TOAST_MESSAGES.TEMPLATE_HWPX_ONLY)
            return false
        }

        // 파일 크기 검증 (10MB)
        const isLt10M = file.size / 1024 / 1024 < 10
        if (!isLt10M) {
            antdMessage.error(TOAST_MESSAGES.TEMPLATE_SIZE_LIMIT)
            return false
        }

        // UploadFile 형식으로 변환하여 originFileObj 포함
        const uploadFile: UploadFile = {
            uid: file.uid,
            name: file.name,
            size: file.size,
            type: file.type,
            originFileObj: file as RcFile
        }

        setFileList([uploadFile])
        return false // 자동 업로드 방지
    }

    // 파일 제거
    const handleRemove = () => {
        if (uploading) return // 업로드 중에는 제거 불가
        setFileList([])
    }

    // 업로드 실행
    const handleUpload = async () => {
        try {
            const values = await form.validateFields()

            if (fileList.length === 0) {
                antdMessage.error(TOAST_MESSAGES.TEMPLATE_FILE_REQUIRED)
                return
            }

            const uploadFile = fileList[0]
            if (!uploadFile.originFileObj) {
                antdMessage.error(TOAST_MESSAGES.TEMPLATE_FILE_INVALID)
                return
            }

            const file = uploadFile.originFileObj as File
            const success = await onUpload(file, values.title)

            if (success) {
                handleClose()
            }
        } catch (error: any) {
            if (error.errorFields) {
                // Form validation error
                return
            }
        }
    }

    // 모달 닫기
    const handleClose = () => {
        form.resetFields()
        setFileList([])
        onClose()
    }

    return (
        <Modal
            title="템플릿 업로드"
            open={open}
            onCancel={handleClose}
            onOk={handleUpload}
            confirmLoading={uploading}
            closable={!uploading}
            maskClosable={!uploading}
            okText="업로드"
            cancelText="취소"
            cancelButtonProps={{disabled: uploading}}
            width={600}
            centered>
            <div className={styles.modalBody}>
                <Form form={form} layout="vertical" className={styles.form}>
                    {/* 제목 입력 */}
                    <Form.Item
                        name="title"
                        label="템플릿 제목"
                        rules={[
                            {required: true, message: '템플릿 제목을 입력해주세요.'},
                            {max: 100, message: '템플릿 제목은 100자 이하여야 합니다.'}
                        ]}>
                        <Input placeholder="예: 2024 분기별 실적 보고서" maxLength={100} showCount disabled={uploading} />
                    </Form.Item>

                    {/* 파일 업로드 */}
                    <Form.Item label="템플릿 파일" required>
                        <Upload.Dragger
                            fileList={[]}
                            beforeUpload={beforeUpload}
                            onRemove={handleRemove}
                            maxCount={1}
                            accept=".hwpx"
                            showUploadList={false}
                            disabled={uploading}
                            className={styles.uploader}>
                            {fileList.length === 0 ? (
                                <>
                                    <p className="ant-upload-drag-icon">
                                        <FileOutlined />
                                    </p>
                                    <p className="ant-upload-text">클릭하거나 파일을 드래그하여 업로드</p>
                                    <p className="ant-upload-hint">HWPX 파일만 업로드 가능 (최대 10MB)</p>
                                </>
                            ) : (
                                <div className={styles.fileInfo}>
                                    <Button
                                        type="text"
                                        icon={<CloseOutlined />}
                                        onClick={handleRemove}
                                        disabled={uploading}
                                        className={styles.removeBtn}
                                    />
                                    <FileOutlined className={styles.fileIcon} />
                                    <div className={styles.fileName}>{fileList[0].name}</div>
                                </div>
                            )}
                        </Upload.Dragger>
                    </Form.Item>

                    {/* 안내 메시지 */}
                    <div className={styles.notice}>
                        <p className={styles.noticeTitle}>템플릿 작성 가이드</p>
                        <ul className={styles.noticeList}>
                            <li>
                                템플릿에는 다음 플레이스홀더를 사용할 수 있습니다.
                                <br />
                                <br />
                                <code>{'{TITLE}'}</code>, <code>{'{DATE}'}</code>, <code>{'{SUMMARY}'}</code>, <code>{'{BACKGROUND}'}</code>,{' '}
                                <code>{'{MAIN_CONTENT}'}</code>, <code>{'{CONCLUSION}'}</code>,
                                <code>{'{TITLE_BACKGROUND}'}</code>, <code>{'{TITLE_CONCLUSION}'}</code>,
                                <code>{'{TITLE_MAIN_CONTENT}'}</code>, <code>{'{TITLE_SUMARY}'}</code>
                            </li>
                            <br />
                            <li>템플릿의 플레이스홀더는 실제 내용으로 대체됩니다.</li>
                            <li>플레이스홀더는 중복될 수 없습니다.</li>
                            <li>HWPX 파일은 한글 2014 이상에서 지원됩니다.</li>
                        </ul>
                    </div>
                </Form>
            </div>
        </Modal>
    )
}

export default TemplateUploadModal
