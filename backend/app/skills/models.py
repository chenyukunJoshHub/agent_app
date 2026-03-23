"""
Skills 数据模型.

定义 Agent Skills 系统的核心数据结构，包括：
- SkillStatus: Skill 状态枚举
- SkillMetadata: Skill 触发元数据
- InvocationPolicy: Skill 调用策略
- SkillDefinition: Skill 完整定义
- SkillEntry: Skill 投影版本（用于 SkillSnapshot）
- SkillSnapshot: Skill 会话快照

参考文档：docs/agent skills.md §1.2
"""

from dataclasses import dataclass, field
from enum import StrEnum


class SkillStatus(StrEnum):
    """
    Skill 状态枚举.

    定义 Skill 的三种状态：
    - ACTIVE: 可被 LLM 发现和激活
    - DISABLED: 已禁用（System Prompt 中不可见）
    - DRAFT: 草稿（不可见，仅内部编辑）
    """

    ACTIVE = "active"
    DISABLED = "disabled"
    DRAFT = "draft"


@dataclass
class SkillMetadata:
    """
    Skill 触发元数据（轻量，常驻 System Prompt）.

    这些元数据会被注入到 System Prompt 中，供 LLM 判断是否激活该 Skill。
    约 30~100 字符/个。

    Attributes:
        description: 触发描述（最长 1024 字符）
            - 必须包含：能力范围（what）、触发条件（when）
            - LLM 触发判断的唯一依据
            - 可选：示例句式、互斥信息
        mutex_group: 互斥组（同组最多同时激活一个）
            - 同一 mutex_group 内只激活 priority 最高的一个
            - 不同 mutex_group 的 skill 可以在同一 session 中先后激活
        priority: 多 skill 同时满足时的优先级（越大越优先）
    """

    description: str
    mutex_group: str | None = None
    priority: int = 0


@dataclass
class InvocationPolicy:
    """
    Skill 调用策略.

    定义 Skill 的调用约束和可见性。

    Attributes:
        user_invocable: 用户是否可以直接调用（预留字段，v2 设计）
            - 当前架构无实现路径
            - 待 UI 层 / 命令层设计完成后定义调用机制
        disable_model_invocation: 是否从 SkillSnapshot 中隐藏
            - 默认 false，LLM 可以自动触发
            - true = LLM 不自动触发（当前 P0/P1 阶段保持 false 即可）
            - ⚠️ user_invocable 与此字段的协同机制属 v2 设计范围
    """

    user_invocable: bool = False
    disable_model_invocation: bool = False


@dataclass
class SkillDefinition:
    """
    Skill 完整定义（运行时解析层）.

    包含 Skill 的所有字段，供运行时过滤和验证使用。

    Attributes:
        id: 唯一标识（小写字母+数字+连字符，最长 64 字符）
        name: 显示名称
        version: 语义版本，如 "1.0.0"
        metadata: 触发元数据（注入 System Prompt）
        file_path: SKILL.md 绝对路径
            - SkillSnapshot 中暴露给 LLM
            - LLM 通过 read_file(file_path) 加载 skill 内容
        tools: 本 skill 依赖的 core tools 声明
        invocation: 调用策略
        status: 状态（active / disabled / draft）
    """

    id: str
    name: str
    version: str
    metadata: SkillMetadata
    file_path: str
    tools: list[str] = field(default_factory=list)
    invocation: InvocationPolicy = field(default_factory=InvocationPolicy)
    status: SkillStatus = SkillStatus.ACTIVE


@dataclass
class SkillEntry:
    """
    Skill 投影版本（用于 SkillSnapshot）.

    这是 SkillDefinition 的轻量投影，只保留 LLM 需要的字段。
    由 SkillDefinition 过滤（status=active，disable_model_invocation=false）
    并投影后生成。

    Attributes:
        name: Skill 名称
        description: 触发描述（含触发条件 + 互斥组）
            - 由 SkillMetadata.description 生成
            - 供 LLM 语义匹配
        file_path: SKILL.md 路径（~ 缩写形式，节省字符）
        tools: 依赖工具列表
    """

    name: str
    description: str
    file_path: str
    tools: list[str] = field(default_factory=list)


@dataclass
class SkillSnapshot:
    """
    Skill 会话快照.

    Agent 启动时构建，包含当前可用的 skills 列表和
    注入 System Prompt 的文本。

    Attributes:
        version: 快照版本号（文件变更时递增）
        skill_filter: 当前 agent 允许的 skill 白名单
            - None = 不限制，全部 active skill 可用
            - list[str] = 只允许白名单中的 skill
        skills: 已过滤的可用 skill 列表（SkillEntry）
        prompt: 最终注入 Slot ① 的 XML 文本
            - 由 SkillManager.build_snapshot() 生成
            - 字符预算精确控制（maxSkillsPromptChars = 30,000）
    """

    version: int
    skill_filter: list[str] | None
    skills: list[SkillEntry]
    prompt: str
