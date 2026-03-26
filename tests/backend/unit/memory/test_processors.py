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
            display_name = "Dummy"
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
