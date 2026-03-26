"""
Skills 模块日志记录器
"""
from typing import Dict, Any, Optional, List

from .base import BaseLogger


class SkillsLogger(BaseLogger):
    """
    Skills 模块日志记录器

    覆盖所有 Skill 扫描、快照、激活、执行相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        thread_id: str,
        step_id: Optional[int] = None,
    ):
        super().__init__(
            module="skills",
            component="skills_manager",
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
            step_id=step_id,
        )

    # ========== Skill 扫描 ==========

    def skill_scan_start(self, skills_dir: str):
        """Skill 扫描开始"""
        self.info(
            "skill.scan_start",
            "Skill directory scan started",
            data={
                "skills_dir": skills_dir,
            },
            tags=["skills", "scan"],
        )

    def skill_scan_file(
        self,
        path: str,
        status: str,
        file_size_bytes: int,
    ):
        """扫描单个 Skill 文件"""
        self.debug(
            "skill.scan_file",
            "Skill file scanned",
            data={
                "path": path,
                "status": status,
                "file_size_bytes": file_size_bytes,
            },
            tags=["skills", "scan"],
        )

    def skill_skip_file(self, path: str, reason: str):
        """跳过 Skill 文件"""
        self.debug(
            "skill.skip_file",
            "Skill file skipped",
            data={
                "path": path,
                "reason": reason,
            },
            tags=["skills", "scan", "skip"],
        )

    def skill_scan_end(
        self,
        total_count: int,
        active_count: int,
        skipped_count: int,
    ):
        """Skill 扫描结束"""
        self.info(
            "skill.scan_end",
            "Skill directory scan completed",
            data={
                "total_count": total_count,
                "active_count": active_count,
                "skipped_count": skipped_count,
            },
            tags=["skills", "scan"],
        )

    # ========== SkillSnapshot 构建 ==========

    def skill_snapshot_build_start(self):
        """SkillSnapshot 构建开始"""
        self.debug(
            "skill.snapshot_build_start",
            "SkillSnapshot build started",
            tags=["skills", "snapshot"],
        )

    def skill_snapshot_chars_calc(
        self,
        full_format_chars: int,
        compact_format_chars: int,
    ):
        """字符数计算"""
        self.debug(
            "skill.snapshot_chars_calc",
            "SkillSnapshot character count calculated",
            data={
                "full_format_chars": full_format_chars,
                "compact_format_chars": compact_format_chars,
            },
            tags=["skills", "snapshot"],
        )

    def skill_snapshot_format_selected(
        self,
        format: str,
        reason: str,
    ):
        """格式选择"""
        self.info(
            "skill.snapshot_format_selected",
            "SkillSnapshot format selected",
            data={
                "format": format,
                "reason": reason,
            },
            tags=["skills", "snapshot"],
        )

    def skill_snapshot_built(
        self,
        version: int,
        skill_count: int,
        prompt_tokens: int,
    ):
        """SkillSnapshot 构建完成"""
        self.info(
            "skill.snapshot_built",
            "SkillSnapshot built",
            data={
                "version": version,
                "skill_count": skill_count,
                "prompt_tokens": prompt_tokens,
            },
            tags=["skills", "snapshot"],
        )

    def skill_snapshot_injected(
        self,
        prompt_length: int,
        system_prompt_total_tokens: int,
    ):
        """SkillSnapshot 注入 Slot ①"""
        self.info(
            "skill.snapshot_injected",
            "SkillSnapshot injected into Slot ①",
            data={
                "prompt_length": prompt_length,
                "system_prompt_total_tokens": system_prompt_total_tokens,
            },
            tags=["skills", "snapshot", "inject"],
        )

    # ========== Skill 激活 ==========

    def skill_llm_matched(
        self,
        skill_name: str,
        confidence: Optional[float],
    ):
        """LLM 识别到 Skill"""
        self.info(
            "skill.llm_matched",
            "LLM matched skill",
            data={
                "skill_name": skill_name,
                "confidence": confidence,
            },
            tags=["skills", "match"],
        )

    def skill_read_file_call(
        self,
        skill_name: str,
        file_path: str,
    ):
        """read_file 调用"""
        self.debug(
            "skill.read_file_call",
            "read_file called for skill",
            data={
                "skill_name": skill_name,
                "file_path": file_path,
            },
            tags=["skills", "read_file"],
        )

    def skill_read_file_loaded(
        self,
        skill_name: str,
        content_length: int,
        tokens: int,
        latency_ms: int,
    ):
        """read_file 读取完成"""
        self.info(
            "skill.read_file_loaded",
            "Skill file loaded",
            data={
                "skill_name": skill_name,
                "content_length": content_length,
                "tokens": tokens,
                "latency_ms": latency_ms,
            },
            tags=["skills", "read_file"],
        )

    def skill_history_found(
        self,
        skill_name: str,
        tool_message_id: str,
    ):
        """历史中发现 Skill 内容"""
        self.debug(
            "skill.history_found",
            "Skill content found in history",
            data={
                "skill_name": skill_name,
                "tool_message_id": tool_message_id,
            },
            tags=["skills", "history"],
        )

    def skill_content_injected(
        self,
        skill_name: str,
        instructions_tokens: int,
        examples_tokens: int,
    ):
        """Skill 内容注入历史"""
        self.info(
            "skill.content_injected",
            "Skill content injected",
            data={
                "skill_name": skill_name,
                "instructions_tokens": instructions_tokens,
                "examples_tokens": examples_tokens,
            },
            tags=["skills", "inject"],
        )

    def skill_execution_completed(
        self,
        skill_name: str,
        used_tools: List[str],
    ):
        """Skill 执行完成"""
        self.info(
            "skill.execution_completed",
            "Skill execution completed",
            data={
                "skill_name": skill_name,
                "used_tools": used_tools,
            },
            tags=["skills", "execute"],
        )
