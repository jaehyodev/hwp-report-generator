import type { ThemeConfig } from 'antd';
import { theme } from 'antd';

// CSS Variables에서 색상만 가져오기 (다크 테마)
const getCSSVariable = (name: string): string => {
  if (typeof window !== 'undefined') {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  return '';
};

export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,

  token: {
    // Primary Colors - variables.css [data-theme='dark']에서 가져옴
    colorPrimary: getCSSVariable('--primary-color') || '#40a9ff',
    colorSuccess: getCSSVariable('--success-color') || '#73d13d',
    colorWarning: getCSSVariable('--warning-color') || '#ffc53d',
    colorError: getCSSVariable('--error-color') || '#ff7875',
    colorInfo: getCSSVariable('--info-color') || '#40a9ff',

    // Text Colors
    colorText: getCSSVariable('--text-primary') || 'rgba(255, 255, 255, 0.85)',
    colorTextSecondary: getCSSVariable('--text-secondary') || 'rgba(255, 255, 255, 0.65)',
    colorTextTertiary: getCSSVariable('--color-grey') || 'rgba(255, 255, 255, 0.45)',
    colorTextQuaternary: getCSSVariable('--text-disabled') || 'rgba(255, 255, 255, 0.25)',

    // Background Colors
    colorBgContainer: getCSSVariable('--bg-primary') || '#1f1f1f',
    colorBgElevated: getCSSVariable('--bg-primary-hover') || '#2a2a2a',
    colorBgLayout: '#141414', // 레이아웃 배경은 더 어둡게

    // Border Colors
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
