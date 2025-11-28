import React, {useState, useEffect} from 'react'
import {MenuOutlined, EditOutlined, DeleteOutlined} from '@ant-design/icons'
import {useNavigate} from 'react-router-dom'
import {useMessage} from '../contexts/MessageContext'
import {TOAST_MESSAGES} from '../constants'
import Sidebar from '../components/layout/Sidebar'
import MainLayout from '../components/layout/MainLayout'
import TopicEditModal from '../components/topic/TopicEditModal'
import TopicDeleteModal from '../components/topic/TopicDeleteModal'
import {useTopicStore} from '../stores/useTopicStore'
import type {Topic} from '../types/topic'
import styles from './TopicListPage.module.css'
import {UI_CONFIG} from '../constants'

const TopicListPage: React.FC = () => {
    const {antdMessage} = useMessage()
    const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(false)
    const [editingTopic, setEditingTopic] = useState<Topic | null>(null)
    const [isEditModalOpen, setIsEditModalOpen] = useState(false)
    const [deletingTopic, setDeletingTopic] = useState<Topic | null>(null)
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
    const navigate = useNavigate()

    const {pageTopics, pageLoading, selectedTopicId, setSelectedTopicId, loadPageTopics, pageTotalTopics, pageCurrentPage} = useTopicStore()

    const pageSize = UI_CONFIG.PAGINATION.TOPICS_PER_PAGE

    useEffect(() => {
        const fetchTopics = async () => {
            try {
                await loadPageTopics(1, pageSize)
            } catch (error: any) {
                antdMessage.error(error.response?.data?.detail || TOAST_MESSAGES.TOPIC_LOAD_FAILED)
                console.error('Failed to load topics:', error)
            }
        }

        fetchTopics()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const handleToggleSidebar = () => {
        setIsLeftSidebarOpen(!isLeftSidebarOpen)
    }

    /** 주제를 클릭한 경우, 주제 변경 및 메인 화면 이동 */
    const handleTopicSelect = (topicId: number) => {
        // pageTopics에서 선택한 토픽 찾기
        const selectedTopic = pageTopics.find((topic) => topic.id === topicId)

        // 토픽 ID와 템플릿 ID 함께 설정
        setSelectedTopicId(topicId, selectedTopic?.template_id ?? null)
        navigate('/')
    }

    const handleNewTopic = () => {
        setSelectedTopicId(null)
        navigate('/')
    }

    const handleEdit = (topic: Topic, e: React.MouseEvent) => {
        e.stopPropagation()
        setEditingTopic(topic)
        setIsEditModalOpen(true)
    }

    const handleCloseEditModal = () => {
        setIsEditModalOpen(false)
        setEditingTopic(null)
    }

    const handleDelete = (topic: Topic, e: React.MouseEvent) => {
        e.stopPropagation()
        setDeletingTopic(topic)
        setIsDeleteModalOpen(true)
    }

    const handleCloseDeleteModal = () => {
        setIsDeleteModalOpen(false)
        setDeletingTopic(null)
    }

    const handleRowClick = (topicId: number) => {
        handleTopicSelect(topicId)
    }

    // Server-side Pagination
    const totalPages = Math.ceil(pageTotalTopics / pageSize)
    const PAGE_GROUP_SIZE = 10 // 한 번에 표시할 페이지 번호 개수

    // 현재 페이지가 속한 페이지 그룹 계산 (1-10, 11-20, 21-30, ...)
    const currentPageGroup = Math.ceil(pageCurrentPage / PAGE_GROUP_SIZE)
    const startPage = (currentPageGroup - 1) * PAGE_GROUP_SIZE + 1
    const endPage = Math.min(currentPageGroup * PAGE_GROUP_SIZE, totalPages)

    // 페이지 번호 배열 생성
    const pageNumbers = []
    for (let i = startPage; i <= endPage; i++) {
        pageNumbers.push(i)
    }

    // 특정 페이지로 이동
    const handleGoToPage = async (page: number) => {
        try {
            await loadPageTopics(page, pageSize)
        } catch (error: any) {
            antdMessage.error(error.response?.data?.detail || TOAST_MESSAGES.TOPIC_LOAD_FAILED)
            console.error('Failed to load topics:', error)
        }
    }

    // 이전 10페이지 그룹으로 이동
    const handlePrevGroup = async () => {
        const prevGroupLastPage = startPage - 1
        if (prevGroupLastPage > 0) {
            await handleGoToPage(prevGroupLastPage)
        }
    }

    // 다음 10페이지 그룹으로 이동
    const handleNextGroup = async () => {
        const nextGroupFirstPage = endPage + 1
        if (nextGroupFirstPage <= totalPages) {
            await handleGoToPage(nextGroupFirstPage)
        }
    }

    const formatDate = (dateString: string) => {
        const date = new Date(dateString)
        return date.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    return (
        <MainLayout sidebarCollapsed={!isLeftSidebarOpen}>
            {/* Dim Overlay - 모바일/태블릿에서 사이드바 열렸을 때 */}
            {isLeftSidebarOpen && <div className={styles.dimOverlay} onClick={handleToggleSidebar} />}

            <Sidebar isOpen={isLeftSidebarOpen} onToggle={handleToggleSidebar} onTopicSelect={handleTopicSelect} onNewTopic={handleNewTopic} />

            <div className={`${styles.topicListPage} ${isLeftSidebarOpen ? styles.sidebarExpanded : styles.sidebarCollapsed}`}>
                {/* 햄버거 메뉴 버튼 - 모바일/태블릿에서만 표시 */}
                <button className={styles.hamburgerBtn} onClick={handleToggleSidebar} aria-label="메뉴 열기">
                    <MenuOutlined />
                </button>

                <div className={styles.container}>
                    <div className={styles.header}>
                        <h1>모든 대화</h1>
                        <p className={styles.subtitle}>총 {pageTotalTopics}개의 대화가 있습니다</p>
                    </div>

                    {pageLoading ? (
                        <div className={styles.loadingState}>
                            <div className={styles.loadingSpinner} />
                            <span>불러오는 중...</span>
                        </div>
                    ) : pageTopics.length === 0 ? (
                        <div className={styles.emptyState}>
                            <p>아직 대화가 없습니다</p>
                            <button className={styles.newTopicBtn} onClick={handleNewTopic}>
                                새 대화 시작하기
                            </button>
                        </div>
                    ) : (
                        <>
                            <div className={styles.tableContainer}>
                                <table className={styles.table}>
                                    <thead>
                                        <tr>
                                            <th className={styles.idColumn}>ID</th>
                                            <th className={styles.topicColumn}>주제</th>
                                            <th className={styles.dateColumn}>생성일</th>
                                            <th className={styles.actionColumn}>액션</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {pageTopics.map((topic) => (
                                            <tr
                                                key={topic.id}
                                                className={`${styles.row} ${selectedTopicId === topic.id ? styles.selected : ''}`}
                                                onClick={() => handleRowClick(topic.id)}>
                                                <td className={styles.idColumn} data-label="ID">
                                                    {topic.id}
                                                </td>
                                                <td className={styles.topicColumn} data-label="주제">
                                                    <div className={styles.topicTitle}>{topic.generated_title || topic.input_prompt}</div>
                                                    <div className={styles.topicPrompt}>{topic.input_prompt}</div>
                                                </td>
                                                <td className={styles.dateColumn} data-label="생성일">
                                                    {formatDate(topic.created_at)}
                                                </td>
                                                <td className={styles.actionColumn} data-label="액션">
                                                    <div className={styles.actionButtons}>
                                                        <button className={styles.actionBtn} onClick={(e) => handleEdit(topic, e)} title="수정">
                                                            <EditOutlined />
                                                        </button>
                                                        <button className={styles.actionBtn} onClick={(e) => handleDelete(topic, e)} title="삭제">
                                                            <DeleteOutlined />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            {/* Pagination */}
                            {totalPages > 1 && (
                                <div className={styles.pagination}>
                                    {/* 이전 그룹 버튼 (startPage가 1보다 크면 표시) */}
                                    {startPage > 1 && (
                                        <button className={styles.pageBtn} onClick={handlePrevGroup}>
                                            &lt;
                                        </button>
                                    )}

                                    {/* 페이지 번호 버튼들 (최대 10개) */}
                                    {pageNumbers.map((pageNum) => (
                                        <button
                                            key={pageNum}
                                            className={`${styles.pageBtn} ${pageNum === pageCurrentPage ? styles.active : ''}`}
                                            onClick={() => handleGoToPage(pageNum)}>
                                            {pageNum}
                                        </button>
                                    ))}

                                    {/* 다음 그룹 버튼 (endPage가 totalPages보다 작으면 표시) */}
                                    {endPage < totalPages && (
                                        <button className={styles.pageBtn} onClick={handleNextGroup}>
                                            &gt;
                                        </button>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Edit Modal */}
            <TopicEditModal topic={editingTopic} isOpen={isEditModalOpen} onClose={handleCloseEditModal} />

            {/* Delete Modal */}
            <TopicDeleteModal topic={deletingTopic} isOpen={isDeleteModalOpen} onClose={handleCloseDeleteModal} />
        </MainLayout>
    )
}

export default TopicListPage
