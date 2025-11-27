import type { ThemeConfig } from 'antd';

// CSS Variables에서 색상만 가져오기
const getCSSVariable = (name: string): string => {
  if (typeof window !== 'undefined') {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  return '';
};

export const lightTheme: ThemeConfig = {
  token: {
    // Primary Colors - variables.css에서 가져옴
    colorPrimary: getCSSVariable('--primary-color') || '#1890ff',
    colorSuccess: getCSSVariable('--success-color') || '#52c41a',
    colorWarning: getCSSVariable('--warning-color') || '#faad14',
    colorError: getCSSVariable('--error-color') || '#ff4d4f',
    colorInfo: getCSSVariable('--info-color') || '#1890ff',

    // Text Colors
    colorText: getCSSVariable('--text-primary') || 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: getCSSVariable('--text-secondary') || '#1a1a1a',
    colorTextTertiary: getCSSVariable('--color-grey') || '#666666',
    colorTextQuaternary: getCSSVariable('--text-disabled') || 'rgba(0, 0, 0, 0.25)',

    // Background Colors
    colorBgContainer: getCSSVariable('--bg-primary') || '#ffffff',
    colorBgElevated: getCSSVariable('--color-white') || '#ffffff',
    colorBgLayout: getCSSVariable('--bg-primary-hover') || '#f5f5f5',

    // Border Colors
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
