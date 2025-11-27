import React, {useState} from 'react'
import {Button, Table, Card, Space, Popconfirm} from 'antd'
import {PlusOutlined, MenuOutlined, DeleteOutlined, EyeOutlined, ReloadOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
import {useNavigate} from 'react-router-dom'
import type {TemplateListItem} from '../types/template'
import MainLayout from '../components/layout/MainLayout'
import Sidebar from '../components/layout/Sidebar'
import TemplateDetailModal from '../components/template/TemplateDetailModal'
import TemplateUploadModal from '../components/template/TemplateUploadModal'
import {useTopicStore} from '../stores/useTopicStore'
import {formatDate, formatFileSize} from '../utils/formatters'
import {useTemplateManagement} from '../hooks/useTemplateManagement'
import styles from './TemplateManagementPage.module.css'

/**
 * TemplateManagementPage.tsx
 *
 * ⭐ 템플릿 관리 페이지
 *
 * 역할:
 * 1. 내 템플릿 목록 조회 및 표시 (Table)
 * 2. 템플릿 업로드 (모달)
 * 3. 템플릿 상세 정보 표시 (모달)
 * 4. 템플릿 삭제
 *
 * 구조:
 * - MainLayout + Sidebar: 좌측 사이드바
 * - Table: 템플릿 목록
 * - TemplateUploadModal: 업로드 모달
 * - TemplateDetailModal: 상세 모달
 */

const TemplateManagementPage: React.FC = () => {
    const navigate = useNavigate()
    const {setSelectedTopicId} = useTopicStore()

    // 커스텀 훅 사용 (일반 사용자 모드)
    const {templates, loading, deleting, uploading, detailModalOpen, selectedTemplateId, loadTemplates, handleViewDetail, handleCloseDetail, handleDelete, handleUpload} =
        useTemplateManagement<TemplateListItem>({isAdmin: false})

    // UI 상태
    const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(false)

    // 모달 상태
    const [uploadModalOpen, setUploadModalOpen] = useState(false)

    // 사이드바 토글
    const handleToggleSidebar = () => {
        setIsLeftSidebarOpen(!isLeftSidebarOpen)
    }

    // 새 토픽 시작
    const handleNewTopic = () => {
        setSelectedTopicId(null)
        navigate('/')
    }

    // 토픽 선택
    const handleTopicSelect = (topicId: number) => {
        setSelectedTopicId(topicId)
        navigate('/')
    }

    // Table 컬럼 정의
    const columns: ColumnsType<TemplateListItem> = [
        {
            title: 'ID',
            dataIndex: 'id',
            key: 'id',
            width: 70
        },
        {
            title: '제목',
            dataIndex: 'title',
            key: 'title',
            ellipsis: true
        },
        {
            title: '파일명',
            dataIndex: 'filename',
            key: 'filename',
            ellipsis: true
        },
        {
            title: '파일 크기',
            dataIndex: 'file_size',
            key: 'file_size',
            width: 120,
            render: (size: number) => formatFileSize(size)
        },
        {
            title: '생성일',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 180,
            render: (date: string) => {
                const timestamp = new Date(date).getTime() / 1000
                return formatDate(timestamp)
            }
        },
        {
            title: '액션',
            key: 'action',
            width: 180,
            render: (_, record) => (
                <Space>
                    <Button size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record.id)}>
                        상세
                    </Button>
                    <Popconfirm
                        title="템플릿을 삭제하시겠습니까?"
                        description="삭제된 템플릿은 복구할 수 없습니다."
                        onConfirm={() => handleDelete(record.id)}
                        okText="삭제"
                        cancelText="취소"
                        okButtonProps={{danger: true}}>
                        <Button size="small" danger icon={<DeleteOutlined />} loading={deleting}>
                            삭제
                        </Button>
                    </Popconfirm>
                </Space>
            )
        }
    ]

    return (
        <MainLayout sidebarCollapsed={!isLeftSidebarOpen}>
            {/* Dim Overlay */}
            {isLeftSidebarOpen && <div className={styles.dimOverlay} onClick={handleToggleSidebar} />}

            <Sidebar isOpen={isLeftSidebarOpen} onToggle={handleToggleSidebar} onTopicSelect={handleTopicSelect} onNewTopic={handleNewTopic} />

            <div className={`${styles.mainContent} ${isLeftSidebarOpen ? styles.sidebarExpanded : styles.sidebarCollapsed}`}>
                {/* 햄버거 메뉴 버튼 */}
                <button className={styles.hamburgerBtn} onClick={handleToggleSidebar} aria-label="메뉴 열기">
                    <MenuOutlined />
                </button>

                <div className={styles.container}>
                    <Card
                        title="템플릿 관리"
                        extra={
                            <Space>
                                <Button icon={<ReloadOutlined />} onClick={() => loadTemplates()} loading={loading}>
                                    새로고침
                                </Button>
                                <Button type="primary" icon={<PlusOutlined />} onClick={() => setUploadModalOpen(true)}>
                                    템플릿 업로드
                                </Button>
                            </Space>
                        }>
                        <Table
                            columns={columns}
                            dataSource={templates}
                            rowKey="id"
                            loading={loading}
                            pagination={false}
                            // 백엔드 페이징 API 없음 - 전체 목록 표시
                            // pagination={{
                            //     pageSize: 10,
                            //     showSizeChanger: true,
                            //     showTotal: (total) => `총 ${total}개`,
                            //     pageSizeOptions: ['10', '20', '50']
                            // }}
                        />
                    </Card>
                </div>
            </div>

            {/* 업로드 모달 */}
            <TemplateUploadModal open={uploadModalOpen} onClose={() => setUploadModalOpen(false)} uploading={uploading} onUpload={handleUpload} />

            {/* 상세 모달 */}
            <TemplateDetailModal open={detailModalOpen} templateId={selectedTemplateId} onClose={handleCloseDetail} />
        </MainLayout>
    )
}

export default TemplateManagementPage
