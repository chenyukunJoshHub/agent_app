"""
LangChain Agent Engine - creates and configures the ReAct agent.

P0: Basic create_agent with web_search tool and middleware.
P1: HIL middleware for manual intervention.
P1: Skills system integration (SkillManager + read_file tool).
"""
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from app.agent.middleware.hil import HILMiddleware
from app.agent.middleware.memory import MemoryMiddleware
from app.agent.middleware.summarization import create_summarization_middleware
from app.agent.middleware.trace import TraceMiddleware
from app.config import settings
from app.db.postgres import get_store
from app.llm.factory import llm_factory
from app.memory.manager import MemoryManager
from app.observability.interrupt_store import get_interrupt_store
from app.prompt.builder import build_system_prompt
from app.skills.manager import SkillManager
from app.tools.file import read_file
from app.tools.search import web_search


async def create_react_agent(
    llm: BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    sse_queue: Any | None = None,
    skills_dir: str | None = None,
) -> CompiledStateGraph:
    """
    Create a LangChain ReAct agent with middleware.

    P0: Single provider, no fallback, basic middleware stack.
    P1: HIL middleware for manual intervention on irreversible operations.
    P1: Skills system integration (SkillManager + read_file tool).

    Args:
        llm: Language model (uses llm_factory() if None)
        tools: List of tools (uses [web_search, send_email, read_file] if None)
        sse_queue: Queue for SSE events (passed to TraceMiddleware)
        skills_dir: Skills directory path (uses settings.skills_dir if None)

    Returns:
        CompiledStateGraph: Configured agent graph (LangGraph 1.0+)

    Raises:
        Exception: If agent creation fails
    """
    # Initialize LLM
    if llm is None:
        llm = llm_factory()

    # Import send_email tool
    from app.tools.send_email import send_email

    # Initialize tools (add send_email and read_file for P1)
    if tools is None:
        tools = [web_search, send_email, read_file]

    # Ensure read_file is in tools
    if read_file not in tools:
        tools = list(tools) + [read_file]

    logger.info(f"Creating ReAct agent with {len(tools)} tool(s)")

    # Initialize SkillManager and build snapshot
    if skills_dir is None:
        skills_dir = settings.skills_dir
    skill_manager = SkillManager(skills_dir=skills_dir)
    skill_snapshot = skill_manager.build_snapshot()
    logger.info(f"Built SkillSnapshot: {len(skill_snapshot.skills)} skills, version {skill_snapshot.version}")

    # Build system prompt using build_system_prompt
    tool_names = [tool.name for tool in tools]
    system_prompt = build_system_prompt(
        skill_snapshot=skill_snapshot,
        available_tools=tool_names,
    )
    logger.debug(f"System prompt length: {len(system_prompt)} characters")

    # Create middleware stack
    # Get interrupt store for HIL middleware
    interrupt_store = await get_interrupt_store()

    # Get store for MemoryMiddleware (Long Memory)
    store = await get_store()
    memory_manager = MemoryManager(store=store)

    # Create middleware stack per architecture doc §2.7
    # Order matters: Memory → Summarization → Trace → HIL
    middleware = [
        MemoryMiddleware(memory_manager=memory_manager),  # P0: load + inject profile
        create_summarization_middleware(),  # P0: compress history when token limit exceeded
        TraceMiddleware(sse_queue=sse_queue),  # P0: SSE streaming
        HILMiddleware(interrupt_store=interrupt_store, sse_queue=sse_queue),  # P1: HIL intervention
    ]

    try:
        # Create agent with create_agent (LangChain 1.0+ API)
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            middleware=middleware,  # type: ignore
        )

        logger.info("Agent created successfully with HIL middleware")
        return agent

    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise


def get_default_tools() -> list[BaseTool]:
    """
    Get default tools for the agent.

    P0: Returns [web_search] only.
    P1: Returns [web_search, send_email].
    P1: Skills system: Adds [read_file] for skill activation.

    Returns:
        list[BaseTool]: Default tool list
    """
    from app.tools.send_email import send_email

    return [web_search, send_email, read_file]


__all__ = ["create_react_agent", "get_default_tools"]
