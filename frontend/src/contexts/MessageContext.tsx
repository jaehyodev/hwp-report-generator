import React, {createContext, useContext} from 'react'
import {App} from 'antd'
import type {MessageInstance} from 'antd/es/message/interface'

interface MessageContextType {
    antdMessage: MessageInstance
}

const MessageContext = createContext<MessageContextType | undefined>(undefined)

/**
 * MessageProvider
 *
 * antd App.useApp() 훅을 통해 message 인스턴스를 제공하는 Provider
 * 다크/라이트 테마를 동적으로 지원하려면 이 방식 사용 필수
 *
 * 사용법:
 * - 컴포넌트/훅: const { antdMessage } = useMessage()
 */
export function MessageProvider({children}: {children: React.ReactNode}) {
    const {message} = App.useApp()

    return (
        <MessageContext.Provider value={{antdMessage: message}}>
            {children}
        </MessageContext.Provider>
    )
}

/**
 * useMessage 훅
 *
 * React 컴포넌트/커스텀 훅에서 antdMessage 인스턴스 사용
 */
export function useMessage() {
    const context = useContext(MessageContext)
    if (!context) {
        throw new Error('useMessage must be used within MessageProvider')
    }
    return context
}
