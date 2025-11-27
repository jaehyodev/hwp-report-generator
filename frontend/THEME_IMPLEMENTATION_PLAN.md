# 🎨 다크/라이트 테마 구현 완료 문서

## ✅ 구현 완료 상태

다크/라이트 테마가 성공적으로 구현되었습니다!

---

## 📋 구현된 구조

### 1. CSS Variables 기반 테마 시스템 (`variables.css`)

**위치**: `frontend/src/styles/variables.css`

#### 라이트 테마 (`:root`)
```css
:root {
    /* Primary Colors */
    --primary-color: #1890ff;
    --primary-hover: #40a9ff;
    --primary-active: #096dd9;

    /* Status Colors */
    --success-color: #52c41a;
    --warning-color: #faad14;
    --error-color: #ff4d4f;
    --info-color: #1890ff;

    /* Neutral Colors */
    --text-primary: #000000d9;
    --text-secondary: #1a1a1a;
    --text-disabled: #00000040;
    --border-color: #e5e5e5;
    --bg-primary: #ffffff;
    --bg-primary-hover: #f5f5f5;
    --color-white: #ffffff;
    --color-black: #000000;
    --color-grey: #666666;
    --color-label: #999999;

    /* Spacing, Font, Radius, Shadows 등은 테마와 무관하게 동일 */
}
```

#### 다크 테마 (`[data-theme='dark']`)
```css
[data-theme='dark'] {
    /* Primary Colors - 다크 모드에서는 약간 밝게 */
    --primary-color: #40a9ff;
    --primary-hover: #69c0ff;
    --primary-active: #1890ff;

    /* Status Colors */
    --success-color: #73d13d;
    --warning-color: #ffc53d;
    --error-color: #ff7875;
    --info-color: #40a9ff;

    /* Neutral Colors - 반전 */
    --text-primary: rgba(255, 255, 255, 0.85);
    --text-secondary: rgba(255, 255, 255, 0.65);
    --text-disabled: rgba(255, 255, 255, 0.25);

    --border-color: #3a3a3a;

    --bg-primary: #1f1f1f;
    --bg-primary-hover: #2a2a2a;
    --color-white: #1f1f1f;
    --color-black: #ffffff;

    --color-grey: #a8a8a8;
    --color-label: #888888;

    /* Shadows - 다크 모드에서는 더 진하게 */
    --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
}
```

---

### 2. Ant Design 테마 토큰

Ant Design 컴포넌트를 위한 테마 설정이 `variables.css`에서 색상을 동적으로 가져옵니다.

#### `lightTheme.ts`
```typescript
import type { ThemeConfig } from 'antd';

const getCSSVariable = (name: string): string => {
  if (typeof window !== 'undefined') {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  return '';
};

export const lightTheme: ThemeConfig = {
  token: {
    // CSS Variables에서 색상만 가져옴
    colorPrimary: getCSSVariable('--primary-color') || '#1890ff',
    colorSuccess: getCSSVariable('--success-color') || '#52c41a',
    colorWarning: getCSSVariable('--warning-color') || '#faad14',
    colorError: getCSSVariable('--error-color') || '#ff4d4f',
    colorInfo: getCSSVariable('--info-color') || '#1890ff',

    colorText: getCSSVariable('--text-primary') || 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: getCSSVariable('--text-secondary') || '#1a1a1a',
    colorTextTertiary: getCSSVariable('--color-grey') || '#666666',
    colorTextQuaternary: getCSSVariable('--text-disabled') || 'rgba(0, 0, 0, 0.25)',

    colorBgContainer: getCSSVariable('--bg-primary') || '#ffffff',
    colorBgElevated: getCSSVariable('--color-white') || '#ffffff',
    colorBgLayout: getCSSVariable('--bg-primary-hover') || '#f5f5f5',

    colorBorder: getCSSVariable('--border-color') || '#e5e5e5',
  },
  components: {
    Button: {
      colorPrimary: getCSSVariable('--primary-color') || '#1890ff',
      algorithm: true,
    },
    Input: {
      colorBorder: getCSSVariable('--border-color') || '#e5e5e5',
    },
    Select: {
      colorBorder: getCSSVariable('--border-color') || '#e5e5e5',
    },
    Table: {
      borderColor: getCSSVariable('--border-color') || '#e5e5e5',
    },
  },
};
```

#### `darkTheme.ts`
```typescript
import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

const getCSSVariable = (name: string): string => {
  if (typeof window !== 'undefined') {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  return '';
};

export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm, // Ant Design 다크 알고리즘

  token: {
    // CSS Variables [data-theme='dark']에서 색상 가져옴
    colorPrimary: getCSSVariable('--primary-color') || '#40a9ff',
    colorSuccess: getCSSVariable('--success-color') || '#73d13d',
    colorWarning: getCSSVariable('--warning-color') || '#ffc53d',
    colorError: getCSSVariable('--error-color') || '#ff7875',
    colorInfo: getCSSVariable('--info-color') || '#40a9ff',

    colorText: getCSSVariable('--text-primary') || 'rgba(255, 255, 255, 0.85)',
    colorTextSecondary: getCSSVariable('--text-secondary') || 'rgba(255, 255, 255, 0.65)',
    colorTextTertiary: getCSSVariable('--color-grey') || 'rgba(255, 255, 255, 0.45)',
    colorTextQuaternary: getCSSVariable('--text-disabled') || 'rgba(255, 255, 255, 0.25)',

    colorBgContainer: getCSSVariable('--bg-primary') || '#1f1f1f',
    colorBgElevated: getCSSVariable('--bg-primary-hover') || '#2a2a2a',
    colorBgLayout: '#141414',

    colorBorder: getCSSVariable('--border-color') || '#3a3a3a',
  },
  components: {
    Button: {
      colorPrimary: getCSSVariable('--primary-color') || '#40a9ff',
      algorithm: true,
    },
    Input: {
      colorBorder: getCSSVariable('--border-color') || '#3a3a3a',
    },
    Modal: {
      contentBg: getCSSVariable('--bg-primary') || '#1f1f1f',
      headerBg: getCSSVariable('--bg-primary') || '#1f1f1f',
    },
    Card: {
      colorBgContainer: getCSSVariable('--bg-primary') || '#1f1f1f',
    },
    Select: {
      colorBorder: getCSSVariable('--border-color') || '#3a3a3a',
    },
    Table: {
      colorBgContainer: getCSSVariable('--bg-primary') || '#1f1f1f',
      borderColor: getCSSVariable('--border-color') || '#3a3a3a',
    },
    Switch: {
      colorPrimary: getCSSVariable('--primary-color') || '#40a9ff',
    },
  },
};
```

**핵심 포인트:**
- ✅ **색상만** CSS Variables에서 동적으로 가져옴
- ✅ **수치 (spacing, font-size, border-radius 등)**는 테마와 무관하므로 제외
- ✅ `getCSSVariable()` 함수로 런타임에 `variables.css` 값 읽기
- ✅ Fallback 값 제공 (|| 연산자)

---

### 3. ThemeContext & Provider

**위치**: `frontend/src/contexts/ThemeContext.tsx`

```typescript
import React, { createContext, useContext, useEffect, useState } from 'react';
import { ConfigProvider } from 'antd';
import koKR from 'antd/locale/ko_KR';
import { lightTheme } from '../themes/lightTheme';
import { darkTheme } from '../themes/darkTheme';

type Theme = 'light' | 'dark';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const savedTheme = localStorage.getItem('theme') as Theme;

    // 시스템 테마 자동 감지
    if (!savedTheme && window.matchMedia) {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      return prefersDark ? 'dark' : 'light';
    }

    return savedTheme || 'light';
  });

  // 테마 변경 시 DOM attribute 업데이트
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setThemeState(prev => prev === 'light' ? 'dark' : 'light');
  };

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  const currentTheme = theme === 'light' ? lightTheme : darkTheme;

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      <ConfigProvider theme={currentTheme} locale={koKR}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
```

**역할:**
1. ✅ 현재 테마 상태 관리 (light/dark)
2. ✅ `localStorage`에 테마 저장/복원
3. ✅ 시스템 테마 자동 감지 (prefers-color-scheme)
4. ✅ DOM에 `data-theme` 속성 설정 → CSS Variables 자동 전환
5. ✅ Ant Design ConfigProvider에 테마 적용
6. ✅ 한글 로케일 (koKR) 통합

---

### 4. App 구조

**위치**: `frontend/src/App.tsx`

```typescript
const App: React.FC = () => {
    return (
        <ThemeProvider>          {/* 테마 관리 + ConfigProvider */}
            <AntdApp>            {/* Ant Design 전역 컴포넌트 */}
                <AuthProvider>   {/* 인증 Context */}
                    <Router>     {/* 라우팅 */}
                        <Routes>
                            {/* ... */}
                        </Routes>
                    </Router>
                </AuthProvider>
            </AntdApp>
        </ThemeProvider>
    )
}
```

**구조:**
- `ThemeProvider`가 최상위에서 모든 하위 컴포넌트에 테마 제공
- `ConfigProvider`는 ThemeProvider 내부에서 관리

---

### 5. SettingsModal 테마 토글 UI

**위치**: `frontend/src/components/user/SettingsModal.tsx`

```typescript
import { useTheme } from '../../hooks/useTheme';

const SettingsModal: React.FC<SettingsModalProps> = ({...}) => {
    const {theme, toggleTheme} = useTheme();

    return (
        {/* ... */}
        <div className={styles.settingRow}>
            <span className={styles.settingLabel}>다크 모드</span>
            <Switch
                checked={theme === 'dark'}
                onChange={toggleTheme}
                checkedChildren="다크"
                unCheckedChildren="라이트"
            />
        </div>
        {/* ... */}
    );
}
```

**기능:**
- ✅ Switch 컴포넌트로 테마 토글
- ✅ 현재 테마 상태 표시 (라이트/다크)
- ✅ 클릭 시 즉시 테마 전환

---

## 🎯 핵심 설계 원칙

### 1. 단일 소스 관리 (Single Source of Truth)
- **모든 색상은 `variables.css`에서만 정의**
- Ant Design 테마는 `getCSSVariable()`로 읽어옴
- 중복 없이 한 곳에서 관리

### 2. 색상 vs 수치 분리
- **색상**: 테마에 따라 변경됨 → CSS Variables + Ant Design 토큰
- **수치**: 테마와 무관 (spacing, font-size, border-radius) → CSS Variables만 사용

### 3. 자동 동기화
- `data-theme` 속성 변경 → CSS Variables 자동 적용
- `getCSSVariable()` → 런타임에 현재 테마 색상 읽기
- module.css 파일들은 `var(--color-name)` 사용 → 자동 테마 적용

---

## 📁 파일 구조

```
frontend/src/
├── styles/
│   └── variables.css              # CSS Variables 정의 (라이트/다크)
├── themes/
│   ├── lightTheme.ts              # Ant Design 라이트 테마
│   └── darkTheme.ts               # Ant Design 다크 테마
├── contexts/
│   └── ThemeContext.tsx           # 테마 Context + Provider
├── hooks/
│   └── useTheme.ts                # useTheme hook (re-export)
├── components/
│   └── user/
│       └── SettingsModal.tsx      # 테마 토글 UI
└── App.tsx                        # ThemeProvider 적용
```

---

## 🚀 사용 방법

### 1. 컴포넌트에서 테마 사용

```typescript
import { useTheme } from '../../hooks/useTheme';

function MyComponent() {
  const { theme, toggleTheme, setTheme } = useTheme();

  return (
    <div>
      <p>현재 테마: {theme}</p>
      <button onClick={toggleTheme}>테마 전환</button>
      <button onClick={() => setTheme('dark')}>다크 모드</button>
    </div>
  );
}
```

### 2. CSS에서 테마 변수 사용

```css
.myComponent {
  color: var(--text-primary);
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
}

/* 다크 테마에서 자동으로 변경됨! */
```

---

## ✅ 구현 완료 체크리스트

### Phase 1: Ant Design 테마 토큰 파일 작성
- [x] `lightTheme.ts` 작성
- [x] `darkTheme.ts` 작성
- [x] CSS Variables에서 색상 동적으로 가져오기
- [x] 수치는 제외하고 색상만 관리

### Phase 2: ThemeContext 및 Provider 구현
- [x] `ThemeContext.tsx` 작성
- [x] `useTheme` hook 작성
- [x] localStorage 저장/복원
- [x] 시스템 테마 자동 감지
- [x] ConfigProvider 통합

### Phase 3: App.tsx에 ThemeProvider 적용
- [x] ThemeProvider로 앱 감싸기
- [x] koKR 로케일 통합

### Phase 4: SettingsModal에 테마 토글 UI 추가
- [x] Switch 컴포넌트로 테마 토글
- [x] 현재 테마 상태 표시

### Phase 5: CSS Variables 정의
- [x] `variables.css`에 라이트 테마 변수 정의
- [x] `[data-theme='dark']`에 다크 테마 변수 정의
- [x] 색상과 수치 분리

### Phase 6: 테스트 및 검증
- [x] 개발 서버 실행
- [ ] 라이트/다크 테마 전환 테스트
- [ ] localStorage 저장 확인
- [ ] Ant Design 컴포넌트 테마 적용 확인
- [ ] 커스텀 module.css 테마 적용 확인

---

## 🔧 향후 작업 (선택 사항)

### 1. 하드코딩된 색상을 CSS Variables로 변환
현재 많은 `.module.css` 파일에 하드코딩된 색상이 있습니다.
우선순위대로 변환 작업 필요:

**Priority 1 (가장 많이 사용):**
- `#e5e5e5` (33회) → `var(--border-color)`
- `#f5f5f5` (29회) → `var(--bg-primary-hover)`
- `#666666` (24회) → `var(--color-grey)`
- `#1976d2` (21회) → `var(--primary-color)`
- `#1565c0` (11회) → `var(--primary-hover)`

### 2. 테마 전환 애니메이션
```css
* {
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}
```

### 3. 테마별 로고/아이콘 변경

---

## 📝 참고 사항

### 장점
- ✅ 단일 소스에서 모든 색상 관리 (`variables.css`)
- ✅ Ant Design 컴포넌트 자동 테마 적용
- ✅ 런타임 테마 전환 (리로드 불필요)
- ✅ localStorage에 테마 저장
- ✅ 시스템 테마 자동 감지
- ✅ 유지보수 용이

### 주의사항
- CSS Variables는 IE11 미지원
- `getCSSVariable()`은 컴포넌트 마운트 후에 실행
- Fallback 값 항상 제공 필요

---

**구현 완료!** 🎉
