import {Card, Table, Button, Space, Popconfirm} from 'antd'
import {ReloadOutlined, EyeOutlined, DeleteOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
import type {AdminTemplateItem} from '../../types/template'
import TemplateDetailModal from '../template/TemplateDetailModal'
import {formatDate, formatFileSize} from '../../utils/formatters'
import {useTemplateManagement} from '../../hooks/useTemplateManagement'
import styles from './AdminTemplateManagement.module.css'


/**
 * AdminTemplateManagement.tsx
 *
 * 관리자 템플릿 관리 컴포넌트
 * - 전체 사용자의 템플릿 목록 조회
 */

const AdminTemplateManagement = () => {
    // 커스텀 훅 사용 (관리자 모드)
    const {templates, loading, deleting, detailModalOpen, selectedTemplateId, loadTemplates, handleViewDetail, handleCloseDetail, handleDelete} =
        useTemplateManagement<AdminTemplateItem>({isAdmin: true})

    // Table 컬럼 정의
    const columns: ColumnsType<AdminTemplateItem> = [
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
            width: 200,
            ellipsis: true
        },
        {
            title: '사용자',
            dataIndex: 'username',
            key: 'username',
            width: 90,
            ellipsis: true
        },
        {
            title: '파일 크기',
            dataIndex: 'file_size',
            key: 'file_size',
            width: 110,
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
        <>
            <Card
                title="템플릿 관리"
                extra={
                    <Button icon={<ReloadOutlined />} onClick={() => loadTemplates()} loading={loading}>
                        새로고침
                    </Button>
                }
                className={styles.dashboardCard}
                >
                
                <Table
                    columns={columns}
                    dataSource={templates}
                    rowKey="id"
                    loading={loading}
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: true,
                        showTotal: (total) => `총 ${total}개`,
                        pageSizeOptions: ['10', '20', '50']
                    }}
                />
            </Card>

            {/* 상세 모달 */}
            <TemplateDetailModal open={detailModalOpen} templateId={selectedTemplateId} onClose={handleCloseDetail} />
        </>
    )
}

export default AdminTemplateManagement
