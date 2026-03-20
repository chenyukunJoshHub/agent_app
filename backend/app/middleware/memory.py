"""
Memory Middleware - LangGraph middleware for memory management

Implements three-layer memory architecture:
1. Short Memory: Session-based (24h TTL)
2. Long Memory: User profile (persistent)
3. Working Memory: Token budget management
"""

from dataclasses import dataclass, field
from uuid import UUID

from app.core.config import settings
from app.core.logger import loguru_logger
from app.db.queries import (
    get_memory,
    list_namespace_memories,
    set_memory,
)


class BudgetExceededError(Exception):
    """Raised when token budget is exceeded"""
    pass


@dataclass
class TokenBudgetManager:
    """Manages token budget allocation for memory slots"""

    working_budget: int
    short_memory_slot: int = 4000
    long_memory_slot: int = 6000
    tool_output_slot: int = 8000

    _usage: dict[str, int] = field(default_factory=dict)

    @property
    def total_slot_budget(self) -> int:
        """Total budget allocated to memory slots"""
        return self.short_memory_slot + self.long_memory_slot + self.tool_output_slot

    @property
    def remaining_budget(self) -> int:
        """Calculate remaining budget for agent reasoning"""
        return self.working_budget - self.total_slot_budget

    def consume(self, slot: str, tokens: int) -> None:
        """Consume tokens from a specific slot"""
        available = self.get_slot_size(slot) - self._usage.get(slot, 0)

        if tokens > available:
            raise BudgetExceededError(
                f"Budget exceeded for {slot}: need {tokens}, available {available}"
            )

        self._usage[slot] = self._usage.get(slot, 0) + tokens
        loguru_logger.info(f"Consumed {tokens} tokens from {slot}")

    def get_usage(self, slot: str) -> int:
        """Get current usage for a slot"""
        return self._usage.get(slot, 0)

    def remaining(self, slot: str) -> int:
        """Get remaining tokens in a slot"""
        return self.get_slot_size(slot) - self.get_usage(slot)

    def get_slot_size(self, slot: str) -> int:
        """Get the size of a specific slot"""
        slot_sizes = {
            "short_memory": self.short_memory_slot,
            "long_memory": self.long_memory_slot,
            "tool_output": self.tool_output_slot,
        }
        return slot_sizes.get(slot, 0)

    def reset_turn(self) -> None:
        """Reset usage for a new turn"""
        self._usage.clear()
        loguru_logger.debug("Token budget reset for new turn")


@dataclass
class UserProfile:
    """Manages user profile in long-term memory"""

    user_id: UUID
    namespace: str = "user_profiles"
    data: dict = field(default_factory=dict)

    async def load(self) -> dict:
        """Load user profile from database"""
        from app.db.connection import async_session_maker

        async with async_session_maker() as session:
            memories = await list_namespace_memories(session, self.user_id, self.namespace)
            self.data = memories
            loguru_logger.info(f"Loaded profile for user {self.user_id}: {len(memories)} keys")
            return self.data

    async def save(self, data: dict | None = None) -> None:
        """Save user profile to database"""
        from app.db.connection import async_session_maker

        if data:
            self.data.update(data)

        async with async_session_maker() as session:
            for key, value in self.data.items():
                await set_memory(session, self.user_id, self.namespace, key, value)
            await session.commit()

        loguru_logger.info(f"Saved profile for user {self.user_id}")

    def inject_ephemeral(self, messages: list[dict]) -> list[dict]:
        """
        Inject profile data as ephemeral system message

        This adds context without polluting chat history
        """
        if not self.data:
            return messages

        # Build system message from profile
        profile_parts = []
        if "name" in self.data:
            profile_parts.append(f"User's name is {self.data['name']}")
        if "role" in self.data:
            profile_parts.append(f"User is a {self.data['role']}")
        if "preferences" in self.data:
            prefs = ", ".join(f"{k}={v}" for k, v in self.data["preferences"].items())
            profile_parts.append(f"User preferences: {prefs}")
        if "expertise" in self.data:
            expertise = ", ".join(self.data["expertise"])
            profile_parts.append(f"User has expertise in: {expertise}")

        if not profile_parts:
            return messages

        system_msg = {"role": "system", "content": "\n".join(profile_parts)}
        return [system_msg] + messages


class MemoryMiddleware:
    """
    LangGraph middleware for memory management

    Hooks:
    - before_agent: Load user profile from long-term memory
    - wrap_model_call: Inject ephemeral profile into model calls
    - after_agent: Save updated profile back to long-term memory
    """

    def __init__(self) -> None:
        self._profiles: dict[UUID, UserProfile] = {}
        self._budget_managers: dict[UUID, TokenBudgetManager] = {}

    async def load_profile(self, user_id: UUID) -> UserProfile:
        """Load or create user profile"""
        if user_id not in self._profiles:
            profile = UserProfile(user_id=user_id)
            await profile.load()
            self._profiles[user_id] = profile
        return self._profiles[user_id]

    async def save_profile(self, user_id: UUID, data: dict | None = None) -> None:
        """Save user profile"""
        profile = await self.load_profile(user_id)
        await profile.save(data)

    async def before_agent(self, context: dict) -> dict:
        """
        Load user profile before agent execution

        Args:
            context: Agent context with user_id

        Returns:
            Updated context with user_profile
        """
        user_id = context.get("user_id")
        if not user_id:
            return context

        profile = await self.load_profile(user_id)
        context["user_profile"] = profile.data

        # Initialize token budget manager
        budget = TokenBudgetManager(working_budget=settings.working_budget)
        self._budget_managers[user_id] = budget
        context["token_budget"] = budget

        loguru_logger.info(f"Loaded profile for user {user_id}")
        return context

    async def wrap_model_call(self, context: dict) -> list[dict]:
        """
        Inject ephemeral profile into model calls

        Args:
            context: Agent context with user_profile and messages

        Returns:
            Messages with ephemeral system message prepended
        """
        profile_data = context.get("user_profile", {})
        messages = context.get("messages", [])

        profile = UserProfile(user_id=context["user_id"], data=profile_data)
        return profile.inject_ephemeral(messages)

    async def after_agent(self, context: dict) -> dict:
        """
        Save updated profile after agent execution

        Args:
            context: Agent context with updated user_profile

        Returns:
            Updated context
        """
        user_id = context.get("user_id")
        if not user_id:
            return context

        # Save any updates to profile
        profile_data = context.get("user_profile")
        if profile_data:
            await self.save_profile(user_id, profile_data)

        loguru_logger.info(f"Saved profile for user {user_id}")
        return context
