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
