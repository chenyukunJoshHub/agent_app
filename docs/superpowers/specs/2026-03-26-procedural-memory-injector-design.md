# Procedural Memory Injector — 设计文档

**日期**: 2026-03-26
**范围**: Memory Injector 中 Procedural 的读取注入流程（P0），Episodic 闭环审查

---

## 背景

Memory Middleware 已实现 Episodic（用户画像）的加载与注入流程。
Procedural（工作流 SOP）的完整加载链路已就绪：
- `memory/schemas.py`：`MemoryContext` 已有 `procedural: ProceduralMemory` 字段
- `abefore_agent`：已调用 `load_procedural` 并写入 `memory_ctx.procedural`
- `api/preferences.py`：`POST /api/user/procedural` 写入 API 已注册

**唯一缺口**：`wrap_model_call` 未将 `memory_ctx.procedural` 内容注入 LLM prompt，导致工作流 SOP 数据从未进入 LLM 视野。

---

## 目标

1. 实现 Procedural 读取注入流程（`wrap_model_call` 注入 + slot emit）
2. 确认 Episodic 闭环状态，补充代码注释

**不在范围内（P2）**：Procedural 写回（`aafter_agent`），Episodic 自动写回。

---

## 数据流

```
abefore_agent
  ├── load_episodic(user_id)     → memory_ctx.episodic
  └── load_procedural(user_id)  → memory_ctx.procedural

wrap_model_call
  ├── build_injection_parts(ctx)          ← 新增协调方法
  │     ├── build_ephemeral_prompt(ctx)   → episodic_text   （原有，不改）
  │     └── build_procedural_prompt(ctx)  → procedural_text （新增）
  │     combined = episodic_text + procedural_text
  ├── 注入 HumanMessage（combined 替代原 memory_text）
  ├── emit_slot_update("episodic",   tokens=count_tokens(episodic_text))
  └── emit_slot_update("procedural", tokens=count_tokens(procedural_text))  ← 新增
```

注入顺序：Episodic 在前，Procedural 在后（SOP 紧贴用户消息，利用近端偏差）。

---

## 改动文件

### 1. `backend/app/memory/manager.py`

新增两个方法：

```python
def build_procedural_prompt(self, ctx: MemoryContext) -> str:
    """构建 Procedural Ephemeral 注入文本，只处理 ctx.procedural。

    与 build_ephemeral_prompt 职责分离：
    - build_ephemeral_prompt  → episodic（用户画像）
    - build_procedural_prompt → procedural（工作流 SOP）

    输出格式（workflows 非空时）：
        \n\n[程序记忆 - 工作流 SOP]\n
        \n### 合同审查流程\n1. 先搜索...\n2. 再发邮件...

    workflows 为空（{}）或 ctx.procedural.workflows 不存在时，返回 ""（与 build_ephemeral_prompt 约定一致）。
    """
    if not ctx.procedural.workflows:
        return ""
    lines = [
        f"\n### {name}\n{instruction}"
        for name, instruction in ctx.procedural.workflows.items()
    ]
    return "\n\n[程序记忆 - 工作流 SOP]\n" + "\n".join(lines)


def build_injection_parts(self, ctx: MemoryContext) -> dict[str, str]:
    """协调所有 Ephemeral 注入源，返回 {slot_name: text}。

    返回类型：dict[str, str]，key 为 slot 名称，value 为注入文本（可为空字符串）。
    调用方（wrap_model_call）从 dict 独立取出各 slot 文本，分别用于 token 计量和 emit_slot_update。

    未来新增注入类型（RAG 等）只需在此添加一行，wrap_model_call 不需改动。
    """
    return {
        "episodic":   self.build_ephemeral_prompt(ctx),
        "procedural": self.build_procedural_prompt(ctx),
    }
```

### 2. `backend/app/agent/middleware/memory.py`

`wrap_model_call` 改动：

```python
# 原：
memory_text = self.mm.build_ephemeral_prompt(memory_ctx)

# 改为：
parts = self.mm.build_injection_parts(memory_ctx)
episodic_text   = parts["episodic"]
procedural_text = parts["procedural"]
# episodic 在前，procedural 紧贴用户消息（近端偏差）
combined = episodic_text + procedural_text

# 注入（combined 替代原 memory_text）
# 注意：架构文档 §1.4 设计为 request.override(system_message=...)，
# 实际采用注入 HumanMessage 的变通方案（框架 override messages 更可靠）。
# 功能等价，但对话历史中用户消息会携带注入内容（不影响 Ephemeral 语义）。

# emit_slot_update 拆为两条（独立计量）
# awrap_model_call 通过 delegation 自动继承此改动，无需单独修改。
emit_slot_update("episodic",   tokens=count_tokens(episodic_text),   enabled=bool(episodic_text))
emit_slot_update("procedural", tokens=count_tokens(procedural_text), enabled=bool(procedural_text))
```

**`emit_slot_update` enabled 逻辑**：

| episodic_text | procedural_text | combined 注入 | episodic enabled | procedural enabled |
|:---:|:---:|:---:|:---:|:---:|
| 非空 | 非空 | ✅ | true | true |
| 非空 | 空 | ✅ | true | false |
| 空 | 非空 | ✅ | false | true |
| 空 | 空 | ❌ 不注入 | false | false |

### 3. `tests/backend/unit/agent/test_memory_middleware.py`

新增 `TestProceduralInjection`，覆盖以下用例：

| 用例 | 说明 |
|------|------|
| `test_build_procedural_prompt_with_workflows` | 有 workflows → 返回包含 `[程序记忆]` 标头的文本 |
| `test_build_procedural_prompt_empty_workflows` | `{}` → 返回 `""` |
| `test_build_injection_parts_returns_both_keys` | 返回 dict 含 episodic / procedural 两个 key |
| `test_injection_order_episodic_before_procedural` | combined 中 episodic 文本在 procedural 之前 |
| `test_wrap_model_call_both_injected` | 两者都有内容 → HumanMessage 包含 combined 文本 |
| `test_wrap_model_call_only_procedural` | 只有 procedural → 正常注入，不报错 |
| `test_wrap_model_call_both_empty` | 两者都空 → 不注入，HumanMessage 不变 |
| `test_procedural_slot_emit_tokens_nonzero` | `emit_slot_update("procedural", tokens=N, enabled=True)` 被调用 |
| `test_procedural_slot_emit_disabled_when_empty` | procedural 空时 `enabled=False` |

---

## Episodic 闭环审查

| 路径 | 状态 |
|------|------|
| 外部写入（`POST /api/user/preferences`） | ✅ 闭环 |
| `abefore_agent` 读取 | ✅ 闭环 |
| `wrap_model_call` 注入 LLM | ✅ 闭环 |
| `emit_slot_update("episodic")` | ✅ 闭环 |
| `aafter_agent` 自动写回 | 🔘 P2，按设计保留 no-op |

**结论**：Episodic 不需要逻辑改动，仅补充一行注释说明注入位置偏差。

---

## 不改动项

- `abefore_agent` — 已正确加载 procedural，无需改动
- `aafter_agent` — P2 no-op，保留
- `api/preferences.py` — 写入 API 已就绪
- `memory/schemas.py` — `ProceduralMemory` 已定义
- `prompt/builder.py` — 静态 System Prompt 中 procedural slot 已注册（用于 ContextPanel 显示）
