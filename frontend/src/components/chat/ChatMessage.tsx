import React, {useState} from 'react'
import {FileTextOutlined, DownloadOutlined, DeleteOutlined} from '@ant-design/icons'
import {useAuth} from '../../hooks/useAuth'
import DeleteChatMessageModal from './DeleteChatMessageModal'
import type {MessageUI} from '../../models/ui/MessageUI'
import styles from './ChatMessage.module.css'

interface ChatMessageProps {
    message: MessageUI
    onReportClick: (reportData: {filename: string; content: string; messageId: number; reportId: number}) => void
    onDownload: (reportData: {filename: string; content: string; messageId: number; reportId: number}) => void
    onDelete?: (messageId: number) => void
    isGenerating?: boolean
    isDeleting?: boolean
}

const ChatMessage = ({message, onReportClick, onDownload, onDelete, isGenerating = false, isDeleting = false}: ChatMessageProps) => {
    const {user} = useAuth()
    const [isHovered, setIsHovered] = useState(false)
    const [showDeleteModal, setShowDeleteModal] = useState(false)

    const formatTime = (date: Date) => {
        return date.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    const handleDeleteClick = (e: React.MouseEvent) => {
        e.stopPropagation()
        setShowDeleteModal(true)
    }

    const handleConfirmDelete = () => {
        if (!message.id) return
        onDelete?.(message.id)
        setShowDeleteModal(false)
    }

    const handleCancelDelete = () => {
        setShowDeleteModal(false)
    }

    return (
        <>
            <div className={`${styles.chatMessage} ${styles[message.role]}`}>
                <div className={styles.messageAvatar}>
                    {message.role === 'user' ? (
                        <div className={styles.userAvatar}>U</div>
                    ) : (
                        <div className={styles.assistantAvatar}>
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                                <circle cx="12" cy="12" r="12" fill="#E8F0FE" />
                                <path
                                    d="M12 7C9.24 7 7 9.24 7 12C7 14.76 9.24 17 12 17C14.76 17 17 14.76 17 12C17 9.24 14.76 7 12 7ZM12 15.5C10.07 15.5 8.5 13.93 8.5 12C8.5 10.07 10.07 8.5 12 8.5C13.93 8.5 15.5 10.07 15.5 12C15.5 13.93 13.93 15.5 12 15.5Z"
                                    fill="#1976D2"
                                />
                                <path d="M11 10.5H13V11.5H11V10.5ZM11 12.5H13V13.5H11V12.5Z" fill="#1976D2" />
                            </svg>
                        </div>
                    )}
                </div>

                <div className={styles.messageContentWrapper}>
                    <div className={styles.messageHeader}>
                        <span className={styles.messageSender}>
                            {message.role === 'user' ? <span>{user?.username || '사용자'} </span> : 'Assistant'}
                        </span>
                        <span className={styles.messageTime}>{formatTime(message.timestamp)}</span>
                    </div>

                    <div className={styles.messageContent} onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
                        {/* 삭제 버튼 - 호버 시에만 표시 */}
                        {!isGenerating && isHovered && onDelete && (
                            <button className={styles.deleteBtn} onClick={handleDeleteClick} disabled={isDeleting} title="메시지 삭제">
                                <DeleteOutlined />
                            </button>
                        )}
                        
                        {/* 보고서 메시지 또는 보고서 내용 */}
                        <p>
                            {message.reportData
                                ? // reportData가 있으면 간단한 안내 메시지만 표시
                                  '보고서가 성공적으로 생성되었습니다!'
                                : // reportData가 없으면 전체 내용 표시
                                  message.content.split('\n').map((line, index) => (
                                      <React.Fragment key={index}>
                                          {line}
                                          {index < message.content.split('\n').length - 1 && <br />}
                                      </React.Fragment>
                                  ))}
                        </p>

                        {/* 보고서 첨부파일 */}          
                        {message.reportData && message.id && (
                            <div className={styles.reportAttachment}>
                                <div
                                    className={styles.reportFile}
                                    onClick={() =>
                                        onReportClick({
                                            filename: message.reportData!.filename,
                                            content: message.reportData!.content,
                                            messageId: message.id!,
                                            reportId: message.reportData!.reportId
                                        })
                                    }>
                                    <div className={styles.reportIcon}>
                                        <FileTextOutlined />
                                    </div>
                                    <div className={styles.reportInfo}>
                                        <div className={styles.reportFilename}>{message.reportData.filename}</div>
                                        <div className={styles.reportMeta}>MD 파일 • 클릭하여 미리보기</div>
                                    </div>
                                </div>
                                <button
                                    className={styles.reportDownloadBtn}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        onDownload({
                                            filename: message.reportData!.filename,
                                            content: message.reportData!.content,
                                            messageId: message.id!,
                                            reportId: message.reportData!.reportId
                                        })
                                    }}
                                    title="HWPX 다운로드">
                                    <DownloadOutlined />
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* 삭제 확인 모달 */}
            <DeleteChatMessageModal open={showDeleteModal} onConfirm={handleConfirmDelete} onCancel={handleCancelDelete} loading={isDeleting} />
        </>
    )
}

export default ChatMessage
