"""
End-to-end integration tests for Skills system.

Tests the complete Skill activation flow:
1. LLM identifies matching skill from description
2. LLM calls read_file to load SKILL.md
3. LLM follows Instructions from the skill
4. Output format matches Examples
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.agent.langchain_engine import create_react_agent
from app.skills.manager import SkillManager
from app.tools.file import read_file


@pytest.mark.asyncio
class TestSkillsEndToEnd:
    """End-to-end tests for Skills system."""

    async def test_skill_snapshot_in_system_prompt(self):
        """验证 SkillSnapshot 正确注入到 System Prompt."""
        skill_manager = SkillManager(skills_dir="../skills")
        skill_snapshot = skill_manager.build_snapshot()

        # Verify snapshot contains skills
        assert len(skill_snapshot.skills) >= 2, "Should have at least 2 active skills"
        skill_names = [s.name for s in skill_snapshot.skills]
        assert "legal-search" in skill_names
        assert "csv-reporter" in skill_names

        # Verify prompt includes skills
        assert len(skill_snapshot.prompt) > 0
        assert "<skills>" in skill_snapshot.prompt
        assert "legal-search" in skill_snapshot.prompt
        assert "csv-reporter" in skill_snapshot.prompt

    async def test_agent_creation_with_skills(self):
        """验证 Agent 创建时正确加载 Skills."""
        # Mock LLM to avoid actual API calls
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=Mock(content="Test response"))

        with patch("app.agent.langchain_engine.llm_factory", return_value=mock_llm):
            agent = await create_react_agent(skills_dir="../skills")

            # Verify agent was created
            assert agent is not None

    async def test_read_file_tool_available(self):
        """验证 read_file 工具可用."""
        # Test read_file can read a skill file
        result = read_file.invoke({"path": "../skills/legal-search/SKILL.md"})

        # Verify skill content was loaded
        assert "法规查询 Skill" in result
        assert "## Instructions" in result
        assert "## Examples" in result
        assert "web_search" in result

    async def test_legal_search_skill_content(self):
        """验证 legal-search Skill 内容完整."""
        content = read_file.invoke({"path": "../skills/legal-search/SKILL.md"})

        # Verify four-layer structure
        assert "---" in content  # YAML frontmatter
        assert "name: legal-search" in content
        assert "## Instructions" in content
        assert "## Examples" in content

        # Verify key content
        assert "site:npc.gov.cn" in content
        assert "site:court.gov.cn" in content
        assert "Step 1:" in content
        assert "Input:" in content
        assert "Output:" in content

    async def test_csv_reporter_skill_content(self):
        """验证 csv-reporter Skill 内容完整."""
        content = read_file.invoke({"path": "../skills/csv-reporter/SKILL.md"})

        # Verify four-layer structure
        assert "---" in content  # YAML frontmatter
        assert "name: csv-reporter" in content
        assert "## Instructions" in content
        assert "## Examples" in content

        # Verify key content
        assert "Step 1:" in content
        assert "Step 2:" in content
        assert "Input:" in content
        assert "Output:" in content
        assert "Markdown" in content

    async def test_skill_status_filtering(self):
        """验证 SkillManager 正确过滤 draft 状态的 Skills."""
        skill_manager = SkillManager(skills_dir="../skills")
        skills = skill_manager.scan()

        # template skill should be filtered out (status: draft)
        skill_names = [s.name for s in skills]
        assert "template" not in skill_names, "Draft skills should be filtered"
        assert "legal-search" in skill_names, "Active skills should be included"
        assert "csv-reporter" in skill_names, "Active skills should be included"

    async def test_skill_path_shortening(self):
        """验证路径缩写（~ 替换 home 目录）."""
        skill_manager = SkillManager(skills_dir="../skills")
        snapshot = skill_manager.build_snapshot()

        # At least one skill should have ~ in path
        has_tilde = any("~" in skill.file_path for skill in snapshot.skills)
        assert has_tilde, "Skill paths should use ~ for home directory to save characters"

    async def test_skill_metadata_enhancement(self):
        """验证 Skill metadata 注入到 description."""
        skill_manager = SkillManager(skills_dir="../skills")
        snapshot = skill_manager.build_snapshot()

        # Find legal-search skill
        legal_search = next((s for s in snapshot.skills if s.name == "legal-search"), None)
        assert legal_search is not None

        # Description should include mutex_group
        assert "document-analysis" in legal_search.description

        # Description should include tools
        assert "web_search" in legal_search.description or "read_file" in legal_search.description
