"""
Tools 模块日志记录器
"""
from typing import Dict, Any, Optional, List

from .base import BaseLogger


class ToolsLogger(BaseLogger):
    """
    Tools 模块日志记录器

    覆盖所有权限决策、工具执行、HIL、幂等保护、子 Agent 委托相关日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        thread_id: str,
        step_id: Optional[int] = None,
    ):
        super().__init__(
            module="tools",
            component="tools_manager",
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
            step_id=step_id,
        )

    # ========== 权限决策 ==========

    def policy_decide_start(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: Optional[List[str]],
    ):
        """PolicyEngine 决策开始"""
        self.info(
            "policy.decide_start",
            "PolicyEngine decision started",
            data={
                "tool_name": tool_name,
                "effect_class": effect_class,
                "allowed_decisions": allowed_decisions,
            },
            tags=["policy", "decide"],
        )

    def policy_decide_result(
        self,
        tool_name: str,
        effect_class: str,
        decision: str,
        reason: str,
    ):
        """PolicyEngine 决策结果"""
        self.info(
            "policy.decide_result",
            "PolicyEngine decision result",
            data={
                "tool_name": tool_name,
                "effect_class": effect_class,
                "decision": decision,
                "reason": reason,
            },
            tags=["policy", "decide"],
        )

    def policy_session_grant(self, tool_name: str):
        """session 级授权"""
        self.info(
            "policy.session_grant",
            "Session-level authorization granted",
            data={
                "tool_name": tool_name,
            },
            tags=["policy", "session_grant"],
        )

    def policy_hil_required(
        self,
        tool_name: str,
        effect_class: str,
        allowed_decisions: Optional[List[str]],
    ):
        """HIL 要求检查"""
        self.warning(
            "policy.hil_required",
            "HIL required for tool execution",
            data={
                "tool_name": tool_name,
                "effect_class": effect_class,
                "allowed_decisions": allowed_decisions,
            },
            tags=["policy", "hil"],
        )

    # ========== 工具执行 ==========

    def toolnode_execute_start(
        self,
        tool_names: List[str],
        parallel: bool,
    ):
        """ToolNode 执行开始"""
        self.info(
            "toolnode.execute_start",
            "ToolNode execution started",
            data={
                "tool_names": tool_names,
                "parallel": parallel,
            },
            tags=["toolnode", "execute"],
        )

    def toolnode_execute_tool_start(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ):
        """单个工具执行开始"""
        self.debug(
            "toolnode.execute_tool_start",
            "Tool execution started",
            data={
                "tool_name": tool_name,
                "args": args,
            },
            tags=["toolnode", "tool_start"],
        )

    def toolnode_execute_tool_end(
        self,
        tool_name: str,
        result_length: int,
        latency_ms: int,
        error: Optional[str],
    ):
        """单个工具执行结束"""
        self.info(
            "toolnode.execute_tool_end",
            "Tool execution completed",
            data={
                "tool_name": tool_name,
                "result_length": result_length,
                "latency_ms": latency_ms,
                "error": error,
            },
            tags=["toolnode", "tool_end"],
        )

    def toolnode_execute_end(
        self,
        total_latency_ms: int,
        success_count: int,
        error_count: int,
    ):
        """ToolNode 执行结束"""
        self.info(
            "toolnode.execute_end",
            "ToolNode execution completed",
            data={
                "total_latency_ms": total_latency_ms,
                "success_count": success_count,
                "error_count": error_count,
            },
            tags=["toolnode", "execute"],
        )

    def toolnode_parallel_start(self, tool_count: int):
        """并行执行开始"""
        self.info(
            "toolnode.parallel_start",
            "Parallel tool execution started",
            data={
                "tool_count": tool_count,
            },
            tags=["toolnode", "parallel"],
        )

    def toolnode_parallel_completed(
        self,
        results: List[Dict[str, Any]],
    ):
        """并行执行完成"""
        self.info(
            "toolnode.parallel_completed",
            "Parallel tool execution completed",
            data={
                "results": results,
            },
            tags=["toolnode", "parallel"],
        )

    def toolnode_serial_step_start(self, step: int, tool_name: str):
        """串行步骤开始"""
        self.info(
            "toolnode.serial_step_start",
            "Serial execution step started",
            data={
                "step": step,
                "tool_name": tool_name,
            },
            tags=["toolnode", "serial"],
        )

    def toolnode_serial_step_end(self, step: int, tool_name: str, result: str):
        """串行步骤结束"""
        self.info(
            "toolnode.serial_step_end",
            "Serial execution step completed",
            data={
                "step": step,
                "tool_name": tool_name,
                "result": result,
            },
            tags=["toolnode", "serial"],
        )

    # ========== 幂等保护 ==========

    def idempotency_key_calculated(self, tool_name: str, key: str):
        """幂等键计算"""
        self.debug(
            "idempotency.key_calculated",
            "Idempotency key calculated",
            data={
                "tool_name": tool_name,
                "key": key,
            },
            tags=["idempotency", "key"],
        )

    def idempotency_check(self, key: str, already_executed: bool):
        """幂等检查"""
        self.info(
            "idempotency.check",
            "Idempotency check performed",
            data={
                "key": key,
                "already_executed": already_executed,
            },
            tags=["idempotency", "check"],
        )

    def idempotency_skip(self, key: str, reason: str):
        """幂等跳过"""
        self.info(
            "idempotency.skip",
            "Tool execution skipped (already executed)",
            data={
                "key": key,
                "reason": reason,
            },
            tags=["idempotency", "skip"],
        )

    def idempotency_mark(self, key: str):
        """幂等标记"""
        self.debug(
            "idempotency.mark",
            "Idempotency key marked",
            data={
                "key": key,
            },
            tags=["idempotency", "mark"],
        )

    # ========== 子 Agent 委托 ==========

    def task_dispatch_guard_check(
        self,
        task_depth: int,
        task_budget: int,
        level_limit: int,
    ):
        """循环防护检查"""
        self.debug(
            "task_dispatch.guard_check",
            "Sub-agent guard check performed",
            data={
                "task_depth": task_depth,
                "task_budget": task_budget,
                "level_limit": level_limit,
            },
            tags=["task_dispatch", "guard"],
        )

    def task_dispatch_guard_rejected(self, reason: str):
        """循环防护拒绝"""
        self.warning(
            "task_dispatch.guard_rejected",
            "Sub-agent dispatch rejected",
            data={
                "reason": reason,
            },
            tags=["task_dispatch", "guard", "rejected"],
        )

    def task_dispatch_child_created(
        self,
        child_thread_id: str,
        subagent_goal: str,
        tools_count: int,
    ):
        """子 Agent 创建"""
        self.info(
            "task_dispatch.child_created",
            "Sub-agent created",
            data={
                "child_thread_id": child_thread_id,
                "subagent_goal": subagent_goal,
                "tools_count": tools_count,
            },
            tags=["task_dispatch", "child"],
        )

    def task_dispatch_child_start(self, child_thread_id: str):
        """子 Agent 开始"""
        self.info(
            "task_dispatch.child_start",
            "Sub-agent execution started",
            data={
                "child_thread_id": child_thread_id,
            },
            tags=["task_dispatch", "child"],
        )

    def task_dispatch_child_end(
        self,
        child_thread_id: str,
        total_steps: int,
        final_report_length: int,
    ):
        """子 Agent 完成"""
        self.info(
            "task_dispatch.child_end",
            "Sub-agent execution completed",
            data={
                "child_thread_id": child_thread_id,
                "total_steps": total_steps,
                "final_report_length": final_report_length,
            },
            tags=["task_dispatch", "child"],
        )

    def task_dispatch_concurrent_start(self, count: int):
        """并发子 Agent 开始"""
        self.info(
            "task_dispatch.concurrent_start",
            "Concurrent sub-agent execution started",
            data={
                "count": count,
            },
            tags=["task_dispatch", "concurrent"],
        )

    def task_dispatch_concurrent_end(self, count: int, total_latency_ms: int):
        """并发子 Agent 完成"""
        self.info(
            "task_dispatch.concurrent_end",
            "Concurrent sub-agent execution completed",
            data={
                "count": count,
                "total_latency_ms": total_latency_ms,
            },
            tags=["task_dispatch", "concurrent"],
        )
