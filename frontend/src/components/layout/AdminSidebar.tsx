import React, {useState} from 'react'
import {
    UserOutlined,
    FileTextOutlined,
    SettingOutlined,
    DashboardOutlined,
    LeftOutlined,
    RightOutlined,
    FileAddOutlined
} from '@ant-design/icons'
import styles from './AdminSidebar.module.css'

interface AdminSidebarProps {
    activeMenu?: string
    onMenuChange?: (menuKey: string) => void
    isCollapsed: boolean
    onCollapseChange: (collapsed: boolean) => void
}

interface MenuItem {
    key: string
    icon: React.ReactNode
    label: string
    description?: string
}

const AdminSidebar = ({activeMenu = 'users', onMenuChange, isCollapsed, onCollapseChange}: AdminSidebarProps) => {
    const menuItems: MenuItem[] = [
        {
            key: 'dashboard',
            icon: <DashboardOutlined />,
            label: '대시보드',
            description: '시스템 현황'
        },
        {
            key: 'users',
            icon: <UserOutlined />,
            label: '사용자 관리',
            description: '사용자 승인 및 관리'
        },
        {
            key: 'templates',
            icon: <FileAddOutlined />,
            label: '템플릿 관리',
            description: '전체 사용자 템플릿 조회'
        },
        {
            key: 'reports',
            icon: <FileTextOutlined />,
            label: '보고서 관리',
            description: '생성된 보고서 조회'
        },
        {
            key: 'settings',
            icon: <SettingOutlined />,
            label: '시스템 설정',
            description: '시스템 환경 설정'
        }
    ]

    const handleMenuClick = (menuKey: string) => {
        if (onMenuChange) {
            onMenuChange(menuKey)
        }
    }

    const handleToggle = () => {
        onCollapseChange(!isCollapsed)
    }

    return (
        <aside className={`${styles.adminSidebar} ${isCollapsed ? styles.collapsed : styles.expanded}`}>
            {/* Sidebar Header */}
            <div className={styles.sidebarHeader}>
                <button className={styles.toggleBtn} onClick={handleToggle} title={isCollapsed ? '사이드바 열기' : '사이드바 닫기'}>
                    {isCollapsed ? <RightOutlined /> : <LeftOutlined />}
                </button>
                {!isCollapsed && <h3 className={styles.title}>관리자 메뉴</h3>}
            </div>

            {/* Menu Items */}
            <nav className={styles.menuList}>
                {menuItems.map((item) => (
                    <button
                        key={item.key}
                        className={`${styles.menuItem} ${activeMenu === item.key ? styles.active : ''}`}
                        onClick={() => handleMenuClick(item.key)}
                        title={isCollapsed ? item.label : undefined}>
                        <span className={styles.menuIcon}>{item.icon}</span>
                        {!isCollapsed && (
                            <div className={styles.menuContent}>
                                <span className={styles.menuLabel}>{item.label}</span>
                                {item.description && <span className={styles.menuDescription}>{item.description}</span>}
                            </div>
                        )}
                    </button>
                ))}
            </nav>
        </aside>
    )
}

export default AdminSidebar
