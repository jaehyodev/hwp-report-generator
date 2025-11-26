import React from 'react'
import {Layout} from 'antd'
import Header from './Header'
import Footer from './Footer'
import styles from './MainLayout.module.css'

const {Content} = Layout

interface MainLayoutProps {
    children: React.ReactNode
    sidebarCollapsed?: boolean | null
    showHeader?: boolean
}

const MainLayout = ({children, sidebarCollapsed = null, showHeader = false}: MainLayoutProps) => {
    return (
        <Layout className={styles.main}>
            {showHeader && <Header />}
            <Content className={styles.content} data-has-header={showHeader}>
                <div>{children}</div>
            </Content>
            <Footer sidebarCollapsed={sidebarCollapsed} />
        </Layout>
    )
}

export default MainLayout
