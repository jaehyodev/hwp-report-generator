import React, {useEffect, useState} from 'react'
import {Modal, Spin, Switch} from 'antd'
import {UserOutlined, CloseOutlined, SettingOutlined} from '@ant-design/icons'
import {useMessage} from '../../contexts/MessageContext'
import {TOAST_MESSAGES} from '../../constants'
import {authApi} from '../../services/authApi'
import {useTheme} from '../../hooks/useTheme'
import type {UserData} from '../../types/user'
import styles from './SettingsModal.module.css'

/**
 * SettingsModal.tsx
 *
 * 사용자 설정 모달
 * - Sidebar: 내 정보 표시 (API 조회)
 * - AdminPage: 선택한 사용자 정보 표시 (테이블 데이터 전달)
 */

interface SettingsModalProps {
    /** null이면 내 정보 조회 (API), UserData 전달 시 해당 데이터 표시 */
    user: UserData | null
    isOpen: boolean
    onClose: () => void
}

type TabType = 'general' | 'profile'

const SettingsModal: React.FC<SettingsModalProps> = ({user, isOpen, onClose}) => {
    const {antdMessage} = useMessage()
    const [userData, setUserData] = useState<UserData | null>(user)
    const [loading, setLoading] = useState(false)
    const [activeTab, setActiveTab] = useState<TabType>('general')
    const {theme, toggleTheme} = useTheme()

    // user가 null이면 내 정보 조회 (API)
    useEffect(() => {
        if (isOpen && user === null) {
            loadMyInfo()
        } else if (user) {
            setUserData(user)
        }
    }, [isOpen, user])

    //내 정보 조회
    const loadMyInfo = async () => {
        setLoading(true)
        try {
            const data = await authApi.getMyInfo()
            setUserData(data)
        } catch (error: any) {
            antdMessage.error(TOAST_MESSAGES.USER_INFO_LOAD_FAILED)
        } finally {
            setLoading(false)
        }
    }

    /*
     * 날짜 변환
     */
    const formatDate = (dateString: string): string => {
        const date = new Date(dateString)
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
    }

    return (
        <Modal open={isOpen} onCancel={onClose} footer={null} width={700} closeIcon={null} className={styles.modal}>
            <div className={styles.modalContainer}>
                {/* Body with Sidebar and Content */}
                <div className={styles.modalBody}>
                    {/* Left Sidebar */}
                    <div className={styles.sidebar}>
                        {/* Sidebar Header with Close Button */}
                        <div className={styles.sidebarHeader}>
                            <button className={styles.closeButton} onClick={onClose}>
                                <CloseOutlined />
                            </button>
                        </div>

                        {/* Sidebar Menu */}
                        <div className={styles.sidebarMenu}>
                            <button
                                className={`${styles.tabButton} ${activeTab === 'general' ? styles.active : ''}`}
                                onClick={() => setActiveTab('general')}>
                                <SettingOutlined className={styles.tabIcon} />
                                <span>일반</span>
                            </button>
                            <button
                                className={`${styles.tabButton} ${activeTab === 'profile' ? styles.active : ''}`}
                                onClick={() => setActiveTab('profile')}>
                                <UserOutlined className={styles.tabIcon} />
                                <span>사용자 정보</span>
                            </button>
                        </div>
                    </div>

                    {/* Right Content */}
                    <div className={styles.content}>
                        {/* Content Header */}
                        <div className={styles.contentHeader}>
                            <h2 className={styles.contentHeaderTitle}>{activeTab === 'general' ? '일반' : '사용자 정보'}</h2>
                        </div>

                        {/* Content Body */}
                        {activeTab === 'general' && (
                            <div className={styles.tabContent}>
                                {/* Dark Mode Row */}
                                <div className={styles.settingRow}>
                                    <span className={styles.settingLabel}>다크 모드</span>
                                    <Switch
                                        checked={theme === 'dark'}
                                        onChange={toggleTheme}
                                        checkedChildren="다크"
                                        unCheckedChildren="라이트"
                                    />
                                </div>
                            </div>
                        )}

                        {activeTab === 'profile' && (
                            <div className={styles.tabContent}>
                                {loading ? (
                                    <div className={styles.loading}>
                                        <Spin size="large" />
                                        <p>사용자 정보를 불러오는 중...</p>
                                    </div>
                                ) : userData ? (
                                    <div className={styles.profileInfo}>
                                        {/* Email */}
                                        <div className={styles.field}>
                                            <label className={styles.label}>이메일</label>
                                            <div className={styles.value}>{userData.email}</div>
                                        </div>

                                        {/* Username */}
                                        <div className={styles.field}>
                                            <label className={styles.label}>사용자명</label>
                                            <div className={styles.value}>{userData.username}</div>
                                        </div>

                                        {/* Created At */}
                                        <div className={styles.field}>
                                            <label className={styles.label}>가입일</label>
                                            <div className={styles.value}>{formatDate(userData.created_at)}</div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className={styles.empty}>사용자 정보를 불러올 수 없습니다.</div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Modal>
    )
}

export default SettingsModal
