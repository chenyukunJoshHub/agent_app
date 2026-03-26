"""
Agent 模块日志记录器
"""
import time
from typing import Dict, Any, Optional, List

from .base import BaseLogger


class AgentLogger(BaseLogger):
    """
    Agent 模块日志记录器

    覆盖所有 Agent Turn、Middleware、Checkpointer、HIL 相关的日志点
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        thread_id: str,
    ):
        super().__init__(
            module="agent",
            component="agent_core",
            session_id=session_id,
            user_id=user_id,
            thread_id=thread_id,
        )

    # ========== Agent Turn ==========

    def turn_start(self, message: str, message_tokens: int):
        """Turn 开始"""
        self.info(
            "agent.turn_start",
            "Agent turn started",
            data={
                "message": message,
                "message_tokens": message_tokens,
            },
            tags=["agent", "turn_start"],
        )

    def invoke_start(self, config: Dict[str, Any]):
        """Agent invoke 开始"""
        self.debug(
            "agent.invoke_start",
            "Agent invoke started",
            data={
                "config": config,
            },
            tags=["agent", "invoke"],
        )

    def turn_end(
        self,
        total_tokens: int,
        total_latency_ms: int,
        final_answer_tokens: int,
    ):
        """Turn 结束"""
        self.info(
            "agent.turn_end",
            "Agent turn completed",
            data={
                "total_tokens": total_tokens,
                "total_latency_ms": total_latency_ms,
                "final_answer_tokens": final_answer_tokens,
            },
            tags=["agent", "turn_end"],
        )

    # ========== Middleware: before_agent ==========

    def middleware_before_agent_start(self, namespace: tuple, user_id: str):
        """before_agent 开始"""
        self.info(
            "middleware.before_agent_start",
            "before_agent hook started",
            data={
                "namespace": namespace,
                "user_id": user_id,
            },
            tags=["middleware", "before_agent"],
        )

    def middleware_before_agent_loaded(
        self,
        episodic_data: Dict[str, Any],
        interaction_count: int,
        latency_ms: int,
    ):
        """before_agent 加载完成"""
        self.debug(
            "middleware.before_agent_loaded",
            "User profile loaded from Long Memory",
            data={
                "episodic_data": episodic_data,
                "interaction_count": interaction_count,
                "latency_ms": latency_ms,
            },
            tags=["middleware", "before_agent", "memory"],
        )

    def middleware_before_agent_end(self, latency_ms: int):
        """before_agent 结束"""
        self.info(
            "middleware.before_agent_end",
            "before_agent hook completed",
            data={
                "latency_ms": latency_ms,
            },
            tags=["middleware", "before_agent"],
        )

    # ========== Middleware: wrap_model_call ==========

    def middleware_wrap_model_call_start(self, llm_call_index: int):
        """wrap_model_call 开始"""
        self.debug(
            "middleware.wrap_model_call_start",
            "wrap_model_call started",
            data={
                "llm_call_index": llm_call_index,
            },
            tags=["middleware", "wrap_model_call"],
        )

    def middleware_wrap_model_call_profile_injected(
        self,
        profile_tokens: int,
        ephemeral: bool,
    ):
        """用户画像注入"""
        self.debug(
            "middleware.wrap_model_call_profile_injected",
            "User profile injected into System Prompt",
            data={
                "profile_tokens": profile_tokens,
                "ephemeral": ephemeral,
            },
            tags=["middleware", "wrap_model_call", "profile"],
        )

    def middleware_wrap_model_call_rag_injected(
        self,
        rag_chunks: List[str],
        rag_tokens: int,
    ):
        """RAG chunk 注入（P2）"""
        self.debug(
            "middleware.wrap_model_call_rag_injected",
            "RAG chunks injected into System Prompt",
            data={
                "rag_chunks": rag_chunks,
                "rag_tokens": rag_tokens,
            },
            tags=["middleware", "wrap_model_call", "rag"],
        )

    def middleware_wrap_model_call_end(self, total_system_tokens: int):
        """wrap_model_call 结束"""
        self.debug(
            "middleware.wrap_model_call_end",
            "wrap_model_call completed",
            data={
                "total_system_tokens": total_system_tokens,
            },
            tags=["middleware", "wrap_model_call"],
        )

    # ========== Middleware: after_agent ==========

    def middleware_after_agent_start(self, turn_duration_ms: int):
        """after_agent 开始"""
        self.info(
            "middleware.after_agent_start",
            "after_agent hook started",
            data={
                "turn_duration_ms": turn_duration_ms,
            },
            tags=["middleware", "after_agent"],
        )

    def middleware_after_agent_profile_updated(
        self,
        interaction_count: int,
        preferences: Optional[Dict[str, Any]],
    ):
        """用户画像更新（P2）"""
        self.info(
            "middleware.after_agent_profile_updated",
            "User profile updated",
            data={
                "interaction_count": interaction_count,
                "preferences": preferences,
            },
            tags=["middleware", "after_agent", "profile"],
        )

    def middleware_after_agent_end(self):
        """after_agent 结束"""
        self.info(
            "middleware.after_agent_end",
            "after_agent hook completed",
            tags=["middleware", "after_agent"],
        )

    # ========== Checkpointer ==========

    def checkpoint_restore_start(self, thread_id: str):
        """restore 开始"""
        self.debug(
            "checkpoint.restore_start",
            "Checkpoint restore started",
            data={
                "thread_id": thread_id,
            },
            tags=["checkpoint", "restore"],
        )

    def checkpoint_restore_first(self):
        """首次 restore（无历史）"""
        self.info(
            "checkpoint.restore_first",
            "First session, no history to restore",
            data={
                "state": {"messages": []},
            },
            tags=["checkpoint", "restore"],
        )

    def checkpoint_restore_history(
        self,
        step_id: int,
        checkpoint_id: str,
        message_count: int,
    ):
        """restore 历史快照"""
        self.info(
            "checkpoint.restore_history",
            "Checkpoint history restored",
            data={
                "step_id": step_id,
                "checkpoint_id": checkpoint_id,
                "message_count": message_count,
            },
            tags=["checkpoint", "restore", "history"],
        )

    def checkpoint_restore_interrupt(
        self,
        step_id: int,
        checkpoint_id: str,
        pending_tool: str,
    ):
        """restore HIL 断点"""
        self.info(
            "checkpoint.restore_interrupt",
            "HIL interrupt point restored",
            data={
                "step_id": step_id,
                "checkpoint_id": checkpoint_id,
                "pending_tool": pending_tool,
            },
            tags=["checkpoint", "restore", "hil"],
        )

    def checkpoint_save_start(self, thread_id: str, step_id: int):
        """save 开始"""
        self.debug(
            "checkpoint.save_start",
            "Checkpoint save started",
            data={
                "thread_id": thread_id,
                "step_id": step_id,
            },
            tags=["checkpoint", "save"],
        )

    def checkpoint_save_end(
        self,
        checkpoint_id: str,
        parent_id: Optional[str],
        message_count: int,
        state_size_bytes: int,
    ):
        """save 完成"""
        self.info(
            "checkpoint.save_end",
            "Checkpoint saved",
            data={
                "checkpoint_id": checkpoint_id,
                "parent_id": parent_id,
                "message_count": message_count,
                "state_size_bytes": state_size_bytes,
            },
            tags=["checkpoint", "save"],
        )

    # ========== HIL ==========

    def hil_trigger(self, tool_name: str, tool_args: Dict[str, Any], effect_class: str):
        """HIL 触发"""
        self.warning(
            "hil.trigger",
            "HIL triggered for tool execution",
            data={
                "tool_name": tool_name,
                "tool_args": tool_args,
                "effect_class": effect_class,
            },
            tags=["hil", "trigger"],
        )

    def hil_agent_paused(self, interrupt_id: str, checkpoint_id: str):
        """Agent 暂停"""
        self.info(
            "hil.agent_paused",
            "Agent paused waiting for user confirmation",
            data={
                "interrupt_id": interrupt_id,
                "checkpoint_id": checkpoint_id,
            },
            tags=["hil", "paused"],
        )

    def hil_sse_interrupt_sent(
        self, interrupt_id: str, tool_name: str, tool_args: Dict[str, Any]
    ):
        """SSE 推送中断事件"""
        self.info(
            "hil.sse_interrupt_sent",
            "SSE interrupt event sent",
            data={
                "interrupt_id": interrupt_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            },
            tags=["hil", "sse"],
        )

    def hil_user_action(self, interrupt_id: str, action: str):
        """用户操作"""
        self.info(
            "hil.user_action",
            "User action received",
            data={
                "interrupt_id": interrupt_id,
                "action": action,
            },
            tags=["hil", "user_action"],
        )

    def hil_resume_start(self, interrupt_id: str, action: str):
        """恢复执行"""
        self.info(
            "hil.resume_start",
            "Resuming execution after HIL",
            data={
                "interrupt_id": interrupt_id,
                "action": action,
            },
            tags=["hil", "resume"],
        )

    def hil_tool_executed(self, tool_name: str, result_summary: str):
        """工具执行完成（批准）"""
        self.info(
            "hil.tool_executed",
            "Tool executed after user approval",
            data={
                "tool_name": tool_name,
                "result_summary": result_summary,
            },
            tags=["hil", "tool_executed"],
        )

    def hil_tool_rejected(self, tool_name: str, rejection_reason: str):
        """工具拒绝（取消）"""
        self.info(
            "hil.tool_rejected",
            "Tool rejected by user",
            data={
                "tool_name": tool_name,
                "rejection_reason": rejection_reason,
            },
            tags=["hil", "tool_rejected"],
        )

    def hil_loop_resumed(self):
        """ReAct 循环恢复"""
        self.info(
            "hil.loop_resumed",
            "ReAct loop resumed after HIL",
            tags=["hil", "loop_resumed"],
        )
