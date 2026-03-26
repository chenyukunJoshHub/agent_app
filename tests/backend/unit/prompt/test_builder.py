"""单元测试：System Prompt 构建器

测试 builder.py 中的 build_system_prompt 函数。
"""

import pytest
from app.prompt.builder import build_system_prompt, build_system_prompt_legacy
from app.skills.models import (
    SkillSnapshot,
    SkillDefinition,
    SkillMetadata,
    SkillEntry,
    InvocationPolicy,
)
from app.memory.schemas import UserProfile


class TestBuildSystemPrompt:
    """测试 build_system_prompt 函数"""

    def test_build_system_prompt_minimal(self):
        """测试最小参数调用（无任何可选参数）"""
        result, _snapshot = build_system_prompt()

        assert result
        assert len(result) > 0
        assert "角色" in result or "AI 助手" in result

    def test_build_system_prompt_with_tools(self):
        """测试带工具列表的调用"""
        prompt, _snapshot = build_system_prompt(available_tools=["web_search", "read_file"])

        assert "web_search" in prompt
        assert "read_file" in prompt
        assert "可用工具" in prompt

    def test_build_system_prompt_with_skill_snapshot(self):
        """测试带 Skill Snapshot 的调用"""
        # 创建 SkillEntry（不是 SkillDefinition）
        skill_entry = SkillEntry(
            name="test_skill",
            description="测试技能 - 用于测试合同分析",
            file_path="/path/to/skill.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## 自定义 Skill Prompt\n这是测试内容",
        )

        prompt, _snapshot = build_system_prompt(skill_snapshot=snapshot)

        assert "test_skill" in prompt
        assert "测试技能" in prompt
        assert "自定义 Skill Prompt" in prompt

    def test_build_system_prompt_with_episodic(self):
        """测试带用户画像的调用"""
        user_profile = UserProfile(
            user_id="test_user",
            preferences={
                "语言": "中文",
                "风格": "简洁",
                "专业领域": "金融",
            }
        )

        prompt, _snapshot = build_system_prompt(episodic=user_profile)

        assert "用户画像" in prompt
        assert "语言: 中文" in prompt
        assert "风格: 简洁" in prompt
        assert "专业领域: 金融" in prompt

    def test_build_system_prompt_with_all_params(self):
        """测试带所有参数的调用"""
        skill_entry = SkillEntry(
            name="contract_analyzer",
            description="合同分析 - 用于分析合同条款和签署状态",
            file_path="/path/to/contract.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## 合同分析 Skill\n请分析合同条款",
        )
        user_profile = UserProfile(
            user_id="test_user",
            preferences={"角色": "法务助理"}
        )

        prompt, _snapshot = build_system_prompt(
            skill_snapshot=snapshot,
            episodic=user_profile,
            available_tools=["web_search", "read_file"],
        )

        # 验证所有部分都存在
        assert "contract_analyzer" in prompt
        assert "用户画像" in prompt
        assert "web_search" in prompt
        assert "可用工具" in prompt
        assert "Skill 使用协议" in prompt

    def test_build_system_prompt_contains_usage_guide(self):
        """验证生成的 Prompt 包含使用指南"""
        prompt, _snapshot = build_system_prompt()

        assert "使用指南" in prompt
        assert "首先理解用户需求" in prompt

    def test_build_system_prompt_contains_static_few_shot(self):
        """验证生成的 Prompt 包含静态 Few-shot"""
        prompt, _snapshot = build_system_prompt()

        assert "示例对话" in prompt
        assert "示例 1" in prompt
        assert "示例 2" in prompt


class TestBuildSystemPromptLegacy:
    """测试向后兼容的简化版本"""

    def test_legacy_function_exists(self):
        """验证向后兼容函数存在"""
        assert callable(build_system_prompt_legacy)

    def test_legacy_function_works(self):
        """验证向后兼容函数可以正常调用"""
        prompt = build_system_prompt_legacy(
            available_tools=["web_search"]
        )

        assert prompt
        assert "web_search" in prompt

    def test_legacy_without_episodic(self):
        """验证不传 episodic 时也能正常工作"""
        prompt = build_system_prompt_legacy()

        assert prompt
        # 不应该包含"用户画像"
        assert "用户画像" not in prompt


class TestPromptStructure:
    """测试生成的 Prompt 结构"""

    def test_prompt_has_proper_order(self):
        """验证 Prompt 各部分顺序正确"""
        prompt, _snapshot = build_system_prompt(available_tools=["web_search"])

        # 验证顺序：角色 → 工具 → 协议 → Few-shot → 使用指南
        role_pos = prompt.find("AI 助手")
        tools_pos = prompt.find("可用工具")
        protocol_pos = prompt.find("Skill 使用协议")
        few_shot_pos = prompt.find("示例对话")
        guide_pos = prompt.find("使用指南")

        # 验证顺序（不一定连续，但应该递增）
        assert role_pos < tools_pos or tools_pos == -1
        assert tools_pos < protocol_pos or protocol_pos == -1
        assert protocol_pos < few_shot_pos or few_shot_pos == -1
        assert few_shot_pos < guide_pos or guide_pos == -1

    def test_prompt_not_empty(self):
        """验证生成的 Prompt 不为空"""
        prompt, _snapshot = build_system_prompt()

        assert prompt.strip()
        assert len(prompt.strip()) > 100  # 至少有一定长度
