# Home Page Style Override

> Multi-Tool AI Agent 主页专用样式规范
> 参考 Linear.app 美学 + shadcn/ui 组件系统

---

## 设计理念

**核心风格**: Linear.app 风格的现代专业界面
- **关键词**: minimal, precision, technical, premium, developer-focused
- **视觉特征**: 深色背景、微妙渐变、精细阴影、流畅动画
- **参考产品**: Linear.app, Vercel Dashboard, Raycast

---

## 颜色系统

### Light Mode (浅色模式)

```css
:root {
  /* Primary - 主色调 */
  --color-primary: #5E6AD2;           /* Linear Purple */
  --color-primary-hover: #4F5BC4;
  --color-primary-light: rgba(94, 106, 210, 0.1);

  /* Secondary - 次要色 */
  --color-secondary: #6366F1;          /* Indigo 500 */
  --color-secondary-hover: #4F46E5;

  /* Accent - 强调色 */
  --color-accent: #22C55E;             /* Success Green */
  --color-accent-hover: #16A34A;
  --color-warning: #F59E0B;            /* Amber */
  --color-danger: #EF4444;             /* Red */
  --color-info: #3B82F6;               /* Blue */

  /* Background - 背景色 */
  --color-bg-base: #FFFFFF;            /* 纯白背景 */
  --color-bg-alt: #F8FAFC;             /* Slate 50 */
  --color-bg-muted: #F1F5F9;           /* Slate 100 */
  --color-bg-card: #FFFFFF;            /* 卡片背景 */
  --color-bg-overlay: rgba(0, 0, 0, 0.5); /* 遮罩 */

  /* Border - 边框色 */
  --color-border-base: #E2E8F0;        /* Slate 200 */
  --color-border-muted: #F1F5F9;       /* Slate 100 */
  --color-border-strong: #CBD5E1;      /* Slate 300 */

  /* Text - 文本色 */
  --color-text-primary: #0F172A;       /* Slate 900 */
  --color-text-secondary: #475569;     /* Slate 600 */
  --color-text-muted: #94A3B8;         /* Slate 400 */
  --color-text-disabled: #CBD5E1;      /* Slate 300 */
  --color-text-inverse: #FFFFFF;

  /* Semantic - 语义色 */
  --color-success-bg: #DCFCE7;          /* Green 100 */
  --color-success-text: #15803D;       /* Green 700 */
  --color-warning-bg: #FEF3C7;          /* Amber 100 */
  --color-warning-text: #A16207;       /* Amber 700 */
  --color-error-bg: #FEE2E2;            /* Red 100 */
  --color-error-text: #B91C1C;          /* Red 700 */
  --color-info-bg: #DBEAFE;             /* Blue 100 */
  --color-info-text: #1D4ED8;           /* Blue 700 */
}
```

### Dark Mode (深色模式) - 推荐

```css
.dark {
  /* Primary - 主色调 */
  --color-primary: #6366F1;           /* Indigo 500 */
  --color-primary-hover: #818CF8;
  --color-primary-light: rgba(99, 102, 241, 0.15);

  /* Secondary */
  --color-secondary: #8B5CF6;          /* Violet 500 */
  --color-secondary-hover: #A78BFA;

  /* Accent */
  --color-accent: #22C55E;             /* Success Green */
  --color-accent-hover: #4ADE80;
  --color-warning: #F59E0B;
  --color-danger: #EF4444;
  --color-info: #3B82F6;

  /* Background - Linear.app 深色系统 */
  --color-bg-base: #0A0A0F;            /* 深黑底色 */
  --color-bg-alt: #0F1014;             /* 次级背景 */
  --color-bg-muted: #15161A;           /* 弱化背景 */
  --color-bg-card: #1A1B1E;            /* 卡片背景 */
  --color-bg-elevated: #222328;        /* 悬浮元素 */
  --color-bg-overlay: rgba(0, 0, 0, 0.7);

  /* Border */
  --color-border-base: rgba(255, 255, 255, 0.08);  /* 微弱边框 */
  --color-border-muted: rgba(255, 255, 255, 0.05);
  --color-border-strong: rgba(255, 255, 255, 0.15);

  /* Text */
  --color-text-primary: #EDEDEF;        /* 主文本 */
  --color-text-secondary: #A1A1AA;     /* 次要文本 */
  --color-text-muted: #71717A;         /* 弱化文本 */
  --color-text-disabled: #52525B;      /* 禁用文本 */
  --color-text-inverse: #0A0A0F;

  /* Glow Effects - 微妙发光 */
  --glow-primary: 0 0 20px rgba(99, 102, 241, 0.3);
  --glow-accent: 0 0 20px rgba(34, 197, 94, 0.3);
  --glow-danger: 0 0 20px rgba(239, 68, 68, 0.3);
}
```

### ReAct 链路颜色（需求文档指定）

```css
/* ReAct Trace Step Colors */
--react-thought: #A78BFA;              /* Purple - 思考 */
--react-tool-call: #3B82F6;            /* Blue - 工具调用 */
--react-tool-result: #14B8A6;         /* Teal - 工具结果 */
--react-final: #22C55E;                /* Green - 最终答案 */
--react-interrupt: #F59E0B;            /* Amber - 人工介入 */
```

---

## 排版系统

### 字体家族

```css
/* 主字体: Inter */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

--font-family-base: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-family-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
```

### 字体大小

```css
--text-xs: 0.75rem;      /* 12px */
--text-sm: 0.875rem;     /* 14px */
--text-base: 1rem;       /* 16px */
--text-lg: 1.125rem;     /* 18px */
--text-xl: 1.25rem;      /* 20px */
--text-2xl: 1.5rem;      /* 24px */
--text-3xl: 1.875rem;    /* 30px */
--text-4xl: 2.25rem;     /* 36px */
```

### 字重

```css
--font-light: 300;
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### 行高

```css
--leading-tight: 1.25;
--leading-normal: 1.5;
--leading-relaxed: 1.625;
```

---

## 间距系统

```css
--spacing-0: 0;
--spacing-px: 1px;
--spacing-0_5: 2px;
--spacing-1: 4px;
--spacing-1_5: 6px;
--spacing-2: 8px;
--spacing-2_5: 10px;
--spacing-3: 12px;
--spacing-3_5: 14px;
--spacing-4: 16px;
--spacing-5: 20px;
--spacing-6: 24px;
--spacing-8: 32px;
--spacing-10: 40px;
--spacing-12: 48px;
--spacing-16: 64px;
--spacing-20: 80px;
--spacing-24: 96px;
```

---

## 圆角系统

```css
--radius-none: 0;
--radius-sm: 4px;
--radius-md: 6px;
--radius-lg: 8px;
--radius-xl: 12px;
--radius-2xl: 16px;
--radius-3xl: 24px;
--radius-full: 9999px;
```

---

## 阴影系统

```css
/* Light Mode Shadows */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);

/* Dark Mode Shadows - 使用发光效果 */
.dark {
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4);

  /* Glow Effects */
  --glow-card: 0 0 0 1px rgba(255, 255, 255, 0.05);
  --glow-input: 0 0 0 2px rgba(99, 102, 241, 0.2);
  --glow-focus: 0 0 0 3px rgba(99, 102, 241, 0.3);
}
```

---

## 动画系统

### 缓动函数

```css
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);     /* Linear.app 风格 */
--ease-in: cubic-bezier(0.67, 0, 0.83, 0.67);
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
--ease-spring: cubic-bezier(0.16, 1, 0.3, 1);
```

### 时长

```css
--duration-fast: 150ms;
--duration-base: 200ms;
--duration-slow: 300ms;
--duration-slower: 500ms;
```

### Framer Motion 变体

```typescript
const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

const slideUp = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 },
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1 },
};

const staggerChildren = {
  visible: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};
```

---

## Z-Index 层级

```css
--z-dropdown: 1000;
--z-sticky: 1020;
--z-fixed: 1030;
--z-modal-backdrop: 1040;
--z-modal: 1050;
--z-popover: 1060;
--z-tooltip: 1070;
```

---

## 组件规范

### 按钮

**尺寸**:
- `sm`: padding 8px 16px, text-sm
- `md`: padding 12px 20px, text-base
- `lg`: padding 16px 24px, text-lg

**变体**:
- `primary`: 主色背景 + 白色文字
- `secondary`: 透明 + 主色边框
- `ghost`: 透明 + hover 背景
- `danger`: 红色背景 + 白色文字

**状态**:
- hover: transform translateY(-1px)
- active: transform translateY(0)
- disabled: opacity 0.5, cursor not-allowed

### 输入框

- Focus 时显示主色光环 (ring)
- Error 时显示红色边框
- 支持前缀/后缀图标

### 卡片

- 默认使用 `--color-bg-card`
- Hover 时轻微上浮 (translateY(-2px))
- 使用微妙边框 `--color-border-base`

### 徽章 (Badge)

- 状态徽章: 圆角 + 内边距
- 尺寸: text-xs + padding 2px 8px
- 颜色: 语义色背景 + 深色文字

---

## 响应式断点

```css
/* Mobile First */
--breakpoint-sm: 640px;    /* 小屏幕 */
--breakpoint-md: 768px;    /* 平板 */
--breakpoint-lg: 1024px;   /* 桌面 */
--breakpoint-xl: 1280px;   /* 大桌面 */
--breakpoint-2xl: 1536px;  /* 超大屏 */
```

---

## 禁止模式

- ❌ 使用 Emoji 作为图标（必须用 SVG/Heroicons/Lucide）
- ❌ 纯黑/纯白背景（使用微妙渐变）
- ❌ 瞬间状态变化（必须 150-300ms 过渡）
- ❌ 低对比度文本（最小 4.5:1）
- ❌ 无障碍焦点状态（必须可见）
- ❌ 布局偏移动画（使用 transform，不用 width/height）

---

## 实施优先级

### P0 - 立即执行
1. 替换所有 Emoji 为 SVG 图标
2. 实施深色模式颜色系统
3. 添加 shadcn/ui 组件
4. 实施基础间距和圆角系统

### P1 - 高优先级
1. 添加 Framer Motion 动画
2. 实施阴影和发光效果
3. 优化响应式布局
4. 添加微交互（hover, focus）

### P2 - 中优先级
1. 实施完整的 Token 预算可视化
2. 添加骨架屏加载状态
3. 优化动画性能
4. 添加触觉反馈（移动端）
