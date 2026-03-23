import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // 主色调
        primary: {
          DEFAULT: '#5E6AD2',
          hover: '#4F5BC4',
          light: 'rgba(94, 106, 210, 0.1)',
        },

        // 次要色
        secondary: {
          DEFAULT: '#6366F1',
          hover: '#818CF8',
        },

        // 强调色
        accent: {
          DEFAULT: '#22C55E',
          hover: '#16A34A',
        },
        warning: '#F59E0B',
        danger: '#EF4444',
        info: '#3B82F6',

        // 背景色（使用 CSS 变量）
        background: {
          base: 'var(--color-bg-base)',
          alt: 'var(--color-bg-alt)',
          muted: 'var(--color-bg-muted)',
          card: 'var(--color-bg-card)',
        },

        // 边框色
        border: {
          base: 'var(--color-border-base)',
          muted: 'var(--color-border-muted)',
          strong: 'var(--color-border-strong)',
        },

        // 文本色
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          muted: 'var(--color-text-muted)',
          disabled: 'var(--color-text-disabled)',
          inverse: 'var(--color-text-inverse)',
        },

        // ReAct 链路颜色
        react: {
          thought: 'var(--react-thought)',
          'tool-call': 'var(--react-tool-call)',
          'tool-result': 'var(--react-tool-result)',
          final: 'var(--react-final)',
          interrupt: 'var(--react-interrupt)',
        },
      },

      fontFamily: {
        sans: ['var(--font-family-base)', 'sans-serif'],
        mono: ['var(--font-family-mono)', 'monospace'],
      },

      fontSize: {
        xs: ['var(--text-xs)', '12px'],
        sm: ['var(--text-sm)', '14px'],
        base: ['var(--text-base)', '16px'],
        lg: ['var(--text-lg)', '18px'],
        xl: ['var(--text-xl)', '20px'],
        '2xl': ['var(--text-2xl)', '24px'],
        '3xl': ['var(--text-3xl)', '30px'],
        '4xl': ['var(--text-4xl)', '36px'],
      },

      fontWeight: {
        light: 'var(--font-light)',
        normal: 'var(--font-normal)',
        medium: 'var(--font-medium)',
        semibold: 'var(--font-semibold)',
        bold: 'var(--font-bold)',
      },

      borderRadius: {
        none: 'var(--radius-none)',
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        '3xl': 'var(--radius-3xl)',
        full: 'var(--radius-full)',
      },

      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
      },

      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'in-expo': 'cubic-bezier(0.67, 0, 0.83, 0.67)',
      },

      transitionDuration: {
        fast: '150ms',
        base: '200ms',
        slow: '300ms',
        slower: '500ms',
      },

      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 300ms ease-out',
        'scale-in': 'scaleIn 200ms ease-out',
        spin: 'spin 1s linear infinite',
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        spin: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
      },

      spacing: {
        0: 'var(--spacing-0)',
        px: 'var(--spacing-px)',
        0.5: 'var(--spacing-0_5)',
        1: 'var(--spacing-1)',
        1.5: 'var(--spacing-1_5)',
        2: 'var(--spacing-2)',
        2.5: 'var(--spacing-2_5)',
        3: 'var(--spacing-3)',
        3.5: 'var(--spacing-3_5)',
        4: 'var(--spacing-4)',
        5: 'var(--spacing-5)',
        6: 'var(--spacing-6)',
        8: 'var(--spacing-8)',
        10: 'var(--spacing-10)',
        12: 'var(--spacing-12)',
        16: 'var(--spacing-16)',
        20: 'var(--spacing-20)',
        24: 'var(--spacing-24)',
      },

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
  plugins: [],
};

export default config;
