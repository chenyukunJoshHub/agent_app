"""
Skills Module - Agent Skills 插件系统.

该模块实现了 Agent Skills 四层结构和加载机制，包括：
- 数据模型（SkillDefinition, SkillEntry, SkillSnapshot 等）
- SkillManager（扫描、解析、构建快照）
- read_file 工具（Skill 激活机制）

参考文档：docs/agent skills.md
"""

from app.skills.models import (
    InvocationPolicy,
    SkillDefinition,
    SkillEntry,
    SkillMetadata,
    SkillSnapshot,
    SkillStatus,
)

__all__ = [
    "SkillStatus",
    "SkillMetadata",
    "InvocationPolicy",
    "SkillDefinition",
    "SkillEntry",
    "SkillSnapshot",
]
