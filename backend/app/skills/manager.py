"""
SkillManager - Agent Skills 系统核心管理器.

负责：
1. 扫描 skills/ 目录，解析 SKILL.md 文件
2. 解析 YAML frontmatter，构建 SkillDefinition
3. 过滤 disabled/draft 状态的 skills
4. 构建 SkillSnapshot（含 XML prompt）
5. 支持技能白名单（skill_filter）
6. 并发安全保护（threading.Lock）

参考文档：docs/agent skills.md §1.6.1 和 §1.7
"""

import threading
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from app.skills.models import (
    InvocationPolicy,
    SkillDefinition,
    SkillEntry,
    SkillMetadata,
    SkillSnapshot,
    SkillStatus,
)


class SkillManager:
    """
    Agent Skills 系统管理器.

    负责扫描、解析、过滤和构建 SkillSnapshot。

    线程安全：build_snapshot() 使用 threading.Lock 保护版本号递增。

    单例模式：使用 get_instance() 获取全局唯一实例。

    Attributes:
        skills_dir: Skills 目录路径（绝对路径）
        _version: 当前快照版本号（文件变更时递增）
        _lock: 线程锁，保护并发访问
        _max_prompt_chars: System Prompt 字符预算上限（默认 30,000）
    """

    # 字符预算上限（参考：docs/arch/skill-v3.md §1.8）
    MAX_SKILLS_PROMPT_CHARS = 30_000

    # 单个 SKILL.md 文件大小上限（防止解析超大文件）
    MAX_SKILL_FILE_BYTES = 100_000  # 100 KB

    # 单例实例
    _instance: "SkillManager | None" = None
    _instance_lock = threading.Lock()

    def __init__(self, skills_dir: str, max_prompt_chars: int | None = None):
        """
        初始化 SkillManager.

        注意：请使用 get_instance() 类方法获取单例实例，
        直接构造函数将创建独立实例（主要用于测试）。

        Args:
            skills_dir: Skills 目录路径（可以是相对或绝对路径）
            max_prompt_chars: 可选的字符预算上限，默认使用 MAX_SKILLS_PROMPT_CHARS
        """
        self.skills_dir = Path(skills_dir).resolve()
        self._version: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._scan_lock: threading.Lock = threading.Lock()
        self._max_prompt_chars = max_prompt_chars or self.MAX_SKILLS_PROMPT_CHARS
        self._definitions: list[SkillDefinition] = []
        self._definitions_by_name: dict[str, SkillDefinition] = {}
        self._scan_cache: dict[str, int] = {}
        self._scan_result_cache: dict[str, SkillDefinition | None] = {}

    @classmethod
    def get_instance(
        cls,
        skills_dir: str | None = None,
        max_prompt_chars: int | None = None,
    ) -> "SkillManager":
        """
        获取 SkillManager 单例实例.

        线程安全的单例创建，使用双重检查锁定模式。

        Args:
            skills_dir: Skills 目录路径（首次创建时必需，后续调用可省略）
            max_prompt_chars: 可选的字符预算上限（仅在首次创建时生效）

        Returns:
            SkillManager 单例实例

        Raises:
            ValueError: 首次创建时未提供 skills_dir

        Example:
            >>> manager = SkillManager.get_instance(skills_dir="skills/")
            >>> snapshot = manager.build_snapshot()
            >>> # 后续调用可直接获取实例
            >>> same_manager = SkillManager.get_instance()
        """
        # 第一次检查（快速路径，无锁）
        if cls._instance is not None:
            return cls._instance

        # 加锁创建
        with cls._instance_lock:
            # 第二次检查（防止竞争条件下重复创建）
            if cls._instance is not None:
                return cls._instance

            # 首次创建，必须提供 skills_dir
            if skills_dir is None:
                raise ValueError(
                    "skills_dir is required for first-time SkillManager initialization"
                )

            cls._instance = cls(skills_dir=skills_dir, max_prompt_chars=max_prompt_chars)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        重置单例实例.

        主要用于测试场景，确保每个测试获得干净的实例。
        生产环境中应谨慎使用。

        Example:
            >>> SkillManager.reset_instance()
            >>> manager = SkillManager.get_instance(skills_dir="test_skills/")
        """
        with cls._instance_lock:
            cls._instance = None

    def scan(self) -> list[SkillDefinition]:
        """
        扫描 skills/ 目录，解析所有 SKILL.md 文件.

        流程：
        1. 遍历 skills_dir 下所有子目录
        2. 查找 SKILL.md 文件
        3. 检查文件大小（跳过超过 MAX_SKILL_FILE_BYTES 的文件）
        4. 解析 YAML frontmatter
        5. 构建 SkillDefinition
        6. 过滤 status != active 的 skills

        Returns:
            SkillDefinition 列表（只包含 active skills）

        Raises:
            无异常，解析失败的文件会被跳过
        """
        with self._scan_lock:
            definitions: list[SkillDefinition] = []
            definitions_by_name: dict[str, SkillDefinition] = {}
            seen_files: set[str] = set()

            # 遍历 skills_dir 下的所有子目录
            for skill_dir in self.skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                # 查找 SKILL.md 文件
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                file_key = str(skill_file.resolve())
                seen_files.add(file_key)

                # 检查文件大小并读取 mtime（用于缓存命中）
                try:
                    stat = skill_file.stat()
                    if stat.st_size > self.MAX_SKILL_FILE_BYTES:
                        # 跳过超大文件，并缓存跳过结果（避免重复解析）
                        self._scan_cache[file_key] = stat.st_mtime_ns
                        self._scan_result_cache[file_key] = None
                        continue
                    mtime_ns = stat.st_mtime_ns
                except Exception:
                    # 无法获取文件元信息，跳过该文件
                    self._scan_cache.pop(file_key, None)
                    self._scan_result_cache.pop(file_key, None)
                    continue

                cached_mtime = self._scan_cache.get(file_key)
                if cached_mtime == mtime_ns:
                    cached_definition = self._scan_result_cache.get(file_key)
                    if cached_definition and cached_definition.status == SkillStatus.ACTIVE:
                        definitions.append(cached_definition)
                        definitions_by_name.setdefault(
                            cached_definition.name, cached_definition
                        )
                    continue

                # 文件变更或首次扫描，重新解析
                try:
                    definition = self._parse_skill_file(skill_file)
                except Exception:
                    definition = None

                self._scan_cache[file_key] = mtime_ns
                self._scan_result_cache[file_key] = definition

                if definition and definition.status == SkillStatus.ACTIVE:
                    definitions.append(definition)
                    definitions_by_name.setdefault(definition.name, definition)

            # 清理已删除文件的缓存
            stale_files = set(self._scan_cache.keys()) - seen_files
            for file_key in stale_files:
                self._scan_cache.pop(file_key, None)
                self._scan_result_cache.pop(file_key, None)

            self._definitions = definitions
            self._definitions_by_name = definitions_by_name
            return definitions

    def _parse_skill_file(self, skill_file: Path) -> SkillDefinition | None:
        """
        解析单个 SKILL.md 文件.

        Args:
            skill_file: SKILL.md 文件路径

        Returns:
            SkillDefinition 对象，解析失败返回 None
        """
        # 读取文件内容
        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception:
            return None

        # 提取 YAML frontmatter（位于 --- 分隔符之间）
        if not content.startswith("---"):
            return None

        # 找到第二个 ---
        end_marker = content.find("\n---", 3)
        if end_marker == -1:
            return None

        frontmatter_text = content[3:end_marker]

        # 解析 YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except Exception:
            return None

        if not isinstance(frontmatter, dict):
            return None

        # 提取字段
        skill_id = skill_file.parent.name
        name = frontmatter.get("name", skill_id)
        version = frontmatter.get("version", "1.0.0")
        description = frontmatter.get("description", "")
        status_str = frontmatter.get("status", "active")
        mutex_group = frontmatter.get("mutex_group")
        priority = frontmatter.get("priority", 0)
        disable_model_invocation = bool(
            frontmatter.get(
                "disable-model-invocation", frontmatter.get("disable_model_invocation", False)
            )
        )
        tools = frontmatter.get("tools", [])

        # 解析 status
        try:
            status = SkillStatus(status_str)
        except ValueError:
            status = SkillStatus.ACTIVE

        # 构建 SkillMetadata
        metadata = SkillMetadata(
            description=description,
            mutex_group=mutex_group,
            priority=priority,
        )

        # 构建 InvocationPolicy
        invocation = InvocationPolicy(
            user_invocable=False,  # P0/P1 阶段固定为 False
            disable_model_invocation=disable_model_invocation,
        )

        # 构建 SkillDefinition
        definition = SkillDefinition(
            id=skill_id,
            name=name,
            version=version,
            metadata=metadata,
            file_path=str(skill_file.resolve()),
            tools=tools if isinstance(tools, list) else [],
            invocation=invocation,
            status=status,
        )

        return definition

    def build_snapshot(
        self, skill_filter: list[str] | None = None
    ) -> SkillSnapshot:
        """
        构建 SkillSnapshot（线程安全）.

        流程：
        1. 扫描 skills 目录，获取所有 active skills
        2. 过滤 disable_model_invocation=true 的 skills
        3. 应用 skill_filter 白名单（如果提供）
        4. 按优先级降序排列
        5. 投影为 SkillEntry（只保留 LLM 需要的字段）
        6. 应用 3 级预算降级策略：
           - Level 1: 完整格式（含 description），字符数在预算内时使用
           - Level 2: 紧凑格式（仅 name + file_path），字符数超限时降级
           - Level 3: 移除优先级最低的 skills，确保总字符数在预算内
        7. 生成 XML prompt
        8. 递增版本号（使用锁保护）

        并发安全：
        - 使用 threading.Lock 保护 _version 递增操作
        - 采用"先构建后替换"模式，避免长时间持锁

        Args:
            skill_filter: 技能白名单，None 表示不限制

        Returns:
            SkillSnapshot 对象
        """
        # 步骤 1-3: 扫描并过滤（锁外操作，可能耗时）
        # 扫描所有 active skills
        definitions = self.scan()

        # 过滤 disable_model_invocation=true 的 skills
        definitions = [
            d for d in definitions if not d.invocation.disable_model_invocation
        ]

        # 应用白名单过滤
        if skill_filter is not None:
            definitions = [d for d in definitions if d.id in skill_filter]

        # 步骤 4: 按优先级降序排列
        definitions.sort(key=lambda d: d.metadata.priority, reverse=True)

        # 步骤 5-6: 投影为 SkillEntry 并应用 3 级预算降级策略
        entries = self._build_entries_with_budget_control(definitions)

        # 步骤 7: 生成 XML prompt
        prompt = self._build_prompt(entries)

        # 步骤 8: 锁内递增版本号（快速操作）
        with self._lock:
            self._version += 1
            version = self._version

        # 构建 SkillSnapshot
        snapshot = SkillSnapshot(
            version=version,
            skill_filter=skill_filter,
            skills=entries,
            prompt=prompt,
        )

        return snapshot

    def _build_entries_with_budget_control(
        self, definitions: list[SkillDefinition]
    ) -> list[SkillEntry]:
        """
        构建 SkillEntry 列表，应用 3 级预算降级策略.

        3 级降级策略（参考：docs/arch/skill-v3.md §1.8）：
        - Level 1 (完整格式): 包含 description，字符数在预算内时使用
        - Level 2 (紧凑格式): 仅 name + file_path，字符数超限时降级
        - Level 3 (超限移除): 移除优先级最低的 skills，确保总字符数在预算内

        Args:
            definitions: SkillDefinition 列表（已按优先级降序排列）

        Returns:
            SkillEntry 列表（可能使用紧凑格式或移除部分 skills）
        """
        # Level 1: 尝试完整格式
        entries_full = [
            SkillEntry(
                name=defn.name,
                description=self._build_entry_description(defn),
                file_path=self._shorten_path(defn.file_path),
                tools=defn.tools,
            )
            for defn in definitions
        ]
        prompt_full = self._build_prompt(entries_full)

        if len(prompt_full) <= self._max_prompt_chars:
            # 完整格式在预算内，直接返回
            return entries_full

        # Level 2: 降级为紧凑格式（省略 description）
        entries_compact = [
            SkillEntry(
                name=defn.name,
                description="",  # 紧凑格式省略 description
                file_path=self._shorten_path(defn.file_path),
                tools=defn.tools,
            )
            for defn in definitions
        ]
        prompt_compact = self._build_prompt(entries_compact)

        if len(prompt_compact) <= self._max_prompt_chars:
            # 紧凑格式在预算内，返回紧凑格式
            return entries_compact

        # Level 3: 仍然超限，移除优先级最低的 skills
        # 使用二分法找到能容纳的最大数量
        return self._truncate_to_fit_budget(definitions)

    def _truncate_to_fit_budget(
        self, definitions: list[SkillDefinition]
    ) -> list[SkillEntry]:
        """
        移除优先级最低的 skills，确保总字符数在预算内.

        使用紧凑格式（Level 2），并基于“前缀长度越小，prompt 越短”的
        单调性，对最高优先级前缀做二分搜索，找到预算内可容纳的最大数量。

        Args:
            definitions: SkillDefinition 列表（已按优先级降序排列）

        Returns:
            SkillEntry 列表（紧凑格式，可能移除了部分 skills）
        """
        compact_entries = [
            SkillEntry(
                name=defn.name,
                description="",  # 紧凑格式
                file_path=self._shorten_path(defn.file_path),
                tools=defn.tools,
            )
            for defn in definitions
        ]

        if not compact_entries:
            return []

        best_count = 0
        low = 1
        high = len(compact_entries)

        # Prompt length is monotonic with respect to a prefix length of compact entries,
        # so we can binary-search the largest prefix that still fits the budget.
        while low <= high:
            mid = (low + high) // 2
            candidate_entries = compact_entries[:mid]
            prompt = self._build_prompt(candidate_entries)

            if len(prompt) <= self._max_prompt_chars:
                best_count = mid
                low = mid + 1
            else:
                high = mid - 1

        if best_count == 0:
            # Even the highest-priority single skill does not fit in the compact form.
            return []

        return compact_entries[:best_count]

    def _build_entry_description(self, definition: SkillDefinition) -> str:
        """
        构建 SkillEntry 的 description.

        将互斥组、工具依赖等信息注入 description，
        供 LLM 语义匹配时参考。

        Args:
            definition: SkillDefinition 对象

        Returns:
            增强后的 description 文本
        """
        desc_parts = [definition.metadata.description]

        # 添加互斥组信息
        if definition.metadata.mutex_group:
            desc_parts.append(
                f"互斥组：{definition.metadata.mutex_group}"
            )

        # 添加工具依赖信息
        if definition.tools:
            tools_str = ", ".join(definition.tools)
            desc_parts.append(f"依赖工具：{tools_str}")

        return " | ".join(desc_parts)

    def _shorten_path(self, file_path: str) -> str:
        """
        缩短文件路径，使用 ~ 替代 home directory.

        Args:
            file_path: 绝对路径

        Returns:
            缩写后的路径
        """
        # 尝试替换 home directory
        home_dir = Path.home()
        try:
            path_obj = Path(file_path)
            if path_obj.is_relative_to(home_dir):
                # 替换为 ~
                relative = path_obj.relative_to(home_dir)
                return f"~/{relative}"
        except Exception:
            pass

        # 无法缩短，返回原路径
        return file_path

    def _build_prompt(self, entries: list[SkillEntry]) -> str:
        """
        构建 XML 格式的 prompt.

        格式参考 docs/arch/skill-v3.md §1.5

        支持两种格式：
        - 完整格式：包含 description 标签和内容
        - 紧凑格式：省略 description 内容（用于 Level 2 降级）

        Args:
            entries: SkillEntry 列表

        Returns:
            XML 格式的 prompt 文本
        """
        lines = ["<skills>"]
        lines.append("  以下 skills 提供特定任务的操作指南。")
        lines.append("  当任务匹配时，使用 read_file 工具读取对应 file_path 获取完整指南。")
        lines.append("")

        for entry in entries:
            lines.append("  <skill>")
            lines.append(f"    <name>{entry.name}</name>")

            # 紧凑格式：如果 description 为空，省略 description 标签
            if entry.description:
                lines.append("    <description>")
                lines.append(f"      {entry.description}")
                lines.append("    </description>")

            lines.append(f"    <file_path>{entry.file_path}</file_path>")
            lines.append("  </skill>")
            lines.append("")

        lines.append("</skills>")

        return "\n".join(lines)

    def read_skill_content(self, skill_name: str) -> str:
        if not self._definitions_by_name:
            self.scan()

        defn = self._definitions_by_name.get(skill_name)
        if defn is not None:
            skill_file = Path(defn.file_path)
            if not skill_file.is_absolute():
                skill_file = self.skills_dir / skill_file.name

            # Path boundary check: ensure resolved path is within skills_dir
            resolved = skill_file.resolve()
            if not resolved.is_relative_to(self.skills_dir):
                return f"Error: skill '{skill_name}' path '{resolved}' is outside skills directory '{self.skills_dir}'"

            if skill_file.exists():
                return skill_file.read_text(encoding="utf-8")

        available = ", ".join(self._definitions_by_name.keys())
        return f"Error: skill '{skill_name}' not found. Available: [{available}]"
