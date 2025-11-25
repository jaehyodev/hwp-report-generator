import {useState} from 'react'
import {Card, Table, Switch, Button, Space, message, Tag, Modal} from 'antd'
import {ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined, KeyOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
import MainLayout from '../components/layout/MainLayout'
import AdminSidebar from '../components/layout/AdminSidebar'
import { useAllTokenUsage } from '@/hooks/useAllTokenUsage'
import PromptManagement from '../components/admin/PromptManagement'
import AdminTemplateManagement from '../components/admin/AdminTemplateManagement'
import {useUsers} from '../hooks/useUsers'
import type {UserData} from '../types/user'
import {formatDate} from '../utils/formatters'
import styles from './AdminPage.module.css'

const AdminPage = () => {
    const {users, isLoading, refetch, approveUser, rejectUser, resetPassword} = useUsers()
    const [resettingUserId, setResettingUserId] = useState<number | null>(null)
    const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
    const [temporaryPassword, setTemporaryPassword] = useState('')
    const [resetMessage, setResetMessage] = useState('')
    const [activeMenu, setActiveMenu] = useState('users')
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
    const { usageList, isLoading: isUsageLoading, error: usageError, refetch: refetchUsage } = useAllTokenUsage()

    const handleToggleActive = async (userId: number, currentValue: boolean) => {
        try {
            if (currentValue) {
                await rejectUser(userId)
                message.success('사용자가 비활성화되었습니다.')
            } else {
                await approveUser(userId)
                message.success('사용자가 활성화되었습니다.')
            }
        } catch (error: any) {
            message.error(error.response?.data?.detail || '상태 변경에 실패했습니다.')
        }
    }

    const handleResetPassword = async (userId: number, username: string) => {
        console.log('비밀번호 초기화 시작:', userId, username)
        setResettingUserId(userId)

        try {
            const result = await resetPassword(userId)
            console.log('비밀번호 초기화 성공:', result)

            setResetMessage(result.message)
            setTemporaryPassword(result.temporary_password)
            setIsPasswordModalOpen(true)
        } catch (error: any) {
            console.error('비밀번호 초기화 실패:', error)
            message.error(error.response?.data?.detail || '비밀번호 초기화에 실패했습니다.')
        } finally {
            setResettingUserId(null)
        }
    }

    const columns: ColumnsType<UserData> = [
        {
            title: 'ID',
            dataIndex: 'id',
            key: 'id',
            width: 70
        },
        {
            title: '이메일',
            dataIndex: 'email',
            key: 'email'
        },
        {
            title: '사용자명',
            dataIndex: 'username',
            key: 'username'
        },
        {
            title: '활성화',
            dataIndex: 'is_active',
            key: 'is_active',
            render: (value: boolean, record) => (
                <Switch
                    checked={value}
                    onChange={() => handleToggleActive(record.id, value)}
                    checkedChildren={<CheckCircleOutlined />}
                    unCheckedChildren={<CloseCircleOutlined />}
                />
            )
        },
        {
            title: '관리자',
            dataIndex: 'is_admin',
            key: 'is_admin',
            render: (value: boolean) => <Tag color={value ? 'blue' : 'default'}>{value ? '관리자' : '일반'}</Tag>
        },
        {
            title: '비밀번호 재설정',
            dataIndex: 'password_reset_required',
            key: 'password_reset_required',
            render: (value: boolean) => <Tag color={value ? 'red' : 'green'}>{value ? '필요' : '불필요'}</Tag>
        },
        {
            title: '가입일',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (date: string) => {
                const timestamp = new Date(date).getTime() / 1000
                return formatDate(timestamp)
            }
        },
        {
            title: '액션',
            key: 'action',
            render: (_, record) => (
                <Space>
                    <Button
                        size="small"
                        icon={<KeyOutlined />}
                        onClick={() => handleResetPassword(record.id, record.username)}
                        loading={resettingUserId === record.id}>
                        비밀번호 초기화
                    </Button>
                </Space>
            )
        }
    ]

    return (
        <MainLayout showHeader={true}>
            <div className={styles.adminPageContainer}>
                <AdminSidebar
                    activeMenu={activeMenu}
                    onMenuChange={setActiveMenu}
                    isCollapsed={isSidebarCollapsed}
                    onCollapseChange={setIsSidebarCollapsed}
                />
                <div className={`${styles.adminContent} ${isSidebarCollapsed ? styles.sidebarCollapsed : undefined}`}>
                    {activeMenu === 'users' && (
                        <Card
                            title="사용자 관리"
                            extra={
                                <Button icon={<ReloadOutlined />} onClick={() => refetch()} loading={isLoading}>
                                    새로고침
                                </Button>
                            }>
                            <Table
                                columns={columns}
                                dataSource={users}
                                rowKey="id"
                                loading={isLoading}
                                pagination={{
                                    pageSize: 10,
                                    showSizeChanger: false,
                                    showTotal: (total) => `총 ${total}명`
                                }}
                            />
                        </Card>
                    )}

                    {activeMenu === 'dashboard' && (
                        <Card
                            title="대시보드"
                            extra={
                            <Button icon={<ReloadOutlined />} onClick={refetchUsage} loading={isUsageLoading}>
                                새로고침
                            </Button>
                            }
                        >
                            <h2>전체 토큰 사용량</h2>
                            {isUsageLoading && <p>전체 토큰 사용량 조회 중...</p>}
                            {usageError && <p style={{ color: 'red' }}>{usageError}</p>}
                            {!isUsageLoading && !usageError && (
                            <Table
                                dataSource={usageList}
                                rowKey="single" // 개수는 1개입니다.
                                pagination={false}
                                columns={[
                                { title: '입력 토큰', dataIndex: 'total_input_tokens', key: 'total_input_tokens' },
                                { title: '출력 토큰', dataIndex: 'total_output_tokens', key: 'total_output_tokens' },
                                { title: '총 토큰', dataIndex: 'total_tokens', key: 'total_tokens' },
                                { title: '보고서 수', dataIndex: 'report_count', key: 'report_count' }
                                ]}
                            />
                            )}
                        </Card>
                    )}

                    {activeMenu === 'prompts' && <PromptManagement />}

                    {activeMenu === 'templates' && <AdminTemplateManagement />}

                    {activeMenu === 'reports' && (
                        <Card title="보고서 관리">
                            <p>보고서 관리 기능은 준비 중입니다.</p>
                        </Card>
                    )}

                    {activeMenu === 'settings' && (
                        <Card title="시스템 설정">
                            <p>시스템 설정 기능은 준비 중입니다.</p>
                        </Card>
                    )}
                </div>
            </div>

            <Modal
                title="비밀번호 초기화 완료"
                open={isPasswordModalOpen}
                onOk={() => setIsPasswordModalOpen(false)}
                onCancel={() => setIsPasswordModalOpen(false)}
                cancelButtonProps={{style: {display: 'none'}}}
                width={500}>
                <div>
                    <p>{resetMessage}</p>
                    <p>
                        <strong>임시 비밀번호:</strong>{' '}
                        <span style={{color: '#1890ff', fontSize: '1.125rem', fontWeight: 'bold'}}>{temporaryPassword}</span>
                    </p>
                    <p style={{color: '#ff4d4f', marginTop: '1rem'}}>⚠️ 이 비밀번호를 사용자에게 전달해주세요.</p>
                </div>
            </Modal>
        </MainLayout>
    )
}

export default AdminPage
