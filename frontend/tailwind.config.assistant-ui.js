/**
 * Tailwind CSS 配置 - assistant-ui 集成版本
 * 运行: 将此内容合并到 tailwind.config.js
 */

import assistantUI from '@assistant-ui/react/tailwind-plugin'

export default {
  darkMode: ['class'],
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './node_modules/@assistant-ui/react/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ========== 颜色扩展 ==========
      colors: {
        // 主色调
        primary: {
          DEFAULT: 'hsl(var(--color-primary))',
          hover: 'hsl(var(--color-primary-hover))',
          light: 'hsl(var(--color-primary-light))',
          foreground: 'hsl(var(--color-primary-foreground))',
        },

        // 强调色
        accent: {
          DEFAULT: 'hsl(var(--color-accent))',
          hover: 'hsl(var(--color-accent-hover))',
          foreground: 'hsl(var(--color-accent-foreground))',
        },

        // 背景色
        background: {
          base: 'hsl(var(--color-bg-base))',
          alt: 'hsl(var(--color-bg-alt))',
          muted: 'hsl(var(--color-bg-muted))',
          card: 'hsl(var(--color-bg-card))',
          elevated: 'hsl(var(--color-bg-elevated))',
          overlay: 'hsl(var(--color-bg-overlay))',
        },

        // 边框色
        border: {
          DEFAULT: 'hsl(var(--color-border-base))',
          muted: 'hsl(var(--color-border-muted))',
          strong: 'hsl(var(--color-border-strong))',
          focus: 'hsl(var(--color-border-focus))',
        },

        // 文本色
        text: {
          primary: 'hsl(var(--color-text-primary))',
          secondary: 'hsl(var(--color-text-secondary))',
          muted: 'hsl(var(--color-text-muted))',
          disabled: 'hsl(var(--color-text-disabled))',
          inverse: 'hsl(var(--color-text-inverse))',
        },

        // 语义色
        success: {
          DEFAULT: 'hsl(var(--color-success))',
          foreground: 'hsl(var(--color-success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--color-warning))',
          foreground: 'hsl(var(--color-warning-foreground))',
        },
        error: {
          DEFAULT: 'hsl(var(--color-error))',
          foreground: 'hsl(var(--color-error-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--color-info))',
          foreground: 'hsl(var(--color-info-foreground))',
        },

        // ReAct 链路色
        react: {
          thought: 'hsl(var(--color-react-thought))',
          toolCall: 'hsl(var(--color-react-tool-call))',
          toolResult: 'hsl(var(--color-react-tool-result))',
          final: 'hsl(var(--color-react-final))',
          interrupt: 'hsl(var(--color-react-interrupt))',
        },
      },

      // ========== 字体家族 ==========
      fontFamily: {
        sans: ['var(--font-family-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-family-mono)', 'monospace'],
      },

      // ========== 字体大小 ==========
      fontSize: {
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.875rem', { lineHeight: '1.25rem' }],
        base: ['1rem', { lineHeight: '1.5rem' }],
        lg: ['1.125rem', { lineHeight: '1.75rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },

      // ========== 字重 ==========
      fontWeight: {
        light: '300',
        normal: '400',
        medium: '500',
        semibold: '600',
        bold: '700',
      },

      // ========== 圆角 ==========
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        '3xl': 'var(--radius-3xl)',
        full: 'var(--radius-full)',
      },

      // ========== 阴影 ==========
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        'glow-primary': 'var(--shadow-glow-primary)',
        'glow-accent': 'var(--shadow-glow-accent)',
        'glow-danger': 'var(--shadow-glow-danger)',
        'glow-success': 'var(--shadow-glow-success)',
      },

      // ========== 动画时长 ==========
      transitionDuration: {
        fast: 'var(--duration-fast)',
        base: 'var(--duration-base)',
        slow: 'var(--duration-slow)',
        slower: 'var(--duration-slower)',
      },

      // ========== 动画缓动 ==========
      transitionTimingFunction: {
        out: 'var(--ease-out)',
        in: 'var(--ease-in)',
        'in-out': 'var(--ease-in-out)',
        spring: 'var(--ease-spring)',
        bounce: 'var(--ease-bounce)',
      },

      // ========== 关键帧动画 ==========
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'shimmer': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
      },

      // ========== 动画组合 ==========
      animation: {
        'fade-in': 'fade-in var(--duration-base) var(--ease-out)',
        'slide-up': 'slide-up var(--duration-slow) var(--ease-out)',
        'slide-down': 'slide-down var(--duration-slow) var(--ease-out)',
        'scale-in': 'scale-in var(--duration-base) var(--ease-spring)',
        'shimmer': 'shimmer 2s linear infinite',
        'pulse-subtle': 'pulse-subtle 2s ease-in-out infinite',
      },

      // ========== Z-Index ==========
      zIndex: {
        dropdown: 'var(--z-dropdown)',
        sticky: 'var(--z-sticky)',
        fixed: 'var(--z-fixed)',
        'modal-backdrop': 'var(--z-modal-backdrop)',
        modal: 'var(--z-modal)',
        popover: 'var(--z-popover)',
        tooltip: 'var(--z-tooltip)',
      },
    },
  },

  plugins: [
    assistantUI(),
    // ... 其他插件
  ],
}
