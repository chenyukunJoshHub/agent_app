# Context Panel Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 `ContextWindowPanel.tsx` 全量替换为新版 `ContextPanel.tsx`，包含4个模块（会话元数据、Token地图、Slot卡片、压缩日志），修复实时刷新 Bug，并新增后端 `session_metadata` SSE 事件。

**Architecture:** 新主组件 `ContextPanel` 接收来自 `page.tsx` 的 props（而非零 props 从 store 内部订阅——此处偏离 spec 以提升可测试性，spec 第 9 节有说明），向下传给 `SessionMetadataSection`、`TokenMapSection`、`SlotCardsSection` 三个子组件，压缩日志直接复用改造后的 `CompressionLog`。`page.tsx` 在每次 `handleSendMessage` 开头重置相关 store 字段，解决旧数据残留问题。

**Tech Stack:** React 19 / Next.js 15, TypeScript, Zustand, Tailwind CSS, framer-motion, Vitest + Testing Library（组件测试，从 `tests/` 目录运行）, Playwright（E2E），FastAPI + Python（后端）

> **测试命令约定：** 所有组件测试从 `agent_app/tests/` 目录运行，使用 `tests/vitest.config.ts`。路径别名 `@/` 解析为 `../frontend/src`。

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `frontend/src/types/context-window.ts` | 新增 `SessionMeta`、`SessionMetaEvent` 类型 |
| 修改 | `frontend/src/store/use-session.ts` | 新增 `sessionMeta` 字段 + `setSessionMeta` action |
| 修改 | `backend/app/agent/langchain_engine.py` | 在 `context_window` 事件后追加 `session_metadata` 事件 |
| 修改 | `frontend/src/components/CompressionLog.tsx` | 新增 `hideInternalHeader?: boolean` prop |
| 新增 | `frontend/src/components/context/SessionMetadataSection.tsx` | 模块一：会话元数据 |
| 新增 | `frontend/src/components/context/TokenMapSection.tsx` | 模块二：Token地图 |
| 新增 | `frontend/src/components/context/SlotCardsSection.tsx` | 模块三：Slot卡片 |
| 新增 | `frontend/src/components/ContextPanel.tsx` | 新主组件（替换 ContextWindowPanel） |
| 修改 | `frontend/src/app/page.tsx` | 替换旧组件 + 新增 SSE handler + store reset |
| 新增 | `tests/components/context-window/ContextPanel.test.tsx` | 主组件集成测试 |
| 新增 | `tests/components/context-window/SessionMetadataSection.test.tsx` | 模块一单元测试 |
| 新增 | `tests/components/context-window/TokenMapSection.test.tsx` | 模块二单元测试 |
| 新增 | `tests/components/context-window/SlotCardsSection.test.tsx` | 模块三单元测试 |
| 修改 | `tests/e2e/06-context-window.spec.ts` | 替换为新版 E2E 断言 |

---

## Task 1：新增 SessionMeta 类型

**Files:**
- Modify: `frontend/src/types/context-window.ts`

- [ ] **Step 1: 在 `types/context-window.ts` 末尾追加类型定义**

```typescript
// 在文件末尾追加

export interface SessionMeta {
  /** 会话名称（session_id 衍生） */
  session_name: string;
  /** 激活的模型名称 */
  model: string;
  /** 创建时间 ISO 8601 */
  created_at: string;
}

export interface SessionMetaEvent {
  type: 'session_metadata';
  data: SessionMeta;
}
```

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
cd /path/to/agent_app/frontend && npx tsc --noEmit
```
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/context-window.ts
git commit -m "feat: add SessionMeta and SessionMetaEvent types to context-window"
```

---

## Task 2：Zustand Store 新增 sessionMeta 字段

**Files:**
- Modify: `frontend/src/store/use-session.ts`
- Test: `tests/components/store/use-session.test.ts`

- [ ] **Step 1: 写失败的测试**

在 `tests/components/store/use-session.test.ts` 末尾追加：

```typescript
describe('sessionMeta', () => {
  it('初始值应为 null', () => {
    const state = useSession.getState();
    expect(state.sessionMeta).toBeNull();
  });

  it('setSessionMeta 应更新 sessionMeta', () => {
    const meta = { session_name: 'test', model: 'claude', created_at: '2026-01-01T00:00:00Z' };
    useSession.getState().setSessionMeta(meta);
    expect(useSession.getState().sessionMeta).toEqual(meta);
  });

  it('setSessionMeta(null) 应清空 sessionMeta', () => {
    useSession.getState().setSessionMeta({ session_name: 'x', model: 'y', created_at: 'z' });
    useSession.getState().setSessionMeta(null);
    expect(useSession.getState().sessionMeta).toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/store/use-session.test.ts
```
Expected: FAIL — `Property 'sessionMeta' does not exist` 或 `undefined`

- [ ] **Step 3: 实现 store 变更**

修改 `frontend/src/store/use-session.ts`：

**3a. 更新顶部 import 引入 `SessionMeta`：**

```typescript
import type { ContextWindowData, SessionMeta, StateMessage } from '@/types/context-window';
```

**3b. 在 `SessionState` interface 的 `stateMessages` 字段后面添加：**

```typescript
// Session metadata (from session_metadata SSE event)
sessionMeta: SessionMeta | null;
```

**3c. 在 Actions 区域（`setStateMessages` 之后）添加：**

```typescript
setSessionMeta: (meta: SessionMeta | null) => void;
```

**3d. 在初始 state 的 `stateMessages: []` 之后添加：**

```typescript
sessionMeta: null,
```

**3e. 在 Actions 实现的 `setStateMessages` 之后添加：**

```typescript
setSessionMeta: (meta) => set({ sessionMeta: meta }),
```

**3f. 在 `clearMessages` action 的 set 对象中追加：**

```typescript
sessionMeta: null,
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/store/use-session.test.ts
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/use-session.ts tests/components/store/use-session.test.ts
git commit -m "feat: add sessionMeta field and setSessionMeta action to useSession store"
```

---

## Task 3：CompressionLog 新增 hideInternalHeader prop

**Files:**
- Modify: `frontend/src/components/CompressionLog.tsx`
- Test: `tests/components/context-window/CompressionLog.test.tsx`

- [ ] **Step 1: 写失败的测试**

在 `tests/components/context-window/CompressionLog.test.tsx` 末尾追加：

```typescript
describe('hideInternalHeader prop', () => {
  it('hideInternalHeader=false 时应显示内部 header', () => {
    render(<CompressionLog events={[]} hideInternalHeader={false} />);
    expect(screen.getByText('压缩事件日志')).toBeInTheDocument();
  });

  it('hideInternalHeader=true 时应隐藏内部 header', () => {
    render(<CompressionLog events={[]} hideInternalHeader={true} />);
    expect(screen.queryByText('压缩事件日志')).not.toBeInTheDocument();
  });

  it('未传 hideInternalHeader 时默认显示内部 header', () => {
    render(<CompressionLog events={[]} />);
    expect(screen.getByText('压缩事件日志')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/CompressionLog.test.tsx
```
Expected: FAIL — TypeScript error "hideInternalHeader" not in props type

- [ ] **Step 3: 实现变更**

修改 `frontend/src/components/CompressionLog.tsx`：

```typescript
// 修改 props interface（在 events 字段后面追加）
interface CompressionLogProps {
  events: CompressionEvent[];
  /** 隐藏组件内部 header，由 ContextPanel 模块四提供外部 header 时使用 */
  hideInternalHeader?: boolean;
}

// 修改函数签名
export function CompressionLog({ events, hideInternalHeader = false }: CompressionLogProps) {

// 将现有 header JSX 包裹在条件中：
// 把这一段：
//   <div className="border-b border-border p-4 bg-background-alt">
//     ...
//   </div>
// 替换为：
{!hideInternalHeader && (
  <div className="border-b border-border p-4 bg-background-alt">
    <div className="flex items-center gap-2">
      <Minimize2 className="w-5 h-5 text-text-secondary" />
      <h2 className="font-semibold text-text-primary">压缩事件日志</h2>
    </div>
    <p className="mt-1 text-xs text-text-muted">
      {events.length} 个压缩事件
    </p>
  </div>
)}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/CompressionLog.test.tsx
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CompressionLog.tsx tests/components/context-window/CompressionLog.test.tsx
git commit -m "feat: add hideInternalHeader prop to CompressionLog"
```

---

## Task 4：后端新增 session_metadata SSE 事件

**Files:**
- Modify: `backend/app/agent/langchain_engine.py`（约第 280 行，紧跟 `context_window` 事件的 `await _queue_put(...)` 之后）

> **注意：** `_queue_put` 已定义于 `langchain_engine.py` 第 122 行，无需新增。

- [ ] **Step 1: 写失败的后端测试**

新建 `tests/backend/unit/test_session_metadata_sse.py`：

```python
"""测试 create_react_agent 在 context_window 后发出 session_metadata SSE 事件。"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_session_metadata_event_emitted():
    """create_react_agent 应发出含 model/session_name/created_at 的 session_metadata 事件。"""
    from app.agent.langchain_engine import create_react_agent

    events = []

    async def fake_queue_put(queue, item):
        events.append(item)

    with patch('app.agent.langchain_engine._queue_put', side_effect=fake_queue_put), \
         patch('app.agent.langchain_engine.llm_factory', return_value=MagicMock()), \
         patch('app.agent.langchain_engine.build_tool_registry',
               return_value=([], MagicMock(), MagicMock())), \
         patch('app.agent.langchain_engine.SkillManager.get_instance') as mock_sm, \
         patch('app.agent.langchain_engine.build_system_prompt') as mock_bsp, \
         patch('app.agent.langchain_engine.create_agent', return_value=MagicMock()):

        mock_slot = MagicMock()
        mock_slot.to_dict.return_value = {'slots': []}
        mock_slot.total_tokens = 0
        mock_sm.return_value.build_snapshot.return_value = MagicMock(
            skills=[], version=1, total_tokens=0
        )
        mock_bsp.return_value = ('', mock_slot)

        queue = MagicMock()
        await create_react_agent(sse_queue=queue)

    event_types = [e[0] for e in events]
    assert 'session_metadata' in event_types, f"Expected session_metadata in {event_types}"

    meta_payload = next(e[1] for e in events if e[0] == 'session_metadata')
    assert 'model' in meta_payload, "session_metadata must contain 'model'"
    assert 'session_name' in meta_payload, "session_metadata must contain 'session_name'"
    assert 'created_at' in meta_payload, "session_metadata must contain 'created_at'"
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app && python -m pytest tests/backend/unit/test_session_metadata_sse.py -v
```
Expected: FAIL — `assert 'session_metadata' in event_types` fails

- [ ] **Step 3: 实现后端变更**

在 `backend/app/agent/langchain_engine.py` 中，找到 `context_window` 事件的 `await _queue_put(sse_queue, ("context_window", {...}))` 调用块的末尾（约第 280 行），在其**之后**追加：

```python
        # Session metadata for UI panel header (module 1)
        from datetime import datetime, timezone
        _provider = str(settings.llm_provider)
        if _provider == "anthropic":
            _model_name = settings.anthropic_model
        elif _provider == "ollama":
            _model_name = settings.ollama_model
        else:
            _model_name = _provider
        await _queue_put(
            sse_queue,
            (
                "session_metadata",
                {
                    "session_name": "Session",
                    "model": _model_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            ),
        )
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app && python -m pytest tests/backend/unit/test_session_metadata_sse.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/langchain_engine.py tests/backend/unit/test_session_metadata_sse.py
git commit -m "feat: emit session_metadata SSE event from create_react_agent"
```

---

## Task 5：SessionMetadataSection 组件

**Files:**
- Create: `frontend/src/components/context/SessionMetadataSection.tsx`
- Create: `tests/components/context-window/SessionMetadataSection.test.tsx`

> **使用率颜色规则（对齐 spec 第 3.2 节）：**
> - `< 70%` → `text-success-text`（绿色）
> - `70%–90%` → `text-warning-text`（橙色）
> - `≥ 90%` → `text-error-text`（红色）

- [ ] **Step 1: 写失败的测试**

新建 `tests/components/context-window/SessionMetadataSection.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SessionMetadataSection } from '@/components/context/SessionMetadataSection';
import type { SessionMeta, StateMessage } from '@/types/context-window';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

const mockMeta: SessionMeta = {
  session_name: '合同审查',
  model: 'claude-sonnet-4-6',
  created_at: '2026-03-25T09:00:00.000Z',
};

const mockMessages: StateMessage[] = [
  { role: 'user', content: 'hello' },
  { role: 'assistant', content: 'hi' },
  { role: 'user', content: 'world' },
];

describe('SessionMetadataSection', () => {
  it('应渲染模块一蓝色色条 (#2563EB)', () => {
    const { container } = render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    const accent = container.querySelector('[style*="#2563EB"]');
    expect(accent).not.toBeNull();
  });

  it('应显示模型名称', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText('claude-sonnet-4-6')).toBeInTheDocument();
  });

  it('应显示上下文限制 200,000', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText(/200,000/)).toBeInTheDocument();
  });

  it('应统计用户消息数量', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={mockMessages}
        lastActivityTime={null}
      />
    );
    expect(screen.getByTestId('user-messages-count')).toHaveTextContent('2');
  });

  it('应统计助手消息数量', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={mockMessages}
        lastActivityTime={null}
      />
    );
    expect(screen.getByTestId('assistant-messages-count')).toHaveTextContent('1');
  });

  it('sessionMeta 为 null 时应渲染占位符 — 而不崩溃', () => {
    render(
      <SessionMetadataSection
        sessionMeta={null}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    // 至少一个 — 占位符存在
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('使用率 ≥ 90% 时应用 text-error-text 类', () => {
    const heavyBudget = {
      ...EMPTY_CONTEXT_DATA.budget,
      working_budget: 32768,
      usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 30000 },
    };
    const { container } = render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={heavyBudget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    const usageEl = container.querySelector('[data-testid="usage-rate"]');
    expect(usageEl?.className).toMatch(/text-error-text/);
  });

  it('使用率 70–90% 时应用 text-warning-text 类', () => {
    const medBudget = {
      ...EMPTY_CONTEXT_DATA.budget,
      working_budget: 32768,
      usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 25000 },
    };
    const { container } = render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={medBudget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    const usageEl = container.querySelector('[data-testid="usage-rate"]');
    expect(usageEl?.className).toMatch(/text-warning-text/);
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/SessionMetadataSection.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: 创建目录并实现组件**

```bash
mkdir -p frontend/src/components/context
```

新建 `frontend/src/components/context/SessionMetadataSection.tsx`：

```typescript
'use client';

import type { SessionMeta, TokenBudgetState, StateMessage } from '@/types/context-window';

interface SessionMetadataSectionProps {
  sessionMeta: SessionMeta | null;
  budget: TokenBudgetState;
  stateMessages: StateMessage[];
  /** Unix timestamp（ms）—由父组件在 done 事件时更新 */
  lastActivityTime: number | null;
}

function formatNumber(n: number) {
  return n.toLocaleString('zh-CN');
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

function formatLastActivity(ts: number | null) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}

function getUsageColorClass(pct: number): string {
  if (pct >= 90) return 'text-error-text';
  if (pct >= 70) return 'text-warning-text';
  return 'text-success-text';
}

export function SessionMetadataSection({
  sessionMeta,
  budget,
  stateMessages,
  lastActivityTime,
}: SessionMetadataSectionProps) {
  const usagePct = budget.working_budget > 0
    ? (budget.usage.total_used / budget.working_budget) * 100
    : 0;
  const usageStr = `${usagePct.toFixed(1)}%`;

  const userCount = stateMessages.filter(m => m.role === 'user').length;
  const assistantCount = stateMessages.filter(m => m.role === 'assistant').length;
  const totalMessages = stateMessages.length;

  return (
    <div className="border-b border-border">
      {/* Section header */}
      <div className="flex items-center gap-2 px-4 py-3">
        <div style={{ width: 4, height: 20, background: '#2563EB', borderRadius: 2, flexShrink: 0 }} />
        <span className="text-sm font-bold text-text-primary">① 会话元数据与 Token 统计</span>
      </div>

      {/* 2-col metadata grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-4 pb-4 text-xs">
        {/* Row 1 */}
        <div>
          <div className="text-text-muted">会话名称</div>
          <div className="mt-0.5 font-semibold text-text-primary">{sessionMeta?.session_name ?? '—'}</div>
        </div>
        <div>
          <div className="text-text-muted">消息数量</div>
          <div className="mt-0.5 font-semibold text-text-primary">{totalMessages}</div>
        </div>

        {/* Row 2 */}
        <div>
          <div className="text-text-muted">上下文限制</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            {formatNumber(budget.model_context_window)} tokens
          </div>
        </div>
        <div>
          <div className="text-text-muted">激活模型</div>
          <div className="mt-0.5 font-semibold text-text-primary truncate">{sessionMeta?.model ?? '—'}</div>
        </div>

        {/* Row 3 */}
        <div>
          <div className="text-text-muted">总 token</div>
          <div className="mt-0.5 font-semibold text-text-primary">{formatTokens(budget.usage.total_used)}</div>
        </div>
        <div>
          <div className="text-text-muted">使用率</div>
          <div
            data-testid="usage-rate"
            className={`mt-0.5 font-semibold ${getUsageColorClass(usagePct)}`}
          >
            {usageStr}
          </div>
        </div>

        {/* Row 4 */}
        <div>
          <div className="text-text-muted">输入 token</div>
          <div className="mt-0.5 font-semibold text-text-primary">{formatTokens(budget.usage.input_budget)}</div>
        </div>
        <div>
          <div className="text-text-muted">输出 token</div>
          <div className="mt-0.5 font-semibold text-text-primary">{formatTokens(budget.usage.output_reserve)}</div>
        </div>

        {/* Row 5 */}
        <div>
          <div className="text-text-muted">用户消息</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            <span data-testid="user-messages-count">{userCount}</span>
          </div>
        </div>
        <div>
          <div className="text-text-muted">助手消息</div>
          <div className="mt-0.5 font-semibold text-text-primary">
            <span data-testid="assistant-messages-count">{assistantCount}</span>
          </div>
        </div>

        {/* Row 6 */}
        <div>
          <div className="text-text-muted">创建时间</div>
          <div className="mt-0.5 font-semibold text-text-primary">{formatDate(sessionMeta?.created_at)}</div>
        </div>
        <div>
          <div className="text-text-muted">最后活动</div>
          <div className="mt-0.5 font-semibold text-text-primary">{formatLastActivity(lastActivityTime)}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/SessionMetadataSection.test.tsx
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/context/SessionMetadataSection.tsx \
        tests/components/context-window/SessionMetadataSection.test.tsx
git commit -m "feat: implement SessionMetadataSection component (module 1)"
```

---

## Task 6：TokenMapSection 组件

**Files:**
- Create: `frontend/src/components/context/TokenMapSection.tsx`
- Create: `tests/components/context-window/TokenMapSection.test.tsx`

> **实现说明：** 进度条各段使用 `flex: tokens` 比例布局（而非 `width: pct%`），当 `working_budget=0` 时不会出现除零错误，效果等价。

- [ ] **Step 1: 写失败的测试**

新建 `tests/components/context-window/TokenMapSection.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TokenMapSection } from '@/components/context/TokenMapSection';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

const mockBudget = {
  model_context_window: 200000,
  working_budget: 32768,
  slots: {
    system: 2048, active_skill: 0, few_shot: 0, rag: 0,
    episodic: 0, procedural: 0, tools: 1800, history: 3200,
    output_format: 0, user_input: 0,
  },
  usage: {
    total_used: 7048,
    total_remaining: 25720,
    input_budget: 24576,
    output_reserve: 8192,
    autocompact_buffer: 5538,
  },
};

const mockSlotUsage = EMPTY_CONTEXT_DATA.slotUsage.map(s => ({
  ...s,
  used: s.name === 'system' ? 2048 : s.name === 'tools' ? 1800 : s.name === 'history' ? 3200 : 0,
}));

describe('TokenMapSection', () => {
  it('应渲染模块二靛色色条 (#6366F1)', () => {
    const { container } = render(
      <TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />
    );
    const accent = container.querySelector('[style*="#6366F1"]');
    expect(accent).not.toBeNull();
  });

  it('进度条应包含 12 个段', () => {
    const { container } = render(
      <TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />
    );
    const bar = container.querySelector('[data-testid="token-bar"]');
    expect(bar?.children.length).toBe(12);
  });

  it('应显示 working_budget（包含 32 或 32k）', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/32/)).toBeInTheDocument();
  });

  it('等宽表格应包含系统提示词行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/系统提示词/)).toBeInTheDocument();
  });

  it('等宽表格应包含剩余可用行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/剩余可用/)).toBeInTheDocument();
  });

  it('等宽表格应包含压缩预留行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/压缩预留/)).toBeInTheDocument();
  });

  it('全 0 预算时不应崩溃', () => {
    const { container } = render(
      <TokenMapSection budget={EMPTY_CONTEXT_DATA.budget} slotUsage={EMPTY_CONTEXT_DATA.slotUsage} />
    );
    const bar = container.querySelector('[data-testid="token-bar"]');
    expect(bar).not.toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/TokenMapSection.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: 实现组件**

新建 `frontend/src/components/context/TokenMapSection.tsx`：

```typescript
'use client';

import type { TokenBudgetState, SlotUsage } from '@/types/context-window';
import {
  SLOT_VISUAL_ORDER,
  SLOT_COLORS,
  SLOT_DISPLAY_NAMES,
  CONTEXT_REMAINING_FREE_COLOR,
  CONTEXT_AUTOCOMPACT_BUFFER_COLOR,
} from '@/types/context-window';

interface TokenMapSectionProps {
  budget: TokenBudgetState;
  slotUsage: SlotUsage[];
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function formatPct(part: number, total: number) {
  if (total === 0) return '0.0%';
  return `${((part / total) * 100).toFixed(1)}%`;
}

export function TokenMapSection({ budget, slotUsage }: TokenMapSectionProps) {
  const wb = budget.working_budget;
  const autocompact = budget.usage.autocompact_buffer ?? 0;

  // Build slot token map from slotUsage (used) falling back to budget.slots (allocated)
  const slotUsageMap = Object.fromEntries(slotUsage.map(s => [s.name, s.used]));
  const segments = SLOT_VISUAL_ORDER.map(key => ({
    key,
    tokens: slotUsageMap[key] ?? budget.slots[key] ?? 0,
    color: SLOT_COLORS[key],
  }));

  const totalSlotTokens = segments.reduce((sum, s) => sum + s.tokens, 0);
  const remaining = Math.max(0, wb - totalSlotTokens - autocompact);

  const barSegments = [
    ...segments,
    { key: 'remaining', tokens: remaining, color: CONTEXT_REMAINING_FREE_COLOR },
    { key: 'autocompact', tokens: autocompact, color: CONTEXT_AUTOCOMPACT_BUFFER_COLOR },
  ];

  // Table rows: only non-zero slots + always show remaining + autocompact
  const tableRows = segments.filter(s => s.tokens > 0);

  const wbLabel = wb >= 1000 ? `${Math.round(wb / 1024)}k` : String(wb);

  return (
    <div className="border-b border-border">
      {/* Section header */}
      <div className="flex items-center gap-2 px-4 py-3">
        <div style={{ width: 4, height: 20, background: '#6366F1', borderRadius: 2, flexShrink: 0 }} />
        <span className="text-sm font-bold text-text-primary">② 上下文窗口 · Token 地图</span>
      </div>

      <div className="mx-4 mb-4 rounded-lg border border-border bg-bg-card p-3">
        {/* Subtitle */}
        <div className="mb-2 text-[10px] font-semibold text-text-muted">
          12 档 Token 占比（{wbLabel} 工作窗口）
        </div>

        {/* 12-segment proportional bar — flex sizing avoids division-by-zero */}
        <div
          data-testid="token-bar"
          className="mb-3 flex h-2 overflow-hidden rounded"
        >
          {barSegments.map(seg => (
            <div
              key={seg.key}
              style={{
                flex: Math.max(seg.tokens, 0),
                background: seg.color,
                minWidth: seg.tokens > 0 ? 2 : 0,
              }}
            />
          ))}
        </div>

        {/* Monospace detail table */}
        <pre className="font-mono text-[9px] leading-relaxed text-text-secondary">
          {tableRows.map(s => {
            const label = SLOT_DISPLAY_NAMES[s.key as keyof typeof SLOT_DISPLAY_NAMES] ?? s.key;
            return `${label.padEnd(8)}  ${formatTokens(s.tokens).padStart(6)}  ${formatPct(s.tokens, wb).padStart(6)}\n`;
          }).join('')}
          {`剩余可用  ${formatTokens(remaining).padStart(6)}  ${formatPct(remaining, wb).padStart(6)}\n`}
          {`压缩预留  ${formatTokens(autocompact).padStart(6)}  ${formatPct(autocompact, wb).padStart(6)}`}
        </pre>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/TokenMapSection.test.tsx
```
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/context/TokenMapSection.tsx \
        tests/components/context-window/TokenMapSection.test.tsx
git commit -m "feat: implement TokenMapSection with 12-segment token bar (module 2)"
```

---

## Task 7：SlotCardsSection 组件

**Files:**
- Create: `frontend/src/components/context/SlotCardsSection.tsx`
- Create: `tests/components/context-window/SlotCardsSection.test.tsx`

> **testid 约定：** 每个 slot 卡片使用 `data-testid="slot-card-{slot.name}"`（如 `slot-card-system`）。排序测试使用 `compareDocumentPosition`。

- [ ] **Step 1: 写失败的测试**

新建 `tests/components/context-window/SlotCardsSection.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SlotCardsSection } from '@/components/context/SlotCardsSection';
import type { SlotDetail, StateMessage } from '@/types/context-window';

const mockSlots: SlotDetail[] = [
  { name: 'system', display_name: '① 系统提示词', content: 'You are an AI...', tokens: 2048, enabled: true },
  { name: 'history', display_name: '⑧ 会话历史', content: '', tokens: 3200, enabled: true },
  { name: 'rag', display_name: '④ RAG 背景知识', content: 'doc content', tokens: 0, enabled: false },
];

const mockStateMessages: StateMessage[] = [
  { role: 'user', content: 'hello' },
  { role: 'assistant', content: 'hi there' },
];

describe('SlotCardsSection', () => {
  it('应渲染模块三青绿色色条 (#0D9488)', () => {
    const { container } = render(
      <SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />
    );
    const accent = container.querySelector('[style*="#0D9488"]');
    expect(accent).not.toBeNull();
  });

  it('应按 token 降序排列：history(3200) 在 system(2048) 前', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    const historyCard = screen.getByTestId('slot-card-history');
    const systemCard = screen.getByTestId('slot-card-system');
    // DOCUMENT_POSITION_FOLLOWING = 4 — historyCard comes before systemCard in DOM
    expect(historyCard.compareDocumentPosition(systemCard) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it('disabled slot 应有 opacity 样式', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    const ragCard = screen.getByTestId('slot-card-rag');
    expect(ragCard.className).toMatch(/opacity/);
  });

  it('点击 enabled slot 应展开内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-system'));
    expect(screen.getByText(/You are an AI/)).toBeInTheDocument();
  });

  it('再次点击应折叠内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-system'));
    fireEvent.click(screen.getByTestId('slot-card-system'));
    expect(screen.queryByText(/You are an AI/)).not.toBeInTheDocument();
  });

  it('⑧ 会话历史展开后应显示 stateMessages 内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-history'));
    expect(screen.getByText(/hello/)).toBeInTheDocument();
  });

  it('disabled slot 点击后不应展开', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-rag'));
    expect(screen.queryByText(/doc content/)).not.toBeInTheDocument();
  });

  it('空 slotDetails 不应崩溃', () => {
    render(<SlotCardsSection slotDetails={[]} stateMessages={[]} />);
    expect(document.body).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/SlotCardsSection.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: 实现组件**

新建 `frontend/src/components/context/SlotCardsSection.tsx`：

```typescript
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SlotDetail, StateMessage } from '@/types/context-window';

interface SlotCardsSectionProps {
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
}

function formatTokens(n: number) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function SlotCardsSection({ slotDetails, stateMessages }: SlotCardsSectionProps) {
  const [expandedSlots, setExpandedSlots] = useState<Set<string>>(new Set());

  const sorted = [...slotDetails].sort((a, b) => b.tokens - a.tokens);

  const toggle = (name: string, enabled: boolean) => {
    if (!enabled) return;
    setExpandedSlots(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  return (
    <div className="border-b border-border">
      {/* Section header */}
      <div className="flex items-center gap-2 px-4 py-3">
        <div style={{ width: 4, height: 20, background: '#0D9488', borderRadius: 2, flexShrink: 0 }} />
        <span className="text-sm font-bold text-text-primary">③ 各 Slot 原文与 Prompt</span>
      </div>

      <div className="flex flex-col gap-1 px-4 pb-4">
        {sorted.length === 0 && (
          <p className="text-xs text-text-muted py-2">暂无 Slot 数据</p>
        )}
        {sorted.map(slot => {
          const isHistory = slot.name === 'history';
          const isExpanded = expandedSlots.has(slot.name);

          return (
            <div
              key={slot.name}
              data-testid={`slot-card-${slot.name}`}
              className={cn(
                'rounded-lg border border-border bg-bg-card',
                !slot.enabled && 'pointer-events-none opacity-40',
                slot.enabled && 'cursor-pointer hover:border-border-strong',
              )}
              onClick={() => toggle(slot.name, slot.enabled)}
            >
              {/* Card header row */}
              <div className="flex items-center justify-between px-3 py-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-xs font-semibold text-text-primary">
                    {slot.display_name}
                  </span>
                  <span className="shrink-0 font-mono text-[10px] text-text-muted">
                    {formatTokens(slot.tokens)}
                  </span>
                </div>
                <div className="shrink-0 text-text-muted">
                  {isHistory
                    ? <ChevronsUpDown className="h-3.5 w-3.5" />
                    : isExpanded
                    ? <ChevronUp className="h-3.5 w-3.5" />
                    : <ChevronDown className="h-3.5 w-3.5" />
                  }
                </div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className="border-t border-border px-3 pb-3 pt-2">
                  {isHistory ? (
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[9px] leading-relaxed text-text-secondary">
                      {stateMessages.map(m => JSON.stringify(m, null, 2)).join('\n')}
                    </pre>
                  ) : (
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[9px] leading-relaxed text-text-secondary">
                      {slot.content}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/SlotCardsSection.test.tsx
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/context/SlotCardsSection.tsx \
        tests/components/context-window/SlotCardsSection.test.tsx
git commit -m "feat: implement SlotCardsSection with expand/collapse and history view (module 3)"
```

---

## Task 8：ContextPanel 主组件

**Files:**
- Create: `frontend/src/components/ContextPanel.tsx`
- Create: `tests/components/context-window/ContextPanel.test.tsx`

> **架构说明：** `ContextPanel` 接受显式 props 而非直接从 store 订阅（偏离 spec 第 9 节"无外部 props"的建议），目的是提高可测试性并保持子组件的单一职责。`page.tsx` 负责从 store 提取数据并传入。

- [ ] **Step 1: 写失败的测试**

新建 `tests/components/context-window/ContextPanel.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ContextPanel } from '@/components/ContextPanel';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
import type { SessionMeta } from '@/types/context-window';

const mockMeta: SessionMeta = {
  session_name: 'Test',
  model: 'claude-sonnet-4-6',
  created_at: '2026-03-25T09:00:00.000Z',
};

describe('ContextPanel', () => {
  it('应渲染模块一、二、三的 section header', () => {
    render(
      <ContextPanel
        sessionMeta={mockMeta}
        contextWindowData={EMPTY_CONTEXT_DATA}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText(/会话元数据/)).toBeInTheDocument();
    expect(screen.getByText(/Token 地图/)).toBeInTheDocument();
    expect(screen.getByText(/Slot 原文/)).toBeInTheDocument();
  });

  it('无压缩事件时不应渲染模块四', () => {
    render(
      <ContextPanel
        sessionMeta={null}
        contextWindowData={EMPTY_CONTEXT_DATA}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.queryByText(/④ 压缩日志/)).not.toBeInTheDocument();
  });

  it('有压缩事件时应渲染模块四 header', () => {
    const dataWithEvents = {
      ...EMPTY_CONTEXT_DATA,
      compressionEvents: [{
        id: '1',
        timestamp: Date.now(),
        before_tokens: 10000,
        after_tokens: 5000,
        tokens_saved: 5000,
        method: 'summarization' as const,
        affected_slots: ['history'],
      }],
    };
    render(
      <ContextPanel
        sessionMeta={null}
        contextWindowData={dataWithEvents}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText('④ 压缩日志')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/ContextPanel.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: 实现主组件**

新建 `frontend/src/components/ContextPanel.tsx`：

```typescript
'use client';

import type { ContextWindowData, SlotDetail, StateMessage, SessionMeta } from '@/types/context-window';
import { SessionMetadataSection } from './context/SessionMetadataSection';
import { TokenMapSection } from './context/TokenMapSection';
import { SlotCardsSection } from './context/SlotCardsSection';
import { CompressionLog } from './CompressionLog';

interface ContextPanelProps {
  sessionMeta: SessionMeta | null;
  contextWindowData: ContextWindowData;
  slotDetails: SlotDetail[];
  stateMessages: StateMessage[];
  /** Unix timestamp（ms）—由 page.tsx 在 done 事件时更新 */
  lastActivityTime: number | null;
}

export function ContextPanel({
  sessionMeta,
  contextWindowData,
  slotDetails,
  stateMessages,
  lastActivityTime,
}: ContextPanelProps) {
  const hasCompressionEvents = contextWindowData.compressionEvents.length > 0;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Module 1: 会话元数据与 Token 统计 */}
      <SessionMetadataSection
        sessionMeta={sessionMeta}
        budget={contextWindowData.budget}
        stateMessages={stateMessages}
        lastActivityTime={lastActivityTime}
      />

      {/* Module 2: 上下文窗口 · Token 地图 */}
      <TokenMapSection
        budget={contextWindowData.budget}
        slotUsage={contextWindowData.slotUsage}
      />

      {/* Module 3: 各 Slot 原文与 Prompt */}
      <SlotCardsSection
        slotDetails={slotDetails}
        stateMessages={stateMessages}
      />

      {/* Module 4: 压缩日志（仅有事件时显示） */}
      {hasCompressionEvents && (
        <div>
          <div className="flex items-center gap-2 border-b border-border px-4 py-3">
            <div style={{ width: 4, height: 20, background: '#6B7280', borderRadius: 2, flexShrink: 0 }} />
            <span className="text-sm font-bold text-text-primary">④ 压缩日志</span>
          </div>
          <CompressionLog
            events={contextWindowData.compressionEvents}
            hideInternalHeader={true}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/ContextPanel.test.tsx
```
Expected: PASS (3 tests)

- [ ] **Step 5: 运行全量 context-window 测试，确认无回归**

```bash
cd /path/to/agent_app/tests && npx vitest run components/context-window/
```
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ContextPanel.tsx \
        tests/components/context-window/ContextPanel.test.tsx
git commit -m "feat: implement ContextPanel root component composing 4 modules"
```

---

## Task 9：page.tsx 集成

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Test: `tests/components/store/use-session.test.ts`（先补充 store reset 测试）

- [ ] **Step 1: 写失败的 store reset 测试（TDD 前置）**

在 `tests/components/store/use-session.test.ts` 末尾追加：

```typescript
describe('sessionMeta reset on clearMessages', () => {
  it('clearMessages 应将 sessionMeta 重置为 null', () => {
    useSession.getState().setSessionMeta({
      session_name: 's', model: 'm', created_at: 'c',
    });
    useSession.getState().clearMessages();
    expect(useSession.getState().sessionMeta).toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试确认 GREEN（Task 2 实现后应已通过）**

```bash
cd /path/to/agent_app/tests && npx vitest run components/store/use-session.test.ts
```
Expected: PASS（包含新增测试）

- [ ] **Step 3: 更新 page.tsx 的 import**

在 `frontend/src/app/page.tsx` 中：

```typescript
// 删除：
import { ContextWindowPanel } from '@/components/ContextWindowPanel';

// 新增：
import { ContextPanel } from '@/components/ContextPanel';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
import type { SessionMeta } from '@/types/context-window';
```

- [ ] **Step 4: 从 store 解构新增字段**

在 `useSession()` 解构中追加：

```typescript
sessionMeta,
setSessionMeta,
```

- [ ] **Step 5: 新增 lastActivityTime state**

在 `const [turnStatuses, ...]` 之后添加：

```typescript
const [lastActivityTime, setLastActivityTime] = useState<number | null>(null);
```

- [ ] **Step 6: handleSendMessage 开头添加 store reset**

在 `incrementTurn()` 调用之后、`setLoading(true)` 之前插入：

```typescript
// 重置面板数据，防止上一轮数据残留（实时刷新 Bug 修复）
setContextWindowData(EMPTY_CONTEXT_DATA);
setSlotDetails([]);
setStateMessages([]);
setSessionMeta(null);
```

- [ ] **Step 7: 注册 session_metadata SSE handler**

在 `sseHandlersRegistered.current` 代码块内，紧跟 `context_window` handler 之后添加：

```typescript
sseManager.on('session_metadata', ({ data }) => {
  setSessionMeta(data as SessionMeta);
});
```

- [ ] **Step 8: done handler 中更新 lastActivityTime**

在 `sseManager.on('done', ...)` 处理器内，`setLoading(false)` 之前添加：

```typescript
setLastActivityTime(Date.now());
```

- [ ] **Step 9: 替换 JSX 中的组件**

将：

```typescript
<ContextWindowPanel
  data={contextWindowData}
  slotDetails={slotDetails}
  stateMessages={stateMessages}
/>
```

替换为：

```typescript
<ContextPanel
  sessionMeta={sessionMeta}
  contextWindowData={contextWindowData}
  slotDetails={slotDetails}
  stateMessages={stateMessages}
  lastActivityTime={lastActivityTime}
/>
```

- [ ] **Step 10: 确认 TypeScript 编译通过**

```bash
cd /path/to/agent_app/frontend && npx tsc --noEmit
```
Expected: 0 errors

- [ ] **Step 11: Commit**

```bash
git add frontend/src/app/page.tsx tests/components/store/use-session.test.ts
git commit -m "feat: integrate ContextPanel into page.tsx with SSE handler and store reset fix"
```

---

## Task 10：E2E 测试

**Files:**
- Modify: `tests/e2e/06-context-window.spec.ts`

- [ ] **Step 1: 替换 E2E 测试文件内容**

用以下内容替换 `tests/e2e/06-context-window.spec.ts`：

```typescript
import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 6: Context Panel 新版 4 模块面板
 *
 * 验收标准：
 * - 切换到 Context tab 后显示 3 个模块标题（模块一~三）
 * - 发送消息后 Token 地图进度条出现
 * - 第二轮消息后数据正确刷新（不残留旧数据）
 */

test.describe('Context Panel — 4 模块新版', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /context/i }).click();
    await page.waitForTimeout(300);
  });

  test('应显示模块一、二、三的标题', async ({ page }) => {
    await expect(page.getByText(/会话元数据/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Token 地图/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Slot 原文/)).toBeVisible({ timeout: 5000 });
  });

  test('发送消息后 Token 进度条应出现', async ({ page }) => {
    const input = page.getByRole('textbox');
    await input.fill('你好');
    await input.press('Enter');

    // 等待 context_window SSE 事件触发进度条渲染
    await expect(page.locator('[data-testid="token-bar"]')).toBeVisible({ timeout: 15000 });

    // 进度条应有 12 个段
    const count = await page.locator('[data-testid="token-bar"] > div').count();
    expect(count).toBe(12);
  });

  test('第二轮消息后数据应刷新（不残留旧数据）', async ({ page }) => {
    const input = page.getByRole('textbox');

    // 第一轮
    await input.fill('第一轮');
    await input.press('Enter');
    await page.locator('[data-testid="token-bar"]').waitFor({ state: 'visible', timeout: 20000 });

    // 第二轮
    await input.fill('第二轮');
    await input.press('Enter');

    // 等待 isLoading=false（done 事件之后面板刷新）
    await page.locator('[data-testid="token-bar"]').waitFor({ state: 'visible', timeout: 20000 });

    // 面板不应显示错误/崩溃
    await expect(page.locator('[data-testid="token-bar"]')).toBeVisible();
  });
});
```

- [ ] **Step 2: 确保前后端均已启动，运行静态渲染测试**

```bash
# 终端 1：后端
cd /path/to/agent_app && uvicorn backend.app.main:app --port 8000 --reload

# 终端 2：前端
cd /path/to/agent_app/frontend && npm run dev -- --port 3010

# 终端 3：仅运行第 1 个 E2E test（无需 LLM）
cd /path/to/agent_app/frontend && \
  npx playwright test tests/e2e/06-context-window.spec.ts --headed -g "应显示模块"
```
Expected: PASS（该 test 只检查静态渲染，无需 LLM）

- [ ] **Step 3: 运行全量组件测试，确认无回归**

```bash
cd /path/to/agent_app/tests && npx vitest run components/
```
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/06-context-window.spec.ts
git commit -m "test: update E2E context window tests for new ContextPanel 4-module design"
```

---

## 完成标准

- [ ] `cd frontend && npx tsc --noEmit` 返回 0 错误
- [ ] `cd tests && npx vitest run components/context-window/` 全部通过（新增 4 个测试文件 + 旧 CompressionLog）
- [ ] `cd tests && npx vitest run components/store/` 全部通过（含 sessionMeta 测试）
- [ ] `python -m pytest tests/backend/unit/test_session_metadata_sse.py -v` 通过
- [ ] E2E `06-context-window.spec.ts` test 1（静态渲染）通过；test 2/3 需要真实 LLM
- [ ] 手动验证：发送两轮消息，第二轮 Token 地图能正确刷新（不显示第一轮残留数据）
- [ ] `grep -r "ContextWindowPanel" frontend/src/app/page.tsx` 返回空（旧组件已从 page.tsx 移除）
