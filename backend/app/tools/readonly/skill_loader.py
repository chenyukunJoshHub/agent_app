from __future__ import annotations

from langchain_core.tools import tool

from app.skills.manager import SkillManager

@tool
def activate_skill(name: str) -> str:
    """激活指定 Agent Skill，获取该场景的完整操作指南。

    适用场景：
    - 当前任务涉及专业领域（法律法规/合同分析/数据报告）且需要标准化流程时
    - 用户明确要求使用某个特定技能时
    - 需要遵循特定操作步骤的任务

    不适用场景：
    - 通用问答（直接回答即可，无需激活技能）
    - 本 session 已激活过同一 skill（历史消息中已可见时，避免重复激活）
    - 读取普通文件内容（请使用 read_file 工具）

    Args:
        name: 技能名称，取值来自 System Prompt 中的 [可用 Skills] 列表

    Raises:
        ValueError: 如果 SkillManager 单例未初始化（应该由 langchain_engine 初始化）
    """
    try:
        skill_manager = SkillManager.get_instance()
    except ValueError as e:
        raise ValueError(f"SkillManager not initialized. Ensure Agent creation calls SkillManager.get_instance(skills_dir=...) first: {e}")

    skill_manager.scan()
    return skill_manager.read_skill_content(name)


__all__ = ["activate_skill"]
