# Slash Skill Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在前端输入框支持 `/skill-name` 命令调出技能选择列表，后端通过 Hint 模式软提示引导 LLM 优先激活指定 skill，并在 Context Window 面板更新 slot 数据。

**Architecture:** 前端解析 `/` 前缀，通过 `useSkillCommand` hook 管理列表与状态，将 `skill_id` + `invocation_mode` 作为额外 query 参数透传到 GET /api/chat；后端在路由函数签名中接收，注入 `[Skill: X]` 软提示，并在执行前 emit `skill_invoked` SSE 事件更新前端 slot 数据。

**Tech Stack:** Python 3.12, FastAPI, pytest, Next.js 15, React 19, TypeScript, Zustand

**Spec:** `docs/superpowers/specs/2026-03-26-slash-skill-command-design.md`

---

## 文件清单

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/config.py` | 更新 skills_dir default；新增 skill_invocation_mode |
| 修改 | `backend/app/main.py` | lifespan startup 初始化 SkillManager 单例 |
| 修改 | `backend/app/api/skills.py` | get_skill_manager() 走单例，加 503 保护 |
| 修改 | `backend/app/prompt/templates.py` | SKILL_PROTOCOL 新增 [Skill: X] hint 说明 |
| 修改 | `backend/app/api/chat.py` | 路由加参数；hint 注入；skill 验证；emit skill_invoked |
| 新增 | `tests/backend/unit/config/test_settings.py` | skill_invocation_mode 配置测试 |
| 新增 | `tests/backend/unit/api/test_skill_hint.py` | hint 注入逻辑单元测试 |
| 修改 | `frontend/src/lib/sse-manager.ts` | ConnectionOptions 加 skill_id + invocation_mode |
| 新增 | `frontend/src/hooks/useSkillCommand.ts` | skill 列表、前缀过滤、模式状态 |
| 修改 | `frontend/src/components/ChatInput.tsx` | `/` 命令检测、下拉列表 UI、发送逻辑 |
| 修改 | `frontend/src/app/page.tsx` | handleSendMessage 传参；skill_invoked SSE handler |

---

## Task 1: 后端 config — 更新 skills_dir 默认值 + 新增 skill_invocation_mode

**Files:**
- Modify: `backend/app/config.py`
- Modify: `tests/backend/unit/config/test_settings.py`

> **背景**：`config.py` 中 `skills_dir` 字段已存在，default 为 `"../skills"`。本任务仅更新 default 值并新增 `skill_invocation_mode` 字段。

- [ ] **Step 1: 写失败测试**

在 `tests/backend/unit/config/test_settings.py` 中添加：

```python
def test_skill_invocation_mode_default():
    """skill_invocation_mode 默认值应为 'hint'"""
    from app.config import Settings
    s = Settings()
    assert s.skill_invocation_mode == "hint"


def test_skills_dir_default_is_agents_skills():
    """skills_dir 默认值应指向 ~/.agents/skills"""
    from app.config import Settings
    from pathlib import Path
    s = Settings()
    expected = str(Path("~/.agents/skills").expanduser().resolve())
    # default 未展开时检查字符串包含 .agents/skills
    assert ".agents/skills" in s.skills_dir or s.skills_dir == "~/.agents/skills"
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd tests/backend && pytest unit/config/test_settings.py -v -k "skill_invocation_mode or skills_dir_default"
```

期望：FAIL — `Settings` 没有 `skill_invocation_mode` 属性

- [ ] **Step 3: 修改 `backend/app/config.py`**

找到现有 `skills_dir` 字段（约第 164 行），更新 default：

```python
skills_dir: str = Field(
    default="~/.agents/skills",
    description="Skills 目录路径（支持 ~ 展开）。原默认值为 ../skills，升级时请确认 .env 配置。",
)
```

在其后新增：

```python
from typing import Literal   # 如果顶部还没有，添加到 import 区

skill_invocation_mode: Literal["hint", "force"] = Field(
    default="hint",
    description="skill 调用模式：hint（软提示引导 LLM）| force（强制注入，待开发）",
)
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd tests/backend && pytest unit/config/test_settings.py -v -k "skill_invocation_mode or skills_dir_default"
```

期望：PASS

- [ ] **Step 5: 运行全量后端测试确认无回归**

```bash
cd tests/backend && pytest -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py tests/backend/unit/config/test_settings.py
git commit -m "feat: update skills_dir default and add skill_invocation_mode config"
```

---

## Task 2: 后端 main.py — lifespan 初始化 SkillManager + skills.py 单例修复

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/skills.py`

> **背景**：`skills.py` 的 `get_skill_manager()` 目前每次调用 `SkillManager(skills_dir=...)` 直接构造新实例，绕过单例。需在 `main.py` 的 lifespan startup 阶段初始化单例，再修复 `skills.py` 走 `get_instance()`。

- [ ] **Step 1: 修改 `backend/app/main.py`**

在 `lifespan` startup 中，`init_db()` 之后添加 SkillManager 初始化：

```python
from pathlib import Path
from app.skills.manager import SkillManager

# 在 lifespan 函数内 init_db 调用之后：
skills_dir = Path(settings.skills_dir).expanduser().resolve()
SkillManager.get_instance(skills_dir=str(skills_dir))
logger.info(f"✅ [技能] SkillManager 初始化完成，目录: {skills_dir}")
```

- [ ] **Step 2: 修改 `backend/app/api/skills.py`**

将 `get_skill_manager()` 改为走单例，加 503 保护：

```python
def get_skill_manager() -> SkillManager:
    """Get SkillManager singleton. Depends on lifespan initialization in main.py."""
    try:
        return SkillManager.get_instance()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"SkillManager not initialized: {e}")
```

- [ ] **Step 3: 手动验证（无自动测试，用 curl 或启动服务）**

启动服务后运行：

```bash
curl http://localhost:8000/api/skills/
```

期望：返回 `{"skills": [...]}` 而非 500 错误

- [ ] **Step 4: 运行全量后端测试确认无回归**

```bash
cd tests/backend && pytest -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/api/skills.py
git commit -m "feat: initialize SkillManager singleton in lifespan, fix skills API"
```

---

## Task 3: 后端 prompt/templates.py — 新增 [Skill: X] hint 说明

**Files:**
- Modify: `backend/app/prompt/templates.py`

> **背景**：`SKILL_PROTOCOL` 常量已定义 skill 使用协议的 4 条规则。需在其中新增第 5 条，告知 LLM 如何识别并响应用户手动指定的 `[Skill: X]` 前缀。

- [ ] **Step 1: 修改 `backend/app/prompt/templates.py`**

找到 `SKILL_PROTOCOL`（约第 83 行），在 `4. **冲突约定**` 之后新增：

```python
SKILL_PROTOCOL = """
## Skill 使用协议

当你需要使用特定技能时，遵循以下约定：

1. **识别约定**：当用户请求匹配某个 skill 的 description 时，在本次 ReAct 循环中激活该 skill。
2. **调用约定**：使用 read_file 工具读取 skill 的 file_path 获取完整内容。
3. **执行约定**：严格按照 SKILL.md 中的 Instructions 执行，遵循 Examples 的格式。
4. **冲突约定**：同一 turn 内只激活一个 skill，避免 Token 消耗过大。
5. **手动指定约定**：当用户消息以 [Skill: <name>] 开头时，表示用户明确指定使用该 skill。
   你必须优先通过 read_file 工具加载该 skill 的完整内容，再执行用户任务，不得跳过此步骤。
"""
```

- [ ] **Step 2: 运行全量后端测试确认无回归**

```bash
cd tests/backend && pytest -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/prompt/templates.py
git commit -m "feat: add [Skill: X] hint instruction to SKILL_PROTOCOL"
```

---

## Task 4: 后端 chat.py — 路由参数 + hint 注入 + skill_invoked 事件

**Files:**
- Modify: `backend/app/api/chat.py`
- Create: `tests/backend/unit/api/test_skill_hint.py`

> **背景**：chat 路由是 GET，参数通过 query string 传递，不使用 `ChatRequest` BaseModel。需在路由函数签名新增 `skill_id` + `invocation_mode`，并沿调用链透传至执行逻辑。

- [ ] **Step 1: 写失败测试**

新建 `tests/backend/unit/api/test_skill_hint.py`：

```python
"""Tests for skill hint injection logic in chat API."""
import pytest


class TestApplySkillHint:
    """Tests for _apply_skill_hint helper function."""

    def test_hint_mode_prepends_skill_tag(self):
        """hint 模式应在消息头部追加 [Skill: X] 前缀"""
        from app.api.chat import _apply_skill_hint
        result = _apply_skill_hint("帮我修改简历", "algo-sensei", "hint")
        assert result == "[Skill: algo-sensei]\n帮我修改简历"

    def test_no_skill_id_returns_original(self):
        """skill_id 为 None 时返回原始消息"""
        from app.api.chat import _apply_skill_hint
        result = _apply_skill_hint("帮我修改简历", None, "hint")
        assert result == "帮我修改简历"

    def test_force_mode_returns_original_with_warning(self):
        """force 模式暂未实现，静默降级返回 hint 效果"""
        from app.api.chat import _apply_skill_hint
        # force 当前降级为 hint
        result = _apply_skill_hint("帮我修改简历", "algo-sensei", "force")
        assert result == "[Skill: algo-sensei]\n帮我修改简历"

    def test_none_mode_uses_settings_default(self):
        """mode 为 None 时使用 settings.skill_invocation_mode 默认值"""
        from app.api.chat import _apply_skill_hint
        # 默认 mode 是 hint，所以应追加前缀
        result = _apply_skill_hint("帮我修改简历", "algo-sensei", None)
        assert result.startswith("[Skill: algo-sensei]")

    def test_empty_skill_id_returns_original(self):
        """skill_id 为空字符串时返回原始消息"""
        from app.api.chat import _apply_skill_hint
        result = _apply_skill_hint("帮我修改简历", "", "hint")
        assert result == "帮我修改简历"
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd tests/backend && pytest unit/api/test_skill_hint.py -v
```

期望：FAIL — `cannot import name '_apply_skill_hint' from 'app.api.chat'`

- [ ] **Step 3: 在 `backend/app/api/chat.py` 中新增 `_apply_skill_hint` 函数**

在文件顶部 import 区添加（如尚未有）：

```python
from app.config import settings
```

在现有 helper 函数区域（`_format_sse_event` 附近）新增：

```python
def _apply_skill_hint(message: str, skill_id: str | None, mode: str | None) -> str:
    """
    Hint 模式：在消息头部追加 [Skill: X] 软提示，引导 LLM 优先激活指定 skill。

    force 模式当前未实现，静默降级为 hint 行为。
    skill_id 为 None 或空字符串时，直接返回原始消息。
    """
    if not skill_id:
        return message
    effective_mode = mode or settings.skill_invocation_mode
    # force 模式暂未实现，降级为 hint
    if effective_mode in ("hint", "force"):
        return f"[Skill: {skill_id}]\n{message}"
    return message
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
cd tests/backend && pytest unit/api/test_skill_hint.py -v
```

期望：全部 PASS

- [ ] **Step 5: 更新路由函数签名**

找到 `async def chat(` 约第 431 行，新增两个可选参数：

```python
@router.get("")
async def chat(
    message: str,
    session_id: str,
    user_id: str = "dev_user",
    skill_id: str | None = None,
    invocation_mode: str | None = None,
) -> StreamingResponse:
```

- [ ] **Step 6: 在 `chat()` 内调用 hint 注入，透传 skill 信息**

在 `chat()` 函数体中，`api_logger.api_request_received(...)` 调用之前，添加 hint 注入和 skill 验证逻辑：

```python
# Skill hint injection
effective_message = _apply_skill_hint(message, skill_id, invocation_mode)
if skill_id and effective_message != message:
    logger.info(f"💡 [Skill] Hint 注入: skill_id={skill_id}, mode={invocation_mode or settings.skill_invocation_mode}")
```

将 `_run_agent_stream` 调用中的 `message=message` 改为 `message=effective_message`，并透传 skill 信息：

```python
return StreamingResponse(
    _run_agent_stream(
        message=effective_message,
        session_id=session_id,
        user_id=user_id,
        skill_id=skill_id,
        api_logger=api_logger,
        tools_logger=tools_logger,
        sse_logger=sse_logger,
    ),
    media_type="text/event-stream",
    headers={...},
)
```

- [ ] **Step 7: 更新 `_run_agent_stream` 签名，emit skill_invoked 事件**

在 `_run_agent_stream` 函数签名中新增 `skill_id: str | None = None`：

```python
async def _run_agent_stream(
    message: str,
    session_id: str,
    user_id: str,
    api_logger: "ApiLogger",
    tools_logger: "ToolsLogger",
    sse_logger: "SseLogger",
    skill_id: str | None = None,
) -> AsyncIterator[str]:
```

在 `agent_task = asyncio.create_task(...)` 之前，若 `skill_id` 存在则通过 queue 推送事件（`_run_agent_stream` 的主循环统一从 queue 取出并 yield，不要直接 yield）：

```python
# Emit skill_invoked event so frontend can update slot data
if skill_id:
    skill_description = _get_skill_description(skill_id)
    await _queue_put(event_queue, ("skill_invoked", {
        "skill_id": skill_id,
        "description": skill_description or "",
        "mode": invocation_mode or settings.skill_invocation_mode,
    }))
    # 注意：不要再 yield，主循环会从 queue 取出并 yield
```

新增 `_get_skill_description` helper（注意：`scan()` 是公开方法，`_definitions` 是 scan 后的缓存，先调用 scan 再访问）：

```python
def _get_skill_description(skill_id: str) -> str | None:
    """从 SkillManager 单例查询 skill 的 description；不存在时返回 None 并 log warning。"""
    try:
        manager = SkillManager.get_instance()
        definitions = manager.scan()  # 使用公开 scan() 方法，返回 SkillDefinition 列表
        for defn in definitions:
            if defn.id == skill_id or defn.name == skill_id:
                return defn.metadata.description
    except Exception:
        pass
    logger.warning(f"⚠️ [Skill] skill_id='{skill_id}' 不在 active 列表中，hint 已注入但 skill 可能无法匹配")
    return None
```

确保导入 `SkillManager`：

```python
from app.skills.manager import SkillManager
```

- [ ] **Step 8: 运行全量后端测试确认无回归**

```bash
cd tests/backend && pytest -v --tb=short
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/chat.py tests/backend/unit/api/test_skill_hint.py
git commit -m "feat: add skill_id param, hint injection and skill_invoked SSE event to chat API"
```

---

## Task 5: 前端 sse-manager.ts — 扩展 ConnectionOptions

**Files:**
- Modify: `frontend/src/lib/sse-manager.ts`

> **背景**：`ConnectionOptions` 接口当前只有 `message`, `session_id`, `user_id`。若直接传入额外字段，TypeScript 会报错，且 `connect()` 构建 `URLSearchParams` 时也不会包含额外字段。

- [ ] **Step 1: 修改 `frontend/src/lib/sse-manager.ts`**

找到 `ConnectionOptions` 接口，新增两个可选字段：

```typescript
export interface ConnectionOptions {
  message: string;
  session_id: string;
  user_id: string;
  skill_id?: string;         // 新增
  invocation_mode?: string;  // 新增
}
```

在 `connect()` 方法中找到 `URLSearchParams` 构建处，添加条件追加：

```typescript
// 在现有三个 params.append 之后添加：
if (options.skill_id) params.append('skill_id', options.skill_id);
if (options.invocation_mode) params.append('invocation_mode', options.invocation_mode);
```

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
cd frontend && npx tsc --noEmit
```

期望：无类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/sse-manager.ts
git commit -m "feat: extend ConnectionOptions with skill_id and invocation_mode"
```

---

## Task 6: 前端 — 新增 useSkillCommand hook

**Files:**
- Create: `frontend/src/hooks/useSkillCommand.ts`

> **背景**：这个 hook 封装所有与 `/` 命令相关的状态：技能列表拉取与缓存、前缀过滤、模式状态（hint/force）。ChatInput 只需调用此 hook，不直接操作 API 或列表逻辑。

- [ ] **Step 1: 新建 `frontend/src/hooks/useSkillCommand.ts`**

```typescript
'use client';

import { useState, useCallback, useRef } from 'react';
import { getSkillsUrl } from '@/lib/api-config';

export interface Skill {
  name: string;
  description: string;
}

export type InvocationMode = 'hint' | 'force';

export interface UseSkillCommandReturn {
  isOpen: boolean;
  filtered: Skill[];
  selectedMode: InvocationMode;
  setMode: (mode: InvocationMode) => void;
  onInputChange: (value: string) => void;
  onSelect: (skill: Skill) => string;
  onClose: () => void;
}

export function useSkillCommand(): UseSkillCommandReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [filtered, setFiltered] = useState<Skill[]>([]);
  const [selectedMode, setMode] = useState<InvocationMode>('hint');
  const skillsCache = useRef<Skill[] | null>(null);

  const fetchSkills = useCallback(async (): Promise<Skill[]> => {
    if (skillsCache.current !== null) return skillsCache.current;
    try {
      const res = await fetch(getSkillsUrl());
      if (!res.ok) return [];
      const data = await res.json() as { skills: Skill[] };
      skillsCache.current = data.skills ?? [];
      return skillsCache.current;
    } catch {
      return [];
    }
  }, []);

  const onInputChange = useCallback(async (value: string) => {
    if (!value.startsWith('/')) {
      setIsOpen(false);
      setFiltered([]);
      return;
    }
    const prefix = value.slice(1).toLowerCase(); // strip leading '/'
    const all = await fetchSkills();
    const matches = all.filter((s) => s.name.toLowerCase().startsWith(prefix));
    setFiltered(matches);
    setIsOpen(matches.length > 0);
  }, [fetchSkills]);

  const onSelect = useCallback((skill: Skill): string => {
    setIsOpen(false);
    return `/${skill.name} `;
  }, []);

  const onClose = useCallback(() => {
    setIsOpen(false);
  }, []);

  return { isOpen, filtered, selectedMode, setMode, onInputChange, onSelect, onClose };
}
```

- [ ] **Step 2: 在 `frontend/src/lib/api-config.ts` 新增 `getSkillsUrl`**

打开 `frontend/src/lib/api-config.ts`，找到现有的 `getChatStreamUrl` 等函数，新增：

```typescript
export function getSkillsUrl(): string {
  return `${getApiBaseUrl()}/skills/`;
}
```

- [ ] **Step 3: 确认 TypeScript 编译通过**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSkillCommand.ts frontend/src/lib/api-config.ts
git commit -m "feat: add useSkillCommand hook and getSkillsUrl"
```

---

## Task 7: 前端 ChatInput.tsx — `/` 命令检测 + 下拉列表 UI

**Files:**
- Modify: `frontend/src/components/ChatInput.tsx`

> **背景**：当前 ChatInput 是纯 textarea，无任何命令支持。需集成 `useSkillCommand` hook，在用户输入 `/` 时弹出下拉列表，键盘导航选中后继续输入。

- [ ] **Step 1: 修改 `frontend/src/components/ChatInput.tsx`**

完整替换文件内容：

```typescript
"use client";

import { useState, KeyboardEvent, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useSkillCommand } from "@/hooks/useSkillCommand";

interface ChatInputProps {
  onSend: (message: string, skillId?: string | null, mode?: string | null) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { isOpen, filtered, selectedMode, onInputChange, onSelect, onClose } =
    useSkillCommand();

  // 自动调整高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  // 下拉列表打开时重置高亮索引
  useEffect(() => {
    if (isOpen) setHighlightedIndex(0);
  }, [isOpen, filtered]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);
    onInputChange(value);
  };

  const handleSelectSkill = (index: number) => {
    const skill = filtered[index];
    if (!skill) return;
    const newValue = onSelect(skill);
    setInput(newValue);
    onInputChange(newValue);
    textareaRef.current?.focus();
  };

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    const match = input.trim().match(/^\/([^\s]+)/);
    const skillId = match ? match[1] : null;
    const mode = skillId ? selectedMode : null;
    onSend(input.trim(), skillId, mode);
    setInput("");
    onClose();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => Math.min(i + 1, filtered.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        handleSelectSkill(highlightedIndex);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-background-alt p-4 transition-colors duration-300">
      <div className="flex items-end gap-3 max-w-4xl mx-auto relative">
        <div className="flex-1 relative">
          {/* 技能下拉列表 */}
          {isOpen && filtered.length > 0 && (
            <div className="absolute bottom-full left-0 mb-1 w-full max-h-60 overflow-y-auto rounded-xl border border-border bg-bg-card shadow-lg z-50">
              {filtered.map((skill, index) => (
                <button
                  key={skill.name}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault(); // 防止 textarea 失焦
                    handleSelectSkill(index);
                  }}
                  className={cn(
                    "w-full px-4 py-2.5 text-left flex items-start gap-2 transition-colors",
                    index === highlightedIndex
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-bg-alt text-text-primary"
                  )}
                >
                  <span className="font-mono font-semibold text-sm shrink-0">
                    /{skill.name}
                  </span>
                  <span className="text-xs text-text-muted truncate">
                    {skill.description.slice(0, 60)}
                    {skill.description.length > 60 ? "…" : ""}
                  </span>
                </button>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="描述任务，或输入 / 选择技能..."
            className={cn(
              "w-full resize-none rounded-xl border border-border",
              "bg-background px-4 py-3 text-sm",
              "placeholder:text-muted-foreground",
              "focus:border-primary focus:ring-2 focus:ring-primary/10",
              "focus:outline-none transition-all duration-200",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "min-h-[48px] max-h-[200px]"
            )}
            rows={1}
            disabled={disabled}
          />
          {input.length > 0 && (
            <div className="absolute bottom-3 right-3 text-xs text-muted-foreground">
              {input.length} 字符
            </div>
          )}
        </div>

        <motion.button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className={cn(
            "rounded-xl bg-primary px-5 py-3",
            "text-sm font-semibold text-white",
            "hover:bg-primary-hover",
            "disabled:bg-muted disabled:cursor-not-allowed",
            "transition-all duration-200",
            "flex items-center gap-2",
            "min-w-[100px]",
            "justify-center"
          )}
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

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChatInput.tsx
git commit -m "feat: add slash command dropdown to ChatInput"
```

---

## Task 8: 前端 page.tsx — 透传 skill 参数 + skill_invoked SSE handler

**Files:**
- Modify: `frontend/src/app/page.tsx`

> **背景**：`handleSendMessage` 当前签名为 `(message: string)`，需扩展接收 `skillId` + `mode`，并透传到 `sseManager.connect()`。同时新增 `skill_invoked` SSE 事件处理，更新 `skill_registry` slot 的展示内容。

- [ ] **Step 1: 修改 `frontend/src/app/page.tsx`**

**1a. 更新 `handleSendMessage` 签名**，接收 `skillId` + `mode`：

```typescript
const handleSendMessage = async (
  message: string,
  skillId?: string | null,
  mode?: string | null
) => {
  // ... 现有 addMessage、incrementTurn、reset 逻辑不变 ...

  sseManager.connect(getChatStreamUrl(), {
    message,
    session_id: sessionId,
    user_id: userId,
    ...(skillId ? { skill_id: skillId } : {}),
    ...(mode ? { invocation_mode: mode } : {}),
  });
  // ... 其余逻辑不变 ...
};
```

**1b. 在 `sseHandlersRegistered` 注册块中，新增 `skill_invoked` handler**（放在 `session_metadata` handler 之后）：

```typescript
sseManager.on('skill_invoked', ({ data }) => {
  const { skill_id, description } = data as { skill_id: string; description: string };
  const currentSlots = useSession.getState().slotDetails;
  const updated = currentSlots.map((s) =>
    s.name === 'skill_registry'
      ? { ...s, content: `[手动激活] ${skill_id}: ${description}` }
      : s
  );
  setSlotDetails(updated);
});
```

**1c. 更新 `ChatInput` 的 `onSend` prop**，透传新参数：

```tsx
<ChatInput
  onSend={handleSendMessage}
  disabled={isLoading}
/>
```

（`onSend` 签名已在 Task 7 中扩展，此处类型自动匹配，无需额外改动。）

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: wire skill_id/mode to SSE connect and handle skill_invoked event"
```

---

## Task 9: 端到端验证

> 确认全链路功能正常工作。

- [ ] **Step 1: 启动后端**

```bash
cd backend && uvicorn app.main:app --reload
```

确认日志出现：`✅ [技能] SkillManager 初始化完成，目录: <HOME>/.agents/skills`

- [ ] **Step 2: 启动前端**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 验证技能列表接口**

```bash
curl http://localhost:8000/api/skills/
```

期望：返回 `{"skills": [...]}` 含 `~/.agents/skills` 下的 active skills

- [ ] **Step 4: 验证前端 `/` 命令**

打开浏览器 `http://localhost:3000`，在输入框输入 `/`：
- 期望：弹出技能下拉列表
- 输入 `/al`：列表过滤为 name 以 `al` 开头的 skill
- 键盘 `↓`/`↑` 导航，`Enter` 选中
- 选中后输入框变为 `/skill-name `，可继续输入任务

- [ ] **Step 5: 验证 Hint 注入**

选中 skill 后输入任务发送，观察后端日志：
- 期望出现：`💡 [Skill] Hint 注入: skill_id=<name>, mode=hint`
- LLM 应调用 `read_file` 加载对应 SKILL.md

- [ ] **Step 6: 验证 skill_invoked slot 更新**

切换到 Context Window 面板 → 查看 `技能注册表` slot：
- 期望：显示 `[手动激活] <skill-name>: <description>`

- [ ] **Step 7: 运行全量后端测试最终确认**

```bash
cd tests/backend && pytest -v --tb=short
```

期望：全部 PASS（含 Task 1 和 Task 4 新增测试）
