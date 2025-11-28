import {useState, useRef, useEffect, forwardRef, useImperativeHandle, type KeyboardEvent} from 'react'
import {SendOutlined, GlobalOutlined, CloseOutlined, ControlOutlined} from '@ant-design/icons'
import styles from './ChatInput.module.css'
import SettingsDropdown from './SettingsDropdown'
import { Button } from 'antd'

interface ChatInputProps {
    onSend: (message: string, files: File[], webSearchEnabled: boolean) => void
    disabled?: boolean
    onReportsClick?: () => void
    reportsDropdown?: React.ReactNode
}

export interface ChatInputHandle {
    focus: () => void
}

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(({onSend, disabled = false, onReportsClick, reportsDropdown}, ref) => {
    const [message, setMessage] = useState('')
    const [files, setFiles] = useState<File[]>([])
    const [webSearchEnabled, setWebSearchEnabled] = useState(false)
    const [isDropdownOpen, setIsDropdownOpen] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    // 외부에서 포커스를 줄 수 있도록 노출
    useImperativeHandle(ref, () => ({
        focus: () => {
            textareaRef.current?.focus()
        }
    }))
    const dropdownRef = useRef<HTMLDivElement>(null)

    /*
     * 드롭다운 외부 클릭 시 닫기 핸들러
     */
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false)
            }
        }

        if (isDropdownOpen) {
            document.addEventListener('mousedown', handleClickOutside)
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [isDropdownOpen])

    {/* 첨부파일 로직 (미사용 및 미구현) */}
    /*
        const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
            const selectedFiles = event.target.files;
            console.log("선택된 파일들:", selectedFiles);

            if (selectedFiles) {
                setFiles(prev => {
                    const updated = [...prev, ...Array.from(selectedFiles)];
                    console.log("업데이트될 files:", updated);
                    return updated;
                });
            }
            // Reset input
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        }

        const handleRemoveFile = (index: number) => {
            setFiles((prev) => prev.filter((_, i) => i !== index))
        }
    */

    /*
     * 메시지 전송 핸들러
     */
    const handleSend = () => {
        if (message.trim() || files.length > 0) {
            onSend(message, files, webSearchEnabled)
            setMessage('')
            setFiles([])
            // 사용자 입력 영역 크기 초기화
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto'
            }
        }
    }

    /*
     * 엔터키 입력 시, 메시지 전송 핸들러
     */
    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    /*
     * 사용자 메시지 입력 핸들러
     */
    const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setMessage(e.target.value)
        // 사용자 입력 영역 크기 자동으로 변경
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto'
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
        }
    }

    /*
     * 웹 검색 스위치 핸들러
     */
    const handleWebSearchChange = (enabled: boolean) => {
        setWebSearchEnabled(enabled)
        setIsDropdownOpen(false)
    }

    return (
        <div className={styles.chatInputContainer}>
            {/* 첨부파일 표시용 (미사용 및 미구현) */}
            {/*
                {files.length > 0 && (
                    <div className={styles.uploadedFiles}>
                        {files.map((file, index) => (
                            <div key={index} className={styles.uploadedFile}>
                                <PaperClipOutlined />
                                <span className={styles.fileName}>{file.name}</span>
                                <button className={styles.removeFileBtn} onClick={() => handleRemoveFile(index)}>
                                    <CloseOutlined />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            */}

            {/* 사용자 입력창 */}
            <div className={`${styles.chatInputBox} ${styles.multiRow}`}>
                <div className={styles.leftButtons}>
                    {/* 첨부파일 (미사용 및 미구현) */}
                    {/*
                        <button className={styles.attachBtn} onClick={() => fileInputRef.current?.click()} disabled={disabled} title="파일 첨부">
                            <PaperClipOutlined />
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept=".hwpx,.txt,.pdf,.doc,.docx"
                            onChange={handleFileSelect}
                            style={{display: 'none'}}
                        />
                    */}

                    {/* 참조 보고서 선택용 (미사용) */}
                    {/*
                        <div className={styles.reportsWrapper}>
                            <button className={styles.reportsBtn} onClick={onReportsClick} disabled={disabled} title="참조 보고서 선택">
                                <FileTextOutlined />
                            </button>
                            {reportsDropdown}
                        </div>
                    */}

                    {/* 설정 버튼 */}
                    <div className={styles.settingsWrapper}>
                        <Button className={styles.settingsBtn} onClick={() => setIsDropdownOpen(!isDropdownOpen)} disabled={disabled} title="설정">
                            <ControlOutlined />
                        </Button>
                        {/* 설정 드랍다운 */}
                        {isDropdownOpen && (
                            <SettingsDropdown ref={dropdownRef} webSearchEnabled={webSearchEnabled} onWebSearchChange={handleWebSearchChange} />
                        )}
                    </div>

                    {/* 웹 검색 켜질 경우 표시용 */}
                    {webSearchEnabled && (
                        <div className={styles.webSearchChip}>
                            <GlobalOutlined />
                            <span>웹 검색</span>
                            <Button className={styles.chipCloseBtn} onClick={() => setWebSearchEnabled(false)} title="웹 검색 끄기">
                                <CloseOutlined />
                            </Button>
                        </div>
                    )}
                </div>

                {/* 사용자 입력 영역 */}
                <textarea
                    ref={textareaRef}
                    className={styles.chatTextarea}
                    placeholder="보고서 주제를 입력하세요... (Shift+Enter로 줄바꿈)"
                    value={message}
                    onChange={handleTextareaChange}
                    onKeyDown={handleKeyDown}
                    disabled={disabled}
                    rows={1}
                />

                {/* 사용자 입력창 안에 전송 버튼 */}
                <Button className={styles.sendBtn} onClick={handleSend} disabled={disabled || (!message.trim() && files.length === 0)} title="전송">
                    <SendOutlined />
                </Button>
            </div>
        </div>
    )
})

ChatInput.displayName = 'ChatInput'

export default ChatInput
