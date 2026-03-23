# Multi-Tool AI Agent · 前端实施计划

**日期**: 2026-03-20
**状态**: 计划中
**版本**: v1.0
**预计工时**: 120-160 小时 (6-8 周)

---

## 目录

1. [项目结构设计](#项目结构设计)
2. [技术栈与依赖](#技术栈与依赖)
3. [Design Tokens 定义](#design-tokens-定义)
4. [实施路线图](#实施路线图)
5. [组件设计规范](#组件设计规范)
6. [SSE 连接管理](#sse-连接管理)
7. [状态管理策略](#状态管理策略)
8. [性能优化方案](#性能优化方案)

---

## 项目结构设计

### 完整目录结构

```
frontend/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # 根布局（字体、主题、Provider）
│   ├── page.tsx                  # 首页（会话列表/新建会话）
│   ├── globals.css               # 全局样式（Tailwind v4）
│   ├── chat/
│   │   ├── page.tsx              # 聊天页面主入口
│   │   └── layout.tsx            # 聊天页面布局
│   └── api/                      # API Routes (可选代理)
│       └── proxy/
│           └── route.ts          # 后端 API 代理
│
├── components/                   # React 组件
│   ├── layout/                   # 布局组件 (Phase 2)
│   │   ├── Header.tsx            # 顶部导航栏
│   │   ├── Sidebar.tsx           # 左侧会话/工具栏
│   │   ├── RightPanel.tsx        # 右侧可观测性面板
│   │   └── ChatArea.tsx          # 中间聊天区域
│   │
│   ├── timeline/                 # 时间轴组件 (Phase 4)
│   │   ├── Timeline.tsx          # 时间轴容器
│   │   ├── TimelineEvent.tsx     # 单个事件节点
│   │   ├── TokenBar.tsx          # Token 使用进度条
│   │   └── TimelineVirtual.tsx   # 虚拟滚动容器
│   │
│   ├── chat/                     # 聊天相关组件 (Phase 2)
│   │   ├── MessageList.tsx       # 消息列表
│   │   ├── MessageBubble.tsx     # 消息气泡
│   │   ├── InputArea.tsx         # 输入区域
│   │   └── TypingIndicator.tsx   # 输入指示器
│   │
│   ├── hil/                      # HIL 人工介入组件 (Phase 5)
│   │   ├── ConfirmModal.tsx      # 确认模态框
│   │   ├── RiskBadge.tsx         # 风险等级标识
│   │   └── ParameterViewer.tsx   # 参数展示器
│   │
│   ├── session/                  # 会话管理组件 (Phase 2)
│   │   ├── SessionList.tsx       # 会话列表
│   │   ├── SessionCard.tsx       # 会话卡片
│   │   └── NewSessionButton.tsx  # 新建会话按钮
│   │
│   └── ui/                       # 基础 UI 组件 (Phase 1)
│       ├── Button.tsx            # 按钮（Radix UI + Tailwind）
│       ├── Input.tsx             # 输入框
│       ├── Dialog.tsx            # 对话框
│       ├── Tabs.tsx              # 标签页
│       ├── ScrollArea.tsx        # 滚动区域
│       ├── Avatar.tsx            # 头像
│       └── Badge.tsx             # 徽章
│
├── lib/                          # 工具库
│   ├── sse-manager.ts            # SSE 连接管理器 (Phase 3)
│   ├── api.ts                    # API 客户端 (Phase 1)
│   ├── api/                      # API 模块
│   │   ├── sessions.ts           # 会话 API
│   │   ├── chat.ts               # 聊天 API
│   │   └── traces.ts             # 追踪 API
│   ├── tokens.ts                 # Design Tokens (Phase 1)
│   ├── cn.ts                     # clsx/cn 工具函数
│   └── utils.ts                  # 通用工具函数
│
├── stores/                       # Zustand 状态管理 (Phase 3)
│   ├── timeline.ts               # 时间轴状态
│   ├── session.ts                # 会话状态
│   ├── chat.ts                   # 聊天状态
│   └── index.ts                  # 统一导出
│
├── hooks/                        # 自定义 Hooks (Phase 3)
│   ├── useSSE.ts                 # SSE 连接 Hook
│   ├── useTimeline.ts            # 时间轴 Hook
│   ├── useSession.ts             # 会话 Hook
│   └── useTheme.ts               # 主题切换 Hook
│
├── types/                        # TypeScript 类型定义
│   ├── sse.ts                    # SSE 事件类型
│   ├── timeline.ts               # 时间轴类型
│   ├── session.ts                # 会话类型
│   ├── hil.ts                    # HIL 类型
│   └── api.ts                    # API 响应类型
│
├── styles/                       # 样式文件
│   └── globals.css               # 全局 CSS 变量
│
├── config/                       # 配置文件
│   └── site.ts                   # 站点配置（字体等）
│
└── public/                       # 静态资源
    └── fonts/                    # 字体文件
        └── PlusJakartaSans/
```

---

## 技术栈与依赖

### 核心依赖

| 包名 | 版本 | 用途 |
|-----|------|-----|
| `next` | `^15.0.0` | React 框架 |
| `react` | `^19.0.0` | UI 库 |
| `@radix-ui/*` | `latest` | 无障碍组件基座 |
| `tailwindcss` | `^4.0.0` | 样式系统 |
| `zustand` | `^5.0.0` | 状态管理 |
| `@tanstack/react-query` | `^5.0.0` | 服务器状态 |
| `@microsoft/fetch-event-source` | `^2.0.0` | SSE 客户端 |
| `@tanstack/react-virtual` | `^3.0.0` | 虚拟滚动 |
| `class-variance-authority` | `^0.7.0` | 样式变体管理 |
| `clsx` | `^2.0.0` | 条件类名 |
| `tailwind-merge` | `^2.0.0` | Tailwind 类名合并 |

### 开发依赖

| 包名 | 版本 | 用途 |
|-----|------|-----|
| `typescript` | `^5.0.0` | 类型系统 |
| `@types/node` | `latest` | Node 类型 |
| `eslint` | `latest` | 代码检查 |
| `prettier` | `latest` | 代码格式化 |
| `@tailwindcss/vite` | `^4.0.0` | Tailwind v4 集成 |

---

## Design Tokens 定义

### 完整 Design Tokens

```typescript
// lib/tokens.ts

/**
 * Design Tokens 定义
 * 从 pencil-new.pen 设计文件提取
 */

export const designTokens = {
  // ========== 颜色系统 ==========
  colors: {
    // 背景色
    bg: {
      primary: 'hsl(var(--bg-primary))',        // #E8EDF3 (light), #0B1221 (dark)
      secondary: 'hsl(var(--bg-secondary))',    // #F1F5F9, #111827
      tertiary: 'hsl(var(--bg-tertiary))',      // #FFFFFF, #1F2937
    },

    // 表面色
    surface: {
      default: 'hsl(var(--surface-default))',   // #FFFFFF, #111827
      muted: 'hsl(var(--surface-muted))',       // #F1F5F9, #1F2937
      elevated: 'hsl(var(--surface-elevated))', // #FFFFFF, #1F2937 (带阴影)
    },

    // 文字色
    text: {
      primary: 'hsl(var(--text-primary))',      // #1E293B, #F9FAFB
      secondary: 'hsl(var(--text-secondary))',  // #64748B, #9CA3AF
      tertiary: 'hsl(var(--text-tertiary))',    // #94A3B8, #6B7280
      inverse: 'hsl(var(--text-inverse))',      // #F9FAFB, #1E293B
    },

    // 主题色
    accent: {
      primary: 'hsl(var(--accent-primary))',    // #2563EB, #60A5FA
      secondary: 'hsl(var(--accent-secondary))',// #3B82F6, #3B82F6
      hover: 'hsl(var(--accent-hover))',        // #1D4ED8, #2563EB
    },

    // 边框色
    border: {
      default: 'hsl(var(--border-default))',    // #E2E8F0, #334155
      subtle: 'hsl(var(--border-subtle))',      // #F1F5F9, #1F2937
    },

    // 功能色
    functional: {
      success: '#10B981',   // 绿色
      warning: '#F59E0B',   // 黄色
      error: '#EF4444',     // 红色
      info: '#3B82F6',      // 蓝色
    },

    // 工具芯片色
    toolChip: {
      bg: 'hsl(var(--tool-chip-bg))',           // #DBEAFE, #1E3A8A
      text: 'hsl(var(--tool-chip-text))',       // #1E40AF, #93C5FD
    },

    // 标签页激活色
    tabActive: {
      bg: 'hsl(var(--tab-active-bg))',          // #EFF6FF, #1E40AF
      text: 'hsl(var(--tab-active-text))',      // #1E40AF, #DBEAFE
    },
  },

  // ========== 间距系统 ==========
  spacing: {
    xs: '4px',      // 0.25rem
    sm: '8px',      // 0.5rem
    md: '16px',     // 1rem
    lg: '24px',     // 1.5rem
    xl: '32px',     // 2rem
    '2xl': '48px',  // 3rem
    '3xl': '64px',  // 4rem
  },

  // ========== 圆角系统 ==========
  borderRadius: {
    sm: '4px',      // 小圆角（按钮、输入框）
    md: '8px',      // 中圆角（卡片）
    lg: '12px',     // 大圆角（对话框）
    xl: '16px',     // 超大圆角
    '2xl': '24px',  // 特大圆角
    full: '9999px', // 完全圆形（徽章、头像）
  },

  // ========== 字体系统 ==========
  typography: {
    fontFamily: {
      sans: 'Plus Jakarta Sans, system-ui, sans-serif',
      mono: 'JetBrains Mono, monospace',
    },

    fontSize: {
      xs: ['12px', { lineHeight: '16px' }],
      sm: ['14px', { lineHeight: '20px' }],
      base: ['16px', { lineHeight: '24px' }],
      lg: ['18px', { lineHeight: '28px' }],
      xl: ['20px', { lineHeight: '28px' }],
      '2xl': ['24px', { lineHeight: '32px' }],
      '3xl': ['30px', { lineHeight: '38px' }],
      '4xl': ['36px', { lineHeight: '44px' }],
    },

    fontWeight: {
      normal: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
    },
  },

  // ========== 阴影系统 ==========
  shadow: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  },

  // ========== 动画 ==========
  animation: {
    duration: {
      fast: '150ms',
      base: '200ms',
      slow: '300ms',
    },
    easing: {
      default: 'cubic-bezier(0.4, 0, 0.2, 1)',
      in: 'cubic-bezier(0.4, 0, 1, 1)',
      out: 'cubic-bezier(0, 0, 0.2, 1)',
    },
  },

  // ========== 布局尺寸 ==========
  layout: {
    header: { height: '56px' },
    sidebar: { width: '272px', minWidth: '200px', maxWidth: '400px' },
    rightPanel: { width: '320px', minWidth: '280px', maxWidth: '480px' },
    chat: { minWidth: '400px' },
  },

  // ========== Z-index 层级 ==========
  zIndex: {
    base: 0,
    dropdown: 10,
    sticky: 20,
    overlay: 40,
    modal: 50,
    tooltip: 60,
  },
} as const;

export type DesignTokens = typeof designTokens;
```

### CSS 变量定义

```css
/* app/globals.css - Tailwind v4 CSS 变量 */

@theme {
  /* 颜色 - Light 模式 */
  --color-bg-primary: 232 237 243;      /* #E8EDF3 */
  --color-bg-secondary: 241 245 249;    /* #F1F5F9 */
  --color-bg-tertiary: 255 255 255;     /* #FFFFFF */

  --color-surface-default: 255 255 255;
  --color-surface-muted: 241 245 249;
  --color-surface-elevated: 255 255 255;

  --color-text-primary: 30 41 59;       /* #1E293B */
  --color-text-secondary: 100 116 139;  /* #64748B */
  --color-text-tertiary: 148 163 184;   /* #94A3B8 */
  --color-text-inverse: 249 250 251;    /* #F9FAFB */

  --color-accent-primary: 37 99 235;    /* #2563EB */
  --color-accent-secondary: 59 130 246; /* #3B82F6 */
  --color-accent-hover: 29 78 216;      /* #1D4ED8 */

  --color-border-default: 226 232 240;  /* #E2E8F0 */
  --color-border-subtle: 241 245 249;   /* #F1F5F9 */

  --color-tool-chip-bg: 219 234 254;    /* #DBEAFE */
  --color-tool-chip-text: 30 64 175;    /* #1E40AF */

  --color-tab-active-bg: 239 246 255;   /* #EFF6FF */
  --color-tab-active-text: 30 64 175;   /* #1E40AF */
}

@layer base {
  :root {
    --bg-primary: var(--color-bg-primary);
    --bg-secondary: var(--color-bg-secondary);
    --bg-tertiary: var(--color-bg-tertiary);

    --surface-default: var(--color-surface-default);
    --surface-muted: var(--color-surface-muted);
    --surface-elevated: var(--color-surface-elevated);

    --text-primary: var(--color-text-primary);
    --text-secondary: var(--color-text-secondary);
    --text-tertiary: var(--color-text-tertiary);
    --text-inverse: var(--color-text-inverse);

    --accent-primary: var(--color-accent-primary);
    --accent-secondary: var(--color-accent-secondary);
    --accent-hover: var(--color-accent-hover);

    --border-default: var(--color-border-default);
    --border-subtle: var(--color-border-subtle);

    --tool-chip-bg: var(--color-tool-chip-bg);
    --tool-chip-text: var(--color-tool-chip-text);

    --tab-active-bg: var(--color-tab-active-bg);
    --tab-active-text: var(--color-tab-active-text);
  }

  /* Dark 模式 */
  .dark {
    --color-bg-primary: 11 18 33;        /* #0B1221 */
    --color-bg-secondary: 17 24 39;      /* #111827 */
    --color-bg-tertiary: 31 41 55;       /* #1F2937 */

    --color-surface-default: 17 24 39;
    --color-surface-muted: 31 41 55;
    --color-surface-elevated: 31 41 55;

    --color-text-primary: 249 250 251;
    --color-text-secondary: 156 163 175;
    --color-text-tertiary: 107 114 128;
    --color-text-inverse: 30 41 59;

    --color-accent-primary: 96 165 250;  /* #60A5FA */
    --color-accent-secondary: 59 130 246;
    --color-accent-hover: 37 99 235;

    --color-border-default: 51 65 85;    /* #334155 */
    --color-border-subtle: 31 41 55;

    --color-tool-chip-bg: 30 58 138;     /* #1E3A8A */
    --color-tool-chip-text: 147 197 253; /* #93C5FD */

    --color-tab-active-bg: 30 64 111;    /* #1E40AF */
    --color-tab-active-text: 219 234 254;
  }
}

@layer base {
  * {
    @apply border-[color:var(--border-default)];
  }

  body {
    @apply bg-[color:var(--bg-primary)] text-[color:var(--text-primary)];
    font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
}
```

---

## 实施路线图

### Phase 1: 项目脚手架 (Week 1) 🔴 P0

**目标**: 搭建 Next.js 15 项目基础，配置开发环境

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 1.1 初始化 Next.js 15 项目 | 2h | - |
| 1.2 配置 Tailwind CSS v4 | 2h | 1.1 |
| 1.3 安装 Radix UI 组件 | 2h | 1.1 |
| 1.4 配置 TypeScript 和 ESLint | 2h | 1.1 |
| 1.5 创建 Design Tokens 系统 | 4h | 1.2 |
| 1.6 配置字体 (Plus Jakarta Sans) | 1h | - |
| 1.7 创建基础 UI 组件库 | 6h | 1.2, 1.3 |
| 1.8 设置主题切换功能 | 3h | 1.5 |

**小计**: 22 小时

**交付物**:
- 可运行的 Next.js 项目
- Design Tokens 完整定义
- 基础 UI 组件（Button, Input, Dialog, Tabs, ScrollArea, Avatar, Badge）
- 主题切换功能

---

### Phase 2: 布局结构 (Week 2) 🔴 P0

**目标**: 实现三栏布局和基础聊天界面

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 2.1 创建 Header 组件 | 3h | Phase 1 |
| 2.2 创建 Sidebar 组件 | 4h | Phase 1 |
| 2.3 创建 RightPanel 组件 | 4h | Phase 1 |
| 2.4 创建 ChatArea 组件 | 5h | Phase 1 |
| 2.5 实现会话列表功能 | 6h | 2.2 |
| 2.6 实现消息气泡组件 | 4h | 2.4 |
| 2.7 实现输入区域 | 5h | 2.4 |
| 2.8 响应式布局适配 | 4h | 2.1-2.4 |

**小计**: 35 小时

**交付物**:
- 完整的三栏布局
- 会话列表展示
- 消息输入和显示
- 响应式设计

---

### Phase 3: SSE 连接管理 (Week 3) 🔴 P0

**目标**: 实现稳定的 SSE 连接和状态管理

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 3.1 实现 SSE Manager | 8h | - |
| 3.2 配置 Zustand stores | 4h | - |
| 3.3 创建 useSSE Hook | 4h | 3.1, 3.2 |
| 3.4 实现指数退避重连 | 4h | 3.1 |
| 3.5 事件序列检测 | 3h | 3.1 |
| 3.6 连接状态 UI 指示 | 2h | 3.3 |
| 3.7 错误处理和恢复 | 3h | 3.4 |

**小计**: 28 小时

**交付物**:
- SSE 连接管理器
- Zustand 状态存储
- 自动重连机制
- 连接状态可视化

---

### Phase 4: 时间轴可视化 (Week 4-5) 🟡 P1

**目标**: 实现 Agent 推理链时间轴展示

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 4.1 设计 TimelineEvent 数据结构 | 2h | Phase 3 |
| 4.2 创建 Timeline 容器组件 | 4h | Phase 3 |
| 4.3 创建 TimelineEvent 节点组件 | 6h | 4.2 |
| 4.4 实现虚拟滚动 | 8h | 4.2 |
| 4.5 添加脉冲动画效果 | 3h | 4.3 |
| 4.6 实现 Token 进度条 | 3h | Phase 3 |
| 4.7 事件折叠/展开功能 | 4h | 4.3 |
| 4.8 时间轴搜索/过滤 | 4h | 4.2 |

**小计**: 34 小时

**交付物**:
- 时间轴可视化组件
- 虚拟滚动支持
- Token 使用进度条
- 事件交互功能

---

### Phase 5: HIL 确认模态框 (Week 5) 🟡 P1

**目标**: 实现人工介入确认机制

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 5.1 设计 HIL 数据结构 | 2h | - |
| 5.2 创建 ConfirmModal 组件 | 6h | Phase 1 |
| 5.3 实现 RiskBadge 组件 | 2h | Phase 1 |
| 5.4 创建 ParameterViewer | 4h | Phase 1 |
| 5.5 集成 HIL 事件处理 | 4h | Phase 3 |
| 5.6 添加超时处理 | 2h | 5.2 |
| 5.7 实现操作历史记录 | 4h | 5.5 |

**小计**: 24 小时

**交付物**:
- HIL 确认模态框
- 风险等级标识
- 参数展示器
- 操作历史

---

### Phase 6: 状态管理优化 (Week 6) 🟡 P1

**目标**: 集成 React Query 优化服务器状态

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 6.1 配置 React Query | 2h | - |
| 6.2 创建会话 API hooks | 4h | 6.1 |
| 6.3 创建追踪 API hooks | 3h | 6.1 |
| 6.4 实现缓存策略 | 4h | 6.1 |
| 6.5 添加乐观更新 | 4h | 6.2 |
| 6.6 实现自动刷新 | 2h | 6.1 |

**小计**: 19 小时

**交付物**:
- React Query 集成
- API hooks 库
- 缓存策略
- 乐观更新

---

### Phase 7: UI 完善与动画 (Week 7) ⚪ P2

**目标**: 完善 UI 细节和添加动画效果

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 7.1 添加页面过渡动画 | 4h | - |
| 7.2 优化滚动体验 | 3h | Phase 4 |
| 7.3 添加加载骨架屏 | 4h | Phase 1 |
| 7.4 实现工具提示 | 3h | Phase 1 |
| 7.5 优化移动端体验 | 6h | Phase 2 |
| 7.6 添加键盘快捷键 | 4h | - |

**小计**: 24 小时

**交付物**:
- 过渡动画
- 骨架屏
- 工具提示
- 移动端优化
- 键盘快捷键

---

### Phase 8: 测试与优化 (Week 8) ⚪ P2

**目标**: 测试覆盖和性能优化

| 任务 | 预计工时 | 依赖 |
|-----|---------|-----|
| 8.1 编写组件单元测试 | 8h | - |
| 8.2 编写集成测试 | 6h | - |
| 8.3 性能分析和优化 | 6h | - |
| 8.4 Lighthouse 评分优化 | 4h | - |
| 8.5 无障碍性审计 | 4h | - |

**小计**: 28 小时

**交付物**:
- 单元测试覆盖
- 集成测试
- 性能优化报告
- Lighthouse 评分 > 90

---

## 组件设计规范

### 1. Button 组件

```typescript
// components/ui/Button.tsx
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-[color:var(--accent-primary)] text-white hover:bg-[color:var(--accent-hover)]',
        secondary: 'bg-[color:var(--surface-muted)] text-[color:var(--text-primary)] hover:bg-[color:var(--border-default)]',
        ghost: 'hover:bg-[color:var(--surface-muted)]',
        danger: 'bg-red-600 text-white hover:bg-red-700',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-base',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = ({ className, variant, size, ...props }: ButtonProps) => {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
};
```

### 2. TimelineEvent 组件

```typescript
// components/timeline/TimelineEvent.tsx
import { designTokens } from '@/lib/tokens';
import type { TimelineEvent as TimelineEventType } from '@/types/timeline';

interface TimelineEventProps {
  event: TimelineEventType;
  isActive: boolean;
}

export function TimelineEvent({ event, isActive }: TimelineEventProps) {
  const statusColors = {
    pending: 'text-gray-400',
    active: 'text-blue-500 animate-pulse',
    done: 'text-green-500',
    error: 'text-red-500',
  };

  return (
    <div
      className={cn(
        'flex gap-3 p-3 rounded-lg transition-all',
        isActive && 'bg-[color:var(--surface-muted)]'
      )}
    >
      {/* 状态指示器 */}
      <div className={cn('flex-shrink-0', statusColors[event.status])}>
        {event.status === 'active' ? (
          <LoadingIcon className="w-4 h-4" />
        ) : event.status === 'done' ? (
          <CheckIcon className="w-4 h-4" />
        ) : event.status === 'error' ? (
          <ErrorIcon className="w-4 h-4" />
        ) : (
          <CircleIcon className="w-4 h-4" />
        )}
      </div>

      {/* 内容 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-[color:var(--text-primary)]">
            {event.step}. {event.title}
          </span>
          {event.focus && (
            <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700">
              Focus
            </span>
          )}
        </div>

        {event.description && (
          <p className="text-sm text-[color:var(--text-secondary)] mt-1">
            {event.description}
          </p>
        )}

        {event.metadata?.toolName && (
          <div className="mt-2 px-2 py-1 text-xs rounded bg-[color:var(--tool-chip-bg)] text-[color:var(--tool-chip-text)]">
            {event.metadata.toolName}
          </div>
        )}

        {event.children && event.children.length > 0 && (
          <div className="mt-3 ml-4 space-y-2">
            {event.children.map((child) => (
              <TimelineEvent
                key={child.id}
                event={child}
                isActive={child.status === 'active'}
              />
            ))}
          </div>
        )}
      </div>

      {/* 时间戳 */}
      {event.timestamp && (
        <span className="text-xs text-[color:var(--text-tertiary)] flex-shrink-0">
          {formatTimestamp(event.timestamp)}
        </span>
      )}
    </div>
  );
}
```

### 3. HIL ConfirmModal 组件

```typescript
// components/hil/ConfirmModal.tsx
import * as Dialog from '@radix-ui/react-dialog';
import { designTokens } from '@/lib/tokens';
import type { HILConfirmData } from '@/types/hil';
import { RiskBadge } from './RiskBadge';
import { ParameterViewer } from './ParameterViewer';
import { Button } from '@/components/ui/Button';

interface ConfirmModalProps {
  data: HILConfirmData;
  onConfirm: () => void;
  onReject: () => void;
  timeout?: number;
}

export function ConfirmModal({ data, onConfirm, onReject, timeout = 30000 }: ConfirmModalProps) {
  const [timeLeft, setTimeLeft] = React.useState(timeout / 1000);

  React.useEffect(() => {
    if (timeLeft <= 0) {
      onReject();
      return;
    }
    const timer = setTimeout(() => setTimeLeft(timeLeft - 1), 1000);
    return () => clearTimeout(timer);
  }, [timeLeft, onReject]);

  return (
    <Dialog.Root open={true}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[color:var(--surface-default)] rounded-xl shadow-lg p-6 z-50">
          {/* 标题 */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-100 text-amber-600">
                <AlertTriangleIcon className="w-5 h-5" />
              </div>
              <div>
                <Dialog.Title className="text-lg font-semibold text-[color:var(--text-primary)]">
                  需要确认操作
                </Dialog.Title>
                <RiskBadge risk={data.risk} />
              </div>
            </div>
            <span className="text-sm text-[color:var(--text-secondary)]">
              {timeLeft}s
            </span>
          </div>

          {/* 工具信息 */}
          <div className="mb-4 p-3 rounded-lg bg-[color:var(--surface-muted)]">
            <span className="text-sm font-medium text-[color:var(--text-primary)]">
              {data.toolName}
            </span>
          </div>

          {/* 参数展示 */}
          <ParameterViewer args={data.args} />

          {/* 预估成本 */}
          {data.estimatedCost && (
            <div className="mt-4 text-sm text-[color:var(--text-secondary)]">
              预估成本: {data.estimatedCost}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-3 mt-6">
            <Button variant="secondary" onClick={onReject} className="flex-1">
              拒绝
            </Button>
            <Button variant="primary" onClick={onConfirm} className="flex-1">
              确认执行
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

---

## SSE 连接管理

### SSE Manager 实现

```typescript
// lib/sse-manager.ts
import { fetchEventSource } from '@microsoft/fetch-event-source';

export interface SSEMessage {
  type: SSEEventType;
  data: unknown;
  sequence?: number;
}

export type SSEEventType =
  | 'thought'
  | 'tool_start'
  | 'tool_result'
  | 'hil_interrupt'
  | 'token_update'
  | 'error'
  | 'done';

export interface SSEOptions {
  url: string;
  token: string;
  sessionId: string;
  onMessage: (message: SSEMessage) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class SSEManager {
  private abortController: AbortController | null = null;
  private retryCount = 0;
  private maxRetries = 5;
  private initialDelay = 1000;
  private maxDelay = 30000;
  private backoffMultiplier = 1.5;
  private lastSequence = -1;
  private reconnectTimeout: NodeJS.Timeout | null = null;

  async connect(options: SSEOptions): Promise<void> {
    this.abortController = new AbortController();

    await fetchEventSource(options.url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${options.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ sessionId: options.sessionId }),
      signal: this.abortController.signal,

      onopen: async (response) => {
        if (response.ok) {
          this.retryCount = 0;
          this.lastSequence = -1;
          options.onOpen?.();
        } else {
          throw new Error(`SSE connection failed: ${response.status}`);
        }
      },

      onmessage: (msg) => {
        try {
          const event: SSEMessage = JSON.parse(msg.data);

          // 序列检测
          if (event.sequence !== undefined) {
            if (this.lastSequence >= 0 && event.sequence !== this.lastSequence + 1) {
              console.warn(`Missing sequence: ${this.lastSequence} -> ${event.sequence}`);
            }
            this.lastSequence = event.sequence;
          }

          options.onMessage(event);
        } catch (error) {
          console.error('Failed to parse SSE message:', error);
        }
      },

      onerror: (error) => {
        this.scheduleReconnect(options);
        options.onError?.(error as Error);
        throw error; // 触发重试
      },

      onclose: () => {
        options.onClose?.();
      },
    });
  }

  private scheduleReconnect(options: SSEOptions): void {
    if (this.retryCount >= this.maxRetries) {
      options.onError?.(new Error('达到最大重试次数'));
      return;
    }

    const delay = Math.min(
      this.initialDelay * Math.pow(this.backoffMultiplier, this.retryCount),
      this.maxDelay
    );

    console.log(`SSE reconnecting in ${delay}ms (attempt ${this.retryCount + 1}/${this.maxRetries})`);

    this.reconnectTimeout = setTimeout(() => {
      this.retryCount++;
      this.connect(options);
    }, delay);
  }

  disconnect(): void {
    this.abortController?.abort();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.retryCount = 0;
  }

  isConnected(): boolean {
    return this.abortController !== null && !this.abortController.signal.aborted;
  }
}

export const sseManager = new SSEManager();
```

### useSSE Hook

```typescript
// hooks/useSSE.ts
import { useEffect, useCallback, useRef } from 'react';
import { useSessionStore } from '@/stores/session';
import { useTimelineStore } from '@/stores/timeline';
import { sseManager, type SSEMessage } from '@/lib/sse-manager';

export function useSSE() {
  const { currentSession } = useSessionStore();
  const addEvent = useTimelineStore((state) => state.addEvent);
  const updateEvent = useTimelineStore((state) => state.updateEvent);
  const processingRef = useRef(new Set<string>());

  const handleMessage = useCallback((message: SSEMessage) => {
    const eventId = `${message.type}_${Date.now()}`;

    switch (message.type) {
      case 'thought':
        if (!processingRef.current.has(eventId)) {
          processingRef.current.add(eventId);
          addEvent({
            id: eventId,
            step: useTimelineStore.getState().events.length + 1,
            title: '思考',
            description: (message.data as { content: string }).content,
            status: 'active',
            eventType: 'thought',
            timestamp: Date.now(),
          });
        }
        break;

      case 'tool_start':
        const toolData = message.data as { toolName: string; args: unknown };
        addEvent({
          id: eventId,
          step: useTimelineStore.getState().events.length + 1,
          title: '工具调用',
          description: `调用 ${toolData.toolName}`,
          status: 'active',
          eventType: 'tool_start',
          metadata: { toolName: toolData.toolName },
          timestamp: Date.now(),
        });
        break;

      case 'tool_result':
        // 更新对应的事件状态
        const events = useTimelineStore.getState().events;
        const toolEvent = events.find((e) =>
          e.eventType === 'tool_start' &&
          e.metadata?.toolName === (message.data as { toolName: string }).toolName
        );
        if (toolEvent) {
          updateEvent(toolEvent.id, { status: 'done' });
        }
        break;

      case 'hil_interrupt':
        // 触发 HIL 确认模态框
        useTimelineStore.getState().setHILPending(message.data);
        break;

      case 'token_update':
        useTimelineStore.getState().updateTokenUsage(message.data as { used: number; total: number });
        break;

      case 'error':
        addEvent({
          id: eventId,
          step: useTimelineStore.getState().events.length + 1,
          title: '错误',
          description: (message.data as { error: string }).error,
          status: 'error',
          eventType: 'error',
          timestamp: Date.now(),
        });
        break;

      case 'done':
        // 标记所有进行中的事件为完成
        events.forEach((event) => {
          if (event.status === 'active') {
            updateEvent(event.id, { status: 'done' });
          }
        });
        break;
    }
  }, [addEvent, updateEvent]);

  useEffect(() => {
    if (!currentSession?.id) return;

    const token = localStorage.getItem('auth_token') ?? '';
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

    sseManager.connect({
      url: `${apiUrl}/api/chat/stream`,
      token,
      sessionId: currentSession.id,
      onMessage: handleMessage,
      onError: (error) => console.error('SSE error:', error),
      onOpen: () => console.log('SSE connected'),
      onClose: () => console.log('SSE closed'),
    });

    return () => {
      sseManager.disconnect();
    };
  }, [currentSession?.id, handleMessage]);

  return {
    isConnected: sseManager.isConnected(),
    disconnect: () => sseManager.disconnect(),
  };
}
```

---

## 状态管理策略

### Zustand Store 设计

```typescript
// stores/timeline.ts
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { TimelineEvent } from '@/types/timeline';

interface TimelineState {
  events: TimelineEvent[];
  tokenUsage: { used: number; total: number };
  hilPending: HILConfirmData | null;

  // Actions
  addEvent: (event: TimelineEvent) => void;
  updateEvent: (id: string, updates: Partial<TimelineEvent>) => void;
  clearEvents: () => void;
  updateTokenUsage: (usage: { used: number; total: number }) => void;
  setHILPending: (data: HILConfirmData | null) => void;
}

export const useTimelineStore = create<TimelineState>()(
  immer((set) => ({
    events: [],
    tokenUsage: { used: 0, total: 32000 },
    hilPending: null,

    addEvent: (event) =>
      set((state) => {
        state.events.push(event);
      }),

    updateEvent: (id, updates) =>
      set((state) => {
        const index = state.events.findIndex((e) => e.id === id);
        if (index !== -1) {
          Object.assign(state.events[index], updates);
        }
      }),

    clearEvents: () =>
      set((state) => {
        state.events = [];
        state.tokenUsage = { used: 0, total: 32000 };
      }),

    updateTokenUsage: (usage) =>
      set((state) => {
        state.tokenUsage = usage;
      }),

    setHILPending: (data) =>
      set((state) => {
        state.hilPending = data;
      }),
  }))
);

// stores/session.ts
interface SessionState {
  sessions: Session[];
  currentSession: Session | null;

  // Actions
  setSessions: (sessions: Session[]) => void;
  setCurrentSession: (session: Session | null) => void;
  addSession: (session: Session) => void;
  updateSession: (id: string, updates: Partial<Session>) => void;
}

export const useSessionStore = create<SessionState>()(
  immer((set) => ({
    sessions: [],
    currentSession: null,

    setSessions: (sessions) =>
      set((state) => {
        state.sessions = sessions;
      }),

    setCurrentSession: (session) =>
      set((state) => {
        state.currentSession = session;
      }),

    addSession: (session) =>
      set((state) => {
        state.sessions.push(session);
      }),

    updateSession: (id, updates) =>
      set((state) => {
        const index = state.sessions.findIndex((s) => s.id === id);
        if (index !== -1) {
          Object.assign(state.sessions[index], updates);
        }
      }),
  }))
);
```

---

## 性能优化方案

### 1. 虚拟滚动

```typescript
// components/timeline/TimelineVirtual.tsx
import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef } from 'react';
import { useTimelineStore } from '@/stores/timeline';
import { TimelineEvent } from './TimelineEvent';

export function TimelineVirtual() {
  const events = useTimelineStore((state) => state.events);
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 5,
  });

  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const event = events[virtualItem.index];
          return (
            <div
              key={virtualItem.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              <TimelineEvent
                event={event}
                isActive={event.status === 'active'}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

### 2. 组件优化

```typescript
// 使用 React.memo 优化
export const TimelineEvent = React.memo(function TimelineEvent({
  event,
  isActive
}: TimelineEventProps) {
  // ...
}, (prevProps, nextProps) => {
  return (
    prevProps.event.id === nextProps.event.id &&
    prevProps.event.status === nextProps.event.status &&
    prevProps.isActive === nextProps.isActive
  );
});

// 使用 useMemo 优化计算
const filteredEvents = useMemo(() => {
  return events.filter((e) => e.status !== 'deleted');
}, [events]);
```

### 3. 事件去重和合并

```typescript
// lib/event-deduplicator.ts
class EventDeduplicator {
  private seen = new Set<string>();
  private buffer = new Map<string, SSEMessage[]>();
  private flushTimer: NodeJS.Timeout | null = null;

  process(message: SSEMessage): SSEMessage[] {
    const key = this.getEventKey(message);

    // 去重
    if (this.seen.has(key)) {
      return [];
    }
    this.seen.add(key);

    // 缓冲和合并
    if (this.shouldBuffer(message)) {
      this.buffer.set(key, [...(this.buffer.get(key) ?? []), message]);
      this.scheduleFlush();
      return [];
    }

    return [message];
  }

  private shouldBuffer(message: SSEMessage): boolean {
    // 快速连续的 token_update 事件可以合并
    return message.type === 'token_update';
  }

  private scheduleFlush(): void {
    if (this.flushTimer) return;

    this.flushTimer = setTimeout(() => {
      this.flush();
    }, 100);
  }

  private flush(): SSEMessage[] {
    const results: SSEMessage[] = [];

    for (const [key, events] of this.buffer) {
      // 合并 token_update 事件
      if (events[0]?.type === 'token_update') {
        const lastEvent = events[events.length - 1];
        results.push(lastEvent);
      } else {
        results.push(...events);
      }
    }

    this.buffer.clear();
    this.flushTimer = null;
    return results;
  }

  private getEventKey(message: SSEMessage): string {
    return `${message.type}_${message.sequence ?? Date.now()}`;
  }
}
```

---

## 类型定义

### SSE 事件类型

```typescript
// types/sse.ts
export type SSEEventType =
  | 'thought'
  | 'tool_start'
  | 'tool_result'
  | 'hil_interrupt'
  | 'token_update'
  | 'error'
  | 'done';

export interface SSEMessage<T = unknown> {
  type: SSEEventType;
  data: T;
  sequence?: number;
  timestamp: number;
}

export interface ThoughtData {
  content: string;
  step: number;
}

export interface ToolStartData {
  toolName: string;
  args: Record<string, unknown>;
}

export interface ToolResultData {
  toolName: string;
  result: unknown;
  duration: number;
}

export interface HILInterruptData {
  toolName: string;
  args: Record<string, unknown>;
  risk: 'low' | 'medium' | 'high';
  operationId: string;
  estimatedCost?: string;
}

export interface TokenUpdateData {
  used: number;
  total: number;
}

export interface ErrorData {
  error: string;
  code?: string;
}
```

### Timeline 类型

```typescript
// types/timeline.ts
export type EventStatus = 'pending' | 'active' | 'done' | 'error';

export interface TimelineEvent {
  id: string;
  step: number;
  title: string;
  description?: string;
  status: EventStatus;
  focus?: boolean;
  timestamp: number;
  duration?: number;
  eventType: SSEEventType;
  metadata?: {
    toolName?: string;
    tokenUsage?: number;
    error?: string;
  };
  children?: TimelineEvent[];
}

export interface TokenUsage {
  used: number;
  total: number;
  percentage: number;
}
```

---

## 总结

### 工时汇总

| Phase | 描述 | 预计工时 | 优先级 |
|-------|------|---------|-------|
| Phase 1 | 项目脚手架 | 22h | 🔴 P0 |
| Phase 2 | 布局结构 | 35h | 🔴 P0 |
| Phase 3 | SSE 连接管理 | 28h | 🔴 P0 |
| Phase 4 | 时间轴可视化 | 34h | 🟡 P1 |
| Phase 5 | HIL 确认模态框 | 24h | 🟡 P1 |
| Phase 6 | 状态管理优化 | 19h | 🟡 P1 |
| Phase 7 | UI 完善与动画 | 24h | ⚪ P2 |
| Phase 8 | 测试与优化 | 28h | ⚪ P2 |
| **总计** | | **214h** | |

### 依赖关系图

```
Phase 1 (脚手架)
    ↓
Phase 2 (布局)
    ↓
Phase 3 (SSE)
    ↓
    ├──→ Phase 4 (时间轴)
    ├──→ Phase 5 (HIL)
    └──→ Phase 6 (状态管理)
            ↓
        Phase 7 (UI 完善)
            ↓
        Phase 8 (测试优化)
```

### 关键里程碑

1. **Week 2 结束**: 完成基础布局，可以进行基本的聊天交互
2. **Week 3 结束**: SSE 连接稳定，可以接收实时事件
3. **Week 5 结束**: 时间轴可视化完成，HIL 模态框可用
4. **Week 6 结束**: React Query 集成，状态管理完善
5. **Week 8 结束**: 测试覆盖达标，性能优化完成

---

**文档版本**: v1.0
**创建日期**: 2026-03-20
**维护者**: Frontend Team
