"""
日志系统使用示例
"""
from logger import (
    AgentLogger,
    ContextLogger,
    ToolsLogger,
    SkillsLogger,
    MemoryLogger,
    ApiLogger,
    SseLogger,
)


def example_agent_logging():
    """Agent 模块日志示例"""

    # 创建 AgentLogger
    logger = AgentLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
    )

    # Turn 开始
    logger.turn_start(
        message="帮我查合同123的签署状态",
        message_tokens=12,
    )

    # before_agent
    logger.middleware_before_agent_start(
        namespace=("profile", "user_456"),
        user_id="user_456",
    )

    logger.middleware_before_agent_loaded(
        episodic_data={
            "user_id": "user_456",
            "preferences": {
                "domain": "legal-tech",
                "language": "zh",
            },
            "interaction_count": 15,
        },
        interaction_count=15,
        latency_ms=12,
    )

    logger.middleware_before_agent_end(latency_ms=15)

    # 设置 Step
    logger.set_step(1)

    # wrap_model_call
    logger.middleware_wrap_model_call_start(llm_call_index=0)
    logger.middleware_wrap_model_call_profile_injected(
        profile_tokens=100,
        ephemeral=True,
    )
    logger.middleware_wrap_model_call_end(total_system_tokens=1200)

    # Turn 结束
    logger.turn_end(
        total_tokens=3456,
        total_latency_ms=2345,
        final_answer_tokens=234,
    )


def example_context_logging():
    """Context 模块日志示例"""

    # 创建 ContextLogger
    logger = ContextLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
    )

    # Context 组装
    logger.context_assemble_start(llm_call_index=0)

    logger.context_slot1_system_prompt(
        tokens={
            "role": 150,
            "skill_registry": 100,
            "fewshot": 300,
            "profile": 100,
        },
    )

    logger.context_slot8_history(
        message_count=12,
        total_tokens=2400,
        compressed=False,
    )

    logger.context_assemble_end(
        total_input_tokens=3500,
        max_output_tokens=8192,
    )

    # Token 预算检查
    logger.context_budget_check(
        total_tokens=3500,
        max_tokens=32768,
        overflow=False,
    )


def example_tools_logging():
    """Tools 模块日志示例"""

    # 创建 ToolsLogger
    logger = ToolsLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
        step_id=3,
    )

    # 权限决策
    logger.policy_decide_result(
        tool_name="send_email",
        effect_class="external_write",
        decision="ask",
        reason="External write operations require user confirmation",
    )

    # 工具执行
    logger.toolnode_execute_tool_start(
        tool_name="send_email",
        args={"to": "boss@...", "subject": "..."},
    )

    logger.toolnode_execute_tool_end(
        tool_name="send_email",
        result_length=45,
        latency_ms=234,
        error=None,
    )


def example_skills_logging():
    """Skills 模块日志示例"""

    # 创建 SkillsLogger
    logger = SkillsLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
        step_id=2,
    )

    # Skill 扫描
    logger.skill_scan_start(skills_dir="~/skills/")
    logger.skill_scan_end(
        total_count=3,
        active_count=2,
        skipped_count=1,
    )

    # Skill 激活
    logger.skill_llm_matched(skill_name="legal-search", confidence=0.95)

    logger.skill_read_file_loaded(
        skill_name="legal-search",
        content_length=1234,
        tokens=320,
        latency_ms=15,
    )

    logger.skill_content_injected(
        skill_name="legal-search",
        instructions_tokens=280,
        examples_tokens=40,
    )


def example_memory_logging():
    """Memory 模块日志示例"""

    # 创建 MemoryLogger
    logger = MemoryLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
        step_id=1,
    )

    # Short Memory
    logger.memory_short_restore_start(thread_id="thread_789")
    logger.memory_short_restore_loaded(message_count=12, total_tokens=2400)

    logger.memory_short_save_saved(message_count=15, checkpoint_id="cp_123")

    # Long Memory
    logger.memory_long_load_start(
        namespace=("profile", "user_456"),
        key="episodic",
    )

    logger.memory_long_loaded(
        episodic_data={
            "user_id": "user_456",
            "preferences": {"domain": "legal-tech", "language": "zh"},
            "interaction_count": 15,
        },
        procedural_count=0,
        latency_ms=12,
    )

    logger.memory_long_written(
        changes={"interaction_count": 16},
        interaction_count_new=16,
        latency_ms=8,
    )


def example_api_logging():
    """API 模块日志示例"""

    # 创建 ApiLogger
    logger = ApiLogger(
        session_id="sess_abc123",
        user_id="user_456",
    )

    # 请求处理
    logger.api_request_received(
        endpoint="/chat",
        method="POST",
        message_length=123,
    )

    logger.api_agent_invoked(
        session_id="sess_abc123",
        user_id="user_456",
        message="查合同123状态",
    )

    # SSE 流
    logger.api_sse_stream_start(
        session_id="sess_abc123",
        client_ip="192.168.1.1",
    )

    logger.api_sse_event_sent(event_type="thought", data_length=45)

    logger.api_sse_stream_end(
        session_id="sess_abc123",
        total_events=50,
        total_bytes=2048,
    )

    logger.api_request_completed(
        session_id="sess_abc123",
        status_code=200,
        total_latency_ms=2345,
    )


def example_sse_logging():
    """SSE 模块日志示例"""

    # 创建 SseLogger
    logger = SseLogger(
        session_id="sess_abc123",
        user_id="user_456",
    )

    # 连接管理
    logger.sse_connection_established(
        session_id="sess_abc123",
        client_ip="192.168.1.1",
    )

    # 事件推送
    logger.sse_event_thought(
        token_text="需要查询合同",
        cumulative_tokens=5,
    )

    logger.sse_event_tool_start(
        tool_name="contract_status",
        args={"id": "123"},
    )

    logger.sse_event_tool_result(
        tool_name="contract_status",
        result_length=123,
    )

    logger.sse_event_done(
        final_answer_length=234,
        total_tokens=3456,
    )

    logger.sse_connection_closed(
        session_id="sess_abc123",
        reason="client_disconnected",
        duration_seconds=30.5,
    )


def example_with_step_increment():
    """使用 step 递增"""

    logger = AgentLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
    )

    logger.turn_start(
        message="查合同123状态",
        message_tokens=10,
    )

    # Step 1: LLM 决策
    logger.set_step(1)
    logger.middleware_wrap_model_call_start(llm_call_index=0)

    # Step 2: 工具执行
    logger.increment_step()
    logger.middleware_wrap_model_call_start(llm_call_index=1)

    # Step 3: 最终答案
    logger.increment_step()
    logger.turn_end(
        total_tokens=1234,
        total_latency_ms=567,
        final_answer_tokens=123,
    )


def example_error_logging():
    """错误日志示例"""

    logger = ToolsLogger(
        session_id="sess_abc123",
        user_id="user_456",
        thread_id="thread_789",
        step_id=3,
    )

    try:
        # 模拟工具执行失败
        raise Exception("Tool execution failed")
    except Exception as e:
        logger.toolnode_execute_tool_end(
            tool_name="send_email",
            result_length=0,
            latency_ms=123,
            error=str(e),
        )

        # 记录完整异常
        logger.exception(
            "toolnode.execute_tool_error",
            "Tool execution failed with exception",
            data={
                "tool_name": "send_email",
                "error_type": type(e).__name__,
            },
            tags=["tools", "error"],
        )


if __name__ == "__main__":
    # 运行示例
    print("=== Agent Logging Example ===")
    example_agent_logging()

    print("\n=== Tools Logging Example ===")
    example_tools_logging()

    print("\n=== Context Logging Example ===")
    example_context_logging()

    print("\n=== Skills Logging Example ===")
    example_skills_logging()

    print("\n=== Memory Logging Example ===")
    example_memory_logging()

    print("\n=== API Logging Example ===")
    example_api_logging()

    print("\n=== SSE Logging Example ===")
    example_sse_logging()

    print("\n=== Step Increment Example ===")
    example_with_step_increment()

    print("\n=== Error Logging Example ===")
    example_error_logging()

    print("\n✅ All logging examples completed successfully!")
