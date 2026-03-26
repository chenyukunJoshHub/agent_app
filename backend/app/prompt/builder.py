"""System Prompt builder for Agent Skills system.

This module provides functions to build comprehensive System Prompts
that include role definition, available tools, Skill Protocol, SkillSnapshot,
and user profile (episodic memory).

P0/P1/P2 渐进式实现：
- P0: 基础角色定义 + 工具说明 + 用户画像
- P1: Skill Registry 元数据 + 静态 Few-shot
- P2: 动态 Few-shot（预留）
"""

from typing import Any

from app.skills.models import SkillSnapshot
from app.memory.schemas import UserProfile

# 导入静态模板
from app.prompt.templates import (
    ROLE_TEMPLATE,
    SKILL_REGISTRY_TEMPLATE,
    STATIC_FEW_SHOT,
    USER_PROFILE_TEMPLATE,
    SKILL_PROTOCOL,
    USAGE_GUIDE,
)
from app.prompt.slot_tracker import SlotContentTracker, SlotSnapshot


def build_system_prompt(
    skill_snapshot: SkillSnapshot | None = None,
    episodic: UserProfile | None = None,
    available_tools: list[str] | None = None,
    active_skill_content: str | None = None,  # 保留参数以兼容调用方；当前不注入 system prompt
    track_slots: bool = True,
) -> str | tuple[str, SlotSnapshot]:
    """
    构建完整的 System Prompt（P0/P1/P2 渐进式）。

    Args:
        skill_snapshot: Skill 快照（包含 skills 列表和 prompt）（P1）
        episodic: 用户画像数据（UserProfile）（P0+）
        available_tools: 可用工具列表（P0）
        active_skill_content: 当前激活的 skill 内容（P1，当前不注入 system prompt）
        track_slots: 是否跟踪 Slot 内容和 token 计数（默认 True）

    Returns:
        str | tuple[str, SlotSnapshot]: 完整的 System Prompt，如果 track_slots=True
            则返回 (prompt, snapshot) 元组

    Example:
        >>> prompt, snapshot = build_system_prompt(
        ...     skill_snapshot=snapshot,
        ...     episodic=user_profile,
        ...     available_tools=["web_search", "read_file"],
        ...     track_slots=True
        ... )
        >>> print(snapshot.to_dict())
    """
    # 创建 Slot 跟踪器
    tracker = SlotContentTracker() if track_slots else None

    parts = [ROLE_TEMPLATE, ""]

    # Slot ①: System Prompt 基础部分
    if tracker:
        tracker.add_slot("system", ROLE_TEMPLATE, "系统提示词（基础）")

    # P1: Skill Registry 元数据
    skill_registry_content = ""
    if skill_snapshot and skill_snapshot.skills:
        skill_lines: list[str] = []
        for skill in skill_snapshot.skills:
            description = getattr(skill, "description", None)
            if description is None:
                metadata = getattr(skill, "metadata", None)
                description = getattr(metadata, "description", "")
            skill_lines.append(f"· {skill.name}：{description}")

        skills_list = "\n".join(skill_lines)
        skill_registry_content = SKILL_REGISTRY_TEMPLATE.format(skills_list=skills_list)
        parts.append(skill_registry_content)
        parts.append("")

        if tracker:
            tracker.add_slot("skill_registry", skill_registry_content, "Skill 注册表")

    # P0: 可用工具说明
    tools_content = ""
    if available_tools:
        parts.append("## 可用工具")
        tool_desc = {
            "web_search": "搜索互联网获取实时信息（股价、新闻、天气等）",
            "send_email": "发送邮件给指定收件人（⚠️ 不可逆操作，会触发人工确认）",
            "read_file": "读取文件内容，用于加载 Agent Skill 或其他文档",
        }
        tool_lines = []
        for tool in available_tools:
            if tool in tool_desc:
                tool_lines.append(f"- {tool}: {tool_desc[tool]}")
        tools_content = "\n".join(tool_lines)
        parts.append(tools_content)
        parts.append("")

        if tracker:
            tracker.add_slot("tools", tools_content, "工具定义")

    # Skill Protocol
    parts.append(SKILL_PROTOCOL)
    parts.append("")

    if tracker:
        tracker.add_slot("skill_protocol", SKILL_PROTOCOL, "Skill 协议")

    # SkillSnapshot.prompt（如果 snapshot 有自定义 prompt）
    if skill_snapshot and skill_snapshot.prompt:
        parts.append(skill_snapshot.prompt)
        parts.append("")

    # P1: 静态 Few-shot
    parts.append(STATIC_FEW_SHOT)
    parts.append("")

    if tracker:
        tracker.add_slot("few_shot", STATIC_FEW_SHOT, "静态示例")

    # P0+: 用户画像动态注入（Ephemeral）
    # 注意：MemoryMiddleware.wrap_model_call() 在每次 LLM call 前会动态追加 episodic 内容。
    # build_system_prompt() 初始化时无 user_id，无法预加载，因此内容为空。
    # 但仍需向 tracker 注册此 slot，使 ContextPanel 能正确展示 slot 状态。
    episodic_content = ""
    if episodic and episodic.preferences:
        prefs_text = "\n".join(f"- {k}: {v}" for k, v in episodic.preferences.items())
        episodic_content = USER_PROFILE_TEMPLATE.format(preferences=prefs_text)
        parts.append(episodic_content)

    if tracker:
        tracker.add_slot("episodic", episodic_content, "用户画像", enabled=bool(episodic_content))

    # Slot ②: Active Skill 内容（当前不注入 System Prompt）
    # active_skill 内容通过 tools message 链路注入，不在此处重复注入，避免上下文冗余。

    # P2 预留 slot：history、rag、procedural — 内容为空，但注册使 ContextPanel 可见
    if tracker:
        tracker.add_slot("history", "", "对话历史", enabled=True)
        tracker.add_slot("rag", "", "背景知识", enabled=False)
        tracker.add_slot("procedural", "", "程序记忆", enabled=True)

    # 使用指南
    parts.append(USAGE_GUIDE)

    if tracker:
        # TODO: output_format slot 的实际内容是 USAGE_GUIDE（行为流程说明），
        # 语义上与"输出格式"不同，待后续重构时拆分。
        tracker.add_slot("output_format", USAGE_GUIDE, "输出格式")

    prompt = "\n".join(parts)

    if tracker:
        return prompt, tracker.build_snapshot()
    return prompt


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
    result = build_system_prompt(
        skill_snapshot=skill_snapshot,
        episodic=None,
        available_tools=available_tools,
        track_slots=False,
    )
    # 如果返回的是元组，取第一个元素
    if isinstance(result, tuple):
        return result[0]
    return result


# =============================================================================
# 便捷函数：获取 Slot 快照
# =============================================================================

def get_slot_snapshot(
    skill_snapshot: SkillSnapshot | None = None,
    episodic: UserProfile | None = None,
    available_tools: list[str] | None = None,
    active_skill_content: str | None = None,  # 保留参数以兼容调用方；当前不注入
) -> SlotSnapshot:
    """
    构建 Slot 快照（不返回完整 prompt，仅返回 Slot 信息）。

    Args:
        skill_snapshot: Skill 快照
        episodic: 用户画像
        available_tools: 可用工具列表
        active_skill_content: 激活的 skill 内容（当前不注入）

    Returns:
        SlotSnapshot: Slot 快照
    """
    _, snapshot = build_system_prompt(
        skill_snapshot=skill_snapshot,
        episodic=episodic,
        available_tools=available_tools,
        active_skill_content=active_skill_content,
        track_slots=True,
    )
    return snapshot
