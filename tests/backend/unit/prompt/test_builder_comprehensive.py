"""
单元测试：Prompt 构建完整流程

测试 prompt 组装的各个方面，包括：
- 基础 prompt 结构
- 技能注入
- 工具 Schema 注入
- Token 预算管理
- 多场景 prompt 生成
"""

import pytest
from app.prompt.builder import build_system_prompt
from app.skills.models import SkillSnapshot, SkillEntry
from app.memory.schemas import UserProfile


class TestPromptBasicStructure:
    """测试 Prompt 基础结构"""

    def test_prompt_contains_role_definition(self):
        """Prompt 应包含角色定义"""
        prompt, _snapshot = build_system_prompt()
        assert "AI 助手" in prompt or "助手" in prompt

    def test_prompt_contains_usage_guide(self):
        """Prompt 应包含使用指南"""
        prompt, _snapshot = build_system_prompt()
        assert "使用指南" in prompt or "指南" in prompt

    def test_prompt_contains_static_few_shot(self):
        """Prompt 应包含静态 few-shot 示例"""
        prompt, _snapshot = build_system_prompt()
        assert "示例" in prompt or "示例对话" in prompt

    def test_prompt_not_empty(self):
        """Prompt 不应为空"""
        prompt, _snapshot = build_system_prompt()
        assert prompt
        assert len(prompt.strip()) > 100


class TestPromptWithTools:
    """测试带工具的 Prompt 生成"""

    def test_prompt_includes_tool_schemas(self):
        """Prompt 应包含工具 Schema"""
        prompt, _snapshot = build_system_prompt(available_tools=["web_search", "read_file"])
        assert "web_search" in prompt
        assert "read_file" in prompt

    def test_prompt_tool_section_order(self):
        """工具 Schema 应在正确位置"""
        prompt, _snapshot = build_system_prompt(available_tools=["web_search"])
        role_pos = prompt.find("AI 助手")
        tools_pos = prompt.find("web_search")
        # 工具应该在角色定义之后
        assert role_pos < tools_pos or tools_pos == -1


class TestPromptWithSkills:
    """测试带技能的 Prompt 生成"""

    def test_prompt_includes_skill_protocol(self):
        """Prompt 应包含 Skill Protocol"""
        prompt, _snapshot = build_system_prompt()
        assert "Skill Protocol" in prompt or "技能协议" in prompt or "技能使用" in prompt or "使用协议" in prompt

    def test_prompt_includes_active_skills(self):
        """Prompt 应包含活跃技能列表"""
        skill_entry = SkillEntry(
            name="legal-search",
            description="法律检索技能，用于搜索法律法规",
            file_path="/path/to/legal.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## Skills\nlegal-search",
        )

        prompt, _snapshot = build_system_prompt(skill_snapshot=snapshot)
        assert "legal-search" in prompt

    def test_prompt_skill_snapshot_format(self):
        """Snapshot prompt 格式正确"""
        skill_entry = SkillEntry(
            name="csv-analyzer",
            description="CSV 分析技能",
            file_path="/path/to/csv.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="<skills><skill><name>csv-analyzer</name></skill></skills>",
        )

        prompt, _snapshot = build_system_prompt(skill_snapshot=snapshot)
        assert "<skills>" in prompt


class TestPromptWithUserProfile:
    """测试带用户画像的 Prompt 生成"""

    def test_prompt_includes_user_profile(self):
        """Prompt 应包含用户画像"""
        user_profile = UserProfile(
            user_id="test_user",
            preferences={
                "language": "zh",
                "style": "concise",
                "domain": "finance",
            }
        )
        prompt, _snapshot = build_system_prompt(episodic=user_profile)
        assert "用户画像" in prompt or "偏好" in prompt

    def test_user_profile_injected_correctly(self):
        """用户画像字段正确注入"""
        user_profile = UserProfile(
            user_id="test_user",
            preferences={"语言": "中文", "风格": "简洁"}
        )
        prompt, _snapshot = build_system_prompt(episodic=user_profile)
        assert "中文" in prompt or "language" in prompt.lower()


class TestPromptSlotBudget:
    """测试 Token Slot 预算"""

    def test_prompt_tracks_slot_usage(self):
        """Prompt 应跟踪 Slot 使用情况"""
        prompt, slot_snapshot = build_system_prompt(
            available_tools=["web_search"],
            track_slots=True,
        )
        assert slot_snapshot is not None
        assert slot_snapshot.total_tokens > 0

    def test_slot_history_dynamic(self):
        """History slot 应该是动态预算"""
        prompt, slot_snapshot = build_system_prompt(track_slots=True)
        # 找到 history slot
        history_slot = None
        for slot in slot_snapshot.slots.values():
            if slot.name == "history":
                history_slot = slot
                break
        assert history_slot is not None


class TestPromptMultiScenario:
    """测试多场景 Prompt 生成"""

    def test_legal_analysis_scenario(self):
        """法律分析场景 Prompt"""
        skill_entry = SkillEntry(
            name="legal-search",
            description="法律检索技能，用于搜索和引用法律法规",
            file_path="/path/to/legal.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## Skills\nlegal-search",
        )
        user_profile = UserProfile(
            user_id="lawyer",
            preferences={"domain": "legal", "language": "zh"}
        )

        prompt, _snapshot = build_system_prompt(
            skill_snapshot=snapshot,
            episodic=user_profile,
            available_tools=["web_search", "read_file"],
        )

        assert "legal-search" in prompt
        assert "web_search" in prompt

    def test_csv_analysis_scenario(self):
        """CSV 分析场景 Prompt"""
        skill_entry = SkillEntry(
            name="csv-analyzer",
            description="CSV 分析技能，用于数据统计和可视化",
            file_path="/path/to/csv.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## Skills\ncsv-analyzer",
        )

        prompt, _snapshot = build_system_prompt(
            skill_snapshot=snapshot,
            available_tools=["python_repl", "read_file"],
        )

        assert "csv-analyzer" in prompt

    def test_multi_skill_scenario(self):
        """多技能场景 Prompt"""
        skill_entries = [
            SkillEntry(
                name="legal-search",
                description="法律检索",
                file_path="/path/legal.md",
            ),
            SkillEntry(
                name="csv-analyzer",
                description="CSV 分析",
                file_path="/path/csv.md",
            ),
        ]
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=skill_entries,
            prompt="## Skills\nlegal-search\ncsv-analyzer",
        )

        prompt, _snapshot = build_system_prompt(skill_snapshot=snapshot)
        assert "legal-search" in prompt
        assert "csv-analyzer" in prompt

    def test_hil_aware_scenario(self):
        """HIL 敏感场景 Prompt"""
        skill_entry = SkillEntry(
            name="email-sender",
            description="邮件发送技能（需人工确认）",
            file_path="/path/email.md",
        )
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=[skill_entry],
            prompt="## Skills\nemail-sender",
        )

        prompt, _snapshot = build_system_prompt(
            skill_snapshot=snapshot,
            available_tools=["send_email"],
        )

        assert "send_email" in prompt


class TestPromptEdgeCases:
    """测试边界情况"""

    def test_empty_tools_list(self):
        """空工具列表"""
        prompt, _snapshot = build_system_prompt(available_tools=[])
        # 应该仍然有基础 prompt
        assert prompt
        assert len(prompt) > 50

    def test_null_skill_snapshot(self):
        """空 Skill Snapshot"""
        prompt, _snapshot = build_system_prompt(skill_snapshot=None)
        # 应该仍然有基础 prompt
        assert prompt

    def test_null_user_profile(self):
        """空用户画像"""
        prompt, _snapshot = build_system_prompt(episodic=None)
        assert prompt

    def test_very_long_tool_list(self):
        """长工具列表"""
        long_tools = [f"tool_{i}" for i in range(50)]
        prompt, _snapshot = build_system_prompt(available_tools=long_tools)
        # Prompt 应该生成（可能有长度限制）
        assert prompt

    def test_unicode_characters(self):
        """Unicode 字符支持"""
        user_profile = UserProfile(
            user_id="test",
            preferences={"语言": "中文", "姓名": "张三"}
        )
        prompt, _snapshot = build_system_prompt(episodic=user_profile)
        assert "张三" in prompt
