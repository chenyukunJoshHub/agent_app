# Context UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 动态化 Context 面板（展示全部 10 个 Slot）、清理链路面板重复内容、强化 Turn 边界感知、并将后端 state["messages"] 同步到前端。

**Architecture:** 从类型层（types）→ Store 层 → 后端 done 事件 → 组件层 → 页面层，逐层推进；每一层变更都有对应测试；组件改动遵循 TDD（先写 Vitest 单元测试，再改组件，最后 E2E 验证）。

**Tech Stack:** Next.js 15 + TypeScript + Zustand + Vitest + Playwright；后端 FastAPI + LangGraph（Python）

**Spec:** `docs/superpowers/specs/2026-03-24-context-ui-redesign.md`

---

## 文件地图

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/types/context-window.ts` | 修改 | 新增 `EMPTY_CONTEXT_DATA`、`summary_text` 字段、扩展 `rawToCanonical` |
| `frontend/src/types/trace.ts` | 修改 | `TraceEvent` 增加 `turnId?: string` |
| `frontend/src/store/use-session.ts` | 修改 | 新增 `stateMessages`、`currentTurnId`、`turnCounter`，更新 `clearMessages` |
| `frontend/src/components/ExecutionTracePanel.tsx` | 修改 | 删除 Slot 快照区块、增加 Turn 分隔线和完成/失败 badge |
| `frontend/src/components/ContextWindowPanel.tsx` | 修改 | 始终渲染、修复 `rawToCanonical`、接受 `stateMessages` prop 用于 Slot ⑧ 展开 |
| `frontend/src/components/MessageList.tsx` | 修改 | 支持 `tool` role 气泡、`StateMessage` 渲染、压缩通知气泡 |
| `frontend/src/components/CompressionLog.tsx` | 修改 | 支持 `summary_text` 展开区块 |
| `frontend/src/app/page.tsx` | 修改 | 更新 `done` handler（解析 messages）、去掉"暂无数据"分支、传新 props |
| `backend/app/agent/middleware/trace.py` | 修改 | `done` 事件 payload 追加 `messages` 字段 |
| `tests/components/context-window/` | 新建/修改 | EMPTY_CONTEXT_DATA 渲染、10-slot 展示 |
| `tests/components/execution-trace/` | 新建/修改 | Turn 分隔线渲染 |
| `tests/components/message-list/` | 新建/修改 | tool 气泡、压缩气泡 |
| `tests/e2e/06-context-window.spec.ts` | 修改 | 验证 10-slot 初始展示 |
| `tests/e2e/09-turn-markers.spec.ts` | 新建 | 验证 Turn 分隔线 E2E |

---

## Task 1: 删除 ExecutionTracePanel 中的 Context Slot 快照

**文件：**
- Modify: `frontend/src/components/ExecutionTracePanel.tsx`
- Modify: `frontend/src/app/page.tsx`

### 背景

`ExecutionTracePanel` 顶部有一个"Context Slot 内容快照"区块（`slotDetails.length > 0` 包裹），与右侧 Context 面板重复。

- [ ] **Step 1.1: 删除 ExecutionTracePanel 中的冗余代码**

在 `frontend/src/components/ExecutionTracePanel.tsx` 中执行以下删除：

1. 删除第 9 行的 `SlotDetail` import：
   ```typescript
   // 删除这行：
   import type { SlotDetail } from '@/types/context-window';
   ```

2. 删除 props 接口中的 `slotDetails` 字段（第 14 行）：
   ```typescript
   // 改前：
   interface ExecutionTracePanelProps {
     traceEvents: TraceEvent[];
     slotDetails: SlotDetail[];
   }
   // 改后：
   interface ExecutionTracePanelProps {
     traceEvents: TraceEvent[];
   }
   ```

3. 删除 `openSlots` state（第 55 行）：
   ```typescript
   // 删除这行：
   const [openSlots, setOpenSlots] = useState<Record<string, boolean>>({});
   ```

4. 删除 `toggleSlot` handler（第 69–71 行）：
   ```typescript
   // 删除这三行：
   const toggleSlot = (id: string) => {
     setOpenSlots((prev) => ({ ...prev, [id]: !prev[id] }));
   };
   ```

5. 删除函数签名中的 `slotDetails` 解构（第 53 行）：
   ```typescript
   // 改前：
   export function ExecutionTracePanel({ traceEvents, slotDetails }: ExecutionTracePanelProps) {
   // 改后：
   export function ExecutionTracePanel({ traceEvents }: ExecutionTracePanelProps) {
   ```

6. 删除整个 `slotDetails.length > 0` 区块（第 86–127 行，含 `<section>` 标签）

- [ ] **Step 1.2: 更新 page.tsx 调用处**

在 `frontend/src/app/page.tsx` 中，找到第 393 行的 `<ExecutionTracePanel>` 调用：
```typescript
// 改前：
<ExecutionTracePanel traceEvents={traceEvents} slotDetails={slotDetails} />
// 改后：
<ExecutionTracePanel traceEvents={traceEvents} />
```

- [ ] **Step 1.3: TypeScript 编译检查**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx tsc --noEmit
```

期望：0 errors

- [ ] **Step 1.4: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/components/ExecutionTracePanel.tsx frontend/src/app/page.tsx
git commit -m "refactor: remove duplicate Context Slot snapshot from ExecutionTracePanel"
```

---

## Task 2: 类型层 — EMPTY_CONTEXT_DATA + TraceEvent.turnId + StateMessage

**文件：**
- Modify: `frontend/src/types/context-window.ts`
- Modify: `frontend/src/types/trace.ts`

所有组件和 Store 依赖类型层，先把类型定义好。

- [ ] **Step 2.1: 为 TraceEvent 添加 turnId 字段**

在 `frontend/src/types/trace.ts` 中，将接口改为：
```typescript
export interface TraceEvent {
  id: string;
  timestamp: string;
  stage: string;
  step: string;
  status: 'start' | 'ok' | 'skip' | 'error' | string;
  payload: Record<string, unknown>;
  turnId?: string;  // 新增：前端标注的 turn 归属
}
```

- [ ] **Step 2.2: 在 context-window.ts 中添加 StateMessage 类型**

在 `frontend/src/types/context-window.ts` 末尾追加：
```typescript
/** 后端 state["messages"] 中的单条消息 */
export interface StateMessage {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string; // 仅 role=tool 时有值
}
```

- [ ] **Step 2.3: 在 CompressionEvent 中添加 summary_text**

在 `frontend/src/types/context-window.ts` 的 `CompressionEvent` 接口末尾（第 83 行后）追加：
```typescript
/** 压缩摘要文本（后端可选提供） */
summary_text?: string;
```

- [ ] **Step 2.4: 新增 EMPTY_CONTEXT_DATA 常量**

在 `frontend/src/types/context-window.ts` 末尾追加，放在 `SLOT_DISPLAY_NAMES` 之后：
```typescript
/** 初始空状态 Context 数据，展示全部 10 个 Slot 且 token 均为 0 */
export const EMPTY_CONTEXT_DATA: ContextWindowData = {
  budget: {
    model_context_window: 200000,
    working_budget: 32768,
    slots: {
      system: 0,
      active_skill: 0,
      few_shot: 0,
      rag: 0,
      episodic: 0,
      procedural: 0,
      tools: 0,
      history: 0,
      output_format: 0,
      user_input: 0,
    },
    usage: {
      total_used: 0,
      total_remaining: 32768,
      input_budget: 0,
      output_reserve: 0,
      autocompact_buffer: 0,
    },
  },
  slotUsage: [
    { name: 'system',       displayName: '① System Prompt',   allocated: 0, used: 0, color: '#5E6AD2' },
    { name: 'active_skill', displayName: '② 活跃技能',          allocated: 0, used: 0, color: '#8B5CF6' },
    { name: 'few_shot',     displayName: '③ 动态 Few-shot',    allocated: 0, used: 0, color: '#06B6D4' },
    { name: 'rag',          displayName: '④ RAG 背景知识',      allocated: 0, used: 0, color: '#10B981' },
    { name: 'episodic',     displayName: '⑤ 用户画像',          allocated: 0, used: 0, color: '#F59E0B' },
    { name: 'procedural',   displayName: '⑥ 程序性记忆',        allocated: 0, used: 0, color: '#EF4444' },
    { name: 'tools',        displayName: '⑦ 工具定义',          allocated: 0, used: 0, color: '#3B82F6' },
    { name: 'history',      displayName: '⑧ 会话历史',          allocated: 0, used: 0, color: '#6366F1' },
    { name: 'output_format',displayName: '⑨ 输出格式规范',      allocated: 0, used: 0, color: '#EC4899' },
    { name: 'user_input',   displayName: '⑩ 本轮用户输入',      allocated: 0, used: 0, color: '#22C55E' },
  ],
  compressionEvents: [],
};
```

注意：`SlotUsage.name` 的类型是 `keyof SlotAllocation`，而 `SlotAllocation` 的 `output_format` 和 `user_input` 是可选字段（`?: number`），TypeScript 允许将可选 key 用作 keyof，但需要确认编译通过。

- [ ] **Step 2.5: 将 SlotAllocation 中 output_format/user_input 改为必填**

在 `frontend/src/types/context-window.ts` 中，将 `SlotAllocation` 接口的两个可选字段改为必填（必须做，避免后续 TypeScript 错误）：
```typescript
// 改前：
output_format?: number;
user_input?: number;
// 改后：
output_format: number;
user_input: number;
```

验证无破坏性引用：
```bash
grep -r "output_format\|user_input" \
  "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend/src" \
  --include="*.ts" --include="*.tsx" -l
```

- [ ] **Step 2.6: TypeScript 编译检查**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx tsc --noEmit
```

期望：0 errors

- [ ] **Step 2.6: Commit**

```bash
git add frontend/src/types/
git commit -m "feat: add EMPTY_CONTEXT_DATA, StateMessage, turnId, summary_text types"
```

---

## Task 3: Store 层 — turnId + stateMessages

**文件：**
- Modify: `frontend/src/store/use-session.ts`
- Test: `tests/components/store/use-session.test.ts`（若不存在则新建）

- [ ] **Step 3.1: 写 failing 测试（Store 新字段）**

新建或修改 `tests/components/store/use-session.test.ts`，添加：

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useSession } from '@/store/use-session';

beforeEach(() => {
  useSession.getState().clearMessages();
});

describe('Turn tracking', () => {
  it('初始 turnCounter 为 0，currentTurnId 为 null', () => {
    const state = useSession.getState();
    expect(state.turnCounter).toBe(0);
    expect(state.currentTurnId).toBeNull();
  });

  it('incrementTurn 后 turnCounter+1，currentTurnId 更新', () => {
    useSession.getState().incrementTurn();
    const state = useSession.getState();
    expect(state.turnCounter).toBe(1);
    expect(state.currentTurnId).toBe('turn_1');
  });

  it('clearMessages 重置 turnCounter 和 currentTurnId', () => {
    useSession.getState().incrementTurn();
    useSession.getState().clearMessages();
    const state = useSession.getState();
    expect(state.turnCounter).toBe(0);
    expect(state.currentTurnId).toBeNull();
  });

  it('addTraceEvent 自动打上 currentTurnId', () => {
    useSession.getState().incrementTurn();
    useSession.getState().addTraceEvent({
      id: 'e1', timestamp: new Date().toISOString(),
      stage: 'react', step: 'start', status: 'start', payload: {},
    });
    const { traceEvents } = useSession.getState();
    expect(traceEvents[0].turnId).toBe('turn_1');
  });
});

describe('stateMessages', () => {
  it('初始 stateMessages 为空数组', () => {
    expect(useSession.getState().stateMessages).toEqual([]);
  });

  it('setStateMessages 更新 stateMessages', () => {
    useSession.getState().setStateMessages([
      { role: 'user', content: 'hello' },
    ]);
    expect(useSession.getState().stateMessages).toHaveLength(1);
  });

  it('clearMessages 重置 stateMessages', () => {
    useSession.getState().setStateMessages([{ role: 'user', content: 'hi' }]);
    useSession.getState().clearMessages();
    expect(useSession.getState().stateMessages).toEqual([]);
  });
});
```

- [ ] **Step 3.2: 运行测试，确认 RED**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/store/use-session.test.ts 2>&1 | tail -20
```

期望：FAIL，提示 `incrementTurn is not a function` 或 `turnCounter` 不存在。

- [ ] **Step 3.3: 实现 Store 新字段和 actions**

在 `frontend/src/store/use-session.ts` 中：

1. 在 `import` 处添加 `StateMessage` 和 `EMPTY_CONTEXT_DATA`：
   ```typescript
   import type { ContextWindowData, StateMessage } from '@/types/context-window';
   import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
   ```

2. 在 `SessionState` 接口中添加新字段：
   ```typescript
   // Turn tracking
   currentTurnId: string | null;
   turnCounter: number;
   // Backend state messages
   stateMessages: StateMessage[];
   ```

3. 在 `SessionState` 接口中添加新 actions：
   ```typescript
   incrementTurn: () => void;
   setStateMessages: (msgs: StateMessage[]) => void;
   ```

4. 在 `SessionState` 接口中，将 `contextWindowData` 类型从可空改为非空，并同步更新 `setContextWindowData` 签名：
   ```typescript
   // 改前：
   contextWindowData: ContextWindowData | null;
   setContextWindowData: (data: ContextWindowData | null) => void;
   // 改后：
   contextWindowData: ContextWindowData;
   setContextWindowData: (data: ContextWindowData) => void;
   ```

5. 在 `create<SessionState>()` 初始值中添加：
   ```typescript
   currentTurnId: null,
   turnCounter: 0,
   stateMessages: [],
   contextWindowData: EMPTY_CONTEXT_DATA, // 改为 EMPTY_CONTEXT_DATA（原来是 null）
   ```

5. 实现 `incrementTurn`：
   ```typescript
   incrementTurn: () => {
     set((state) => {
       const turnCounter = state.turnCounter + 1;
       return { turnCounter, currentTurnId: `turn_${turnCounter}` };
     });
   },
   ```

6. 实现 `setStateMessages`：
   ```typescript
   setStateMessages: (msgs) => set({ stateMessages: msgs }),
   ```

7. 修改 `addTraceEvent`，自动打上 `turnId`：
   ```typescript
   addTraceEvent: (event) => {
     set((state) => ({
       traceEvents: [
         ...state.traceEvents,
         { ...event, turnId: state.currentTurnId ?? undefined },
       ].slice(-500),
     }));
   },
   ```

8. 修改 `clearMessages`，重置新字段：
   ```typescript
   clearMessages: () =>
     set({
       messages: [],
       stateMessages: [],
       traceEvents: [],
       tokenUsed: 0,
       contextWindowData: EMPTY_CONTEXT_DATA,
       slotDetails: [],
       currentTurnId: null,
       turnCounter: 0,
     }),
   ```

- [ ] **Step 3.4: 运行测试，确认 GREEN**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/store/use-session.test.ts 2>&1 | tail -20
```

期望：全部 PASS

- [ ] **Step 3.5: TypeScript 编译检查**

```bash
npx tsc --noEmit
```

期望：0 errors

- [ ] **Step 3.6: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/store/use-session.ts tests/components/store/
git commit -m "feat: add turnId tracking and stateMessages to session store"
```

---

## Task 4: 后端 — done 事件附带 messages

**文件：**
- Modify: `backend/app/agent/middleware/trace.py`
- Test: `tests/backend/unit/test_trace_done_messages.py`（新建）

`done` 事件（第 256–264 行）目前只发送 `answer` 和 `finish_reason`，需追加序列化的 `messages`。

- [ ] **Step 4.0: 写 failing 后端单元测试**

新建 `tests/backend/unit/test_trace_done_messages.py`：

```python
import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage


def _serialize_message(msg):
    """从 trace.py 提取的序列化函数（先在此处实现，再搬到 trace.py）"""
    role_map = {
        "HumanMessage": "user",
        "AIMessage": "assistant",
        "ToolMessage": "tool",
        "SystemMessage": "system",
    }
    role = role_map.get(type(msg).__name__, "assistant")
    serialized = {"role": role, "content": str(msg.content or "")}
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        serialized["tool_calls"] = [
            {"id": tc.get("id", ""), "type": "function",
             "function": {"name": tc.get("name", ""), "arguments": str(tc.get("args", {}))}}
            for tc in msg.tool_calls
        ]
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        serialized["tool_call_id"] = msg.tool_call_id
    return serialized


class TestSerializeMessage:
    def test_human_message_serializes_to_user(self):
        msg = HumanMessage(content="hello")
        result = _serialize_message(msg)
        assert result["role"] == "user"
        assert result["content"] == "hello"

    def test_ai_message_serializes_to_assistant(self):
        msg = AIMessage(content="hi there")
        result = _serialize_message(msg)
        assert result["role"] == "assistant"

    def test_tool_message_serializes_to_tool_with_tool_call_id(self):
        msg = ToolMessage(content="result", tool_call_id="tc1")
        result = _serialize_message(msg)
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "tc1"

    def test_system_message_filtered_out_by_frontend_roles(self):
        """SystemMessage 序列化后 role='system'，前端过滤掉，不在 user/assistant/tool 中"""
        msg = SystemMessage(content="system prompt")
        result = _serialize_message(msg)
        # 确认 role='system'，前端过滤逻辑会排除它
        assert result["role"] == "system"

    def test_filter_keeps_only_frontend_roles(self):
        messages = [
            HumanMessage(content="hi"),
            SystemMessage(content="sys"),
            AIMessage(content="hello"),
            ToolMessage(content="result", tool_call_id="tc1"),
        ]
        serialized = [_serialize_message(m) for m in messages]
        filtered = [m for m in serialized if m["role"] in ("user", "assistant", "tool")]
        assert len(filtered) == 3
        assert filtered[0]["role"] == "user"
        assert filtered[1]["role"] == "assistant"
        assert filtered[2]["role"] == "tool"
```

运行确认 RED（测试文件引用的 `_serialize_message` 是本地定义，测试本身应该 PASS；这步的目的是确认测试结构和逻辑正确）：
```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
python -m pytest tests/backend/unit/test_trace_done_messages.py -v 2>&1 | tail -20
```

期望：全部 PASS（验证序列化逻辑正确后再搬入 trace.py）

- [ ] **Step 4.1: 修改 trace.py 的 done 事件**

在 `backend/app/agent/middleware/trace.py` 第 251–264 行的 `done` 事件中，将：
```python
await self._send_sse_event(
    "done",
    {
        "answer": last_message.content,
        "finish_reason": getattr(last_message, "response_metadata", {}).get(
            "finish_reason", "unknown"
        ),
    },
)
```

改为：
```python
# 序列化完整 messages 列表供前端同步
def _serialize_message(msg: Any) -> dict:
    role_map = {
        "HumanMessage": "user",
        "AIMessage": "assistant",
        "ToolMessage": "tool",
        "SystemMessage": "system",
    }
    role = role_map.get(type(msg).__name__, "assistant")
    serialized: dict = {"role": role, "content": str(msg.content or "")}
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        serialized["tool_calls"] = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": str(tc.get("args", {})),
                },
            }
            for tc in msg.tool_calls
        ]
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        serialized["tool_call_id"] = msg.tool_call_id
    return serialized

_all_messages = [_serialize_message(m) for m in messages]
# 仅保留前端 StateMessage 支持的 role（user/assistant/tool），过滤掉 system
serialized_messages = [m for m in _all_messages if m["role"] in ("user", "assistant", "tool")]

await self._send_sse_event(
    "done",
    {
        "answer": last_message.content,
        "finish_reason": getattr(last_message, "response_metadata", {}).get(
            "finish_reason", "unknown"
        ),
        "messages": serialized_messages,
    },
)
```

注意：`_serialize_message` 是局部辅助函数，定义在 `if messages:` 块内部。

- [ ] **Step 4.2: 手动验证（无自动测试）**

启动后端后发送一条消息，检查 SSE 输出中 `done` 事件的 data 字段包含 `messages` 数组：
```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
# 在另一个终端启动后端
# curl 测试（替换 session_id）
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"你好","session_id":"test","user_id":"dev"}' \
  2>/dev/null | grep "done" | head -5
```

期望：`done` 行的 JSON 中包含 `"messages":[...]`

- [ ] **Step 4.3: Python 语法检查**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/backend"
python -m py_compile app/agent/middleware/trace.py && echo "OK"
```

期望：`OK`

- [ ] **Step 4.4: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add backend/app/agent/middleware/trace.py
git commit -m "feat: append serialized messages to done SSE event payload"
```

---

## Task 5: ExecutionTracePanel — Turn 分隔线

**文件：**
- Modify: `frontend/src/components/ExecutionTracePanel.tsx`
- Test: `tests/components/execution-trace/ExecutionTracePanel.test.tsx`

- [ ] **Step 5.1: 写 failing 测试**

新建 `tests/components/execution-trace/ExecutionTracePanel.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import type { TraceEvent } from '@/types/trace';

const makeEvent = (id: string, turnId?: string): TraceEvent => ({
  id,
  timestamp: new Date().toISOString(),
  stage: 'react',
  step: 'some_step',
  status: 'ok',
  payload: {},
  turnId,
});

describe('ExecutionTracePanel Turn markers', () => {
  it('无事件时不渲染 Turn 分隔线', () => {
    render(<ExecutionTracePanel traceEvents={[]} />);
    expect(screen.queryByTestId('turn-divider')).toBeNull();
  });

  it('有 turnId 的事件渲染 Turn 分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_1')];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(1);
    expect(screen.getByText(/Turn #1/)).toBeInTheDocument();
  });

  it('两个不同 turnId 渲染两条分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_2')];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(2);
  });

  it('turnId 为 undefined 的事件渲染 Pre-session 分隔线', () => {
    const events = [makeEvent('e1', undefined)];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getByText(/Pre-session/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 5.2: 运行测试，确认 RED**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/execution-trace/ExecutionTracePanel.test.tsx 2>&1 | tail -20
```

期望：FAIL

- [ ] **Step 5.3: 实现 Turn 分隔线渲染**

在 `frontend/src/components/ExecutionTracePanel.tsx` 中，替换"事件流水"的 `<div className="divide-y divide-border">` 内部渲染逻辑：

1. 在组件顶部（现有 `useMemo` 之后）添加分组逻辑：
   ```typescript
   // 按 turnId 分组，保留原始顺序
   const groupedEvents = useMemo(() => {
     const groups: Array<{ turnId: string | undefined; events: TraceEvent[] }> = [];
     for (const evt of traceEvents) {
       const last = groups[groups.length - 1];
       if (!last || last.turnId !== evt.turnId) {
         groups.push({ turnId: evt.turnId, events: [evt] });
       } else {
         last.events.push(evt);
       }
     }
     return groups;
   }, [traceEvents]);
   ```

2. 在 JSX 中，将平铺的 `traceEvents.map(...)` 替换为分组渲染：
   ```tsx
   <div className="divide-y divide-border">
     {groupedEvents.map((group, groupIdx) => {
       const turnNumber = group.turnId
         ? parseInt(group.turnId.replace('turn_', ''), 10)
         : null;
       const firstEvent = group.events[0];

       return (
         <div key={group.turnId ?? `pre_${groupIdx}`}>
           {/* Turn 分隔线 */}
           <div
             data-testid="turn-divider"
             className="flex items-center gap-2 px-3 py-1.5 bg-primary/5 border-b border-primary/20"
           >
             <div className="flex-1 h-px bg-border" />
             <span className="text-[11px] text-text-muted px-2 shrink-0">
               {turnNumber !== null
                 ? `Turn #${turnNumber}  ${formatTime(firstEvent?.timestamp ?? '')}`
                 : 'Pre-session'}
             </span>
             <div className="flex-1 h-px bg-border" />
           </div>

           {/* 该 Turn 的事件列表 */}
           {group.events.map((evt, idx) => {
             // 此处放原有的单条事件渲染逻辑（ToolCallCard 分支 + 普通事件 motion.div）
             // 保持原有逻辑不变，只是从原来的顶层 map 移入此 map
             if (evt.stage === 'tools') {
               return (
                 <ToolCallCard
                   key={evt.id}
                   toolName={String(evt.payload.tool_name ?? evt.step)}
                   status={evt.status as 'start' | 'ok' | 'error' | 'skip'}
                   args={evt.payload.args as Record<string, unknown> | undefined}
                   contentPreview={evt.payload.content_preview as string | undefined}
                   contentLength={evt.payload.content_length as number | undefined}
                   errorMessage={evt.payload.error as string | undefined}
                   timestamp={evt.timestamp}
                 />
               );
             }
             const expanded = !!openIds[evt.id];
             return (
               <motion.div
                 key={evt.id}
                 initial={{ opacity: 0, y: 4 }}
                 animate={{ opacity: 1, y: 0 }}
                 transition={{ duration: 0.12, delay: Math.min(0.3, idx * 0.01) }}
                 className="px-3 py-2"
               >
                 {/* 将原 ExecutionTracePanel.tsx 第 166–205 行内容完整复制到此处，包括：
                     - button.w-full.text-left（含 onClick toggle）
                     - 内部 div.flex.items-center.justify-between.gap-2
                     - ChevronDown/ChevronRight 图标
                     - stage label span、step text span
                     - status badge span、timestamp span
                     - expanded 时的 <pre> JSON 展示
                     注意：delay 现在基于组内 idx 而非全局 idx，是预期行为变化 */}
               </motion.div>
             );
           })}
         </div>
       );
     })}
   </div>
   ```

3. Turn 完成/失败 badge 通过 store 传入（`page.tsx` 层处理）：在 `ExecutionTracePanel` 中接受新的可选 prop：
   ```typescript
   interface ExecutionTracePanelProps {
     traceEvents: TraceEvent[];
     turnStatuses?: Record<string, 'done' | 'error'>; // turnId -> status
   }
   ```
   在每组末尾渲染：
   ```tsx
   {group.turnId && turnStatuses?.[group.turnId] && (
     <div className={`px-3 py-1 text-xs ${
       turnStatuses[group.turnId] === 'done'
         ? 'text-success-text'
         : 'text-error-text'
     }`}>
       {turnStatuses[group.turnId] === 'done'
         ? `✓ Turn #${turnNumber} 完成 · ${group.events.length} 个事件`
         : `✗ Turn #${turnNumber} 失败`}
     </div>
   )}
   ```

- [ ] **Step 5.4: 运行测试，确认 GREEN**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/execution-trace/ExecutionTracePanel.test.tsx 2>&1 | tail -20
```

期望：全部 PASS

- [ ] **Step 5.5: TypeScript 编译检查**

```bash
npx tsc --noEmit
```

- [ ] **Step 5.6: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/components/ExecutionTracePanel.tsx \
        tests/components/execution-trace/
git commit -m "feat: add Turn dividers and completion badges to ExecutionTracePanel"
```

---

## Task 6: ContextWindowPanel — 10 Slot 空状态 + Slot ⑧ 预览

**文件：**
- Modify: `frontend/src/components/ContextWindowPanel.tsx`
- Test: `tests/components/context-window/ContextWindowPanel.test.tsx`

- [ ] **Step 6.1: 写 failing 测试**

在 `tests/components/context-window/ContextWindowPanel.test.tsx` 中添加（或新建）：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ContextWindowPanel } from '@/components/ContextWindowPanel';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

describe('ContextWindowPanel with EMPTY_CONTEXT_DATA', () => {
  it('Slot 预算分解区块展示全部 10 行（含 ⑨ 和 ⑩）', () => {
    render(<ContextWindowPanel data={EMPTY_CONTEXT_DATA} />);
    // 在 slot-breakdown testid 范围内查找 ⑨/⑩，确保是 Slot 分解区块而非 category 区块
    const breakdown = screen.getByTestId('slot-breakdown');
    expect(within(breakdown).getByText(/⑨ 输出格式规范/)).toBeInTheDocument();
    expect(within(breakdown).getByText(/⑩ 本轮用户输入/)).toBeInTheDocument();
  });

  it('Slot ⑨ 和 ⑩ 出现在 category 汇总中（当 tokens > 0）', () => {
    // 给 output_format 和 user_input 注入非零数据以触发 category 显示
    const data = {
      ...EMPTY_CONTEXT_DATA,
      slotUsage: EMPTY_CONTEXT_DATA.slotUsage.map(s =>
        s.name === 'output_format' ? { ...s, used: 100 } :
        s.name === 'user_input' ? { ...s, used: 200 } : s
      ),
      budget: {
        ...EMPTY_CONTEXT_DATA.budget,
        slots: { ...EMPTY_CONTEXT_DATA.budget.slots, output_format: 100, user_input: 200 },
        usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 300 },
      },
    };
    render(<ContextWindowPanel data={data} />);
    // 这两个 data-testid 在 Task 6.3 中新增，此测试在实现前应 FAIL
    expect(screen.getByTestId('context-row-output_format')).toBeInTheDocument();
    expect(screen.getByTestId('context-row-user_input')).toBeInTheDocument();
  });
});
```

- [ ] **Step 6.2: 运行测试，确认 RED**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/context-window/ContextWindowPanel.test.tsx 2>&1 | tail -20
```

期望：FAIL

- [ ] **Step 6.3: 修复 ContextWindowPanel 的 rawToCanonical 和 categoryUsage**

在 `frontend/src/components/ContextWindowPanel.tsx` 中：

1. 扩展 `rawToCanonical`（第 82–95 行），将 ⑨/⑩ 映射到独立 canonical key：
   ```typescript
   const rawToCanonical: Record<string, string> = {
     system: 'system',
     skill_registry: 'system',
     skill_protocol: 'system',
     output_format: 'output_format',   // 改：原来映射到 'system'
     active_skill: 'active_skill',
     few_shot: 'few_shot',
     rag: 'rag',
     episodic: 'episodic',
     procedural: 'procedural',
     tools: 'tools',
     history: 'history',
     user_input: 'user_input',         // 改：原来映射到 'history'
   };
   ```

2. 扩展 `categoryLabels`：
   ```typescript
   const categoryLabels: Record<string, string> = {
     system: '① System Prompt',
     active_skill: '② 活跃技能',
     few_shot: '③ 动态 Few-shot',
     rag: '④ RAG 背景知识',
     episodic: '⑤ 用户画像',
     procedural: '⑥ 程序性记忆',
     tools: '⑦ 工具定义',
     history: '⑧ 会话历史',
     output_format: '⑨ 输出格式规范',
     user_input: '⑩ 本轮用户输入',
   };
   ```

3. 扩展 `aggregate` 初始化，加入 `output_format` 和 `user_input`：
   ```typescript
   const aggregate: Record<string, number> = {
     system: 0,
     active_skill: 0,
     few_shot: 0,
     rag: 0,
     episodic: 0,
     procedural: 0,
     tools: 0,
     history: 0,
     output_format: 0,
     user_input: 0,
   };
   ```

4. 为每个 `context-row-*` 的 `data-testid` 加上 name（若尚未添加），确保 `output_format` 和 `user_input` 可被测试定位：
   ```tsx
   <div
     key={item.name}
     className="flex items-center justify-between text-sm"
     data-testid={`context-row-${item.name}`}
   >
   ```

- [ ] **Step 6.4: 运行测试，确认 GREEN**

```bash
npx vitest run tests/components/context-window/ContextWindowPanel.test.tsx 2>&1 | tail -20
```

期望：全部 PASS

- [ ] **Step 6.5: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/components/ContextWindowPanel.tsx \
        tests/components/context-window/
git commit -m "feat: fix 10-slot rendering in ContextWindowPanel, add slots ⑨ and ⑩"
```

---

## Task 7: page.tsx 串联 — 初始值 + done 事件处理 + Turn 状态

**文件：**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 7.1: 在 page.tsx 顶部定义 turnStatuses 本地 state**

`turnStatuses` 是 UI 展示状态（不需要持久化），在组件 state 里管理。**必须在 done/error handler 之前定义，否则 TypeScript 报错。**

在 `page.tsx` 中已有 `const [showConfirmModal, ...] = useState(...)` 的下方添加：
```typescript
const [turnStatuses, setTurnStatuses] = useState<Record<string, 'done' | 'error'>>({});

const setTurnStatus = (turnId: string, status: 'done' | 'error') => {
  setTurnStatuses(prev => ({ ...prev, [turnId]: status }));
};
```

- [ ] **Step 7.2: 更新 useSession 解构，加入新 actions**

在 `useSession()` 解构中加入新 actions：
```typescript
const {
  messages,
  isLoading,
  traceEvents,
  slotDetails,
  contextWindowData,
  stateMessages,          // 新增
  addMessage,
  addTraceEvent,
  setContextWindowData,
  setSlotDetails,
  setStateMessages,       // 新增
  incrementTurn,          // 新增
  setLoading,
  setError,
} = useSession();
```

- [ ] **Step 7.3: 更新 handleSendMessage，调用 incrementTurn**

在 `page.tsx` 的 `handleSendMessage` 函数中，在 `addMessage` 之后、`setLoading(true)` 之前添加：
```typescript
const handleSendMessage = async (message: string) => {
  addMessage({ role: 'user', content: message });
  incrementTurn(); // 新增：生成新 turnId
  setLoading(true);
  ...
```

- [ ] **Step 7.4: 更新 done 事件 handler，解析 messages**

在 `sseManager.on('done', ...)` 处（第 219–223 行）：
```typescript
sseManager.on('done', ({ data }) => {
  clearLoadTimeout();

  // 解析后端 state["messages"]
  const payload = data as { messages?: StateMessage[]; answer?: string };
  if (payload.messages && payload.messages.length > 0) {
    const { messages: frontendMsgs } = useSession.getState();
    // 后端消息数 >= 前端消息数时替换（后端数据更完整）
    if (payload.messages.length >= frontendMsgs.length) {
      setStateMessages(payload.messages);
    }
  }

  // 记录 Turn 完成状态（供 ExecutionTracePanel badge 使用）
  const turnId = useSession.getState().currentTurnId;
  if (turnId) {
    setTurnStatus(turnId, 'done');
  }

  setLoading(false);
  sseManager.disconnect();
});
```

在 `sseManager.on('error', ...)` 处同理添加：
```typescript
const turnId = useSession.getState().currentTurnId;
if (turnId) setTurnStatus(turnId, 'error');
```

同时在 `page.tsx` 顶部 import 处添加 `StateMessage` 的引用（已在 `context-window.ts` 中定义）：
```typescript
import type { SlotDetailsResponse, StateMessage } from '@/types/context-window';
```

- [ ] **Step 7.5: 去掉"暂无数据"占位分支**

将 `page.tsx` 第 395–403 行：
```typescript
{activeTab === 'context' &&
  (contextWindowData ? (
    <ContextWindowPanel data={contextWindowData} slotDetails={slotDetails} />
  ) : (
    <div className="flex h-full items-center justify-center text-sm text-text-muted">
      暂无 Context 数据，请先发起一次请求
    </div>
  ))}
```

改为：
```typescript
{activeTab === 'context' && (
  <ContextWindowPanel
    data={contextWindowData}
    slotDetails={slotDetails}
    stateMessages={stateMessages}
  />
)}
```

注意：`contextWindowData` 初始值现在是 `EMPTY_CONTEXT_DATA`（Store 已在 Task 3 中修改），因此不再需要 null 判断。

- [ ] **Step 7.6: 将 turnStatuses 传给 ExecutionTracePanel**

```typescript
{activeTab === 'chain' && (
  <ExecutionTracePanel
    traceEvents={traceEvents}
    turnStatuses={turnStatuses}
  />
)}
```

- [ ] **Step 7.7: ContextWindowPanel 接受并展示 stateMessages**

在 `frontend/src/components/ContextWindowPanel.tsx` 中：

1. 添加 prop：
   ```typescript
   interface ContextWindowPanelProps {
     data: ContextWindowData;
     slotDetails?: SlotDetail[];
     stateMessages?: import('@/types/context-window').StateMessage[]; // 新增
   }
   ```

2. 在"Slot 预算分解"中，为 `history` 行添加展开预览（使用 `useState` 控制）：
   ```tsx
   {slot.name === 'history' && stateMessages && stateMessages.length > 0 && (
     <details className="mt-1">
       <summary className="text-xs text-text-muted cursor-pointer">
         展开 {stateMessages.length} 条消息
       </summary>
       <div className="mt-1 space-y-0.5 max-h-48 overflow-y-auto">
         {stateMessages.map((msg, i) => (
           <div key={i} className="text-[11px] text-text-secondary">
             <span className="font-mono text-text-muted mr-1">[{msg.role}]</span>
             {(msg.content || '').slice(0, 80)}{(msg.content || '').length > 80 ? '...' : ''}
           </div>
         ))}
       </div>
     </details>
   )}
   ```

- [ ] **Step 7.8: TypeScript 编译检查**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx tsc --noEmit
```

- [ ] **Step 7.9: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/app/page.tsx frontend/src/components/ContextWindowPanel.tsx
git commit -m "feat: wire done event to stateMessages, remove null context guard, add Turn status"
```

---

## Task 8: MessageList — tool 气泡 + 压缩通知气泡

**文件：**
- Modify: `frontend/src/components/MessageList.tsx`
- Modify: `frontend/src/components/CompressionLog.tsx`
- Test: `tests/components/message-list/MessageList.test.tsx`

- [ ] **Step 8.1: 写 failing 测试**

新建 `tests/components/message-list/MessageList.test.tsx`：

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList } from '@/components/MessageList';
import type { CompressionEvent } from '@/types/context-window';
import type { StateMessage } from '@/types/context-window';

const baseMessages = [
  { id: '1', role: 'user' as const, content: '你好', timestamp: Date.now(), tool_calls: [] },
  { id: '2', role: 'assistant' as const, content: '你好！', timestamp: Date.now() },
];

describe('MessageList with stateMessages', () => {
  it('stateMessages 中的 tool role 渲染工具气泡', () => {
    const stateMessages: StateMessage[] = [
      { role: 'tool', content: '搜索结果', tool_call_id: 'tc1' },
    ];
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={stateMessages}
        compressionEvents={[]}
      />
    );
    expect(screen.getByTestId('tool-message-bubble')).toBeInTheDocument();
    expect(screen.getByText('搜索结果')).toBeInTheDocument();
  });
});

describe('MessageList compression notification', () => {
  it('有压缩事件时渲染压缩通知气泡', () => {
    const event: CompressionEvent = {
      id: 'c1',
      timestamp: Date.now(),
      before_tokens: 2000,
      after_tokens: 800,
      tokens_saved: 1200,
      method: 'summarization',
      affected_slots: ['history'],
    };
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={[]}
        compressionEvents={[event]}
      />
    );
    expect(screen.getByTestId('compression-notification')).toBeInTheDocument();
    expect(screen.getByText(/节省 1,200 tokens/)).toBeInTheDocument();
  });

  it('无压缩事件时不渲染压缩通知气泡', () => {
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={[]}
        compressionEvents={[]}
      />
    );
    expect(screen.queryByTestId('compression-notification')).toBeNull();
  });
});
```

- [ ] **Step 8.2: 运行测试，确认 RED**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run tests/components/message-list/MessageList.test.tsx 2>&1 | tail -20
```

期望：FAIL

- [ ] **Step 8.3: 修改 MessageList 组件，支持新 props**

在 `frontend/src/components/MessageList.tsx` 中：

1. 更新 `MessageListProps`：
   ```typescript
   import type { StateMessage, CompressionEvent } from '@/types/context-window';

   interface MessageListProps {
     messages: Message[];
     isLoading: boolean;
     stateMessages?: StateMessage[];         // 新增
     compressionEvents?: CompressionEvent[]; // 新增
   }
   ```

2. 新增 `ToolMessageBubble` 组件：
   ```tsx
   function ToolMessageBubble({ msg }: { msg: StateMessage }) {
     const [expanded, setExpanded] = useState(false);
     return (
       <div
         data-testid="tool-message-bubble"
         className="flex gap-3 mb-3"
       >
         <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-bg-muted border border-border flex items-center justify-center">
           <Wrench className="w-4 h-4 text-text-muted" />
         </div>
         <div className="max-w-[80%] rounded-xl bg-bg-muted border border-border px-3 py-2">
           <p className="text-[11px] text-text-muted mb-1">工具返回</p>
           <button
             className="text-xs text-text-secondary text-left"
             onClick={() => setExpanded(!expanded)}
           >
             {expanded ? msg.content : (msg.content || '').slice(0, 100) + ((msg.content || '').length > 100 ? '...' : '')}
           </button>
         </div>
       </div>
     );
   }
   ```

3. 新增 `CompressionNotification` 组件：
   ```tsx
   function CompressionNotification({ event }: { event: CompressionEvent }) {
     return (
       <div
         data-testid="compression-notification"
         className="flex items-center gap-2 my-3 px-4"
       >
         <div className="flex-1 h-px bg-border" />
         <span className="text-xs text-text-muted shrink-0">
           💾 历史已压缩 · 节省 {event.tokens_saved.toLocaleString()} tokens ({event.method})
         </span>
         <div className="flex-1 h-px bg-border" />
       </div>
     );
   }
   ```

4. 在 `MessageList` 函数中，接收 `stateMessages` 和 `compressionEvents`，并在消息列表末尾渲染：
   ```tsx
   export function MessageList({ messages, isLoading, stateMessages = [], compressionEvents = [] }: MessageListProps) {
     // ...原有逻辑不变...

     return (
       <div className="flex-1 overflow-y-auto p-6">
         <div className="mx-auto max-w-3xl">
           {/* 原有消息渲染 */}
           ...

           {/* tool role 消息气泡（来自 stateMessages） */}
           {stateMessages
             .filter(m => m.role === 'tool')
             .map((msg, i) => (
               <ToolMessageBubble key={`tool_${i}`} msg={msg} />
             ))}

           {/* 压缩通知气泡 */}
           {compressionEvents.map(event => (
             <CompressionNotification key={event.id} event={event} />
           ))}

           {isLoading && /* 原有 loading 动画 */}
         </div>
         <div ref={scrollRef} />
       </div>
     );
   }
   ```

- [ ] **Step 8.4: 运行测试，确认 GREEN**

```bash
npx vitest run tests/components/message-list/MessageList.test.tsx 2>&1 | tail -20
```

期望：全部 PASS

- [ ] **Step 8.5: 更新 page.tsx 传入 stateMessages 和 compressionEvents 给 MessageList**

在 `frontend/src/app/page.tsx` 中找到 `<MessageList>` 调用。

注意：经过 Task 3 的修改，`contextWindowData` 的类型已从 `ContextWindowData | null` 改为 `ContextWindowData`（非空），可以直接访问 `.compressionEvents`。

```typescript
// 改前：
<MessageList messages={messages} isLoading={isLoading} />
// 改后：
<MessageList
  messages={messages}
  isLoading={isLoading}
  stateMessages={stateMessages}
  compressionEvents={contextWindowData.compressionEvents}
/>
```

如果编译时仍报类型错误（例如 Task 3 的接口更新未完整执行），可使用安全访问：
```typescript
compressionEvents={contextWindowData?.compressionEvents ?? []}
```

- [ ] **Step 8.6: CompressionLog 支持 summary_text 展开**

在 `frontend/src/components/CompressionLog.tsx` 中，在"Affected slots"区块之后添加：
```tsx
{event.summary_text && (
  <details className="mt-2">
    <summary className="text-xs text-text-muted cursor-pointer">
      查看压缩摘要
    </summary>
    <pre className="mt-1 max-h-48 overflow-auto rounded bg-bg-muted p-2 text-[11px] text-text-secondary whitespace-pre-wrap">
      {event.summary_text}
    </pre>
  </details>
)}
```

- [ ] **Step 8.7: TypeScript 编译检查**

```bash
npx tsc --noEmit
```

- [ ] **Step 8.8: Commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add frontend/src/components/MessageList.tsx \
        frontend/src/components/CompressionLog.tsx \
        frontend/src/app/page.tsx \
        tests/components/message-list/
git commit -m "feat: add tool bubble, compression notification, and CompressionLog summary_text"
```

---

## Task 9: 全量测试 + E2E 验证

**文件：**
- Modify: `tests/e2e/06-context-window.spec.ts`
- Create: `tests/e2e/09-turn-markers.spec.ts`

- [ ] **Step 9.1: 运行全量 Vitest 单元测试**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx vitest run 2>&1 | tail -30
```

期望：全部 PASS，0 failures

- [ ] **Step 9.2: 更新 E2E 测试 — Context 面板初始 10 Slot**

在 `tests/e2e/06-context-window.spec.ts` 中添加：
```typescript
test('初始进入页面，Context 面板展示全部 10 个 Slot（均为 0/0）', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Context/ }).click();
  await expect(page.getByText(/① System Prompt/)).toBeVisible();
  await expect(page.getByText(/⑩ 本轮用户输入/)).toBeVisible();
});
```

- [ ] **Step 9.3: 新建 E2E 测试 — Turn 分隔线**

新建 `tests/e2e/09-turn-markers.spec.ts`：
```typescript
import { test, expect } from '@playwright/test';

test('发送两条消息后，事件流水出现两条 Turn 分隔线', async ({ page }) => {
  await page.goto('/');

  // 发第一条消息
  await page.getByPlaceholder(/输入消息/).fill('你好');
  await page.keyboard.press('Enter');
  await page.waitForSelector('[data-testid="turn-divider"]', { timeout: 15000 });

  // 发第二条消息
  await page.getByPlaceholder(/输入消息/).fill('再说一次');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2000);

  const dividers = page.locator('[data-testid="turn-divider"]');
  await expect(dividers).toHaveCount(2, { timeout: 20000 });
  await expect(page.getByText(/Turn #1/)).toBeVisible();
  await expect(page.getByText(/Turn #2/)).toBeVisible();
});
```

- [ ] **Step 9.4: 运行 E2E 测试（需后端在线）**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app/frontend"
npx playwright test tests/e2e/06-context-window.spec.ts tests/e2e/09-turn-markers.spec.ts \
  --headed 2>&1 | tail -30
```

期望：全部 PASS

- [ ] **Step 9.5: Final commit**

```bash
cd "/Users/josh/Documents/work/learn_test/AI Developer Assistant/agent_app"
git add tests/e2e/
git commit -m "test: add E2E tests for 10-slot context panel and Turn markers"
```

---

## 验收清单

- [ ] 初始页面 Context 面板展示全部 10 个 Slot（均为 0/0）
- [ ] 链路面板无"Context Slot 内容快照"区块
- [ ] 每次 Turn 有分隔线，Turn 结束有 ✓ 完成 badge
- [ ] MessageList 收到 `done` 后显示 tool 气泡
- [ ] Slot ⑧ 展开显示 stateMessages 摘要
- [ ] 压缩发生时 MessageList 有轻量提示气泡
- [ ] `clearMessages` 后 Turn 计数从 #1 重新开始
- [ ] TypeScript 编译 0 errors
- [ ] Vitest 全量通过
- [ ] E2E 关键路径通过
