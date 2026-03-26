# Slash Skill Command — 设计文档

**日期**: 2026-03-26
**范围**: 前端 `/` 命令触发技能、后端 Hint 注入、调用模式配置、Slot 数据更新

---

## 背景

项目已有完整的 SkillManager 体系：扫描 `~/.agents/skills` 目录下的 `SKILL.md` 文件，生成 skill registry 注入 system prompt，由 LLM 自主判断何时调用 `read_file` 工具加载 skill 内容。

**当前缺口**：用户无法手动指定使用某个 skill。当用户明确知道需要哪个 skill 时，依赖 LLM 自主触发存在不确定性，交互体验较差。

**目标**：参考 Claude Code 的交互方案，在前端输入框支持 `/skill-name` 命令，弹出技能选择列表，并在发送时通知后端优先激活指定 skill。同时，Context Window 面板的 slot 数据应反映手动激活的 skill 信息。

---

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 用户可调用范围 | 所有 active skill | 无需 `user_invocable` 字段，目录即权限 |
| 调用模式 | Hint（当前）+ Force（占位，待开发） | Force 需要 synthetic message 机制，当前阶段不实现 |
| 模式配置层级 | 全局默认（.env） + 用户临时切换（下拉框） | 灵活性与简单性平衡 |
| 下拉搜索方式 | 前缀匹配 | 简单可预期，与 CLI 工具习惯一致 |
| 选中后输入框状态 | 保留文本，光标追加 | 用户可见完整指令，发送前可修改 |
| skill_id 传递方式 | 结构化 query 参数（非文本解析） | chat 路由是 GET，参数以 query string 传递；前端独立传字段，后端无需文本 parsing |
| Force UI | 不在本阶段展示 | YAGNI：功能未实现，不展示禁用态 UI |

---

## 数据流

```
前端输入框
  用户输入 "/"
    → 拉取 GET /api/skills/（首次触发，后续缓存至组件卸载）
    → 展示技能下拉列表（skill name 前缀过滤）
    → 用户选中 algo-sensei（下拉框含模式切换，默认 hint）
    → 继续输入任务文本："/algo-sensei 帮我基于JD修改简历"

  用户发送
    → 解析 message 开头的 /skill-name → skill_id = "algo-sensei"
    → EventSource URL 追加 &skill_id=algo-sensei&invocation_mode=hint
    → GET /api/chat?message=...&skill_id=algo-sensei&invocation_mode=hint

后端 chat 路由
  接收 skill_id + invocation_mode 查询参数
    → 验证 skill_id 在 active skill 列表中（不在则 log warning + 忽略）
    → mode == "hint":
        effective_message = "[Skill: algo-sensei]\n{原始message}"
        注入 HumanMessage
    → mode == "force": 静默降级为 hint（TODO，后续实现）
    → 通过 skill_id 查出 skill description
    → 在 agent 初始化后 emit skill_invoked SSE 事件（含 skill_id + description）
    → 正常走 SSE agent 执行流程

前端 SSE 处理
  收到 skill_invoked 事件
    → 更新 slotDetails 中 skill_registry slot 的 content 字段（追加当前激活 skill 名称）
    → Context Window 面板实时反映

Agent 执行层
  LLM 收到软提示 "[Skill: algo-sensei]"
  + system prompt 中有对应说明（见后端改动 §1）
    → 在 skill registry 中匹配 algo-sensei
    → 调用 read_file(~/.agents/skills/algo-sensei/SKILL.md)
    → 获取完整 skill 内容，按指令执行任务
```

---

## 后端改动

### 1. `backend/app/config.py`

**修改** `skills_dir` 默认值（字段已存在，仅更新 default）：

```python
skills_dir: str = Field(
    default="~/.agents/skills",
    description="Skills 目录路径（支持 ~ 展开）。修改此项需同步更新 .env 文件。",
)
```

> ⚠️ 迁移注意：原默认值为 `"../skills"`。已有 `.env` 文件中显式设置了 `SKILLS_DIR` 的项目不受影响；未设置则目录自动切换。

**新增** `skill_invocation_mode`（使用 `Literal` 类型约束）：

```python
from typing import Literal

skill_invocation_mode: Literal["hint", "force"] = Field(
    default="hint",
    description="skill 调用模式：hint（软提示）| force（强制注入，待开发）",
)
```

### 2. `backend/app/main.py` — 启动时初始化 SkillManager

在 `lifespan` startup 中统一初始化 SkillManager 单例，确保后续所有调用方（`/skills/` API、chat 路由）共享同一实例：

```python
from pathlib import Path
from app.skills.manager import SkillManager

# lifespan startup（init_db 之后）
skills_dir = Path(settings.skills_dir).expanduser().resolve()
SkillManager.get_instance(skills_dir=str(skills_dir))
logger.info(f"✅ [技能] SkillManager 初始化完成，目录: {skills_dir}")
```

### 3. `backend/app/api/skills.py`

修复 `get_skill_manager()` 走单例（依赖 §2 的 lifespan 初始化，若未初始化则抛出明确错误）：

```python
def get_skill_manager() -> SkillManager:
    try:
        return SkillManager.get_instance()  # 无需再传 skills_dir
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"SkillManager not initialized: {e}")
```

### 4. `backend/app/api/chat.py`

**路由函数签名**新增两个可选查询参数（chat 路由是 GET，不使用 `ChatRequest` BaseModel）：

```python
@router.get("")
async def chat(
    message: str,
    session_id: str,
    user_id: str = "dev_user",
    skill_id: str | None = None,           # 新增
    invocation_mode: str | None = None,    # 新增
) -> StreamingResponse:
```

透传至 `_run_agent_stream`：

```python
return StreamingResponse(
    _run_agent_stream(
        message=message,
        session_id=session_id,
        user_id=user_id,
        skill_id=skill_id,
        invocation_mode=invocation_mode,
        ...
    ),
    ...
)
```

**`_run_agent_stream`** 签名同步更新，在构建 HumanMessage 之前调用 hint 注入，并在 agent 初始化后 emit `skill_invoked` 事件：

```python
def _apply_skill_hint(message: str, skill_id: str | None, mode: str) -> str:
    """Hint 模式：在消息头部追加软提示，引导 LLM 优先激活指定 skill。"""
    if not skill_id or mode != "hint":
        return message
    return f"[Skill: {skill_id}]\n{message}"


async def _validate_and_get_skill(skill_id: str) -> str | None:
    """验证 skill_id 是否在 active 列表中，返回 description；不存在则 log warning 返回 None。"""
    try:
        manager = SkillManager.get_instance()
        manager.scan()
        for defn in manager._definitions:
            if defn.id == skill_id or defn.name == skill_id:
                return defn.metadata.description
    except Exception:
        pass
    logger.warning(f"⚠️ [Skill] skill_id '{skill_id}' 不在 active 列表中，忽略 hint 注入")
    return None
```

**Slot 更新**：在 agent 初始化完成后、执行前，向 SSE 队列推送 `skill_invoked` 事件：

```python
if skill_id and skill_description:
    await _queue_put(event_queue, ("skill_invoked", {
        "skill_id": skill_id,
        "description": skill_description,
        "mode": effective_mode,
    }))
```

### 5. `backend/app/prompt/templates.py` 或 `prompt/builder.py`

在 system prompt 中新增关于 `[Skill: X]` hint 格式的说明，确保 LLM 可靠识别：

```
当用户消息以 [Skill: <name>] 开头时，表示用户明确要求使用该 skill。
你应当优先通过 read_file 工具加载该 skill 的完整内容，再执行用户的任务。
```

此说明注入到 `system` slot（基础系统提示词部分）。

---

## 前端改动

### 1. `frontend/src/lib/sse-manager.ts`

`ConnectionOptions` 新增可选字段，`connect()` 中 `URLSearchParams` 条件追加：

```typescript
export interface ConnectionOptions {
  message: string;
  session_id: string;
  user_id: string;
  skill_id?: string;           // 新增
  invocation_mode?: string;    // 新增
}
```

`connect()` 内部：

```typescript
if (options.skill_id) params.append('skill_id', options.skill_id);
if (options.invocation_mode) params.append('invocation_mode', options.invocation_mode);
```

### 2. 新增 `frontend/src/hooks/useSkillCommand.ts`

职责：技能列表拉取与缓存、前缀过滤、模式状态管理。

```typescript
interface Skill {
  name: string;
  description: string;
}

interface UseSkillCommandReturn {
  isOpen: boolean;
  filtered: Skill[];
  selectedMode: 'hint' | 'force';
  setMode: (mode: 'hint' | 'force') => void;
  onInputChange: (value: string) => void;
  onSelect: (skill: Skill) => string;   // 返回选中后的输入框文本
  onClose: () => void;
}
```

**过滤逻辑**：
- 输入以 `/` 开头 → `isOpen = true`
- 提取 `/` 后的前缀，按 skill `name` 前缀匹配（大小写不敏感）
- 选中后返回 `/skill-name `（含尾部空格，光标在末尾）
- 输入不以 `/` 开头 → `isOpen = false`

**缓存策略**：
- 首次触发 `/` 时调用 `GET /api/skills/`，结果缓存在 hook 内部
- 已知限制：缓存在组件挂载期间不刷新；skill 目录变更需刷新页面生效

### 3. 修改 `frontend/src/components/ChatInput.tsx`

**下拉列表 UI**：
- 定位：textarea 上方，左对齐，`z-50`
- 每行：skill name（粗体）+ 描述摘要（≤60 字符截断）
- 当前阶段不展示模式徽章（Force 功能未实现，不显示禁用态）
- 键盘：`↑↓` 导航，`Enter`/`Tab` 选中，`Esc` 关闭
- 鼠标：hover 高亮，click 选中

**发送逻辑**：

```typescript
const handleSend = () => {
  if (!input.trim() || disabled) return;
  const match = input.trim().match(/^\/([^\s]+)/);
  const skill_id = match ? match[1] : null;
  const invocation_mode = skill_id ? selectedMode : null;
  onSend(input.trim(), skill_id, invocation_mode);
  setInput('');
};
```

**ChatInputProps 扩展**：

```typescript
interface ChatInputProps {
  onSend: (message: string, skillId?: string | null, mode?: string | null) => void;
  disabled?: boolean;
}
```

### 4. 修改 `frontend/src/app/page.tsx`

**`handleSendMessage`** 接收并透传 `skillId` + `mode`：

```typescript
const handleSendMessage = async (
  message: string,
  skillId?: string | null,
  mode?: string | null
) => {
  // ... existing reset logic ...
  sseManager.connect(getChatStreamUrl(), {
    message,
    session_id: sessionId,
    user_id: userId,
    ...(skillId && { skill_id: skillId }),
    ...(mode && { invocation_mode: mode }),
  });
};
```

**新增 `skill_invoked` SSE 事件处理**，更新 `slotDetails` 中 `skill_registry` slot 的展示内容：

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

---

## 改动文件清单

| 操作 | 文件 | 内容 |
|------|------|------|
| 修改 | `backend/app/config.py` | 更新 `skills_dir` 默认值；新增 `skill_invocation_mode`（Literal 类型） |
| 修改 | `backend/app/main.py` | lifespan startup 初始化 SkillManager 单例 |
| 修改 | `backend/app/api/skills.py` | get_skill_manager() 走单例，加 503 保护 |
| 修改 | `backend/app/api/chat.py` | 路由函数签名加 skill_id + invocation_mode；hint 注入；skill 验证；emit skill_invoked 事件 |
| 修改 | `backend/app/prompt/templates.py` | system prompt 新增 [Skill: X] hint 说明 |
| 修改 | `frontend/src/lib/sse-manager.ts` | ConnectionOptions 加 skill_id + invocation_mode；connect() 追加 URLSearchParams |
| 新增 | `frontend/src/hooks/useSkillCommand.ts` | skill 列表拉取、前缀过滤、模式状态 |
| 修改 | `frontend/src/components/ChatInput.tsx` | `/` 命令检测、下拉列表 UI、发送逻辑 |
| 修改 | `frontend/src/app/page.tsx` | handleSendMessage 传参；skill_invoked SSE handler 更新 slot 数据 |

---

## 不在范围内（后续阶段）

- Force 模式实现（synthetic ToolMessage 注入）
- Force 模式 UI（模式徽章、切换按钮）
- skill 调用历史记录与 trace 可视化
- skill 权限控制（allow/deny/ask）
- 多 skill 目录支持
- skill 列表实时刷新（目前缓存至组件卸载）

---

## 完成标准

- [ ] `GET /api/skills/` 返回 `~/.agents/skills` 下所有 active skill
- [ ] 前端输入 `/` 触发下拉列表，前缀过滤正常工作
- [ ] 选中 skill 后输入框保留 `/skill-name`，可继续输入
- [ ] 键盘导航（↑↓ Enter Esc）工作正常
- [ ] `skill_id` + `invocation_mode` 通过 query params 正确传递至后端
- [ ] 后端验证 skill_id 存在；不存在时 log warning 并忽略（不报错）
- [ ] 后端 Hint 模式正确在消息头部追加 `[Skill: X]` 软提示
- [ ] System prompt 包含 `[Skill: X]` 格式说明
- [ ] Force 模式静默降级为 Hint（log warning）
- [ ] 后端 emit `skill_invoked` SSE 事件
- [ ] 前端 skill_invoked handler 更新 skill_registry slot content
- [ ] `settings.skills_dir` 和 `settings.skill_invocation_mode` 可通过 `.env` 配置
- [ ] SkillManager 在 lifespan startup 初始化，`/skills/` API 走单例
