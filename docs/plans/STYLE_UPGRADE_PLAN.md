# 样式系统升级实施计划

> Multi-Tool AI Agent 前端全面改造方案
> 目标：从当前基础样式升级到 Linear.app 风格的专业界面

---

## 🎯 改造目标

**当前状态**: 基础 Tailwind 样式，使用 Emoji 图标，缺乏现代感
**目标状态**: Linear.app 风格 + shadcn/ui + Framer Motion 动画

---

## 📦 Phase 1: 基础设施升级 (P0)

### 1.1 安装 shadcn/ui

```bash
cd frontend

# 安装依赖
bun add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-select
bun add @radix-ui/react-tabs @radix-ui/react-toast @radix-ui/react-tooltip
bun add class-variance-authority clsx tailwind-merge
bun add framer-motion
bun add lucide-react

# 初始化 shadcn/ui
npx shadcn-ui@latest init
```

**配置选择**:
- TypeScript: Yes
- Style: Default
- Base color: Slate
- CSS variables: Yes
- Tailwind config: Yes
- Components: Yes
- Utils path: `@/lib/utils`

### 1.2 更新 Tailwind 配置

```javascript
// tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Linear.app 风格颜色
        primary: {
          DEFAULT: "#5E6AD2",
          hover: "#4F5BC4",
          light: "rgba(94, 106, 210, 0.1)",
        },
        accent: {
          DEFAULT: "#22C55E",
          hover: "#16A34A",
        },
        // 深色模式
        background: {
          base: "var(--color-bg-base)",
          alt: "var(--color-bg-alt)",
          muted: "var(--color-bg-muted)",
          card: "var(--color-bg-card)",
        },
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "var(--radius-2xl)",
      },
      animation: {
        "fade-in": "fadeIn 200ms ease-out",
        "slide-up": "slideUp 300ms ease-out",
        "scale-in": "scaleIn 200ms ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

### 1.3 更新 globals.css

```css
/* globals.css */
@import "tailwindcss";
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

@theme {
  /* 颜色系统 */
  --color-primary: #5E6AD2;
  --color-primary-hover: #4F5BC4;
  --color-accent: #22C55E;

  /* 浅色模式 */
  --color-bg-base: #FFFFFF;
  --color-bg-alt: #F8FAFC;
  --color-bg-muted: #F1F5F9;
  --color-bg-card: #FFFFFF;
  --color-border-base: #E2E8F0;
  --color-text-primary: #0F172A;
  --color-text-secondary: #475569;
  --color-text-muted: #94A3B8;

  /* 深色模式 */
  --color-bg-base-dark: #0A0A0F;
  --color-bg-alt-dark: #0F1014;
  --color-bg-muted-dark: #15161A;
  --color-bg-card-dark: #1A1B1E;
  --color-border-base-dark: rgba(255, 255, 255, 0.08);
  --color-text-primary-dark: #EDEDEF;
  --color-text-secondary-dark: #A1A1AA;

  /* 排版 */
  --font-family-base: 'Inter', -apple-system, sans-serif;
  --font-family-mono: 'JetBrains Mono', monospace;

  /* 间距 */
  --spacing-unit: 4px;

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-2xl: 16px;

  /* 动画 */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
  --duration-base: 200ms;
  --duration-slow: 300ms;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-base: var(--color-bg-base-dark);
    --color-bg-alt: var(--color-bg-alt-dark);
    --color-bg-muted: var(--color-bg-muted-dark);
    --color-bg-card: var(--color-bg-card-dark);
    --color-border-base: var(--color-border-base-dark);
    --color-text-primary: var(--color-text-primary-dark);
    --color-text-secondary: var(--color-text-secondary-dark);
  }
}

body {
  font-family: var(--font-family-base);
  background-color: var(--color-bg-base);
  color: var(--color-text-primary);
  min-height: 100vh;
  transition: background-color var(--duration-slow) var(--ease-out),
              color var(--duration-slow) var(--ease-out);
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--color-text-muted);
  border-radius: 4px;
  transition: background var(--duration-fast) var(--ease-out);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-secondary);
}

/* Focus 可见性 */
*:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* 减少动画 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 🎨 Phase 2: 组件改造 (P0)

### 2.1 替换所有 Emoji 为 SVG 图标

**当前代码** (Timeline.tsx):
```typescript
const getEventIcon = (type: TimelineEvent['type']) => {
  switch (type) {
    case 'thought': return '💭';
    case 'tool_start': return '🔧';
    case 'tool_result': return '✅';
    // ...
  }
};
```

**改造后**:
```typescript
import {
  Brain,
  Wrench,
  CheckCircle,
  Flag,
  XCircle,
  Hand,
  Sparkles,
  ChevronRight,
  Clock
} from 'lucide-react';

const getEventIcon = (type: TimelineEvent['type']) => {
  const iconClassName = "w-4 h-4";

  switch (type) {
    case 'thought':
      return <Brain className={iconClassName} />;
    case 'tool_start':
      return <Wrench className={iconClassName} />;
    case 'tool_result':
      return <CheckCircle className={iconClassName} />;
    case 'done':
      return <Flag className={iconClassName} />;
    case 'error':
      return <XCircle className={iconClassName} />;
    case 'hil_interrupt':
      return <Hand className={iconClassName} />;
    default:
      return <Sparkles className={iconClassName} />;
  }
};
```

### 2.2 改造 ChatInput 组件

```typescript
// components/ChatInput.tsx
"use client";

import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--color-border-base)] bg-[var(--color-bg-alt)] p-4 transition-colors duration-300">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述任务，例如：帮我查一下茅台今天的股价..."
            className="w-full resize-none rounded-xl border border-[var(--color-border-base)]
                       bg-[var(--color-bg-card)] px-4 py-3 text-sm
                       placeholder:text-[var(--color-text-muted)]
                       focus:border-[var(--color-primary)] focus:ring-2
                       focus:ring-[var(--color-primary-light)]
                       focus:outline-none transition-all duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed
                       min-h-[48px] max-h-[200px]"
            rows={1}
            disabled={disabled}
          />
          {/* 字符计数 */}
          <div className="absolute bottom-3 right-3 text-xs text-[var(--color-text-muted)]">
            {input.length > 0 && `${input.length} 字符`}
          </div>
        </div>

        <motion.button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="rounded-xl bg-[var(--color-primary)] px-5 py-3
                     text-sm font-semibold text-white
                     hover:bg-[var(--color-primary-hover)]
                     disabled:bg-[var(--color-text-muted)]
                     disabled:cursor-not-allowed
                     transition-all duration-200
                     flex items-center gap-2
                     min-w-[100px]
                     justify-center"
          whileHover={{ scale: disabled ? 1 : 1.02 }}
          whileTap={{ scale: disabled ? 1 : 0.98 }}
        >
          {disabled ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              发送中...
            </>
          ) : (
            <>
              发送
              <Send className="w-4 h-4" />
            </>
          )}
        </motion.button>
      </div>
    </div>
  );
}
```

### 2.3 改造 MessageList 组件

```typescript
// components/MessageList.tsx
'use client';

import { Message, ToolCall } from '@/store/use-session';
import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
}

function MessageBubble({ message, index }: { message: Message; index: number }) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={cn(
        "flex gap-3 mb-6",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)]
                          flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-[var(--color-primary)] text-white rounded-br-sm"
            : "bg-[var(--color-bg-card)] border border-[var(--color-border-base)] text-[var(--color-text-primary)] rounded-bl-sm"
        )}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </p>

        {/* Tool Calls */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.tool_calls.map((toolCall) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600
                          flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      )}
    </motion.div>
  );
}

function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const statusConfig = {
    pending: {
      color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200",
      label: "等待中"
    },
    running: {
      color: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200",
      label: "执行中"
    },
    completed: {
      color: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200",
      label: "完成"
    },
    error: {
      color: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200",
      label: "错误"
    },
  };

  const config = statusConfig[toolCall.status] || statusConfig.pending;

  return (
    <div className="rounded-lg border border-[var(--color-border-base)] bg-[var(--color-bg-alt)] p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-[var(--color-primary)]" />
          <span className="font-mono text-xs font-semibold">{toolCall.tool_name}</span>
        </div>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", config.color)}>
          {config.label}
        </span>
      </div>

      {/* Args */}
      {toolCall.args && (
        <div className="mb-2">
          <details className="group">
            <summary className="cursor-pointer text-xs text-[var(--color-text-muted)]
                            hover:text-[var(--color-text-secondary)] transition-colors">
              参数
            </summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-[var(--color-bg-muted)] p-2 text-xs
                         border border-[var(--color-border-base)]">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </details>
        </div>
      )}

      {/* Result */}
      {toolCall.result && (
        <div>
          <details className="group" open>
            <summary className="cursor-pointer text-xs text-[var(--color-text-muted)]
                            hover:text-[var(--color-text-secondary)] transition-colors">
              结果
            </summary>
            <div className="mt-2 max-h-32 overflow-y-auto rounded-lg bg-[var(--color-bg-muted)] p-2 text-xs
                        border border-[var(--color-border-base)]">
              {typeof toolCall.result === 'string'
                ? toolCall.result
                : JSON.stringify(toolCall.result, null, 2)}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <AnimatePresence mode="wait">
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex h-full items-center justify-center min-h-[400px]"
            >
              <div className="text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)]
                                flex items-center justify-center">
                  <Bot className="w-8 h-8 text-white" />
                </div>
                <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] mb-2">
                  开始对话
                </h2>
                <p className="text-[var(--color-text-muted)]">
                  试试问："帮我查一下茅台今天的股价"
                </p>
              </div>
            </motion.div>
          ) : (
            messages.map((message, index) => (
              <MessageBubble key={message.id} message={message} index={index} />
            ))
          )}
        </AnimatePresence>

        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 mb-6"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-secondary)]
                            flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-[var(--color-bg-card)] border border-[var(--color-border-base)]
                        rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.6, repeat: Infinity }}
                    className="w-2 h-2 rounded-full bg-[var(--color-primary)]"
                  />
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: 0.1 }}
                    className="w-2 h-2 rounded-full bg-[var(--color-primary)]"
                  />
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                    className="w-2 h-2 rounded-full bg-[var(--color-primary)]"
                  />
                </div>
                <span className="text-sm text-[var(--color-text-muted)]">思考中...</span>
              </div>
            </div>
          </motion.div>
        )}
      </div>
      <div ref={scrollRef} />
    </div>
  );
}

import { Wrench } from 'lucide-react';
```

---

## 🚀 Phase 3: 高级特性 (P1)

### 3.1 ReAct 链路可视化（带动画）

```typescript
// components/react-trace/ReActPanel.tsx
'use client';

import { Message } from '@/store/use-session';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  ChevronRight,
  Brain,
  Wrench,
  CheckCircle,
  Flag,
  Clock,
  Hand
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

interface ReActPanelProps {
  messages: Message[];
}

interface ReActStep {
  id: string;
  type: 'thought' | 'tool_call' | 'tool_result' | 'final';
  content: string;
  toolName?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  timestamp: number;
  duration?: number;
}

function ReActStep({ step, index }: { step: ReActStep; index: number }) {
  const [isExpanded, setIsExpanded] = useState(true);

  const stepConfig = {
    thought: {
      icon: Brain,
      color: "border-l-purple-500 bg-purple-50 dark:bg-purple-900/20",
      iconColor: "text-purple-600 dark:text-purple-400",
      label: "思考",
    },
    tool_call: {
      icon: Wrench,
      color: "border-l-blue-500 bg-blue-50 dark:bg-blue-900/20",
      iconColor: "text-blue-600 dark:text-blue-400",
      label: "工具调用",
    },
    tool_result: {
      icon: CheckCircle,
      color: "border-l-teal-500 bg-teal-50 dark:bg-teal-900/20",
      iconColor: "text-teal-600 dark:text-teal-400",
      label: "结果",
    },
    final: {
      icon: Flag,
      color: "border-l-green-500 bg-green-50 dark:bg-green-900/20",
      iconColor: "text-green-600 dark:text-green-400",
      label: "完成",
    },
  };

  const config = stepConfig[step.type];
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.1 }}
      className={cn(
        "relative border-l-4 rounded-r-lg p-4 mb-3",
        config.color
      )}
    >
      {/* Step Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <Icon className={cn("w-4 h-4", config.iconColor)} />
          <span className="text-xs font-semibold uppercase text-[var(--color-text-secondary)]">
            {config.label}
          </span>
          {step.toolName && (
            <span className="font-mono text-sm text-[var(--color-text-primary)]">
              {step.toolName}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {step.duration && (
            <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {step.duration}ms
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-[var(--color-text-muted)]" />
          ) : (
            <ChevronRight className="w-4 h-4 text-[var(--color-text-muted)]" />
          )}
        </div>
      </div>

      {/* Step Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-3 pl-6">
              {/* Content */}
              <p className="text-sm text-[var(--color-text-primary)] whitespace-pre-wrap">
                {step.content}
              </p>

              {/* Args */}
              {step.args && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-[var(--color-text-muted)]
                                  hover:text-[var(--color-text-secondary)]">
                    参数
                  </summary>
                  <pre className="mt-1 overflow-x-auto rounded-lg bg-[var(--color-bg-base)] p-2 text-xs
                               border border-[var(--color-border-base)]">
                    {JSON.stringify(step.args, null, 2)}
                  </pre>
                </details>
              )}

              {/* Result */}
              {step.result && (
                <div className="mt-2">
                  <details open>
                    <summary className="cursor-pointer text-xs text-[var(--color-text-muted)]
                                    hover:text-[var(--color-text-secondary)]">
                      结果
                    </summary>
                    <div className="mt-1 max-h-48 overflow-y-auto rounded-lg bg-[var(--color-bg-base)] p-2 text-xs
                                border border-[var(--color-border-base)]">
                      {typeof step.result === 'string'
                        ? step.result
                        : JSON.stringify(step.result, null, 2)}
                    </div>
                  </details>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function ReActPanel({ messages }: ReActPanelProps) {
  const steps: ReActStep[] = [];

  // 从 messages 中提取 ReAct 步骤
  // ... 实现逻辑

  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-[var(--color-border-base)] bg-[var(--color-bg-card)] overflow-hidden">
      <div className="border-b border-[var(--color-border-base)] px-4 py-3 bg-[var(--color-bg-alt)]">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[var(--color-text-primary)]">ReAct 链路</h3>
          <span className="text-xs text-[var(--color-text-muted)]">{steps.length} 步</span>
        </div>
      </div>
      <div className="p-4">
        {steps.map((step, index) => (
          <ReActStep key={step.id} step={step} index={index} />
        ))}
      </div>
    </div>
  );
}
```

---

## 📋 实施清单

### 组件改造优先级

| 组件 | 优先级 | 工作量 | 状态 |
|------|--------|--------|------|
| `globals.css` | P0 | 2h | ⏳ 待开始 |
| `ChatInput.tsx` | P0 | 1h | ⏳ 待开始 |
| `MessageList.tsx` | P0 | 2h | ⏳ 待开始 |
| `ToolCallTrace.tsx` | P0 | 1.5h | ⏳ 待开始 |
| `Timeline.tsx` | P0 | 1.5h | ⏳ 待开始 |
| `ConfirmModal.tsx` | P0 | 1h | ⏳ 待开始 |
| `TokenBar.tsx` | P1 | 1h | ⏳ 待开始 |
| `page.tsx` (布局) | P1 | 2h | ⏳ 待开始 |

### 总工作量估算

- **Phase 1 (基础设施)**: 4 小时
- **Phase 2 (组件改造)**: 10 小时
- **Phase 3 (高级特性)**: 8 小时
- **总计**: 约 22 小时

---

## ✅ 验收标准

### 视觉质量
- [ ] 无 Emoji 图标，全部使用 SVG
- [ ] 所有图标来自同一系列 (Lucide)
- [ ] 深色模式对比度 >= 4.5:1
- [ ] 浅色模式对比度 >= 4.5:1
- [ ] 动画流畅，无卡顿

### 交互质量
- [ ] 所有可点击元素有 cursor-pointer
- [ ] Hover 状态有视觉反馈
- [ ] Focus 状态可见（键盘导航）
- [ ] 触摸目标 >= 44×44pt

### 动画质量
- [ ] 微交互时长 150-300ms
- [ ] 使用缓动函数，无线性突变
- [ ] 支持 prefers-reduced-motion
- [ ] ReAct 步骤有 staggered 动画

### 响应式
- [ ] 375px (小手机) 正常显示
- [ ] 768px (平板) 正常显示
- [ ] 1024px+ (桌面) 正常显示
- [ ] 横屏模式正常显示
