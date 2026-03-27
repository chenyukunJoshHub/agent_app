# Procedural Memory Injector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `BaseInjectionProcessor` 统一注入契约，将 Episodic 和 Procedural 封装为各自 Processor，并通过 `wrap_model_call` 将 Procedural 工作流 SOP 注入到 LLM prompt 中。

**Architecture:** 新增 `memory/processors.py` 定义抽象基类和两个实现类；`MemoryManager.build_injection_parts` 改为迭代 processors 列表；`wrap_model_call` 改为通用迭代，对未来新处理器零改动。

**Tech Stack:** Python 3.12, pydantic v2, pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-03-26-procedural-memory-injector-design.md`

---

## 文件清单

| 操作 | 路径 | 职责 |
|------|------|------|
| 新增 | `backend/app/memory/processors.py` | BaseInjectionProcessor + EpisodicProcessor + ProceduralProcessor |
| 修改 | `backend/app/memory/manager.py` | 接受 processors 列表，build_injection_parts 改为迭代 |
| 修改 | `backend/app/agent/middleware/memory.py` | wrap_model_call 改为通用迭代 |
| 新增 | `tests/backend/unit/memory/test_processors.py` | processors 单元测试 |
| 修改 | `tests/backend/unit/agent/test_memory_middleware.py` | 新增 TestProceduralInjection |

> **注意**：运行测试前请确认当前已有 2 个预存在的测试失败（与本次无关）：
> - `test_memory_middleware.py::TestMemoryMiddlewareWrapModelCall::test_wrap_model_call_passes_through_with_no_memory_ctx`
> - `test_memory_middleware.py::TestMemoryMiddlewareWrapModelCall::test_wrap_model_call_passes_through_with_empty_preferences`
> 本次实现不负责修复这两个测试，但不能使其变更为新的失败原因。

---

## Task 1: 新增 processors.py — BaseInjectionProcessor + EpisodicProcessor

**Files:**
- Create: `backend/app/memory/processors.py`
- Create: `tests/backend/unit/memory/test_processors.py`

- [ ] **Step 1: 写 EpisodicProcessor 的失败测试**

新建 `tests/backend/unit/memory/test_processors.py`：

```python
"""Tests for memory injection processors."""
import pytest
from app.memory.processors import BaseInjectionProcessor, EpisodicProcessor
from app.memory.schemas import MemoryContext, UserProfile, ProceduralMemory


class TestEpisodicProcessor:
    """Tests for EpisodicProcessor."""

    def test_slot_name_is_episodic(self):
        """EpisodicProcessor.slot_name 应为 'episodic'"""
        assert EpisodicProcessor.slot_name == "episodic"

    def test_is_base_injection_processor(self):
        """EpisodicProcessor 应继承 BaseInjectionProcessor"""
        assert issubclass(EpisodicProcessor, BaseInjectionProcessor)

    def test_display_name_exists(self):
        """EpisodicProcessor 应有 display_name 属性（emit_slot_update 必填）"""
        assert hasattr(EpisodicProcessor, "display_name")
        assert EpisodicProcessor.display_name != ""

    def test_build_prompt_with_preferences(self):
        """有 preferences 时应返回包含 [用户画像] 标头的文本"""
        proc = EpisodicProcessor()
        ctx = MemoryContext(
            episodic=UserProfile(preferences={"domain": "legal-tech", "language": "zh"})
        )
        result = proc.build_prompt(ctx)
        assert "[用户画像]" in result
        assert "domain: legal-tech" in result
        assert "language: zh" in result

    def test_build_prompt_empty_preferences_returns_empty_string(self):
        """preferences 为 {} 时应返回空字符串"""
        proc = EpisodicProcessor()
        ctx = MemoryContext(episodic=UserProfile(preferences={}))
        result = proc.build_prompt(ctx)
        assert result == ""

    def test_build_prompt_default_context_returns_empty_string(self):
        """默认 MemoryContext（无 preferences）应返回空字符串"""
        proc = EpisodicProcessor()
        ctx = MemoryContext()
        result = proc.build_prompt(ctx)
        assert result == ""
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
cd <PROJECT_ROOT>
python -m pytest tests/backend/unit/memory/test_processors.py -v
```

期望：`ModuleNotFoundError: No module named 'app.memory.processors'`

- [ ] **Step 3: 创建 processors.py，实现 BaseInjectionProcessor + EpisodicProcessor**

新建 `backend/app/memory/processors.py`：

```python
"""Memory injection processors.

Each processor extracts one type of memory from MemoryContext and builds
an ephemeral text snippet to inject into the LLM's HumanMessage.

Convention:
- slot_name maps to ContextPanel slot names (episodic, procedural, rag, ...)
- build_prompt returns "" when there is nothing to inject
- build_prompt never raises; it returns "" on any missing data
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.memory.schemas import MemoryContext


class BaseInjectionProcessor(ABC):
    """Unified contract for all ephemeral injection processors.

    Implement this to add a new memory type to the injection pipeline.
    Register the instance in MemoryManager(processors=[...]).
    """

    slot_name: str     # Must match a slot name in ContextPanel
    display_name: str  # Human-readable label shown in ContextPanel (required by emit_slot_update)

    @abstractmethod
    def build_prompt(self, ctx: MemoryContext) -> str:
        """Extract memory from ctx and return injection text.

        Returns:
            str: Non-empty injection text, or "" if nothing to inject.
        """
        ...


class EpisodicProcessor(BaseInjectionProcessor):
    """Episodic memory processor: user profile preferences.

    Output format (when preferences non-empty):

        \\n\\n[用户画像]\\n  domain: legal-tech\\n  language: zh

    Returns "" when preferences is empty or missing.
    """

    slot_name = "episodic"
    display_name = "用户画像"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
python -m pytest tests/backend/unit/memory/test_processors.py::TestEpisodicProcessor -v
```

期望：5 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/processors.py tests/backend/unit/memory/test_processors.py
git commit -m "feat: add BaseInjectionProcessor and EpisodicProcessor"
```

---

## Task 2: 新增 ProceduralProcessor

**Files:**
- Modify: `backend/app/memory/processors.py`
- Modify: `tests/backend/unit/memory/test_processors.py`

- [ ] **Step 1: 写 ProceduralProcessor 的失败测试**

在 `tests/backend/unit/memory/test_processors.py` 末尾追加：

```python
class TestProceduralProcessor:
    """Tests for ProceduralProcessor."""

    def test_slot_name_is_procedural(self):
        """ProceduralProcessor.slot_name 应为 'procedural'"""
        from app.memory.processors import ProceduralProcessor
        assert ProceduralProcessor.slot_name == "procedural"

    def test_is_base_injection_processor(self):
        """ProceduralProcessor 应继承 BaseInjectionProcessor"""
        from app.memory.processors import ProceduralProcessor
        assert issubclass(ProceduralProcessor, BaseInjectionProcessor)

    def test_display_name_exists(self):
        """ProceduralProcessor 应有 display_name 属性（emit_slot_update 必填）"""
        from app.memory.processors import ProceduralProcessor
        assert hasattr(ProceduralProcessor, "display_name")
        assert ProceduralProcessor.display_name != ""

    def test_build_prompt_with_workflows(self):
        """有 workflows 时应返回包含 [程序记忆 - 工作流 SOP] 标头的文本"""
        from app.memory.processors import ProceduralProcessor
        proc = ProceduralProcessor()
        ctx = MemoryContext(
            procedural=ProceduralMemory(
                workflows={"合同审查流程": "1. 先搜索\n2. 再发邮件"}
            )
        )
        result = proc.build_prompt(ctx)
        assert "[程序记忆 - 工作流 SOP]" in result
        assert "合同审查流程" in result
        assert "先搜索" in result

    def test_build_prompt_empty_workflows_returns_empty_string(self):
        """workflows 为 {} 时应返回空字符串"""
        from app.memory.processors import ProceduralProcessor
        proc = ProceduralProcessor()
        ctx = MemoryContext(procedural=ProceduralMemory(workflows={}))
        result = proc.build_prompt(ctx)
        assert result == ""

    def test_build_prompt_default_context_returns_empty_string(self):
        """默认 MemoryContext 应返回空字符串"""
        from app.memory.processors import ProceduralProcessor
        proc = ProceduralProcessor()
        ctx = MemoryContext()
        result = proc.build_prompt(ctx)
        assert result == ""

    def test_multiple_workflows_all_appear_in_output(self):
        """多个 workflows 时，所有名称和内容都应出现在输出中"""
        from app.memory.processors import ProceduralProcessor
        proc = ProceduralProcessor()
        ctx = MemoryContext(
            procedural=ProceduralMemory(
                workflows={
                    "流程A": "步骤A1",
                    "流程B": "步骤B1",
                }
            )
        )
        result = proc.build_prompt(ctx)
        assert "流程A" in result
        assert "步骤A1" in result
        assert "流程B" in result
        assert "步骤B1" in result
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
python -m pytest tests/backend/unit/memory/test_processors.py::TestProceduralProcessor -v
```

期望：`ImportError: cannot import name 'ProceduralProcessor'`

- [ ] **Step 3: 在 processors.py 中追加 ProceduralProcessor**

在 `backend/app/memory/processors.py` 末尾追加：

```python

class ProceduralProcessor(BaseInjectionProcessor):
    """Procedural memory processor: workflow SOPs.

    Output format (when workflows non-empty):

        \\n\\n[程序记忆 - 工作流 SOP]\\n
        \\n### 合同审查流程\\n1. 先搜索...\\n2. 再发邮件...

    Returns "" when workflows is empty or missing.
    """

    slot_name = "procedural"
    display_name = "工作流 SOP"

    def build_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.procedural.workflows:
            return ""
        lines = [
            f"\n### {name}\n{instruction}"
            for name, instruction in ctx.procedural.workflows.items()
        ]
        return "\n\n[程序记忆 - 工作流 SOP]\n" + "\n".join(lines)
```

- [ ] **Step 4: 运行全量 processors 测试确认 GREEN**

```bash
python -m pytest tests/backend/unit/memory/test_processors.py -v
```

期望：全部 PASS（11 个测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory/processors.py tests/backend/unit/memory/test_processors.py
git commit -m "feat: add ProceduralProcessor"
```

---

## Task 3: 更新 MemoryManager — 接受 processors 列表

**Files:**
- Modify: `backend/app/memory/manager.py`
- Modify: `tests/backend/unit/memory/test_processors.py` (新增集成测试 class)

- [ ] **Step 1: 写 MemoryManager processors 集成的失败测试**

在 `tests/backend/unit/memory/test_processors.py` 末尾追加：

```python
class TestMemoryManagerWithProcessors:
    """Tests for MemoryManager processors integration."""

    def test_default_processors_include_episodic_and_procedural(self):
        """默认 processors 应包含 EpisodicProcessor 和 ProceduralProcessor"""
        from unittest.mock import MagicMock
        from app.memory.processors import EpisodicProcessor, ProceduralProcessor
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        slot_names = [p.slot_name for p in mm.processors]
        assert "episodic" in slot_names
        assert "procedural" in slot_names

    def test_custom_processor_is_used_in_build_injection_parts(self):
        """注入自定义 processor 时，build_injection_parts 应包含其 slot"""
        from unittest.mock import MagicMock
        from app.memory.processors import BaseInjectionProcessor
        from app.memory.manager import MemoryManager

        class DummyProcessor(BaseInjectionProcessor):
            slot_name = "dummy"
            def build_prompt(self, ctx):
                return "dummy-text"

        mm = MemoryManager(store=MagicMock(), processors=[DummyProcessor()])
        parts = mm.build_injection_parts(MemoryContext())
        assert "dummy" in parts
        assert parts["dummy"] == "dummy-text"

    def test_build_injection_parts_episodic_with_preferences(self):
        """有 preferences 时 episodic key 应有内容"""
        from unittest.mock import MagicMock
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        ctx = MemoryContext(episodic=UserProfile(preferences={"domain": "legal-tech"}))
        parts = mm.build_injection_parts(ctx)
        assert "episodic" in parts
        assert "legal-tech" in parts["episodic"]

    def test_build_injection_parts_procedural_with_workflows(self):
        """有 workflows 时 procedural key 应有内容"""
        from unittest.mock import MagicMock
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"})
        )
        parts = mm.build_injection_parts(ctx)
        assert "procedural" in parts
        assert "流程A" in parts["procedural"]

    def test_build_injection_parts_both_empty(self):
        """两者都空时，所有 value 应为空字符串"""
        from unittest.mock import MagicMock
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        parts = mm.build_injection_parts(MemoryContext())
        assert all(v == "" for v in parts.values())

    def test_injection_order_episodic_before_procedural(self):
        """默认 processors 顺序应保证 episodic 排在 procedural 之前"""
        from unittest.mock import MagicMock
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        slot_names = [p.slot_name for p in mm.processors]
        assert slot_names.index("episodic") < slot_names.index("procedural")

    def test_build_ephemeral_prompt_deprecated_wrapper_still_works(self):
        """build_ephemeral_prompt 保留为兼容 wrapper，功能不变"""
        from unittest.mock import MagicMock
        from app.memory.manager import MemoryManager
        mm = MemoryManager(store=MagicMock())
        ctx = MemoryContext(episodic=UserProfile(preferences={"lang": "zh"}))
        result = mm.build_ephemeral_prompt(ctx)
        assert "[用户画像]" in result
        assert "lang: zh" in result
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
python -m pytest tests/backend/unit/memory/test_processors.py::TestMemoryManagerWithProcessors -v
```

期望：失败（`MemoryManager.__init__` 不接受 `processors` 参数，`build_injection_parts` 未迭代 processors）

- [ ] **Step 3: 更新 manager.py**

打开 `backend/app/memory/manager.py`，做以下三处修改：

**（1）顶部新增 import**（在现有 import 行后）：

```python
from app.memory.processors import (
    BaseInjectionProcessor,
    EpisodicProcessor,
    ProceduralProcessor,
)
```

**（2）更新 `__init__`**，将：

```python
def __init__(self, store: AsyncPostgresStore) -> None:
    """Initialize MemoryManager.

    Args:
        store: AsyncPostgresStore instance for long-term memory
    """
    self.store = store
```

替换为：

```python
def __init__(
    self,
    store: AsyncPostgresStore,
    processors: list[BaseInjectionProcessor] | None = None,
) -> None:
    """Initialize MemoryManager.

    Args:
        store: AsyncPostgresStore instance for long-term memory
        processors: Injection processors in injection order.
            Defaults to [EpisodicProcessor(), ProceduralProcessor()].
            Pass a custom list to add or replace processors.
    """
    self.store = store
    self.processors = processors or [EpisodicProcessor(), ProceduralProcessor()]
```

**（3）替换 `build_ephemeral_prompt` 方法**，将：

```python
def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
    """Build ephemeral injection text for System Prompt.
    ...
    """
    if not ctx.episodic.preferences:
        return ""

    lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
    return "\n\n[用户画像]\n" + "\n".join(lines)
```

替换为：

```python
def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
    """Build episodic injection text (deprecated — use build_injection_parts).

    Kept for backward compatibility with existing tests.
    Delegates to EpisodicProcessor.
    """
    return EpisodicProcessor().build_prompt(ctx)

def build_injection_parts(self, ctx: MemoryContext) -> dict[str, str]:
    """Iterate all injection processors, returning {slot_name: text}.

    Order is determined by self.processors list order (affects injection order).
    To add a new memory type, register a new processor — no changes needed here.

    Returns:
        dict[str, str]: slot_name → injection text (may be "" if nothing to inject)
    """
    return {p.slot_name: p.build_prompt(ctx) for p in self.processors}
```

- [ ] **Step 4: 运行测试确认 GREEN**

```bash
python -m pytest tests/backend/unit/memory/test_processors.py -v
```

期望：全部 PASS

- [ ] **Step 5: 确认原有 memory 测试无回归**

```bash
python -m pytest tests/backend/unit/memory/ -v
```

期望：`test_save_episodic_is_noop_p0` 仍然失败（预存在），其余无新增失败

- [ ] **Step 6: Commit**

```bash
git add backend/app/memory/manager.py tests/backend/unit/memory/test_processors.py
git commit -m "feat: update MemoryManager to use processor list for injection"
```

---

## Task 4: 更新 wrap_model_call — 通用迭代注入

**Files:**
- Modify: `backend/app/agent/middleware/memory.py`
- Modify: `tests/backend/unit/agent/test_memory_middleware.py`

- [ ] **Step 1: 写 TestProceduralInjection 失败测试**

打开 `tests/backend/unit/agent/test_memory_middleware.py`，在文件末尾追加：

```python
class TestProceduralInjection:
    """Tests for procedural injection via build_injection_parts."""

    @pytest.fixture
    def mock_store(self):
        store = MagicMock()
        store.aput = AsyncMock()
        store.aget = AsyncMock()
        return store

    @pytest.fixture
    def memory_manager(self, mock_store):
        return MemoryManager(store=mock_store)

    @pytest.fixture
    def middleware(self, memory_manager):
        return MemoryMiddleware(memory_manager=memory_manager)

    def _make_request(self, memory_ctx=None, messages=None):
        """Helper: build a mock ModelRequest with messages list and optional state."""
        request = MagicMock()
        request.messages = messages or [HumanMessage(content="你好")]
        request.state = {"memory_ctx": memory_ctx} if memory_ctx else {}
        request.runtime = MagicMock()
        request.runtime.context = None
        # override returns a new request with updated messages
        def override(**kwargs):
            new_req = MagicMock()
            new_req.messages = kwargs.get("messages", request.messages)
            new_req.state = request.state
            new_req.runtime = request.runtime
            return new_req
        request.override.side_effect = override
        return request

    def test_procedural_text_injected_when_workflows_exist(self, middleware):
        """有 workflows 时，HumanMessage 应包含程序记忆文本"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1\n步骤2"})
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        def handler(req):
            captured.append(req)
            return MagicMock()
        middleware.wrap_model_call(request, handler)
        assert len(captured) == 1
        injected_content = captured[0].messages[0].content
        assert "程序记忆" in injected_content or "流程A" in injected_content

    def test_episodic_before_procedural_in_injection(self, middleware):
        """combined 注入中，episodic 内容应出现在 procedural 内容之前"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            episodic=UserProfile(preferences={"domain": "legal"}),
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"}),
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        content = captured[0].messages[0].content
        episodic_pos = content.find("用户画像")
        procedural_pos = content.find("程序记忆")
        assert episodic_pos < procedural_pos

    def test_only_procedural_injects_without_error(self, middleware):
        """只有 procedural，没有 episodic 时，应正常注入不报错"""
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"})
        )
        request = self._make_request(memory_ctx=ctx)
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        assert len(captured) == 1
        assert "流程A" in captured[0].messages[0].content

    def test_both_empty_no_injection(self, middleware):
        """episodic 和 procedural 都空时，HumanMessage 内容不变（无 --- 分隔符）"""
        ctx = MemoryContext()
        original_content = "原始消息"
        request = self._make_request(
            memory_ctx=ctx,
            messages=[HumanMessage(content=original_content)]
        )
        captured = []
        middleware.wrap_model_call(request, lambda r: captured.append(r) or MagicMock())
        assert len(captured) == 1
        content = captured[0].messages[0].content
        assert content == original_content
        assert "---" not in content  # 确认无注入分隔符被插入

    def test_procedural_slot_emit_enabled_when_workflows_exist(self, middleware):
        """有 workflows 时，emit_slot_update('procedural', enabled=True) 应被调用"""
        from app.memory.schemas import ProceduralMemory
        import unittest.mock as mock_module
        ctx = MemoryContext(
            procedural=ProceduralMemory(workflows={"流程A": "步骤1"})
        )
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())
        calls = {call.kwargs.get("name") or call.args[1] if call.args else None
                 for call in mock_emit.call_args_list}
        # procedural slot should have been emitted
        slot_names_called = []
        for c in mock_emit.call_args_list:
            if c.args:
                slot_names_called.append(c.args[0] if len(c.args) > 0 else None)
            if c.kwargs:
                slot_names_called.append(c.kwargs.get("name"))
        assert "procedural" in slot_names_called

    def test_procedural_slot_emit_disabled_when_empty(self, middleware):
        """workflows 为空时，emit_slot_update('procedural') 应以 enabled=False 调用"""
        import unittest.mock as mock_module
        ctx = MemoryContext()
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())
        for call in mock_emit.call_args_list:
            args = call.args
            kwargs = call.kwargs
            name = args[0] if args else kwargs.get("name", "")
            enabled = kwargs.get("enabled", True)
            if name == "procedural":
                assert enabled is False, "procedural enabled 应为 False when empty"
                break

    @pytest.mark.parametrize("episodic_prefs,procedural_wfs,exp_ep_enabled,exp_proc_enabled", [
        ({"domain": "legal"}, {"流程A": "步骤1"}, True,  True),   # 两者都有
        ({"domain": "legal"}, {},                 True,  False),  # 只有 episodic
        ({},                  {"流程A": "步骤1"}, False, True),   # 只有 procedural
        ({},                  {},                 False, False),  # 两者都空
    ])
    def test_slot_emit_enabled_four_combinations(
        self, middleware, episodic_prefs, procedural_wfs, exp_ep_enabled, exp_proc_enabled
    ):
        """spec enabled 逻辑表格 4 种组合验证"""
        import unittest.mock as mock_module
        from app.memory.schemas import ProceduralMemory
        ctx = MemoryContext(
            episodic=UserProfile(preferences=episodic_prefs),
            procedural=ProceduralMemory(workflows=procedural_wfs),
        )
        request = self._make_request(memory_ctx=ctx)
        with mock_module.patch(
            "app.agent.middleware.memory.emit_slot_update"
        ) as mock_emit:
            middleware.wrap_model_call(request, lambda r: MagicMock())

        emitted = {}
        for call in mock_emit.call_args_list:
            kwargs = call.kwargs
            emitted[kwargs.get("name")] = kwargs.get("enabled")

        assert emitted.get("episodic") == exp_ep_enabled, \
            f"episodic enabled 期望 {exp_ep_enabled}，实际 {emitted.get('episodic')}"
        assert emitted.get("procedural") == exp_proc_enabled, \
            f"procedural enabled 期望 {exp_proc_enabled}，实际 {emitted.get('procedural')}"
```

- [ ] **Step 2: 运行测试确认 RED**

```bash
python -m pytest tests/backend/unit/agent/test_memory_middleware.py::TestProceduralInjection -v
```

期望：多个失败（`wrap_model_call` 仍使用旧逻辑，无 procedural 注入）

- [ ] **Step 3: 更新 wrap_model_call**

打开 `backend/app/agent/middleware/memory.py`，将 `wrap_model_call` 方法中以下代码：

```python
        memory_text = ""
        if memory_ctx:
            logger.info("MemoryMiddleware: wrap_model_call  build_ephemeral_prompt")
            memory_text = self.mm.build_ephemeral_prompt(memory_ctx)
```

替换为：

```python
        # Build injection text from all processors via unified contract.
        # Each processor (EpisodicProcessor, ProceduralProcessor, ...) returns "" if nothing to inject.
        # Order in parts dict determines injection order (episodic before procedural).
        #
        # Note: Architecture doc §1.4 specifies request.override(system_message=...),
        # but injecting into HumanMessage is used instead (more reliable with this framework).
        # Functionally equivalent — content is ephemeral and does not pollute history semantics.
        parts: dict[str, str] = {}
        if memory_ctx:
            logger.info("MemoryMiddleware: wrap_model_call  build_injection_parts")
            parts = self.mm.build_injection_parts(memory_ctx)
        memory_text = "".join(parts.values())
```

然后将 slot emit 部分（在 `wrap_model_call` 末尾）从：

```python
        # --- 3. Always emit slot_update for episodic + history ---
        if sse_queue is not None:
            try:
                episodic_tokens = count_tokens(memory_text) if memory_text else 0
                # history = all non-system messages (human + ai + tool)
                history_tokens = sum(
                    count_tokens(str(m.content or ""))
                    for m in messages
                    if not isinstance(m, SystemMessage)
                )
                asyncio.create_task(
                    emit_slot_update(
                        sse_queue, name="episodic", display_name="用户画像",
                        tokens=episodic_tokens, enabled=bool(memory_text),
                    )
                )
                asyncio.create_task(
                    emit_slot_update(
                        sse_queue, name="history", display_name="对话历史",
                        tokens=history_tokens, enabled=True,
                    )
                )
            except RuntimeError:
                pass
```

替换为：

```python
        # --- 3. Emit slot_update for each processor + history ---
        # Build display_name lookup from processors (required by emit_slot_update signature).
        display_names = {p.slot_name: p.display_name for p in self.mm.processors}

        if sse_queue is not None:
            try:
                # Emit per-processor slot (generic — works for any future processor)
                for slot_name, text in parts.items():
                    asyncio.create_task(
                        emit_slot_update(
                            sse_queue,
                            name=slot_name,
                            display_name=display_names.get(slot_name, ""),
                            tokens=count_tokens(text) if text else 0,
                            enabled=bool(text),
                        )
                    )
                # history slot (not a processor, emitted separately)
                history_tokens = sum(
                    count_tokens(str(m.content or ""))
                    for m in messages
                    if not isinstance(m, SystemMessage)
                )
                asyncio.create_task(
                    emit_slot_update(
                        sse_queue, name="history", display_name="对话历史",
                        tokens=history_tokens, enabled=True,
                    )
                )
            except RuntimeError:
                pass
```

- [ ] **Step 4: 运行新增测试确认 GREEN**

```bash
python -m pytest tests/backend/unit/agent/test_memory_middleware.py::TestProceduralInjection -v
```

期望：全部 PASS

- [ ] **Step 5: 确认原有 middleware 测试无新增失败**

```bash
python -m pytest tests/backend/unit/agent/test_memory_middleware.py -v
```

期望：预存在的 2 个失败仍在（原因不变），新增 6 个测试全部 PASS，其余已通过的测试保持通过

- [ ] **Step 6: 运行全量 memory 相关测试**

```bash
python -m pytest tests/backend/unit/memory/ tests/backend/unit/agent/test_memory_middleware.py -v
```

期望：无新增失败

- [ ] **Step 7: Commit**

```bash
git add backend/app/agent/middleware/memory.py \
        tests/backend/unit/agent/test_memory_middleware.py
git commit -m "feat: update wrap_model_call to inject procedural via processor pipeline"
```

---

## 验收检查

- [ ] **全量相关测试通过**

```bash
python -m pytest tests/backend/unit/memory/ tests/backend/unit/agent/test_memory_middleware.py -q
```

期望：只有预存在的 `test_save_episodic_is_noop_p0` 和 2 个 `TestMemoryMiddlewareWrapModelCall` 失败，其余全部 PASS

- [ ] **端到端验证（可选）**：通过 `POST /api/user/procedural` 写入工作流，发起对话，在日志中确认 `inject_success` trace 事件包含 procedural 内容

---

## 不改动项确认

- `abefore_agent` — 已正确加载 procedural，无需改动 ✅
- `aafter_agent` — P2 no-op 保留 ✅
- `api/preferences.py` — 写入 API 已就绪 ✅
- `memory/schemas.py` — `ProceduralMemory` / `MemoryContext` 已定义 ✅
- `prompt/builder.py` — 静态 System Prompt 中 procedural slot 已注册 ✅
