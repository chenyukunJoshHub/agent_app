# Procedural Memory Injector — 设计文档

**日期**: 2026-03-26
**范围**: Memory Injector 中 Procedural 的读取注入流程（P0）+ BaseProcessor 统一契约 + Episodic 闭环审查

---

## 背景

Memory Middleware 已实现 Episodic（用户画像）的加载与注入流程。
Procedural（工作流 SOP）的完整加载链路已就绪：
- `memory/schemas.py`：`MemoryContext` 已有 `procedural: ProceduralMemory` 字段
- `abefore_agent`：已调用 `load_procedural` 并写入 `memory_ctx.procedural`
- `api/preferences.py`：`POST /api/user/procedural` 写入 API 已注册

**唯一缺口**：`wrap_model_call` 未将 `memory_ctx.procedural` 内容注入 LLM prompt，导致工作流 SOP 数据从未进入 LLM 视野。

**扩展动机**：未来 RAGRetrieverMiddleware、FewshotMiddleware 等处理器加入时，若无统一契约，`build_injection_parts` 将成为无规范的硬编码堆砌。引入 `BaseInjectionProcessor` 确保每个注入源遵循相同接口，`wrap_model_call` 对新处理器零改动。

---

## 目标

1. 新增 `BaseInjectionProcessor` 抽象，统一注入处理器契约
2. 将 Episodic / Procedural 封装为各自的 Processor 实现
3. `MemoryManager.build_injection_parts` 改为迭代 processors 列表
4. `wrap_model_call` 改为通用迭代，未来扩展零成本
5. 确认 Episodic 闭环状态，补充代码注释

**不在范围内（P2）**：Procedural 写回（`aafter_agent`），Episodic 自动写回，动态注册 / 配置文件驱动。

---

## 数据流

```
abefore_agent
  ├── load_episodic(user_id)     → memory_ctx.episodic
  └── load_procedural(user_id)  → memory_ctx.procedural
                   ↓
wrap_model_call
  ├── build_injection_parts(ctx)
  │     ├── EpisodicProcessor.build_prompt(ctx)   → episodic_text
  │     └── ProceduralProcessor.build_prompt(ctx) → procedural_text
  │     → dict[slot_name, text]，顺序由 processors 列表决定
  ├── combined = "".join(parts.values())   # episodic 在前（近端偏差）
  ├── 注入 HumanMessage（combined 替代原 memory_text）
  └── for slot_name, text in parts.items():
          emit_slot_update(slot_name, tokens=count_tokens(text), enabled=bool(text))
```

注入顺序：由 `processors = [EpisodicProcessor(), ProceduralProcessor()]` 列表顺序决定，Episodic 在前。

---

## 改动文件

### 1. 新增 `backend/app/memory/processors.py`

```python
from abc import ABC, abstractmethod
from app.memory.schemas import MemoryContext


class BaseInjectionProcessor(ABC):
    """所有 Ephemeral 注入处理器的统一契约。

    每个处理器负责从 MemoryContext 中提取特定类型的记忆内容，
    构建为可注入 HumanMessage 的文本片段。

    约定：
    - slot_name 对应 ContextPanel 中的 slot 名称
    - build_prompt 返回空字符串 "" 表示无内容（不注入）
    - build_prompt 不抛出异常，静默返回 "" 即可
    """

    slot_name: str

    @abstractmethod
    def build_prompt(self, ctx: MemoryContext) -> str:
        """从 ctx 构建注入文本，无内容时返回 ""。"""
        ...


class EpisodicProcessor(BaseInjectionProcessor):
    """Episodic 注入处理器：用户画像（preferences）。

    输出格式（preferences 非空时）：
        \n\n[用户画像]\n  domain: legal-tech\n  language: zh

    preferences 为空时返回 ""。
    """

    slot_name = "episodic"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)


class ProceduralProcessor(BaseInjectionProcessor):
    """Procedural 注入处理器：工作流 SOP。

    输出格式（workflows 非空时）：
        \n\n[程序记忆 - 工作流 SOP]\n\n### 合同审查流程\n1. 先搜索...

    workflows 为空（{}）时返回 ""。
    """

    slot_name = "procedural"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.procedural.workflows:
            return ""
        lines = [
            f"\n### {name}\n{instruction}"
            for name, instruction in ctx.procedural.workflows.items()
        ]
        return "\n\n[程序记忆 - 工作流 SOP]\n" + "\n".join(lines)
```

---

### 2. `backend/app/memory/manager.py`

**`__init__` 新增 `processors` 参数**：

```python
def __init__(
    self,
    store: AsyncPostgresStore,
    processors: list[BaseInjectionProcessor] | None = None,
) -> None:
    self.store = store
    self.processors = processors or [EpisodicProcessor(), ProceduralProcessor()]
```

**`build_injection_parts` 改为迭代**：

```python
def build_injection_parts(self, ctx: MemoryContext) -> dict[str, str]:
    """迭代所有注入处理器，返回 {slot_name: text}。

    顺序由 self.processors 列表决定（影响注入顺序）。
    未来新增处理器只需修改构造函数中的 processors 列表。
    """
    return {p.slot_name: p.build_prompt(ctx) for p in self.processors}
```

**`build_ephemeral_prompt` 保留为 deprecated wrapper**（避免破坏现有测试）：

```python
def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
    """已废弃，请使用 build_injection_parts。保留以兼容现有测试。"""
    return EpisodicProcessor().build_prompt(ctx)
```

---

### 3. `backend/app/agent/middleware/memory.py`

`wrap_model_call` 改动（通用迭代，不再硬编码 slot 名称）：

```python
# 原：
memory_text = self.mm.build_ephemeral_prompt(memory_ctx)

# 改为：
parts = self.mm.build_injection_parts(memory_ctx)
combined = "".join(parts.values())

# 注入（combined 替代原 memory_text）
# 注意：架构文档 §1.4 设计为 request.override(system_message=...)，
# 实际采用注入 HumanMessage 的变通方案（框架 override messages 更可靠）。
# 功能等价，但对话历史中用户消息会携带注入内容（不影响 Ephemeral 语义）。
# awrap_model_call 通过 delegation 自动继承此改动，无需单独修改。

# 通用迭代 emit_slot_update，新增处理器无需改动此处
for slot_name, text in parts.items():
    emit_slot_update(slot_name, tokens=count_tokens(text), enabled=bool(text))
```

**`emit_slot_update` enabled 逻辑**：

| episodic_text | procedural_text | combined 注入 | episodic enabled | procedural enabled |
|:---:|:---:|:---:|:---:|:---:|
| 非空 | 非空 | ✅ | true | true |
| 非空 | 空 | ✅ | true | false |
| 空 | 非空 | ✅ | false | true |
| 空 | 空 | ❌ 不注入 | false | false |

---

### 4. 新增 `tests/backend/unit/memory/test_processors.py`

覆盖 `BaseInjectionProcessor` 及两个实现类：

| 用例 | 说明 |
|------|------|
| `test_episodic_processor_with_preferences` | 有 preferences → 返回 `[用户画像]` 格式文本 |
| `test_episodic_processor_empty_preferences` | `{}` → 返回 `""` |
| `test_procedural_processor_with_workflows` | 有 workflows → 返回 `[程序记忆 - 工作流 SOP]` 格式文本 |
| `test_procedural_processor_empty_workflows` | `{}` → 返回 `""` |
| `test_processor_slot_names` | 两者 `slot_name` 分别为 `"episodic"` / `"procedural"` |
| `test_custom_processor_integration` | 自定义 Processor 注入 MemoryManager，出现在 `build_injection_parts` 结果中 |

### 5. `tests/backend/unit/agent/test_memory_middleware.py`

新增 `TestProceduralInjection`：

| 用例 | 说明 |
|------|------|
| `test_build_injection_parts_returns_both_keys` | dict 含 episodic / procedural 两个 key |
| `test_injection_order_episodic_before_procedural` | combined 中 episodic 文本在 procedural 之前 |
| `test_wrap_model_call_both_injected` | 两者都有内容 → HumanMessage 包含 combined 文本 |
| `test_wrap_model_call_only_procedural` | 只有 procedural → 正常注入，不报错 |
| `test_wrap_model_call_both_empty` | 两者都空 → 不注入，HumanMessage 不变 |
| `test_slot_emit_for_each_processor` | 每个 slot 各自 emit，tokens 和 enabled 正确 |
| `test_procedural_slot_emit_disabled_when_empty` | procedural 空时 `enabled=False` |

---

## Episodic 闭环审查

| 路径 | 状态 |
|------|------|
| 外部写入（`POST /api/user/preferences`） | ✅ 闭环 |
| `abefore_agent` 读取 | ✅ 闭环 |
| `wrap_model_call` 注入 LLM | ✅ 闭环（通过 `EpisodicProcessor`） |
| `emit_slot_update("episodic")` | ✅ 闭环（通用迭代，自动覆盖） |
| `aafter_agent` 自动写回 | 🔘 P2，按设计保留 no-op |

**结论**：Episodic 仅需将 `build_ephemeral_prompt` 逻辑迁移至 `EpisodicProcessor`，功能行为不变。

---

## 不改动项

- `abefore_agent` / `aafter_agent` — 加载链路已就绪，P2 no-op 保留
- `api/preferences.py` — 写入 API 已就绪
- `memory/schemas.py` — `ProceduralMemory` / `MemoryContext` 已定义
- `prompt/builder.py` — 静态 System Prompt 中 procedural slot 已注册
