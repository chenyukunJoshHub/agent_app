# Prompt + Context 模块 - 完整实施设计

> **文档版本**: v1.0
> **创建日期**: 2026-03-22
> **基于架构**: `docs/Prompt + Context 模块完整设计文档.md`
> **目标**: 实现十大子模块的完整 Prompt + Context 系统

---

## 📋 目录

1. [模块概述](#1-模块概述)
2. [十大子模块设计](#2-十大子模块设计)
3. [Context Window 10个Slot](#3-context-window-10个slot)
4. [实现优先级](#4-实现优先级)
5. [文件结构](#5-文件结构)
6. [P0 实施计划](#6-p0-实施计划)

---

## 1. 模块概述

### 1.1 核心问题

LLM 只有一个输入口（Context Window），我们需要在有限的 Token 预算里，以最优的方式组装 LLM 的每次输入。

### 1.2 设计理念

```
Prompt + Context = 静态内容 + 动态注入

静态内容（启动时固定）:
  - 角色定义
  - 能力边界
  - 行为约束
  - Skill Registry 元数据
  - 静态 Few-shot

动态注入（每次 LLM 调用前）:
  - 用户画像（Episodic Memory）
  - 活跃技能内容（Agent Skill）
  - 动态 Few-shot（语义检索）
  - RAG 背景知识（向量检索）
  - 程序性记忆（Procedural Memory）
```

### 1.3 Ephemeral vs Persistent

| 内容类型 | 注入方式 | 是否写入历史 | 原因 |
|---------|---------|-------------|------|
| 用户画像 | Ephemeral | ❌ 否 | 避免重复堆积 |
| RAG chunk | Ephemeral | ❌ 否 | 每轮基于当前问题重新检索 |
| Human 消息 | Persistent | ✅ 是 | 核心对话内容 |
| AI 回复 | Persistent | ✅ 是 | 核心对话内容 |
| 工具结果 | Persistent | ✅ 是 | 后续推理依赖 |

---

## 2. 十大子模块设计

### 2.1 ① System Prompt Builder

**职责**: 把"静态模板"、"Skill Registry 元数据"、"静态 Few-shot"和"动态画像"拼成 LLM 每次调用的指令基础。

**文件**: `backend/app/prompt/templates.py`

```python
"""静态 Prompt 模板 - P0/P1/P2 分阶段实现"""

# P0: 基础角色定义
ROLE_TEMPLATE = """你是一个专业的多工具 AI 助手，能够自主规划并执行复杂任务。

## 核心能力
- 实时信息搜索（web_search）
- 数据分析（csv_analyze）
- 合同流程查询
- 文件操作（read_file）

## 行为准则
- 每次行动前先推理，说明为什么选择当前工具
- 遇到不确定信息，优先搜索而不是猜测
- 最终答案使用 Markdown 格式
"""

# P1: Skill Registry 元数据
SKILL_REGISTRY_TEMPLATE = """
## 可用 Skills
{skills_list}

激活方式：当任务匹配某个 skill 的 description 时，使用 read_file 工具读取对应的 SKILL.md
"""

# P1: 静态 Few-shot
STATIC_FEW_SHOT = """
## 示例对话（演示推理方式）

示例 1：
用户：查合同123的签署进度
思考：用户需要查询指定合同的状态，直接使用 contract_status 工具
操作：contract_status(contract_id="123")
观察：合同123已有2/3方签署，待签：财务总监（截止 2026-03-20）
回复：合同123进度：2/3 已签署，财务总监需在3月20日前完成签署。

示例 2：
用户：批量提醒所有逾期未签合同的签署方
思考：这是批量操作，需先确认范围再执行，必须触发人工确认
操作：query_overdue_contracts()
观察：15 份逾期合同，23 位签署方
HIL：此操作将向 23 位签署方发送提醒邮件，请确认是否继续？
"""

# P0: 用户画像模板（动态注入）
USER_PROFILE_TEMPLATE = """
## 用户画像
{preferences}
"""
```

**文件**: `backend/app/prompt/builder.py`（已存在，需增强）

```python
"""System Prompt 构建器 - 完整版"""

from app.skills.models import SkillSnapshot
from app.prompt.templates import (
    ROLE_TEMPLATE,
    SKILL_REGISTRY_TEMPLATE,
    STATIC_FEW_SHOT,
    USER_PROFILE_TEMPLATE,
)
from app.memory.schemas import EpisodicData

def build_system_prompt(
    skill_snapshot: SkillSnapshot | None = None,
    episodic: EpisodicData | None = None,
    available_tools: list[str] | None = None,
) -> str:
    """
    构建完整的 System Prompt（P0/P1/P2 渐进式）

    Args:
        skill_snapshot: Skill 快照（P1）
        episodic: 用户画像数据（P0+）
        available_tools: 可用工具列表（P0）

    Returns:
        str: 完整的 System Prompt
    """
    parts = [ROLE_TEMPLATE, ""]

    # P1: Skill Registry 元数据
    if skill_snapshot and skill_snapshot.skills:
        skills_list = "\n".join([
            f"· {s.skill_id}：{s.description}（触发：{s.trigger}）"
            for s in skill_snapshot.skills
        ])
        parts.append(SKILL_REGISTRY_TEMPLATE.format(skills_list=skills_list))
        parts.append("")

    # P0: 可用工具说明
    if available_tools:
        parts.append("## 可用工具")
        tool_desc = {
            "web_search": "搜索互联网获取实时信息",
            "send_email": "发送邮件（⚠️ 不可逆操作）",
            "read_file": "读取文件内容（用于加载 Agent Skill）",
        }
        for tool in available_tools:
            if tool in tool_desc:
                parts.append(f"- {tool}: {tool_desc[tool]}")
        parts.append("")

    # P1: 静态 Few-shot
    parts.append(STATIC_FEW_SHOT)
    parts.append("")

    # P0+: 用户画像动态注入（Ephemeral）
    if episodic and episodic.preferences:
        prefs_text = "\n".join(f"- {k}: {v}" for k, v in episodic.preferences.items())
        parts.append(USER_PROFILE_TEMPLATE.format(preferences=prefs_text))

    # 使用指南
    parts.extend([
        "## 使用指南",
        "1. 首先理解用户需求",
        "2. 判断是否需要激活某个 skill",
        "3. 如果需要，使用 read_file 读取对应的 SKILL.md",
        "4. 按 skill 的 Instructions 执行任务",
        "5. 如果不需要 skill，直接使用可用工具完成任务",
        "",
        "## 重要",
        "- 不要编造信息",
        "- 保持回答简洁但完整",
        "- send_email 操作需要用户确认后才会执行",
    ])

    return "\n".join(parts)
```

---

### 2.2 ② Token Budget Manager

**职责**: 管理 Context Window 的 Token 预算，决定每个 Slot 能用多少。

**文件**: `backend/app/prompt/budget.py`（新建）

```python
"""Token 预算管理 - P0"""

from dataclasses import dataclass

@dataclass
class TokenBudget:
    """Token 预算配置（Claude Sonnet 4.6）"""

    # 模型规格
    MODEL_CONTEXT_WINDOW: int = 200_000   # 200K 硬上限
    MODEL_MAX_OUTPUT: int = 8_192         # 标准输出上限

    # Agent 工作预算
    WORKING_BUDGET: int = 32_768          # 32K 工作预算

    # Slot 配置
    SLOT_OUTPUT: int = 8_192              # 输出预留
    SLOT_SYSTEM: int = 2_000              # System Prompt + Few-shot
    SLOT_ACTIVE_SKILL: int = 0            # P1 改为 1_500
    SLOT_FEW_SHOT: int = 0                 # P1 改为 800
    SLOT_RAG: int = 0                      # P2 改为 2_000
    SLOT_EPISODIC: int = 500              # 用户画像
    SLOT_PROCEDURAL: int = 0               # P2 改为 400
    SLOT_TOOLS: int = 1_200                # 工具 Schema

    @property
    def input_budget(self) -> int:
        """可用输入 Token = 工作预算 - 输出预留"""
        return self.WORKING_BUDGET - self.SLOT_OUTPUT

    @property
    def slot_history(self) -> int:
        """会话历史弹性预算"""
        fixed = (
            self.SLOT_SYSTEM + self.SLOT_ACTIVE_SKILL + self.SLOT_FEW_SHOT
            + self.SLOT_RAG + self.SLOT_EPISODIC + self.SLOT_PROCEDURAL
            + self.SLOT_TOOLS
        )
        return self.input_budget - fixed

    def calculate_history_usage(self, messages: list) -> int:
        """计算当前历史消息的 Token 占用"""
        # P0: 近似估算
        total_chars = sum(len(msg.content) if hasattr(msg, 'content') else 0 for msg in messages)
        return int(total_chars / 3)  # 粗略估算

    def should_compress(self, messages: list) -> bool:
        """判断是否需要压缩历史"""
        return self.calculate_history_usage(messages) > self.slot_history
```

---

### 2.3 ③ Token Counter

**职责**: 统计文本 Token 数量，驱动 Budget Manager 的超限判断。

**文件**: `backend/app/utils/token.py`（已存在，需验证）

```python
"""Token 计数工具 - P0 近似版"""

def count_tokens_approx(text: str) -> int:
    """
    P0：字符数近似估算，Ollama 本地模型够用
    P2：替换为 tiktoken 精确计数
    """
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
```

---

### 2.4 ④ Compressor（消息压缩器）

**职责**: 会话历史超出 Token 预算时，把旧消息压缩成摘要腾出空间。

**文件**: `backend/app/agent/middleware/compression.py`（新建）

```python
"""消息压缩中间件 - P0"""

from langchain.agents.middleware import AgentMiddleware
from typing import Any

class CompressorMiddleware(AgentMiddleware):
    """Token 超限时自动压缩历史"""

    def __init__(self, budget: TokenBudget):
        self.budget = budget

    async def abefore_model(self, state: Any, runtime: Any) -> dict | None:
        """每次 LLM 调用前检查是否需要压缩"""
        messages = state.get("messages", [])

        if self.budget.should_compress(messages):
            # 压缩旧消息（保留最近 N 条）
            compressed = await self._compress_messages(messages)
            return {"messages": compressed}

        return None

    async def _compress_messages(self, messages: list) -> list:
        """压缩消息：保留最近 5 条 + 摘要"""
        keep_recent = 5
        if len(messages) <= keep_recent:
            return messages

        # TODO: 调用 LLM 生成摘要（P1 实现）
        # P0: 简单截断
        return messages[-keep_recent:]
```

---

### 2.5 ⑤ Memory Injector（记忆注入器）

**职责**: 在每次 LLM 调用前，把相关记忆动态注入到 Context Window。

**文件**: `backend/app/agent/middleware/memory.py`（已存在，需增强）

```python
"""Memory 中间件 - Ephemeral 注入（已在 Memory 模块实现）"""

# 已通过 MemoryMiddleware.wrap_model_call 实现
# 参考 Memory 模块架构设计文档
```

---

### 2.6 ⑥ Tool Schema Formatter

**职责**: 把工具函数定义转成 LLM 能理解的 JSON Schema。

**实现**: 框架自动处理（@tool 装饰器）

```python
from langchain_core.tools import tool

@tool
def web_search(query: str) -> str:
    """
    搜索互联网获取实时信息。
    适用：最新法规、实时价格、新闻动态。
    不适用：静态知识、数学计算。
    """
    # 框架自动生成 JSON Schema
```

---

### 2.7 ⑦ RAG Retriever（P2）

**职责**: 根据用户输入从知识库检索相关背景。

**文件**: `backend/app/rag/retriever.py`（P2，预留）

```python
"""RAG 检索器 - P2（预留）"""

class RAGRetriever:
    """向量检索 + Ephemeral 注入"""

    async def retrieve(self, query: str, limit: int = 3) -> str:
        """语义检索相关背景知识"""
        # TODO: 向量检索实现
        pass
```

---

### 2.8 ⑧ Few-shot Builder

**职责**: 提供 LLM 推理和工具调用的"示范样本"。

**文件**: `backend/app/prompt/fewshot.py`（新建）

```python
"""Few-shot 管理器 - P0 静态 / P1 动态"""

# P0: 静态 Few-shot（已在 templates.py 中）
# P1: 动态 Few-shot 检索（预留）

class DynamicFewshotRetriever:
    """语义检索最相关的 Few-shot 示例"""

    async def retrieve(self, user_input: str, limit: int = 2) -> str:
        """从 Few-shot 库中检索最相关示例"""
        # TODO: 向量检索实现
        pass
```

---

### 2.9 ⑨ Agent Skill Manager

**职责**: 管理 Agent Skills 的注册与加载。

**文件**: `backend/app/skills/manager.py`（已实现）

```python
# Skills 系统已完成
# 参考 Phase 4 实施结果
```

---

### 2.10 ⑩ 内部操作 Prompt

**职责**: 各节点系统级 LLM 调用的 Prompt 模板。

**文件**: `backend/app/prompt/internal.py`（新建）

```python
"""内部操作 Prompt - 系统级 LLM 调用"""

# 压缩 Prompt
COMPRESSOR_PROMPT = """
请将以下对话历史压缩成简洁摘要（控制在 400 Token 以内）。

【必须保留】
· 用户的核心任务目标和意图
· 已确认的关键事实
· 工具调用结果及其核心含义
· 当前任务进度和尚未完成的事项

【可以省略】
· 闲聊、礼貌用语、重复确认
· 格式排版相关的指令

[对话历史]
{messages}

摘要：
"""

# HIL 确认模板
HIL_CONFIRM_TEMPLATE = """
⚠️ 即将执行以下操作，请确认：

操作类型：{action_type}
影响范围：{scope_description}
具体内容：{action_detail}
预期结果：{expected_result}

[✅ 确认执行]   [❌ 取消操作]
"""

# 错误恢复规则
ERROR_RECOVERY_RULES = """
工具调用失败时的处理规则：
1. 分析错误类型，修改参数后重试（最多 2 次）
2. 2 次重试后仍失败，切换备用方案或告知用户限制原因
3. 禁止使用相同参数重复调用（防死循环）
"""
```

---

## 3. Context Window 10个Slot

### 3.1 Slot 分区配置

```
┌─────────────────────────────────────────────────────────────────┐
│                  Context Window (32K 工作预算)                   │
├─────────────────────────────────────────────────────────────────┤
│ Slot ①  System Prompt + Skill Registry + 静态 Few-shot    2,000  │
│ Slot ②  Active Skill 内容（持久化到 Slot ⑧）               1,500  │
│ Slot ③  Dynamic Few-shot（P1）                             800    │
│ Slot ④  RAG 背景知识（P2）                                2,000  │
│ Slot ⑤  用户画像 Episodic（Ephemeral）                     500    │
│ Slot ⑥  程序性记忆 Procedural（P2）                         400    │
│ Slot ⑦  工具 Schema（框架自动注入）                         1,200  │
│ Slot ⑧  会话历史（弹性）                                   16,176  │
│ Slot ⑧  输出格式规范                                       ~100   │
│ Slot ⑩  用户输入（最高优先级）                              实时   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Ephemeral vs Persistent 对照表

| 内容类型 | Slot | 注入方式 | 是否写入历史 | 来源 |
|---------|------|---------|-------------|------|
| Skill Registry 元数据 | ① | 静态 | ❌ | 代码硬编码 |
| 静态 Few-shot | ① | 静态 | ❌ | templates.py |
| 用户画像 Episodic | ①/⑤ | Ephemeral | ❌ | Long Memory |
| Dynamic Few-shot | ③ | Ephemeral | ❌ | 向量存储 |
| RAG 背景知识 | ④ | Ephemeral | ❌ | 向量存储 |
| 程序性记忆 Procedural | ⑥ | Ephemeral | ❌ | Long Memory |
| Active Skill 内容 | ⑧ | Persistent | ✅ | ToolMessage |
| 会话历史 | ⑧ | Persistent | ✅ | Short Memory |
| 用户输入 | ⑩ | Persistent | ✅ | 当前请求 |

---

## 4. 实现优先级

### P0（面试前必须）

| 任务 | 文件 | 状态 | 工作量 |
|-----|------|------|-------|
| System Prompt Builder | templates.py | ⚠️ 需创建 | 2h |
| Token Budget Manager | budget.py | ⚠️ 需创建 | 2h |
| Token Counter（近似） | utils/token.py | ✅ 已存在 | - |
| 静态 Few-shot | templates.py | ⚠️ 需创建 | 1h |
| 用户画像注入 | memory.py | ✅ 已实现 | - |

### P1（加分项）

| 任务 | 文件 | 状态 | 工作量 |
|-----|------|------|-------|
| Skill Registry 元数据注入 | builder.py | ✅ 已实现 | - |
| Agent Skill Manager | skills/ | ✅ 已完成 | - |
| 动态 Few-shot 检索 | fewshot.py | ⚠️ 需创建 | 4h |
| 消息压缩器 | compression.py | ⚠️ 需创建 | 4h |

### P2（面试后）

| 任务 | 文件 | 状态 | 工作量 |
|-----|------|------|-------|
| RAG Retriever | rag/retriever.py | ⚠️ 预留 | 8h |
| 程序性记忆注入 | memory.py | ⚠️ 预留 | 6h |
| Token 精确计数（tiktoken） | utils/token.py | ⚠️ 需升级 | 2h |

---

## 5. 文件结构

```
backend/app/prompt/
├── __init__.py
├── builder.py              ✅ 已存在（需增强）
├── templates.py            ⚠️ 需创建
├── budget.py               ⚠️ 需创建
├── fewshot.py              ⚠️ 需创建（P1）
└── internal.py             ⚠️ 需创建

backend/app/agent/middleware/
├── memory.py               ✅ 已存在
├── compression.py          ⚠️ 需创建（P1）
└── hil.py                  ✅ 已存在

backend/app/utils/
├── token.py                ✅ 已存在（需验证）
└── security.py             ⚠️ 需创建（安全加固）

backend/app/rag/             ⚠️ P2 预留
└── __init__.py
```

---

## 6. P0 实施计划

### Phase 1: 静态模板（2h）

**任务**: 创建 `templates.py`

- [ ] ROLE_TEMPLATE（角色定义）
- [ ] SKILL_REGISTRY_TEMPLATE（P1 预留）
- [ ] STATIC_FEW_SHOT（2个示例对话）
- [ ] USER_PROFILE_TEMPLATE

### Phase 2: Token 预算（2h）

**任务**: 创建 `budget.py`

- [ ] TokenBudget dataclass
- [ ] 预算常量定义
- [ ] input_budget 属性
- [ ] slot_history 属性
- [ ] calculate_history_usage 方法
- [ ] should_compress 方法

### Phase 3: 增强 builder.py（1h）

**任务**: 增强 `builder.py`

- [ ] 导入新模板
- [ ] 集成 episodic 参数
- [ ] P0 基础版完成

### Phase 4: 内部操作 Prompt（1h）

**任务**: 创建 `internal.py`

- [ ] COMPRESSOR_PROMPT
- [ ] HIL_CONFIRM_TEMPLATE
- [ ] ERROR_RECOVERY_RULES

### Phase 5: 单元测试（2h）

**任务**: 创建测试

- [ ] test_templates.py
- [ ] test_budget.py
- [ ] test_builder.py
- [ ] 集成测试

### 验收标准

- [ ] build_system_prompt() 能生成完整的 System Prompt
- [ ] TokenBudget 能正确计算弹性预算
- [ ] 用户画像能正确注入到 System Prompt
- [ ] 单元测试覆盖率 > 80%

---

## 7. P1 扩展计划

### Phase 6: 动态 Few-shot（4h）

**任务**: 创建 `fewshot.py`

- [ ] FewShotExample 数据模型
- [ ] 向量存储集成
- [ ] 语义检索逻辑
- [ ] Ephemeral 注入机制

### Phase 7: 消息压缩器（4h）

**任务**: 创建 `compression.py`

- [ ] CompressorMiddleware 实现
- [ ] LLM 压缩调用
- [ ] 压缩触发逻辑
- [ ] 集成到 langchain_engine

---

## 8. 关键设计决策

### 8.1 为什么用户画像要 Ephemeral 注入？

```
❌ Persistent 注入（错误）：
  第1轮：System Prompt 包含用户画像 → 写入历史
  第2轮：恢复历史 + 再注入 → 历史里出现2份
  第N轮：历史里有N份重复用户画像 → Token严重浪费

✅ Ephemeral 注入（正确）：
  每次LLM调用前：把用户画像注入请求级SystemPrompt
  调用结束后：只把 Human + AI + Tool 消息写入历史
  → 对话历史永远干净
  → Token可控，压缩质量好
```

### 8.2 Memory Middleware vs System Prompt Builder

| 职责 | 负责模块 | 说明 |
|-----|---------|------|
| 静态内容 | System Prompt Builder | 启动时固定，写入模板 |
| 动态注入 | Memory Middleware | 每次调用前注入，不写历史 |

---

## 9. 面试话术

**Q: 你的 Prompt + Context 模块是怎么设计的？**

> "分两层设计。第一层是框架无关的概念层，定义了10个子模块和10个Slot的职责分工。第二层是 LangChain 实现，我基于 AgentMiddleware.wrap_model_call 实现 Ephemeral 注入机制，确保用户画像等动态内容不污染对话历史。Token 预算采用32K工作预算，Slot⑧会话历史有16K弹性空间，几乎不需要压缩。"

**Q: Ephemeral 注入是怎么实现的？**

> "通过 MemoryMiddleware.wrap_model_call 钩子，在每次 LLM 调用前从 Long Memory 读取用户画像，用 request.override(system_message=...) 注入到请求级 SystemMessage。这个注入只在当次调用生效，不写入 state['messages']，所以对话历史永远干净。"

**Q: Token 预算是怎么管理的？**

> "采用32K工作预算，扣除8K输出预留，剩下24K可用于输入。固定Slot占3.7K（System Prompt + 用户画像 + 工具Schema），会话历史有16K弹性空间。每次 LLM 调用前用 TokenCounter 统计历史占用，超限则触发 SummarizationMiddleware 压缩。"

---

**下一步**: 从 Phase 1 任务开始创建 `templates.py`
