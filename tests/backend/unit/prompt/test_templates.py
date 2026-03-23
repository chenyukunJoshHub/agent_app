"""单元测试：静态 Prompt 模板

测试 templates.py 中的所有模板内容。
"""

import pytest
from app.prompt.templates import (
    ROLE_TEMPLATE,
    USER_PROFILE_TEMPLATE,
    SKILL_REGISTRY_TEMPLATE,
    STATIC_FEW_SHOT,
)


class TestRoleTemplate:
    """测试角色定义模板"""

    def test_role_template_exists(self):
        """验证 ROLE_TEMPLATE 非空"""
        assert ROLE_TEMPLATE
        assert len(ROLE_TEMPLATE) > 0
        assert "核心能力" in ROLE_TEMPLATE
        assert "行为准则" in ROLE_TEMPLATE

    def test_role_template_contains_key_sections(self):
        """验证 ROLE_TEMPLATE 包含关键章节"""
        assert "多工具 AI 助手" in ROLE_TEMPLATE
        assert "web_search" in ROLE_TEMPLATE
        assert "read_file" in ROLE_TEMPLATE


class TestUserProfileTemplate:
    """测试用户画像模板"""

    def test_user_profile_template_has_placeholder(self):
        """验证模板有 {preferences} 占位符"""
        assert "{preferences}" in USER_PROFILE_TEMPLATE

    def test_user_profile_template_format(self):
        """验证模板可以正确格式化"""
        result = USER_PROFILE_TEMPLATE.format(preferences="- 语言: 中文\n- 风格: 简洁")
        assert "语言: 中文" in result
        assert "风格: 简洁" in result


class TestSkillRegistryTemplate:
    """测试 Skill Registry 模板"""

    def test_skill_registry_template_has_placeholder(self):
        """验证模板有 {skills_list} 占位符"""
        assert "{skills_list}" in SKILL_REGISTRY_TEMPLATE

    def test_skill_registry_template_format(self):
        """验证模板可以正确格式化"""
        skills_list = "· skill1: 描述1\n· skill2: 描述2"
        result = SKILL_REGISTRY_TEMPLATE.format(skills_list=skills_list)
        assert "skill1: 描述1" in result
        assert "skill2: 描述2" in result


class TestStaticFewShot:
    """测试静态 Few-shot 模板"""

    def test_static_few_shot_exists(self):
        """验证 STATIC_FEW_SHOT 非空"""
        assert STATIC_FEW_SHOT
        assert len(STATIC_FEW_SHOT) > 0

    def test_static_few_shot_contains_examples(self):
        """验证包含示例对话"""
        assert "示例 1" in STATIC_FEW_SHOT
        assert "示例 2" in STATIC_FEW_SHOT
        assert "合同123" in STATIC_FEW_SHOT

    def test_static_few_shot_shows_reasoning(self):
        """验证示例展示推理过程"""
        assert "思考：" in STATIC_FEW_SHOT
        assert "操作：" in STATIC_FEW_SHOT
        assert "观察：" in STATIC_FEW_SHOT
        assert "回复：" in STATIC_FEW_SHOT
