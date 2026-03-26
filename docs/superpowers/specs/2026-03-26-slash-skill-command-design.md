# Slash Skill Command — 设计文档

**日期**: 2026-03-26
**范围**: 前端 `/` 命令触发技能、后端 Hint 注入、调用模式配置

---

## 背景

项目已有完整的 SkillManager 体系：扫描 `~/.agents/skills` 目录下的 `SKILL.md` 文件，生成 skill registry 注入 system prompt，由 LLM 自主判断何时调用 `read_file` 工具加载 skill 内容。

**当前缺口**：用户无法手动指定使用某个 skill。当用户明确知道需要哪个 skill 时，依赖 LLM 自主触发存在不确定性，交互体验较差。

**目标**：参考 Claude Code 的交互方案，在前端输入框支持 `/skill-name` 命令，弹出技能选择列表，并在发送时通知后端优先激活指定 skill。

---

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 用户可调用范围 | 所有 active skill | 无需 `user_invocable` 字段，目录即权限 |
| 调用模式 | Hint（当前）+ Force（占位，待开发） | Force 需要 synthetic message 机制，当前阶段不实现 |
| 模式配置层级 | 全局默认（.env） + 用户临时切换（下拉框） | 灵活性与简单性平衡 |
| 下拉搜索方式 | 前缀匹配 | 简单可预期，与 CLI 工具习惯一致 |
| 选中后输入框状态 | 保留文本，光标追加 | 用户可见完整指令，发送前可修改 |
| skill_id 传递方式 | 结构化字段（非文本解析） | 前端解析 `/` 前缀，独立字段传递，后端无需文本 parsing |

---

## 数据流

```
前端输入框
  用户输入 "/"
    → 拉取 GET /skills/（首次，后续缓存）
    → 展示技能下拉列表（前缀过滤）
    → 用户选中 algo-sensei，切换模式（可选）
    → 继续输入任务文本

  用户发送
    → 解析 message 开头的 /skill-name
    → 构造 { message, skill_id: "algo-sensei", invocation_mode: "hint" }
    → POST /chat/stream

后端 chat 路由
  接收 skill_id + invocation_mode
    → mode == "hint":
        effective_message = "[Skill: algo-sensei]\n{原始message}"
        注入 HumanMessage
    → mode == "force": TODO（预留，暂不实现）
    → 正常走 SSE agent 执行流程

Agent 执行层
  LLM 收到软提示 "[Skill: algo-sensei]"
    → 在 system prompt skill registry 中找到 algo-sensei
    → 调用 read_file(~/.agents/skills/algo-sensei/SKILL.md)
    → 获取完整 skill 内容
    → 按 skill 指令执行任务
```

---

## 后端改动

### 1. `backend/app/config.py`

新增两个配置项：

```python
# Skills
skills_dir: str = Field(
    default="~/.agents/skills",
    description="Skills 目录路径，支持 ~ 展开",
)
skill_invocation_mode: str = Field(
    default="hint",
    description="skill 调用模式：hint | force（force 待开发）",
)
```

### 2. `backend/app/api/skills.py`

修复 `get_skill_manager()` 走单例，`skills_dir` 从 `settings.skills_dir` 读取并展开 `~`：

```python
def get_skill_manager() -> SkillManager:
    skills_dir = Path(settings.skills_dir).expanduser().resolve()
    return SkillManager.get_instance(skills_dir=str(skills_dir))
```

### 3. `backend/app/api/chat.py`

`ChatRequest` 新增可选字段：

```python
skill_id: str | None = Field(default=None, description="用户手动指定的 skill ID")
invocation_mode: str | None = Field(default=None, description="调用模式：hint | force")
```

在构建 `HumanMessage` 之前注入 Hint：

```python
def _apply_skill_hint(message: str, skill_id: str | None, mode: str | None) -> str:
    """Hint 模式：在消息头部追加软提示，引导 LLM 优先激活指定 skill。"""
    effective_mode = mode or settings.skill_invocation_mode
    if not skill_id or effective_mode != "hint":
        return message
    return f"[Skill: {skill_id}]\n{message}"
```

---

## 前端改动

### 1. 新增 `frontend/src/hooks/useSkillCommand.ts`

职责：技能列表拉取与缓存、前缀过滤、调用模式状态管理。

```typescript
interface Skill {
  name: string;
  description: string;
}

interface UseSkillCommandReturn {
  isOpen: boolean;           // 下拉列表是否展示
  filtered: Skill[];         // 前缀过滤后的列表
  selectedMode: 'hint' | 'force';
  setMode: (mode: 'hint' | 'force') => void;
  onInputChange: (value: string) => void;  // 检测 / 并过滤
  onSelect: (skill: Skill) => string;      // 返回选中后的输入框文本
  onClose: () => void;
}
```

**过滤逻辑**：
- 输入以 `/` 开头 → `isOpen = true`
- 提取 `/` 后的前缀，按 skill name 前缀匹配
- 选中后返回 `/skill-name `（含尾部空格，光标定位在末尾）

**缓存策略**：
- 首次触发 `/` 时调用 `GET /api/skills/`
- 结果缓存在 hook 内部（组件生命周期内不重复请求）

### 2. 修改 `frontend/src/components/ChatInput.tsx`

**下拉列表 UI**：
- 定位：textarea 上方，左对齐
- 每行：`skill-name`（粗体）+ 描述摘要（最多 60 字符，截断）+ 右侧模式徽章
- 模式徽章：`HINT`（蓝色）/ `FORCE`（橙色，灰显 + tooltip "即将推出"）
- 键盘支持：`↑↓` 导航，`Enter`/`Tab` 选中，`Esc` 关闭
- 鼠标支持：hover 高亮，click 选中

**发送逻辑**：

```typescript
const handleSend = () => {
  const match = input.match(/^\/([^\s]+)/);
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

### 3. 修改 `frontend/src/app/page.tsx`

`handleSendMessage` 接收 `skillId` + `mode`，透传到 SSE 请求：

```typescript
const handleSendMessage = async (
  message: string,
  skillId?: string | null,
  mode?: string | null
) => {
  sseManager.connect(getChatStreamUrl(), {
    message,
    session_id: sessionId,
    user_id: userId,
    skill_id: skillId ?? undefined,
    invocation_mode: mode ?? undefined,
  });
};
```

---

## 改动文件清单

| 操作 | 文件 | 内容 |
|------|------|------|
| 修改 | `backend/app/config.py` | 新增 `skills_dir` + `skill_invocation_mode` |
| 修改 | `backend/app/api/skills.py` | 修复单例，skills_dir 展开 `~` |
| 修改 | `backend/app/api/chat.py` | ChatRequest 加 skill_id + mode，Hint 注入函数 |
| 新增 | `frontend/src/hooks/useSkillCommand.ts` | skill 列表、过滤、模式状态 |
| 修改 | `frontend/src/components/ChatInput.tsx` | `/` 命令检测、下拉列表 UI、发送逻辑 |
| 修改 | `frontend/src/app/page.tsx` | handleSendMessage 传入 skill_id + mode |

---

## 不在范围内（后续阶段）

- Force 模式实现（synthetic ToolMessage 注入）
- skill 调用历史记录
- skill 权限控制（allow/deny/ask）
- 自定义 skill 目录（多目录支持）

---

## 完成标准

- [ ] `GET /api/skills/` 返回 `~/.agents/skills` 下所有 active skill
- [ ] 前端输入 `/` 触发下拉列表，前缀过滤正常工作
- [ ] 选中 skill 后输入框保留 `/skill-name`，可继续输入
- [ ] 键盘导航（↑↓ Enter Esc）工作正常
- [ ] 发送时 `skill_id` + `invocation_mode` 正确传递
- [ ] 后端 Hint 模式正确拼接软提示
- [ ] Force 模式占位，返回 "not implemented" 或静默降级为 Hint
- [ ] `settings.skills_dir` 和 `settings.skill_invocation_mode` 可通过 `.env` 配置
