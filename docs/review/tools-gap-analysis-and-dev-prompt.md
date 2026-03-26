# Tools 模块 Gap 分析 + 完整开发需求 Prompt

> 生成日期：2026-03-24
> 对比来源：`docs/arch/tools-v12.md` vs 当前实现
> 注意：`task_dispatch`（子 Agent 调度）为 P2，本次不开发

---

## 一、差距总结（当前实现 vs 架构设计）

### 1.1 后端缺失项

| 缺失组件 | 文件路径 | 严重程度 |
|----------|---------|---------|
| `ToolMeta` dataclass | `tools/base.py` | P0（架构基础） |
| `activate_skill` 工具 | `tools/readonly/skill_loader.py` | P0（重要工具） |
| `ToolManager` 类 | `tools/manager.py` | P1 |
| `PolicyEngine` 类 | `tools/policy.py` | P1 |
| `IdempotencyStore` 类 | `tools/idempotency.py` | P1 |
| `build_tool_registry()` 升级 | `tools/registry.py` | P1 |
| 工具层 SSE trace 事件 | `agent/middleware/trace.py` | P0（前端链路） |

### 1.2 前端缺失项

- `ExecutionTracePanel` 有「工具层」阶段标签，但后端从未发出 `stage="tools"` 的事件
- 无 `ToolCallCard` 组件（展示工具名 + 参数 + 结果的卡片）

### 1.3 已实现项（不需改动）

| 工具/组件 | 文件 | 状态 |
|---------|------|------|
| `web_search` | `tools/search.py` | ✅ 保留 |
| `csv_analyze` | `tools/csv_analyze.py` | ✅ 保留 |
| `send_email`（mock） | `tools/send_email.py` | ✅ 保留 |
| `read_file` | `tools/file.py` | ✅ 保留（与 activate_skill 并存） |
| `fetch_url` | `tools/fetch.py` | ✅ 保留 |
| `ToolRegistry`（简单注册表） | `tools/registry.py` | ✅ 保留类，新增函数 |
| `TraceMiddleware` | `agent/middleware/trace.py` | ✅ 已有，补充 tools 事件 |
| `HILMiddleware` | `agent/middleware/hil.py` | ✅ 不动 |

---

## 二、完整开发需求 Prompt

```
# Multi-Tool AI Agent — Tools 模块补全开发需求

## 项目背景

当前项目是一个基于 LangChain + LangGraph 的多工具 AI Agent，
已实现的模块：web_search、csv_analyze、send_email、read_file、fetch_url、
ToolRegistry（简单注册表）、TraceMiddleware（SSE 链路追踪）、HILMiddleware（人工介入）。

本次需求是根据架构设计文档补全 Tools 模块中尚未实现的关键能力，
分为「后端补全」和「前端工具链路展示」两部分，共 8 个任务。

task_dispatch（子 Agent 调度）为 P2，本次不开发。

---

## 技术栈

- 后端：Python 3.11+，FastAPI，LangChain v1.2.13，LangGraph v1.1.3，PostgreSQL
- 前端：Next.js 15，TypeScript，Tailwind CSS，Lucide React
- 测试：pytest（后端），Playwright（前端 E2E）

---

## 任务一：ToolMeta dataclass（tools/base.py）

### 目标
创建 `ToolMeta` dataclass，作为贯穿整个工具系统的元数据载体。

### 文件路径
`backend/app/tools/base.py`（新建）

### 完整字段定义

​```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ToolMeta:
    # ─── 安全字段 ───────────────────────────────────────────────────
    effect_class: str
    # 取值：
    #   "read"           → 只读，无外部影响（PolicyEngine → allow）
    #   "write"          → 写本地状态，session 内可撤销（PolicyEngine → allow）
    #   "external_write" → 触达外部系统，不可撤回（PolicyEngine → ask）
    #   "destructive"    → 不可逆破坏性操作（PolicyEngine → deny）
    #   "orchestration"  → 编排工具，直接放行（PolicyEngine → allow）

    requires_hil: bool = False
    # True = PolicyEngine 决策为 ask，触发 HIL 中断流程
    # 等价于 effect_class 为 external_write 或 destructive

    allowed_decisions: list[str] = field(default_factory=list)
    # PolicyEngine 对该工具的决策范围约束（防御性字段）
    # 示例：web_search → ["allow"]（只读工具永远不应被 deny）
    #       send_email → ["ask", "deny"]
    # PolicyEngine.decide() 后做 assert 校验，超出范围则 raise ValueError

    # ─── 可靠性字段 ──────────────────────────────────────────────────
    idempotent: bool = True
    # True  = 相同参数多次调用结果一致，允许重试（web_search ✓）
    # False = 有副作用，禁止重试（send_email ✗）

    idempotency_key_fn: Callable | None = None
    # 写操作 resume 前计算幂等键，已执行则跳过
    # read 类工具置 None
    # send_email 示例：lambda args: f"email:{args['to']}:{args['subject']}"

    max_retries: int = 0
    # 仅 idempotent=True 时有效，False 时强制为 0

    timeout_seconds: int = 30

    backoff: dict | None = None
    # 重试退避策略，结构：
    # { "strategy": "fixed"|"linear"|"exponential", "base_seconds": int }
    # None = 不重试
    # web_search 示例：{ "strategy": "exponential", "base_seconds": 1 }

    # ─── 调度字段 ─────────────────────────────────────────────────────
    can_parallelize: bool = True
    # True = 允许与其他工具并行执行
    # False = 需串行（send_email 等写操作工具）

    concurrency_group: str | None = None
    # 同组内工具互斥，同一时刻最多执行一个
    # None = 不参与任何互斥组

    # ─── 治理字段 ─────────────────────────────────────────────────────
    permission_key: str = ""
    # 供 PolicyEngine 匹配规则的键，默认取 tool_name
    # 外部写工具可细化，如 "email.send"

    audit_tags: list[str] = field(default_factory=list)
    # TraceMiddleware 写日志时附加的标签列表
    # 示例：web_search → ["network", "search", "readonly"]
    #       send_email → ["network", "email", "external", "write"]
​```

### 要求
- 纯 dataclass，无业务逻辑
- 补充完整的中文注释（字段含义 + 取值规范）
- 导出到 `tools/__init__.py` 的 `__all__`

---

## 任务二：activate_skill 工具（tools/readonly/skill_loader.py）

### 目标
实现 `activate_skill` 工具，替代当前用 `read_file` 直接读 Skill 文件的临时方案。
`activate_skill` 通过 `SkillManager.read_skill_content()` 获取 SKILL.md 内容，
语义上是「激活技能、获取操作手册」，而非通用文件读取。

### 文件路径
`backend/app/tools/readonly/skill_loader.py`（新建）
（同时需要创建 `backend/app/tools/readonly/__init__.py`）

### 工具函数

​```python
from langchain_core.tools import tool
from app.skills.manager import SkillManager
from app.config import settings

@tool
def activate_skill(name: str) -> str:
    """
    激活指定 Agent Skill，获取该场景的完整操作指南。

    适用场景：
    - 当前任务涉及专业领域（法律法规/合同分析/数据报告）且需要标准化流程时
    - 用户明确要求使用某个特定技能时
    - 需要遵循特定操作步骤的任务

    不适用场景：
    - 通用问答（直接回答即可，无需激活技能）
    - 本 session 已激活过同一 skill（历史消息中已可见时，避免重复激活）
    - 读取普通文件内容（请使用 read_file 工具）

    Args:
        name: 技能名称，取值来自 System Prompt 中的 [可用 Skills] 列表

    Returns:
        str: SKILL.md 完整操作手册内容，或包含可用技能列表的错误提示
    """
    skill_manager = SkillManager(skills_dir=settings.skills_dir)
    skill_manager.scan()
    return skill_manager.read_skill_content(name)
​```

### ToolMeta 配置（供任务三 build_tool_registry 使用）
​```python
ToolMeta(
    effect_class="read",
    allowed_decisions=["allow"],
    idempotent=True,
    max_retries=2,
    timeout_seconds=10,
    backoff={"strategy": "fixed", "base_seconds": 1},
    can_parallelize=True,
    concurrency_group=None,
    audit_tags=["skill", "readonly"],
)
​```

### 要求
- 遵循 docstring 三要素：做什么 / 适用 / 不适用
- `read_file` 工具保留（继续用于通用文件读取），`activate_skill` 是独立新工具
- 将 `activate_skill` 加入 `tools/__init__.py` 的 `__all__`

---

## 任务三：ToolManager 类（tools/manager.py）

### 目标
实现元数据查询组件，不做权限决策（单一职责）。

### 文件路径
`backend/app/tools/manager.py`（新建）

### 完整实现

​```python
from app.tools.base import ToolMeta

class ToolManager:
    """
    工具管理器：元数据查询与路由，不做权限决策。
    权限判断统一交给 PolicyEngine。
    """

    def __init__(self, tool_metas: dict[str, ToolMeta]):
        self._metas = tool_metas  # 工具名 → ToolMeta 映射

    def get_meta(self, tool_name: str) -> ToolMeta | None:
        """获取工具元数据，不存在返回 None"""
        return self._metas.get(tool_name)

    def list_available(self) -> list[str]:
        """列出所有已注册工具名"""
        return list(self._metas.keys())

    def can_retry(self, tool_name: str) -> bool:
        """
        判断工具是否可安全重试。
        条件：idempotent=True 且 max_retries > 0
        """
        meta = self._metas.get(tool_name)
        return bool(meta and meta.idempotent and meta.max_retries > 0)
​```

---

## 任务四：PolicyEngine 类（tools/policy.py）

### 目标
实现权限决策引擎，来源 OpenCode PermissionNext 设计。

### 文件路径
`backend/app/tools/policy.py`（新建）

### 完整实现

​```python
class PolicyEngine:
    """
    权限决策引擎，遵循单一职责原则。
    决策依据（优先级从高到低）：
      1. session 级用户授权记录（用户选「总是允许」后缓存）
      2. effect_class 默认规则
    """

    # effect_class → 默认权限映射
    # ⚠️ orchestration 必须显式声明 allow，否则走兜底 ask 触发 HIL
    _DEFAULT_RULES: dict[str, str] = {
        "read":           "allow",
        "write":          "allow",
        "external_write": "ask",
        "destructive":    "deny",
        "orchestration":  "allow",
        # 未知值 → "ask"（保守兜底）
    }

    def __init__(self):
        self._session_grants: dict[str, str] = {}  # 运行时 session 级授权缓存

    def decide(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
    ) -> str:
        """
        返回权限决策：'allow' / 'ask' / 'deny'

        Args:
            tool_name: 工具名称
            effect_class: 副作用级别（来自 ToolMeta）
            allowed_decisions: 该工具允许的决策范围（防御性校验）

        Returns:
            str: 'allow' | 'ask' | 'deny'

        Raises:
            ValueError: 决策结果不在 allowed_decisions 范围内（配置错误快速失败）
        """
        # 优先：session 级用户授权
        if tool_name in self._session_grants:
            decision = self._session_grants[tool_name]
        else:
            # 兜底：effect_class 默认规则；未知值走 "ask" 保守兜底
            decision = self._DEFAULT_RULES.get(effect_class, "ask")

        # 防御性校验：配置错误时快速失败
        if allowed_decisions and decision not in allowed_decisions:
            raise ValueError(
                f"PolicyEngine: tool '{tool_name}' 决策结果 '{decision}' "
                f"不在 allowed_decisions {allowed_decisions} 范围内，"
                f"请检查 ToolMeta.allowed_decisions 配置"
            )
        return decision

    def grant_session(self, tool_name: str) -> None:
        """用户选「本 session 总是允许」时调用"""
        self._session_grants[tool_name] = "allow"

    def hil_required(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: list[str] | None = None,
    ) -> bool:
        """判断是否需要人工确认，供 HILMiddleware 的 interrupt_on 动态生成"""
        return self.decide(tool_name, effect_class, allowed_decisions) == "ask"
​```

---

## 任务五：IdempotencyStore 类（tools/idempotency.py）

### 目标
实现轻量幂等键存储，防止 HIL resume 后重复执行写操作。

### 文件路径
`backend/app/tools/idempotency.py`（新建）

### 完整实现

​```python
class IdempotencyStore:
    """
    轻量幂等键存储。
    写操作执行前检查，已执行则跳过，防止 resume 后重复副作用。
    幂等键由 ToolMeta.idempotency_key_fn(args) 生成。

    当前实现：内存存储（单 session 有效）
    生产场景可扩展为 Redis / PostgreSQL
    """

    def __init__(self):
        self._executed: set[str] = set()

    def check_and_mark(self, key: str) -> bool:
        """
        检查幂等键是否已执行，并标记为已执行。

        Returns:
            True  → 已执行，跳过（resume 防重复）
            False → 未执行，继续执行并记录
        """
        if key in self._executed:
            return True
        self._executed.add(key)
        return False

    def clear(self) -> None:
        """清除所有幂等记录（测试用）"""
        self._executed.clear()
​```

---

## 任务六：升级 build_tool_registry（tools/registry.py）

### 目标
将现有简单 ToolRegistry 升级，新增 `build_tool_registry()` 函数，
同时输出 `list[Tool] + ToolManager + PolicyEngine`，三者共享同一份 ToolMeta。

### 文件路径
`backend/app/tools/registry.py`（修改现有文件，保留 ToolRegistry 类，新增函数）

### 需要新增的函数

​```python
def build_tool_registry(
    enable_hil: bool = False,
) -> tuple[list, "ToolManager", "PolicyEngine"]:
    """
    唯一装配口：输出 list[Tool] + ToolManager + PolicyEngine
    三者共享同一份 ToolMeta，数据来源一致。

    Args:
        enable_hil: 是否启用人工确认
            False（测试环境）→ send_email 不注册，LLM 工具列表中无 send_email
            True（生产环境） → send_email 注册，HIL 流程完整启用

    Returns:
        tuple: (tools_list, tool_manager, policy_engine)
    """
    from app.tools.base import ToolMeta
    from app.tools.manager import ToolManager
    from app.tools.policy import PolicyEngine
    from app.tools.search import web_search
    from app.tools.fetch import fetch_url
    from app.tools.file import read_file
    from app.tools.csv_analyze import csv_analyze
    from app.tools.readonly.skill_loader import activate_skill
    from app.tools.send_email import send_email

    # 工具定义：(工具函数, ToolMeta)
    tool_defs = [
        (web_search, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff={"strategy": "exponential", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["network", "search", "readonly"],
        )),
        (fetch_url, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff={"strategy": "exponential", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["network", "fetch", "readonly"],
        )),
        (csv_analyze, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=30,
            backoff=None,
            can_parallelize=True,
            audit_tags=["data", "csv", "readonly"],
        )),
        (read_file, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=1,
            timeout_seconds=10,
            backoff=None,
            can_parallelize=True,
            audit_tags=["file", "readonly"],
        )),
        (activate_skill, ToolMeta(
            effect_class="read",
            allowed_decisions=["allow"],
            idempotent=True,
            max_retries=2,
            timeout_seconds=10,
            backoff={"strategy": "fixed", "base_seconds": 1},
            can_parallelize=True,
            audit_tags=["skill", "readonly"],
        )),
    ]

    # enable_hil 控制 send_email 是否注册
    if enable_hil:
        tool_defs.append((send_email, ToolMeta(
            effect_class="external_write",
            requires_hil=True,
            allowed_decisions=["ask", "deny"],
            idempotent=False,
            idempotency_key_fn=lambda args: f"email:{args.get('to','')}:{args.get('subject','')}",
            max_retries=0,
            timeout_seconds=30,
            backoff=None,
            can_parallelize=False,
            concurrency_group="external_io",
            permission_key="email.send",
            audit_tags=["network", "email", "external", "write"],
        )))

    # 构建三件套，共享同一份 ToolMeta
    tools_list = [tool_fn for tool_fn, _ in tool_defs]
    tool_metas = {tool_fn.name: meta for tool_fn, meta in tool_defs}

    tool_manager = ToolManager(tool_metas)
    policy_engine = PolicyEngine()

    return tools_list, tool_manager, policy_engine
​```

### 同时修改 langchain_engine.py
将 `create_react_agent` 中的工具初始化改为调用 `build_tool_registry(enable_hil=True)`：

​```python
# 旧代码（需替换）
tools = [web_search, send_email, read_file]

# 新代码
from app.tools.registry import build_tool_registry
tools, tool_manager, policy_engine = build_tool_registry(enable_hil=True)
​```

---

## 任务七：工具层 SSE trace 事件（agent/middleware/trace.py）

### 目标
在 `TraceMiddleware` 中补充工具调用的 SSE 事件，
让前端 `ExecutionTracePanel` 的「工具层」阶段有实际数据展示。

### 当前缺失
TraceMiddleware 只在 ReAct 循环层（`stage="react"`）和 Context 层（`stage="context"`）
发出事件，从未发出 `stage="tools"` 的事件。

### 需要新增的事件

在 `aafter_model` 钩子中，当检测到 AIMessage 包含 tool_calls 时，新增：

​```python
# 检测 LLM 决定调用工具
if isinstance(latest_message, AIMessage) and latest_message.tool_calls:
    for tc in latest_message.tool_calls:
        await emit_trace_event(
            self.sse_queue,
            stage="tools",
            step="tool_call_planned",
            status="start",
            payload={
                "tool_name": tc["name"],
                "tool_call_id": tc.get("id", ""),
                "args": tc["args"],
            },
        )
​```

在 `aafter_agent` 中通过检测 ToolMessage 补发结果事件：

​```python
from langchain_core.messages import ToolMessage
for msg in messages:
    if isinstance(msg, ToolMessage):
        await emit_trace_event(
            self.sse_queue,
            stage="tools",
            step="tool_call_result",
            status="ok",
            payload={
                "tool_call_id": msg.tool_call_id,
                "content_preview": str(msg.content)[:200],  # 最多 200 字符预览
                "content_length": len(str(msg.content)),
            },
        )
​```

### 事件格式标准（stage="tools"）

| step | 触发时机 | payload 关键字段 |
|------|---------|----------------|
| `tool_call_planned` | LLM 决定调用工具 | `tool_name`, `tool_call_id`, `args` |
| `tool_call_result` | 工具执行完成 | `tool_call_id`, `content_preview`, `content_length` |
| `tool_call_error` | 工具执行失败 | `tool_call_id`, `error` |

### 约束
- `content_preview` 截取前 200 字符，避免大结果撑爆 SSE 流
- 不修改已有的 `react` 和 `context` 阶段事件

---

## 任务八：前端 ToolCallCard 组件

### 目标
在 `ExecutionTracePanel` 中，对 `stage="tools"` 的事件进行专属渲染，
用卡片形式展示：工具名 + 状态徽章 + 参数折叠 + 结果折叠。

### 文件路径
- 新建 `frontend/src/components/ToolCallCard.tsx`
- 修改 `frontend/src/components/ExecutionTracePanel.tsx`（添加 ToolCallCard 渲染分支）

### ToolCallCard 组件 Props

​```tsx
// frontend/src/components/ToolCallCard.tsx
'use client';

interface ToolCallCardProps {
  toolName: string;
  status: 'start' | 'ok' | 'error' | 'skip';
  args?: Record<string, unknown>;       // tool_call_planned 时有值
  contentPreview?: string;              // tool_call_result 时有值
  contentLength?: number;
  errorMessage?: string;                // tool_call_error 时有值
  timestamp: string;
}
​```

### 视觉规格

- **卡片整体**：左边有 4px 竖线色块区分工具类型（只读 = 蓝色，写操作 = 橙色，HIL = 红色）
- **工具名**：`font-mono text-sm font-semibold`，前置 🔧 图标
- **状态徽章**：
  - `start` → 蓝色「调用中」
  - `ok` → 绿色「成功」
  - `error` → 红色「失败」
- **参数区**：折叠面板，展示 `JSON.stringify(args, null, 2)`，`bg-muted` 代码块
- **结果预览区**：折叠面板，展示 `contentPreview`，右侧显示 `{contentLength} 字符`
- **错误区**：红色文字展示 `errorMessage`

### ExecutionTracePanel 修改

在事件渲染区（`traceEvents.map`）中，对 `stage="tools"` 的事件替换为 `ToolCallCard`：

​```tsx
// 在 traceEvents.map 内：
if (evt.stage === 'tools') {
  return (
    <ToolCallCard
      key={evt.id}
      toolName={evt.payload.tool_name ?? evt.step}
      status={evt.status as 'start' | 'ok' | 'error'}
      args={evt.payload.args}
      contentPreview={evt.payload.content_preview}
      contentLength={evt.payload.content_length}
      errorMessage={evt.payload.error}
      timestamp={evt.timestamp}
    />
  );
}
// 其余事件走原有渲染逻辑
​```

---

## 三、测试要求

### 后端单元测试（pytest）

每个新文件对应一个测试文件，位于 `backend/tests/unit/tools/`：

#### test_tool_meta.py
- `test_toolmeta_defaults` — 验证默认值合理（idempotent=True，timeout=30）
- `test_toolmeta_all_fields` — 验证所有字段可正常赋值

#### test_policy_engine.py
- `test_read_effect_allows` — effect_class="read" → "allow"
- `test_external_write_asks` — effect_class="external_write" → "ask"
- `test_destructive_denies` — effect_class="destructive" → "deny"
- `test_orchestration_allows` — effect_class="orchestration" → "allow"（**不能走兜底 ask**）
- `test_unknown_effect_asks` — 未知 effect_class → "ask"（保守兜底）
- `test_allowed_decisions_validation` — 决策超出范围抛出 ValueError
- `test_grant_session_overrides_default` — session 级授权优先于默认规则
- `test_hil_required_returns_bool` — hil_required 返回正确布尔值

#### test_tool_manager.py
- `test_list_available` — 返回所有工具名
- `test_get_meta_existing` — 存在的工具返回 ToolMeta
- `test_get_meta_missing` — 不存在的工具返回 None
- `test_can_retry_idempotent` — idempotent=True, max_retries=2 → True
- `test_can_retry_non_idempotent` — idempotent=False → False

#### test_idempotency.py
- `test_first_call_returns_false` — 首次调用返回 False（未执行）
- `test_second_call_returns_true` — 相同 key 第二次返回 True（已执行，跳过）
- `test_clear_resets_store` — clear() 后同 key 可再次执行

#### test_build_tool_registry.py
- `test_returns_tuple_of_three` — 返回 (list, ToolManager, PolicyEngine)
- `test_enable_hil_false_no_send_email` — send_email 不在工具列表中
- `test_enable_hil_true_has_send_email` — send_email 在工具列表中
- `test_activate_skill_in_tools` — activate_skill 始终在工具列表中
- `test_shared_meta_consistency` — ToolManager 的元数据与工具列表一致

#### test_activate_skill.py
- `test_activate_existing_skill` — 存在的 skill 返回内容（需要 tmp_skills_dir fixture）
- `test_activate_missing_skill` — 不存在的 skill 返回错误提示（含可用列表）

### 覆盖率要求

| 文件 | 最低覆盖率 |
|------|---------|
| `tools/base.py` | 100% |
| `tools/policy.py` | 90%+ |
| `tools/manager.py` | 90%+ |
| `tools/idempotency.py` | 100% |

---

## 四、文件变更清单

### 新建文件
```
backend/app/tools/base.py
backend/app/tools/manager.py
backend/app/tools/policy.py
backend/app/tools/idempotency.py
backend/app/tools/readonly/__init__.py
backend/app/tools/readonly/skill_loader.py
backend/tests/unit/tools/test_tool_meta.py
backend/tests/unit/tools/test_policy_engine.py
backend/tests/unit/tools/test_tool_manager.py
backend/tests/unit/tools/test_idempotency.py
backend/tests/unit/tools/test_build_tool_registry.py
backend/tests/unit/tools/test_activate_skill.py
frontend/src/components/ToolCallCard.tsx
```

### 修改文件
```
backend/app/tools/registry.py          # 新增 build_tool_registry()
backend/app/tools/__init__.py          # 导出新增模块
backend/app/agent/langchain_engine.py  # 改用 build_tool_registry()
backend/app/agent/middleware/trace.py  # 新增 stage="tools" 事件
frontend/src/components/ExecutionTracePanel.tsx  # 接入 ToolCallCard
```

---

## 五、关键约束（不可违反）

1. **不实现 task_dispatch** — P2，本次跳过
2. **保留 read_file 工具** — `activate_skill` 是新工具，两者并存，语义不同
3. **不修改 TraceMiddleware 已有事件** — 只新增 `stage="tools"` 事件，不改 `react`/`context`
4. **build_tool_registry 是唯一装配口** — `create_react_agent` 必须改为调用它
5. **ToolMeta 字段命名不可改动** — 架构文档已明确定义，后续模块有依赖
6. **前端 ToolCallCard 只渲染 stage="tools"** — 不影响其他阶段的渲染逻辑
```
