# assistant-ui 集成快速开始

> 按照以下步骤将 assistant-ui 集成到项目中

## Step 1: 安装依赖

```bash
cd frontend
bun add @assistant-ui/react @assistant-ui/shadcn@latest
bun add @radix-ui/react-avatar @radix-ui/react-dialog @radix-ui/react-dropdown-menu
bun add @radix-ui/react-popover @radix-ui/react-scroll-area @radix-ui/react-separator
bun add @radix-ui/react-slot @radix-ui/react-tooltip
```

## Step 2: 更新 Tailwind 配置

将 `tailwind.config.assistant-ui.js` 的内容合并到 `tailwind.config.js`:

```javascript
import assistantUI from '@assistant-ui/react/tailwind-plugin'

export default {
  darkMode: ['class'],
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './node_modules/@assistant-ui/react/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ... 复制 tailwind.config.assistant-ui.js 中的 extend 内容
    },
  },
  plugins: [
    assistantUI(),
    // ... 其他插件
  ],
}
```

## Step 3: 更新全局样式

在 `src/app/globals.css` 顶部添加:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
@import "tailwindcss";

/* 导入 assistant-ui 主题变量 */
@import './globals.assistant-ui.css';

/* ... 现有样式 */
```

## Step 4: 创建 AssistantProvider

```typescript
// src/components/assistant/AssistantProvider.tsx
'use client';

import { ThreadProvider } from '@assistant-ui/react';
import { useSession } from '@/store/use-session';

interface AssistantProviderProps {
  children: React.ReactNode;
}

export function AssistantProvider({ children }: AssistantProviderProps) {
  const { messages, addMessage, setLoading, setError } = useSession();

  return (
    <ThreadProvider
      config={{
        initialState: {
          messages: messages.map(m => ({
            id: m.id,
            role: m.role,
            content: [{ type: 'text', text: m.content }],
          })),
        },
        onNewMessage: async (message) => {
          const text = message.content[0].text;
          addMessage({ role: 'user', content: text });

          // 触发现有的 SSE 流处理
          setLoading(true);
          // ... 调用现有的 handleSendMessage 逻辑
        },
      }}
    >
      {children}
    </ThreadProvider>
  );
}
```

## Step 5: 更新主页面

```typescript
// src/app/page.tsx
'use client';

import { AssistantProvider } from '@/components/assistant/AssistantProvider';
import { AssistantRoot } from '@/components/assistant';
import { AssistantThread } from '@/components/assistant';
import { AssistantComposer } from '@/components/assistant';
import { Sidebar } from '@/components/sidebar/Sidebar'; // 保留现有侧边栏

export default function HomePage() {
  return (
    <AssistantProvider>
      <AssistantRoot>
        <div className="flex h-screen">
          {/* 主聊天区域 */}
          <div className="flex flex-1 flex-col">
            <header className="border-b border-border bg-bg-card px-6 py-4">
              <h1 className="text-lg font-semibold">Multi-Tool AI Agent</h1>
            </header>
            <AssistantThread />
            <AssistantComposer />
          </div>

          {/* 右侧面板 - 保留现有实现 */}
          <Sidebar />
        </div>
      </AssistantRoot>
    </AssistantProvider>
  );
}
```

## Step 6: 保留现有功能

### SSE 集成

```typescript
// 在 AssistantProvider 中集成现有的 SSE 管理
import { sseManager } from '@/lib/sse-manager';

export function AssistantProvider({ children }: AssistantProviderProps) {
  // ...

  const handleSendMessage = async (text: string) => {
    addMessage({ role: 'user', content: text });
    setLoading(true);

    try {
      sseManager.connect(getChatStreamUrl(), {
        message: text,
        session_id: sessionId,
        user_id: userId,
      });

      // ... 现有的事件处理逻辑
    } catch (error) {
      setError(error instanceof Error ? error.message : '发送消息失败');
      setLoading(false);
    }
  };

  // ...
}
```

### 侧边栏保留

现有的 `ExecutionTracePanel` 和 `ContextWindowPanel` 可以完全保留，
只需确保它们能接收到 SSE 事件更新。

## Step 7: 自定义样式

如需进一步自定义样式，可以修改以下文件:

| 文件 | 用途 |
|------|------|
| `AssistantRoot.tsx` | 根容器样式 |
| `AssistantMessage.tsx` | 消息气泡样式 |
| `AssistantComposer.tsx` | 输入框样式 |
| `AssistantThread.tsx` | 消息列表样式 |
| `AssistantThreadWelcome.tsx` | 欢迎界面样式 |

## Step 8: 测试

```bash
# 启动开发服务器
bun dev

# 访问 http://localhost:3000
# 测试发送消息、查看响应、检查样式
```

## 常见问题

### Q: 如何保留现有的流式响应处理？

A: 在 `AssistantProvider` 的 `onNewMessage` 中调用现有的 `handleSendMessage` 函数。

### Q: 如何保留 ReAct 链路可视化？

A: 继续使用现有的 `ExecutionTracePanel` 和 `ContextWindowPanel`，
确保 SSE 事件正确更新 zustand store。

### Q: 如何自定义主题颜色？

A: 修改 `globals.assistant-ui.css` 中的 CSS 变量。

### Q: 如何添加代码高亮？

A: assistant-ui 内置支持，只需确保 `MessageContent` 组件正确渲染。

## 下一步

- [ ] 添加附件支持
- [ ] 添加命令建议
- [ ] 添加分支管理
- [ ] 优化移动端响应式
- [ ] 添加更多自定义组件

## 参考资源

- [assistant-ui 官方文档](https://assistant-ui.com/)
- [assistant-ui 示例项目](https://github.com/Yonom/assistant-ui/tree/main/apps/web)
- [shadcn/ui 组件库](https://ui.shadcn.com/)
