"""System Prompt builder for Agent Skills system.

This module provides functions to build comprehensive System Prompts
that include role definition, available tools, Skill Protocol, SkillSnapshot,
and user profile (episodic memory).

P0/P1/P2 渐进式实现：
- P0: 基础角色定义 + 工具说明 + 用户画像
- P1: Skill Registry 元数据 + 静态 Few-shot
- P2: 动态 Few-shot（预留）
"""

from app.skills.models import SkillSnapshot
from app.memory.schemas import UserProfile

# 导入静态模板
from app.prompt.templates import (
    ROLE_TEMPLATE,
    SKILL_REGISTRY_TEMPLATE,
    STATIC_FEW_SHOT,
    USER_PROFILE_TEMPLATE,
)

# Skill Protocol - 四个约定（注入 System Prompt）
SKILL_PROTOCOL = """
## Skill 使用协议

当你需要使用特定技能时，遵循以下约定：

1. **识别约定**：当用户请求匹配某个 skill 的 description 时，在本次 ReAct 循环中激活该 skill。
2. **调用约定**：使用 read_file 工具读取 skill 的 file_path 获取完整内容。
3. **执行约定**：严格按照 SKILL.md 中的 Instructions 执行，遵循 Examples 的格式。
4. **冲突约定**：同一 turn 内只激活一个 skill，避免 Token 消耗过大。
"""


def build_system_prompt(
    skill_snapshot: SkillSnapshot | None = None,
    episodic: UserProfile | None = None,
    available_tools: list[str] | None = None,
) -> str:
    """
    构建完整的 System Prompt（P0/P1/P2 渐进式）。

    Args:
        skill_snapshot: Skill 快照（包含 skills 列表和 prompt）（P1）
        episodic: 用户画像数据（UserProfile）（P0+）
        available_tools: 可用工具列表（P0）

    Returns:
        str: 完整的 System Prompt

    Example:
        >>> prompt = build_system_prompt(
        ...     skill_snapshot=snapshot,
        ...     episodic=user_profile,
        ...     available_tools=["web_search", "read_file"]
        ... )
    """
    parts = [ROLE_TEMPLATE, ""]

    # P1: Skill Registry 元数据
    if skill_snapshot and skill_snapshot.skills:
        skills_list = "\n".join([
            f"· {s.name}：{s.description}"
            for s in skill_snapshot.skills
        ])
        parts.append(SKILL_REGISTRY_TEMPLATE.format(skills_list=skills_list))
        parts.append("")

    # P0: 可用工具说明
    if available_tools:
        parts.append("## 可用工具")
        tool_desc = {
            "web_search": "搜索互联网获取实时信息（股价、新闻、天气等）",
            "send_email": "发送邮件给指定收件人（⚠️ 不可逆操作，会触发人工确认）",
            "read_file": "读取文件内容，用于加载 Agent Skill 或其他文档",
        }
        for tool in available_tools:
            if tool in tool_desc:
                parts.append(f"- {tool}: {tool_desc[tool]}")
        parts.append("")

    # Skill Protocol
    parts.append(SKILL_PROTOCOL)
    parts.append("")

    # SkillSnapshot.prompt（如果 snapshot 有自定义 prompt）
    if skill_snapshot and skill_snapshot.prompt:
        parts.append(skill_snapshot.prompt)
        parts.append("")

    # P1: 静态 Few-shot
    parts.append(STATIC_FEW_SHOT)
    parts.append("")

    # P0+: 用户画像动态注入（Ephemeral）
    if episodic and episodic.preferences:
        prefs_text = "\n".join(f"- {k}: {v}" for k, v in episodic.preferences.items())
        parts.append(USER_PROFILE_TEMPLATE.format(preferences=prefs_text))

    # 使用指南
    parts.extend([
        "## 使用指南",
        "1. 首先理解用户需求",
        "2. 判断是否需要激活某个 skill（参考 skill 的 description）",
        "3. 如果需要，使用 read_file 读取对应的 SKILL.md",
        "4. 按 skill 的 Instructions 执行任务",
        "5. 如果不需要 skill，直接使用可用工具完成任务",
        "",
        "## 重要",
        "- 不要编造信息",
        "- 保持回答简洁但完整",
        "- send_email 操作需要用户确认后才会执行",
    ])

    return "\n".join(parts)


# =============================================================================
# 向后兼容的简化版本（保持现有代码可用）
# =============================================================================

def build_system_prompt_legacy(
    skill_snapshot: SkillSnapshot | None = None,
    available_tools: list[str] | None = None,
) -> str:
    """
    向后兼容的简化版本（不使用 episodic 参数）。

    .. deprecated::
        请使用 build_system_prompt() 并传入 episodic 参数。
        此函数仅用于保持向后兼容。
    """
    return build_system_prompt(
        skill_snapshot=skill_snapshot,
        episodic=None,
        available_tools=available_tools,
    )
