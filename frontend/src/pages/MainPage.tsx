import {useState, useRef, useEffect} from 'react'
import {message as antdMessage} from 'antd'
import {MenuOutlined} from '@ant-design/icons'
import {OutlineMessage} from '../components/chat/OutlineMessage'
import ChatMessage from '../components/chat/ChatMessage'
import ChatInput, {type ChatInputHandle} from '../components/chat/ChatInput'
import ReportPreview from '../components/report/ReportPreview'
import PlanPreview from '../components/plan/PlanPreview'
import ReportsDropdown from '../components/chat/ReportsDropdown'
import {ChatWelcome} from '../components/chat/ChatWelcome'
import {ChatLoading} from '../components/chat/ChatLoading'
import {GeneratingIndicator} from '../components/chat/GeneratingIndicator'
import Sidebar from '../components/layout/Sidebar'
import TemplateSelectionView from '../components/template/TemplateSelectionView'
import styles from './MainPage.module.css'
import MainLayout from '../components/layout/MainLayout'
import {useTopicStore} from '../stores/useTopicStore'
import {useMessageStore} from '../stores/useMessageStore'
import {useArtifactHandlers} from '../hooks/useArtifactHandlers'
import {useChatActions} from '../hooks/useChatActions'
import {useMessages} from '../hooks/useMessages'
import {useReportPreview} from '../hooks/useReportPreview'

const MainPage = () => {
    // 주제 관리
    const {
        selectedTopicId,
        selectedTemplateId,
        setSelectedTopicId,
        setSelectedTemplateId,
        sidebarTopics,
        handleTopicPlanWithMessages,
        generateReportFromPlan,
        plan
    } = useTopicStore()

    // 템플릿 선택 화면 표시 여부
    const showTemplateSelection = selectedTopicId === null && selectedTemplateId === null

    // 메시지 관리
    const {addMessages, setMessages, isDeletingMessage, loadMessages, refreshMessages} = useMessageStore()

    // 현재 토픽에서 AI 응답 생성 중인지 확인 (토픽별로 GeneratingIndicator 표시 제어)
    const isGeneratingMessage = useTopicStore((state) => state.isTopicGenerating(selectedTopicId))

    // 현재 토픽의 메시지가 로딩 중인지 확인 (토픽별로 ChatLoading 표시 제어)
    const isLoadingMessages = useMessageStore((state) => state.isTopicMessagesLoading(selectedTopicId))

    // 메시지 구독 및 UI 변환 (커스텀 훅)
    const messages = useMessages(selectedTopicId)

    // UI 상태
    const chatInputRef = useRef<ChatInputHandle>(null)

    // 보고서 미리보기 및 다운로드 관리
    const {selectedReport, setSelectedReport, handleReportClick, handleClosePreview, handleDownload} = useReportPreview()

    // 계획 편집 사이드바 상태
    const [planPreviewOpen, setPlanPreviewOpen] = useState(false)
    const [editablePlan, setEditablePlan] = useState<string>('')
    const [showOutlineButtons, setShowOutlineButtons] = useState(true)

    /**
     * "생성" 버튼 클릭 → 원본 plan으로 보고서 생성 (실제 API)
     */
    const handleGenerateFromOutline = async () => {
        // PlanPreview가 열려있다면 닫기
        if (planPreviewOpen) {
            setPlanPreviewOpen(false)
        }

        // OutlineMessage 버튼 숨기기
        setShowOutlineButtons(false)

        await generateReportFromPlan()
    }

    /**
     * "수정" 버튼 클릭 → PlanPreview 열기
     */
    const handleContinueOutline = () => {
        // 이미 열려있으면 아무 동작 안 함
        if (planPreviewOpen) {
            return
        }

        // ReportPreview가 열려있으면 닫기
        if (selectedReport) {
            setSelectedReport(null)
        }

        const currentPlan = useTopicStore.getState().plan?.plan || ''
        if (!currentPlan) {
            antdMessage.error('계획 정보가 없습니다.')
            return
        }

        setEditablePlan(currentPlan)
        setPlanPreviewOpen(true)
    }

    /**
     * PlanPreview "보고서 생성" 버튼 클릭 → 편집된 plan으로 보고서 생성
     */
    const handleGenerateFromEditedPlan = async (editedPlan: string) => {
        // 1. plan 상태 업데이트
        const {updatePlan} = useTopicStore.getState()
        updatePlan(editedPlan)

        // 2. PlanPreview 닫기
        setPlanPreviewOpen(false)

        // 3. OutlineMessage 버튼 숨기기
        setShowOutlineButtons(false)

        // 4. 편집된 plan으로 보고서 생성
        await generateReportFromPlan()
    }

    /**
     * PlanPreview 닫기
     */
    const handleClosePlanPreview = () => {
        setPlanPreviewOpen(false)
    }

    // MainPage 언마운트 시 정리 (URL 이동 후 복귀 대응)
    useEffect(() => {
        return () => {
            const messageStore = useMessageStore.getState()
            const topicStore = useTopicStore.getState()
            const currentTopicId = topicStore.selectedTopicId

            // 1. 계획 모드(topicId=0)인 경우 메시지 초기화
            if (currentTopicId === 0) {
                messageStore.clearMessages(0)
                topicStore.clearPlan()
            }

            // 2. 선택된 주제의 메시지 초기화
            if (currentTopicId !== null && currentTopicId > 0) {
                messageStore.clearMessages(currentTopicId)
            }

            // 3. 주제 초기화
            topicStore.setSelectedTopicId(null)

            // 4. PlanPreview 닫기
            setPlanPreviewOpen(false)
            setEditablePlan('')
        }
    }, [])

    // 선택된 주제가 변경되면 메시지 자동 조회
    useEffect(() => {
        if (selectedTopicId !== null && selectedTopicId > 0) {
            const messageStore = useMessageStore.getState()
            const storedMessages = messageStore.getMessages(selectedTopicId)

            // Zustand에 메시지가 없을 때만 서버에서 로드
            if (storedMessages.length === 0) {
                loadMessages(selectedTopicId)
            }
        }
    }, [selectedTopicId])

    // 아티팩트(보고서) 관련 핸들러
    const {
        isReportsDropdownOpen,
        setIsReportsDropdownOpen,
        getMarkdownArtifacts,
        getSelectedArtifactId,
        loadingTopics,
        handleReportsClick,
        handleArtifactSelect,
        handleArtifactDownload,
        handleArtifactPreview
    } = useArtifactHandlers()

    // 채팅 액션 훅
    const {handleSendMessage: sendMessage, handleDeleteMessage: deleteMessage} = useChatActions({
        selectedTopicId,
        setSelectedTopicId,
        setMessages,
        refreshMessages
    })

    /**
     * 메시지 전송 래퍼 함수
     * 첫 메시지일 경우 계획 모드로 전환
     */
    const handleSendMessage = async (message: string, files: File[], webSearchEnabled: boolean) => {
        // 계획 모드 판단: selectedTopicId가 null(첫 시작) 또는 0(계획 생성 중)
        if (selectedTopicId === null || selectedTopicId === 0) {
            // 보고서 생성 이전인 계획 모드인 경우
            const templateId = selectedTemplateId || 1

            // 새 plan 요청 시 버튼 표시 상태 리셋
            setShowOutlineButtons(true)

            // handleTopicPlanWithMessages 내부에서 isTopicPlan=true 설정됨
            await handleTopicPlanWithMessages(templateId, message, addMessages)
        } else {
            // 보고서 생성 이후로 토픽이 만들어진 이후인 경우, 메시지 전송
            await sendMessage(message, files, webSearchEnabled)
        }
    }

    // 사이드바 열림 상태
    const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(false)

    // 마지막 사용자 메시지 참조 (스크롤용)
    const lastUserMessageRef = useRef<HTMLDivElement>(null)

    // 보고서 드롭다운 참조
    const reportsDropdownRef = useRef<HTMLDivElement>(null)

    // Close reports dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (reportsDropdownRef.current && !reportsDropdownRef.current.contains(event.target as Node)) {
                setIsReportsDropdownOpen(false)
            }
        }

        if (isReportsDropdownOpen) {
            document.addEventListener('mousedown', handleClickOutside)
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [isReportsDropdownOpen])

    // 두 번째 메시지부터 마지막 사용자 메시지를 헤더 아래로 스크롤
    useEffect(() => {
        if (messages.length > 2 && lastUserMessageRef.current) {
            const lastMessage = messages[messages.length - 1]
            if (lastMessage.role === 'user') {
                setTimeout(() => {
                    lastUserMessageRef.current?.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    })
                }, 100)
            }
        }
    }, [messages])

    /**
     * 메시지 삭제 핸들러 (useChatActions 훅 래핑)
     */
    const handleDeleteMessage = async (messageId: number) => {
        await deleteMessage(messageId, setSelectedReport, selectedReport, messages)
    }

    /**
     * 템플릿 선택 완료 후 채팅 시작
     */
    const handleStartChat = (templateId: number) => {
        setSelectedTemplateId(templateId)
        // 템플릿이 선택되면 채팅 화면으로 전환되지만, 아직 토픽은 생성되지 않음
        // 첫 메시지 전송 시 handleSendMessage에서 토픽 생성

        // 템플릿 ChatWelcome 컴포넌트에 표시
    }

    /**
     * 새 토픽 시작 시
     */
    const handleNewTopik = () => {
        const prevTopicId = selectedTopicId

        // 이전 토픽의 메시지 정리
        if (prevTopicId !== null) {
            const messageStore = useMessageStore.getState()

            // 계획 모드(topicId=0) 메시지 정리
            if (prevTopicId === 0) {
                messageStore.clearMessages(0)
            }

            // 실제 토픽 메시지는 유지 (나중에 다시 볼 수 있음)
            // 만약 완전히 지우고 싶다면: messageStore.clearMessages(prevTopicId)
        }

        // 보고서 미리보기 닫기
        setSelectedReport(null)

        // 템플릿 선택 화면으로 돌아가기
        setSelectedTopicId(null)
        setSelectedTemplateId(null)
    }

    /**
     * 사이드바에서 토픽 선택 시 핸들러
     */
    const handleSidebarTopicSelect = (topicId: number) => {
        // sidebarTopics에서 선택한 토픽 찾기
        const selectedTopic = sidebarTopics.find((topic) => topic.id === topicId)

        // 토픽 ID와 템플릿 ID 함께 설정
        setSelectedTopicId(topicId, selectedTopic?.template_id ?? null)
    }

    /**
     * 사이드바 토글
     */
    const handleToggleSidebar = () => {
        setIsLeftSidebarOpen(!isLeftSidebarOpen)
    }

    return (
        <MainLayout sidebarCollapsed={!isLeftSidebarOpen}>
            {/* Dim Overlay - 모바일/태블릿에서 사이드바 열렸을 때 */}
            {isLeftSidebarOpen && <div className={styles.dimOverlay} onClick={handleToggleSidebar} />}

            <Sidebar isOpen={isLeftSidebarOpen} onToggle={handleToggleSidebar} onTopicSelect={handleSidebarTopicSelect} onNewTopic={handleNewTopik} />

            <div className={`${styles.mainChatPage} ${isLeftSidebarOpen ? styles.sidebarExpanded : styles.sidebarCollapsed}`}>
                {/* 템플릿 선택 화면 또는 채팅 화면 */}
                {showTemplateSelection ? (
                    // 템플릿 선택 화면
                    <TemplateSelectionView onStartChat={handleStartChat} />
                ) : (
                    // 기존 채팅 화면
                    <>
                        {/* 햄버거 메뉴 버튼 - 모바일/태블릿에서만 표시 */}
                        <button className={styles.hamburgerBtn} onClick={handleToggleSidebar} aria-label="메뉴 열기">
                            <MenuOutlined />
                        </button>
                        <div className={styles.chatContainer}>
                            <div className={styles.chatContent}>
                                {isLoadingMessages ? (
                                    <ChatLoading />
                                ) : messages.length === 0 ? (
                                    <ChatWelcome />
                                ) : (
                                    <div className={styles.chatMessages}>
                                        {messages.map((message, index) => {
                                            const isLastUserMessage = message.role === 'user' && index === messages.length - 1

                                            return (
                                                <div key={message.clientId} ref={isLastUserMessage ? lastUserMessageRef : null}>
                                                    {message.isPlan ? (
                                                        <OutlineMessage
                                                            message={message}
                                                            onGenerateReport={handleGenerateFromOutline}
                                                            onContinue={handleContinueOutline}
                                                            showButtons={showOutlineButtons && plan !== null}
                                                        />
                                                    ) : (
                                                        <ChatMessage
                                                            message={message}
                                                            onReportClick={handleReportClick}
                                                            onDownload={handleDownload}
                                                            onDelete={handleDeleteMessage}
                                                            isGenerating={isGeneratingMessage}
                                                            isDeleting={isDeletingMessage}
                                                        />
                                                    )}
                                                </div>
                                            )
                                        })}
                                        {isGeneratingMessage && <GeneratingIndicator />}
                                    </div>
                                )}
                            </div>

                            <div className={styles.chatInputWrapper}>
                                <ChatInput
                                    ref={chatInputRef}
                                    onSend={handleSendMessage}
                                    disabled={isGeneratingMessage || isLoadingMessages || planPreviewOpen}
                                    onReportsClick={() => handleReportsClick(selectedTopicId)}
                                    reportsDropdown={
                                        isReportsDropdownOpen && selectedTopicId ? (
                                            <ReportsDropdown
                                                ref={reportsDropdownRef}
                                                artifacts={getMarkdownArtifacts(selectedTopicId)}
                                                loading={loadingTopics.has(selectedTopicId)}
                                                selectedArtifactId={getSelectedArtifactId(selectedTopicId)}
                                                onSelect={(id) => handleArtifactSelect(selectedTopicId, id)}
                                                onClose={() => setIsReportsDropdownOpen(false)}
                                                onDownload={(art) => handleArtifactDownload(art, selectedTopicId)}
                                                onPreview={(art) => handleArtifactPreview(art, setSelectedReport)}
                                            />
                                        ) : null
                                    }
                                />
                            </div>
                        </div>

                        {selectedReport && (
                            <ReportPreview report={selectedReport} onClose={handleClosePreview} onDownload={() => handleDownload(selectedReport)} />
                        )}

                        {planPreviewOpen && (
                            <PlanPreview plan={editablePlan} onClose={handleClosePlanPreview} onGenerate={handleGenerateFromEditedPlan} />
                        )}
                    </>
                )}
            </div>
        </MainLayout>
    )
}

export default MainPage
