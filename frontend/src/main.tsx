import {StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import App from './App'

import './styles/variables.css' // CSS 변수 정의 (색상, 간격 등)
import './styles/global.css' // 전역 스타일
import './styles/common.css' // 공통 스타일
import 'antd/dist/reset.css' // Ant Design 기본 스타일 초기화

/**
 * main.tsx
 *
 * ⭐ 리액트 앱의 시작점 (진입점)
 *
 * 역할:
 * 1. HTML의 #root 요소를 찾아서
 * 2. 그 안에 리액트 앱(<App />)을 렌더링
 *
 * StrictMode: 개발 모드에서 잠재적 문제를 경고해주는 도구
 * MSW: 개발 환경에서 Mock Service Worker 활성화
 */

/**
 * MSW 초기화
 * 개발 환경에서만 MSW worker를 시작합니다.
 * npm run dev로 Vite를 실행하면
 * 자동으로 import.meta.env.MODE의 값은 'development'가 됩니다.
 */
async function enableMocking() {
    // MSW 비활성화 옵션 체크
    if (import.meta.env.VITE_ENABLE_MSW === 'false') {
        console.log('[MSW] MSW disabled by environment variable')
        return
    }

    if (import.meta.env.MODE !== 'development') {
        console.log('[MSW] Not in development mode, skipping MSW')
        return
    }

    console.log('[MSW] Starting MSW in development mode...')
    const {worker} = await import('./mocks/browser')

    // MSW worker 시작
    return worker.start({
        onUnhandledRequest: 'bypass' // Mock되지 않은 요청은 실제 API로 통과
    })
}

// MSW 초기화 후 앱 렌더링
enableMocking().then(() => {
    console.log('[MSW] MSW initialization complete, rendering app...')
    createRoot(document.getElementById('root')!).render(
        <StrictMode>
            <App />
        </StrictMode>
    )
})
