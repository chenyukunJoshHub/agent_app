"""
Session Context API - Token Budget State Endpoint.

P0: GET /session/{session_id}/context endpoint that returns token budget state.
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.prompt.budget import DEFAULT_BUDGET


# Response Models
class SlotAllocation(BaseModel):
    """Token slot allocations."""

    system: int = Field(..., description="System Prompt + Few-shot slot")
    active_skill: int = Field(..., description="Active Skill slot")
    few_shot: int = Field(..., description="Few-shot slot")
    rag: int = Field(..., description="RAG background knowledge slot")
    episodic: int = Field(..., description="Episodic memory slot")
    procedural: int = Field(..., description="Procedural memory slot")
    tools: int = Field(..., description="Tools schema slot")
    history: int = Field(..., description="Conversation history slot")


class UsageMetrics(BaseModel):
    """Token usage metrics."""

    total_used: int = Field(..., description="Total tokens used")
    total_remaining: int = Field(..., description="Total tokens remaining")
    input_budget: int = Field(..., description="Available input budget")
    output_reserve: int = Field(..., description="Output reservation")


class TokenBudgetState(BaseModel):
    """Token budget state."""

    model_context_window: int = Field(..., description="Model context window size")
    working_budget: int = Field(..., description="Agent working budget")
    slots: SlotAllocation = Field(..., description="Slot allocations")
    usage: UsageMetrics = Field(..., description="Usage metrics")


class ContextResponse(BaseModel):
    """Session context response."""

    session_id: str = Field(..., description="Session identifier")
    token_budget: dict[str, Any] = Field(..., description="Token budget state")


# Router
router = APIRouter(prefix="/session", tags=["session"])


@router.get("/{session_id}/context", response_model=ContextResponse)
async def get_session_context(session_id: str) -> ContextResponse:
    """
    Get session context including token budget state.

    P0: Returns default token budget configuration.
    P1: Include actual session usage metrics from state.

    Args:
        session_id: Session identifier

    Returns:
        ContextResponse: Session context with token budget state
    """
    # Get default budget
    budget = DEFAULT_BUDGET

    # Build slot allocations
    slots = SlotAllocation(
        system=budget.SLOT_SYSTEM,
        active_skill=budget.SLOT_ACTIVE_SKILL,
        few_shot=budget.SLOT_FEW_SHOT,
        rag=budget.SLOT_RAG,
        episodic=budget.SLOT_EPISODIC,
        procedural=budget.SLOT_PROCEDURAL,
        tools=budget.SLOT_TOOLS,
        history=budget.slot_history,
    )

    # Build usage metrics
    # P0: No actual usage tracking yet, return defaults
    # P1: Fetch actual usage from session state
    usage = UsageMetrics(
        total_used=0,  # P0: No tracking yet
        total_remaining=budget.WORKING_BUDGET,  # P0: Full budget available
        input_budget=budget.input_budget,
        output_reserve=budget.SLOT_OUTPUT,
    )

    # Build token budget state
    token_budget_state = TokenBudgetState(
        model_context_window=budget.MODEL_CONTEXT_WINDOW,
        working_budget=budget.WORKING_BUDGET,
        slots=slots,
        usage=usage,
    )

    # Return response
    return ContextResponse(
        session_id=session_id,
        token_budget=token_budget_state.model_dump(),
    )


__all__ = ["router"]
