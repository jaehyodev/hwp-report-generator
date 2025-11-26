// src/components/admin/AdminDashboard.tsx

import {Card, Button, Table, Statistic} from 'antd'
import {ReloadOutlined} from '@ant-design/icons'
import type {ColumnsType} from 'antd/es/table'
// ✨ 훅 이름과 import 경로를 useTokenUsage로 변경합니다.
import {useTokenUsage} from '@/hooks/useTokenUsage'
import type {TokenUsageUI} from '@/models/ui/TokenUsageUI' // TokenUsageUI 타입을 가져옵니다.

import styles from './AdminDashboard.module.css'
import {formatDate} from '@/utils/formatters'

// 사용자별 토큰 사용량 테이블의 컬럼 정의
// ✨ 컬럼 타입을 TokenUsageUI로 변경합니다.
const userUsageColumns: ColumnsType<TokenUsageUI> = [
    {
        title: 'ID',
        dataIndex: 'userId',
        key: 'userId',
        sorter: (a, b) => {
            // userId가 string이라고 가정하고 비교합니다. (useTokenUsage에서 string으로 변환했음)
            return String(a.userId).localeCompare(String(b.userId))
        },
        width: 100
    },
    {
        title: '사용자명',
        dataIndex: 'username',
        key: 'username',
        sorter: (a, b) => a.username.localeCompare(b.username),
    },
    {
        title: '입력 토큰',
        dataIndex: 'totalInputTokens',
        key: 'totalInputTokens',
        render: (value: number) => value.toLocaleString(),
        sorter: (a, b) => a.totalInputTokens - b.totalInputTokens,
        align: 'right',
    },
    {
        title: '출력 토큰',
        dataIndex: 'totalOutputTokens',
        key: 'totalOutputTokens',
        render: (value: number) => value.toLocaleString(),
        sorter: (a, b) => a.totalOutputTokens - b.totalOutputTokens,
        align: 'right',
    },
    {
        title: '총 토큰 사용량',
        dataIndex: 'totalTokens',
        key: 'totalTokens',
        render: (value: number) => value.toLocaleString(),
        sorter: (a, b) => a.totalTokens - b.totalTokens,
        align: 'right',
        defaultSortOrder: 'descend'
    },
    {
        title: '보고서 수',
        dataIndex: 'reportCount',
        key: 'reportCount',
        render: (value: number) => value.toLocaleString(),
        sorter: (a, b) => a.reportCount - b.reportCount,
        align: 'right',
    },
    {
        title: '최근 사용 시각',
        dataIndex: 'lastUsage',
        key: 'lastUsage',
        sorter: (a, b) => {
            const timeA = a.lastUsage ? new Date(a.lastUsage).getTime() : 0;
            const timeB = b.lastUsage ? new Date(b.lastUsage).getTime() : 0;
            return timeA - timeB;
        }
    },
]

const AdminDashboard = () => {
    // ✨ useTokenUsage 훅으로 변경하고, 분리된 상태를 가져옵니다.
    const {
        totalTokenUsage,
        isTotalUsageLoading,
        totalUsageError,
        userTokenUsageList,
        isUserUsageLoading,
        userUsageError,
        refetch: refetchUsage,
    } = useTokenUsage()

    // 로딩 상태 및 에러 상태를 통합하여 사용합니다.
    const isDashboardLoading = isTotalUsageLoading || isUserUsageLoading
    const dashboardError = totalUsageError || userUsageError

    return (
        <div className={styles.dashboardContainer}>
            <Card
                title="관리자 대시보드"
                extra={
                    <Button icon={<ReloadOutlined />} onClick={refetchUsage} loading={isDashboardLoading}>
                        새로고침
                    </Button>
                }
                className={styles.dashboardCard}
            >
                {/* 1. 전체 토큰 사용량 조회 */}
                <h2 className={styles.sectionTitle}>전체 토큰 사용 현황</h2>
                {isTotalUsageLoading && <p>전체 토큰 사용량 조회 중...</p>}
                {totalUsageError && <p style={{color: 'red'}}>{totalUsageError}</p>}
                {!isTotalUsageLoading && !totalUsageError && totalTokenUsage && (
                    <div className={styles.statsGrid}>
                        <Statistic 
                            title="입력 토큰" 
                            value={
                                totalTokenUsage.totalInputTokens != null 
                                ? totalTokenUsage.totalInputTokens.toLocaleString() 
                                : 'N/A'
                            } 
                        />
                        <Statistic 
                            title="출력 토큰" 
                            value={
                                totalTokenUsage.totalOutputTokens != null 
                                ? totalTokenUsage.totalOutputTokens.toLocaleString() 
                                : 'N/A'
                            } 
                        />
                        <Statistic 
                            title="총 토큰 사용량" 
                            value={
                                totalTokenUsage.totalTokens != null 
                                ? totalTokenUsage.totalTokens.toLocaleString() 
                                : 'N/A'
                            } 
                        />
                        <Statistic 
                            title="총 보고서 생성 수" 
                            value={
                                totalTokenUsage.reportCount != null 
                                ? totalTokenUsage.reportCount.toLocaleString() 
                                : 'N/A'
                            } 
                        />
                        <Statistic 
                            title="최근 사용 시각" 
                            value={totalTokenUsage.lastUsage ? totalTokenUsage.lastUsage : 'N/A'} 
                        />
                    </div>
                )}
                
                <hr className={styles.divider} />

                {/* 2. 사용자별 토큰 사용량 조회 테이블 */}
                <h2 className={styles.sectionTitle}>사용자별 토큰 사용량</h2>
                {userUsageError && <p style={{color: 'red'}}>{userUsageError}</p>}

                <Table
                    columns={userUsageColumns}
                    // ✨ 훅에서 가져온 userTokenUsageList를 사용합니다.
                    dataSource={userTokenUsageList || []} 
                    rowKey="userId" // ✨ rowKey를 userId로 설정합니다.
                    loading={isUserUsageLoading}
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: false,
                        showTotal: (total) => `총 ${total}명`
                    }}
                    className={styles.usageTable}
                />
            </Card>
        </div>
    )
}

export default AdminDashboard