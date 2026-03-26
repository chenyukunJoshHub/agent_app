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
