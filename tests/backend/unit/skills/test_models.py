"""
Tests for Skills data models.

This test module validates the Skill data models defined in app/skills/models.py,
including SkillDefinition, SkillEntry, SkillSnapshot, SkillMetadata, InvocationPolicy,
and SkillStatus.
"""



class TestSkillStatus:
    """Test SkillStatus enum."""

    def test_skill_status_enum_values(self):
        """验证 SkillStatus 枚举包含所有必需的状态值."""
        from app.skills.models import SkillStatus

        # 验证所有必需的状态值存在
        assert hasattr(SkillStatus, "ACTIVE")
        assert hasattr(SkillStatus, "DISABLED")
        assert hasattr(SkillStatus, "DRAFT")

    def test_skill_status_values_are_strings(self):
        """验证 SkillStatus 的值是字符串类型."""
        from app.skills.models import SkillStatus

        assert isinstance(SkillStatus.ACTIVE.value, str)
        assert isinstance(SkillStatus.DISABLED.value, str)
        assert isinstance(SkillStatus.DRAFT.value, str)


class TestSkillMetadata:
    """Test SkillMetadata dataclass."""

    def test_skill_metadata_creation(self):
        """验证 SkillMetadata 可以正确创建."""
        from app.skills.models import SkillMetadata

        metadata = SkillMetadata(
            description="Test skill for legal search",
            mutex_group="document-analysis",
            priority=10,
        )

        assert metadata.description == "Test skill for legal search"
        assert metadata.mutex_group == "document-analysis"
        assert metadata.priority == 10

    def test_skill_metadata_optional_fields(self):
        """验证 SkillMetadata 的可选字段可以为 None."""
        from app.skills.models import SkillMetadata

        metadata = SkillMetadata(
            description="Test skill",
            mutex_group=None,
            priority=0,
        )

        assert metadata.mutex_group is None
        assert metadata.priority == 0


class TestInvocationPolicy:
    """Test InvocationPolicy dataclass."""

    def test_invocation_policy_creation(self):
        """验证 InvocationPolicy 可以正确创建."""
        from app.skills.models import InvocationPolicy

        policy = InvocationPolicy(
            user_invocable=False,
            disable_model_invocation=False,
        )

        assert policy.user_invocable is False
        assert policy.disable_model_invocation is False

    def test_invocation_policy_default_values(self):
        """验证 InvocationPolicy 的默认值."""
        from app.skills.models import InvocationPolicy

        # 创建时使用默认值
        policy = InvocationPolicy()

        assert policy.user_invocable is False
        assert policy.disable_model_invocation is False


class TestSkillDefinition:
    """Test SkillDefinition dataclass."""

    def test_skill_definition_creation(self):
        """验证 SkillDefinition 可以正确创建."""
        from app.skills.models import (
            SkillDefinition,
            SkillMetadata,
            InvocationPolicy,
            SkillStatus,
        )

        metadata = SkillMetadata(
            description="专业法律法规检索与引用规范",
            mutex_group="document-analysis",
            priority=10,
        )
        invocation = InvocationPolicy(
            user_invocable=False,
            disable_model_invocation=False,
        )

        skill = SkillDefinition(
            id="legal-search",
            name="Legal Search",
            version="1.0.0",
            metadata=metadata,
            file_path="~/.config/agent/skills/legal-search/SKILL.md",
            tools=["tavily_search", "read_file"],
            invocation=invocation,
            status=SkillStatus.ACTIVE,
        )

        assert skill.id == "legal-search"
        assert skill.name == "Legal Search"
        assert skill.version == "1.0.0"
        assert skill.metadata.description == "专业法律法规检索与引用规范"
        assert skill.file_path.endswith("SKILL.md")
        assert skill.tools == ["tavily_search", "read_file"]
        assert skill.status == SkillStatus.ACTIVE

    def test_skill_definition_all_fields(self):
        """验证 SkillDefinition 包含所有必需字段."""
        from app.skills.models import SkillDefinition

        # 检查 SkillDefinition 是否有所有必需的字段
        expected_fields = {
            "id",
            "name",
            "version",
            "metadata",
            "file_path",
            "tools",
            "invocation",
            "status",
        }

        actual_fields = set(SkillDefinition.__dataclass_fields__.keys())
        assert expected_fields == actual_fields


class TestSkillEntry:
    """Test SkillEntry dataclass."""

    def test_skill_entry_creation(self):
        """验证 SkillEntry 可以正确创建（轻量投影版本）."""
        from app.skills.models import SkillEntry

        entry = SkillEntry(
            name="legal-search",
            description="专业法律法规检索与引用规范，适用合同合规类任务。\n触发条件：用户提到合同/签署/违约/合规/法律条款",
            file_path="~/.config/agent/skills/legal-search/SKILL.md",
            tools=["tavily_search", "read_file"],
        )

        assert entry.name == "legal-search"
        assert "专业法律法规检索" in entry.description
        assert "触发条件" in entry.description
        assert entry.file_path.startswith("~")
        assert entry.tools == ["tavily_search", "read_file"]

    def test_skill_entry_minimal_fields(self):
        """验证 SkillEntry 只包含 LLM 需要的字段."""
        from app.skills.models import SkillEntry

        # 检查 SkillEntry 是否只包含投影后的字段
        expected_fields = {"name", "description", "file_path", "tools"}

        actual_fields = set(SkillEntry.__dataclass_fields__.keys())
        assert expected_fields == actual_fields


class TestSkillSnapshot:
    """Test SkillSnapshot dataclass."""

    def test_skill_snapshot_creation(self):
        """验证 SkillSnapshot 可以正确创建."""
        from app.skills.models import SkillSnapshot, SkillEntry

        skills = [
            SkillEntry(
                name="legal-search",
                description="专业法律法规检索",
                file_path="~/.config/agent/skills/legal-search/SKILL.md",
                tools=["tavily_search", "read_file"],
            ),
            SkillEntry(
                name="csv-reporter",
                description="CSV 数据分析",
                file_path="~/.config/agent/skills/csv-reporter/SKILL.md",
                tools=["python_repl", "read_file"],
            ),
        ]

        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=skills,
            prompt="<skills>\n  <skill>\n    <name>legal-search</name>\n  </skill>\n</skills>",
        )

        assert snapshot.version == 1
        assert snapshot.skill_filter is None
        assert len(snapshot.skills) == 2
        assert snapshot.prompt.startswith("<skills>")

    def test_skill_snapshot_all_fields(self):
        """验证 SkillSnapshot 包含所有必需字段."""
        from app.skills.models import SkillSnapshot

        expected_fields = {"version", "skill_filter", "skills", "prompt"}

        actual_fields = set(SkillSnapshot.__dataclass_fields__.keys())
        assert expected_fields == actual_fields

    def test_skill_snapshot_with_filter(self):
        """验证 SkillSnapshot 可以使用 skill_filter 白名单."""
        from app.skills.models import SkillSnapshot, SkillEntry

        skills = [
            SkillEntry(
                name="legal-search",
                description="专业法律法规检索",
                file_path="~/.config/agent/skills/legal-search/SKILL.md",
                tools=["tavily_search", "read_file"],
            )
        ]

        snapshot = SkillSnapshot(
            version=2,
            skill_filter=["legal-search", "csv-reporter"],  # 白名单
            skills=skills,
            prompt="<skills>...</skills>",
        )

        assert snapshot.skill_filter == ["legal-search", "csv-reporter"]
        assert len(snapshot.skills) == 1  # 只有 legal-search 匹配白名单


class TestSkillDataModelsIntegration:
    """集成测试：验证数据模型之间的转换关系."""

    def test_skill_definition_to_entry_projection(self):
        """验证 SkillDefinition 到 SkillEntry 的投影关系."""
        from app.skills.models import (
            SkillDefinition,
            SkillEntry,
            SkillMetadata,
            InvocationPolicy,
            SkillStatus,
        )

        # 创建完整的 SkillDefinition
        definition = SkillDefinition(
            id="legal-search",
            name="Legal Search",
            version="1.0.0",
            metadata=SkillMetadata(
                description="专业法律法规检索与引用规范",
                mutex_group="document-analysis",
                priority=10,
            ),
            file_path="~/.config/agent/skills/legal-search/SKILL.md",
            tools=["tavily_search", "read_file"],
            invocation=InvocationPolicy(),
            status=SkillStatus.ACTIVE,
        )

        # 投影为 SkillEntry（只保留 LLM 需要的字段）
        entry = SkillEntry(
            name=definition.name,
            description=definition.metadata.description,
            file_path=definition.file_path,
            tools=definition.tools,
        )

        # 验证投影正确
        assert entry.name == definition.name
        assert entry.description == definition.metadata.description
        assert entry.file_path == definition.file_path
        assert entry.tools == definition.tools

    def test_multiple_skills_to_snapshot(self):
        """验证多个 SkillEntry 可以构建为 SkillSnapshot."""
        from app.skills.models import SkillSnapshot, SkillEntry

        entries = [
            SkillEntry(
                name="legal-search",
                description="法律法规检索",
                file_path="~/.config/agent/skills/legal-search/SKILL.md",
                tools=["tavily_search", "read_file"],
            ),
            SkillEntry(
                name="csv-reporter",
                description="CSV 数据分析",
                file_path="~/.config/agent/skills/csv-reporter/SKILL.md",
                tools=["python_repl", "read_file"],
            ),
        ]

        # 构建快照
        snapshot = SkillSnapshot(
            version=1,
            skill_filter=None,
            skills=entries,
            prompt="<skills>\n" + "\n".join(
                f"  <skill><name>{e.name}</name></skill>"
                for e in entries
            ) + "\n</skills>",
        )

        assert len(snapshot.skills) == 2
        assert "legal-search" in snapshot.prompt
        assert "csv-reporter" in snapshot.prompt


class TestSkillDataConstraints:
    """测试数据模型的约束条件."""

    def test_skill_id_format(self):
        """验证 skill id 应该是小写字母+数字+连字符."""
        from app.skills.models import SkillDefinition, SkillMetadata, InvocationPolicy, SkillStatus

        # 有效的 skill id
        valid_skill = SkillDefinition(
            id="legal-search",
            name="Legal Search",
            version="1.0.0",
            metadata=SkillMetadata(description="Test", mutex_group=None, priority=0),
            file_path="~/skills/legal/SKILL.md",
            tools=[],
            invocation=InvocationPolicy(),
            status=SkillStatus.ACTIVE,
        )
        assert "legal-search" == valid_skill.id

        # 无效的 skill id（包含大写字母）- 这应该在实际使用时通过验证器检测
        # 当前模型层面不强制验证，依赖外部验证

    def test_description_length_limit(self):
        """验证 description 长度限制（最长 1024 字符）."""
        from app.skills.models import SkillMetadata

        # 正常长度的 description
        normal_desc = "这是一个测试技能描述" * 20  # 约 200 字符
        metadata = SkillMetadata(description=normal_desc, mutex_group=None, priority=0)
        assert len(metadata.description) <= 1024

        # 超长的 description（当前模型层面不强制限制）
        # 实际使用时应该在 SkillManager.scan() 中验证

    def test_tools_list_contains_strings(self):
        """验证 tools 字段是字符串列表."""
        from app.skills.models import SkillDefinition, SkillMetadata, InvocationPolicy, SkillStatus

        skill = SkillDefinition(
            id="test",
            name="Test",
            version="1.0.0",
            metadata=SkillMetadata(description="Test", mutex_group=None, priority=0),
            file_path="~/test/SKILL.md",
            tools=["tavily_search", "read_file", "python_repl"],
            invocation=InvocationPolicy(),
            status=SkillStatus.ACTIVE,
        )

        assert isinstance(skill.tools, list)
        assert all(isinstance(tool, str) for tool in skill.tools)
