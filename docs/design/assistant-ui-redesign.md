# Multi-Tool AI Agent — assistant-ui 重新设计方案

> 基于 assistant-ui 的企业级 AI 聊天界面升级方案

## 📋 目录

1. [项目分析](#项目分析)
2. [assistant-ui 简介](#assistant-ui-简介)
3. [设计系统](#设计系统)
4. [集成方案](#集成方案)
5. [组件映射](#组件映射)
6. [实施计划](#实施计划)

---

## 项目分析

### 当前状态

| 组件 | 现状 | 问题 |
|------|------|------|
| MessageList | 自定义实现 | 缺少流式响应优化、代码块语法高亮、思维链展示 |
| ChatInput | 基础 textarea | 缺少附件支持、命令建议、多行输入优化 |
| Sidebar | 自定义 tab 面板 | 缺少响应式设计、移动端适配 |
| 主题系统 | CSS Variables | 缺少 assistant-ui 主题集成 |

### 技术栈

```json
{
  "framework": "Next.js 15 + React 19",
  "styling": "Tailwind CSS 4",
  "animation": "Framer Motion",
  "state": "Zustand",
  "icons": "Lucide React",
  "目标集成": "assistant-ui"
}
```

---

## assistant-ui 简介

### 核心特性

```typescript
// assistant-ui 提供的核心能力
import {
  Thread,           // 会话线程管理
  Message,          // 消息组件
  MessageContent,   // 消息内容（支持 Markdown）
  Composer,         // 输入框组件
  Attachment,       // 附件支持
  BranchPicker,     // 分支选择
  ThreadWelcome,    // 欢迎界面
  Tooltip,         // 工具提示
} from '@assistant-ui/react';

import {
  renderThread,    // 核心渲染器
  useThread,       // 状态管理 Hook
  useExternalStore, // 外部状态集成
} from '@assistant-ui/react';
```

### 为什么选择 assistant-ui？

| 特性 | assistant-ui | 自定义实现 |
|------|-------------|-----------|
| **流式响应** | ✅ 开箱即用 | ❌ 需手动实现 |
| **思维链展示** | ✅ 内置支持 | ❌ 需自定义 |
| **代码高亮** | ✅ 集成 Shiki | ❌ 需额外配置 |
| **分支管理** | ✅ 原生支持 | ❌ 复杂实现 |
| **可访问性** | ✅ WCAG 2.1 AA | ❌ 需持续维护 |
| **主题系统** | ✅ shadcn/ui 集成 | ⚠️ 自定义维护 |

---

## 设计系统

### 颜色方案

基于 **Dark Mode (OLED)** 风格 + 企业级配色：

```css
/* globals.css - assistant-ui 主题覆盖 */
@theme {
  /* ===== 主色调 - 企业蓝 ===== */
  --color-primary: #3B82F6;          /* Blue 500 */
  --color-primary-hover: #2563EB;    /* Blue 600 */
  --color-primary-light: rgba(59, 130, 246, 0.1);

  /* ===== 强调色 - 活力橙 ===== */
  --color-accent: #F97316;           /* Orange 500 */
  --color-accent-hover: #EA580C;     /* Orange 600 */

  /* ===== 深色背景 - OLED 优化 ===== */
  --color-bg-base: #0A0A0F;          /* 近纯黑 */
  --color-bg-alt: #0F1014;           /* 次级背景 */
  --color-bg-muted: #15161A;         /* 弱化背景 */
  --color-bg-card: #1A1B1E;          /* 卡片背景 */
  --color-bg-elevated: #222328;      /* 悬浮元素 */

  /* ===== 边框系统 ===== */
  --color-border-base: rgba(255, 255, 255, 0.08);
  --color-border-muted: rgba(255, 255, 255, 0.05);
  --color-border-strong: rgba(255, 255, 255, 0.15);
  --color-border-focus: var(--color-primary);

  /* ===== 文本系统 ===== */
  --color-text-primary: #EDEDEF;     /* 主要文本 */
  --color-text-secondary: #A1A1AA;   /* 次要文本 */
  --color-text-muted: #71717A;       /* 弱化文本 */
  --color-text-disabled: #52525B;    /* 禁用文本 */

  /* ===== ReAct 链路状态色 ===== */
  --color-react-thought: #A78BFA;     /* 思考阶段 */
  --color-react-tool-call: #3B82F6;   /* 工具调用 */
  --color-react-tool-result: #14B8A6; /* 工具结果 */
  --color-react-final: #22C55E;       /* 最终输出 */
  --color-react-interrupt: #F59E0B;   /* 人工干预 */
}
```

### 排版系统

```css
/* 继续使用 Inter + JetBrains Mono */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

@theme {
  --font-family-sans: 'Inter', system-ui, sans-serif;
  --font-family-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* 字体大小 - 精细分级 */
  --text-xs: 0.75rem;    /* 12px - 辅助信息 */
  --text-sm: 0.875rem;   /* 14px - 正文 */
  --text-base: 1rem;     /* 16px - 基准 */
  --text-lg: 1.125rem;   /* 18px - 强调 */
  --text-xl: 1.25rem;    /* 20px - 小标题 */
  --text-2xl: 1.5rem;    /* 24px - 标题 */
  --text-3xl: 1.875rem;  /* 30px - 大标题 */
}

/* 行高系统 */
--leading-tight: 1.25;    /* 标题 */
--leading-normal: 1.5;    /* 正文 */
--leading-relaxed: 1.625; /* 长文本 */
```

### 间距系统 (8pt Grid)

```css
--spacing-1: 4px;
--spacing-2: 8px;
--spacing-3: 12px;
--spacing-4: 16px;
--spacing-5: 20px;
--spacing-6: 24px;
--spacing-8: 32px;
--spacing-10: 40px;
--spacing-12: 48px;
```

### 圆角系统

```css
--radius-sm: 4px;      /* 小元素 */
--radius-md: 6px;      /* 按钮、标签 */
--radius-lg: 8px;      /* 卡片 */
--radius-xl: 12px;     /* 大卡片 */
--radius-2xl: 16px;    /* 模态框 */
--radius-full: 9999px; /* 圆形元素 */
```

### 阴影系统 (深色模式优化)

```css
/* 深色模式下使用微弱发光替代传统阴影 */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.4);
--shadow-glow-primary: 0 0 20px rgba(59, 130, 246, 0.15);
--shadow-glow-accent: 0 0 20px rgba(249, 115, 22, 0.15);
```

---

## 集成方案

### Step 1: 安装依赖

```bash
cd frontend
bun add @assistant-ui/react @assistant-ui/shadcn@latest
bun add @radix-ui/react-avatar @radix-ui/react-dialog @radix-ui/react-dropdown-menu
bun add @radix-ui/react-popover @radix-ui/react-scroll-area @radix-ui/react-separator
bun add @radix-ui/react-slot @radix-ui/react-tooltip
bun add class-variance-authority clsx tailwind-merge
```

### Step 2: 配置 Tailwind 插件

```javascript
// tailwind.config.js
import assistantUI from '@assistant-ui/react/tailwind-plugin'

export default {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './node_modules/@assistant-ui/react/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ... 现有配置
    },
  },
  plugins: [
    assistantUI(),
    // ... 其他插件
  ],
}
```

### Step 3: 创建 Assistant UI Provider

```typescript
// src/components/assistant/AssistantProvider.tsx
'use client';

import { ThreadProvider } from '@assistant-ui/react';
import { useSession } from '@/store/use-session';

interface AssistantProviderProps {
  children: React.ReactNode;
}

export function AssistantProvider({ children }: AssistantProviderProps) {
  const { messages, addMessage } = useSession();

  return (
    <ThreadProvider
      config={{
        // 集成现有状态管理
        initialState: {
          messages: messages.map(m => ({
            id: m.id,
            role: m.role,
            content: [{ type: 'text', text: m.content }],
          })),
        },
        // 消息发送处理
        onNewMessage: async (message) => {
          addMessage({ role: 'user', content: message.content[0].text });
          // 触发现有的 SSE 流处理
        },
      }}
    >
      {children}
    </ThreadProvider>
  );
}
```

### Step 4: 自定义主题组件

```typescript
// src/components/assistant/MyRoot.tsx
import { Root } from '@assistant-ui/react';
import { cn } from '@/lib/utils';

export const MyRoot = ({
  className,
  ...props
}: React.ComponentProps<typeof Root>) => {
  return (
    <Root
      className={cn(
        'bg-bg-base text-text-primary',
        'focus-within:ring-2 focus-within:ring-primary/20',
        className
      )}
      {...props}
    />
  );
};

// src/components/assistant/MyMessage.tsx
import { Message } from '@assistant-ui/react';
import { cn } from '@/lib/utils';

export const MyMessage = ({
  className,
  ...props
}: React.ComponentProps<typeof Message>) => {
  return (
    <Message
      className={cn(
        'group/message relative',
        'px-6 py-4',
        'hover:bg-bg-alt/50',
        'transition-colors duration-200',
        className
      )}
      {...props}
    />
  );
};
```

---

## 组件映射

### 现有组件 → assistant-ui 替代

| 现有组件 | assistant-ui 组件 | 改进点 |
|---------|------------------|--------|
| `MessageList.tsx` | `<ThreadMessages />` | 流式响应、思维链展开 |
| `MessageBubble` | `<Message />` + `<MessageContent />` | Markdown 渲染、代码高亮 |
| `ChatInput.tsx` | `<Composer />` | 附件支持、命令建议 |
| `ConfirmModal.tsx` | `<Dialog />` (Radix UI) | 可访问性、动画 |
| `Sidebar` | 自定义 Layout | 响应式、抽屉模式 |

### 布局结构重构

```typescript
// 新的页面结构
// src/app/page.tsx
import { AssistantProvider } from '@/components/assistant/AssistantProvider';
import { MainLayout } from '@/components/layout/MainLayout';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { Sidebar } from '@/components/sidebar/Sidebar';

export default function HomePage() {
  return (
    <AssistantProvider>
      <MainLayout>
        <div className="flex h-screen">
          {/* 主聊天区域 */}
          <ChatPanel />

          {/* 右侧面板 - 链路/Context */}
          <Sidebar />
        </div>
      </MainLayout>
    </AssistantProvider>
  );
}
```

---

## 实施计划

### Phase 1: 基础集成 (1-2天)

- [ ] 安装 assistant-ui 及依赖
- [ ] 配置 Tailwind 插件
- [ ] 创建主题组件 (Root, Message, Composer)
- [ ] 集成现有 Zustand 状态

### Phase 2: 核心组件重构 (2-3天)

- [ ] 重构 MessageList → ThreadMessages
- [ ] 重构 ChatInput → Composer
- [ ] 添加流式响应处理
- [ ] 实现思维链展开组件

### Phase 3: 功能增强 (2-3天)

- [ ] 代码块语法高亮 (Shiki)
- [ ] 附件支持
- [ ] 分支管理
- [ ] 移动端响应式适配

### Phase 4: 视觉优化 (1-2天)

- [ ] 应用完整设计系统
- [ ] 动画效果优化
- [ ] 深色模式完美适配
- [ ] 可访问性测试

### Phase 5: 测试与部署 (1天)

- [ ] E2E 测试更新
- [ ] 性能测试
- [ ] 用户验收测试
- [ ] 生产部署

---

## 预期效果

### 视觉对比

| 方面 | 当前 | 升级后 |
|------|------|--------|
| **配色** | 基础蓝紫色 | 专业企业级深色主题 |
| **消息展示** | 简单文本气泡 | Markdown + 代码高亮 + 思维链 |
| **输入体验** | 纯文本 textarea | 支持附件、命令建议、自动完成 |
| **响应式** | 桌面优先 | 移动优先 + 抽屉式侧边栏 |
| **可访问性** | 基础支持 | WCAG 2.1 AA 完全合规 |

### 性能提升

- **首次加载**: 优化组件懒加载
- **流式响应**: 原生 SSE 支持，减少延迟
- **渲染性能**: React 19 并发特性优化

---

## 参考资源

- [assistant-ui 官方文档](https://assistant-ui.com/)
- [shadcn/ui 组件库](https://ui.shadcn.com/)
- [Radix UI Primitives](https://www.radix-ui.com/primitives)
- [Tailwind CSS 文档](https://tailwindcss.com/)
