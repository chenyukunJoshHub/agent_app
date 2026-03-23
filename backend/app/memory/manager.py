"""Memory manager - P0 implementation per architecture doc §2.4."""

from langgraph.store.postgres import AsyncPostgresStore

from app.memory.schemas import EpisodicData, MemoryContext, UserProfile


class MemoryManager:
    """Memory manager for long-term memory (user profiles).

    P0 Implementation:
    - load_episodic: Loads user profile from store (returns empty if not found)
    - save_episodic: No-op (P0 stub)
    - build_ephemeral_prompt: Builds injection text for System Prompt

    P2 Future:
    - Implement save_episodic with dirty flag optimization
    - Implement preference extraction from interactions
    """

    def __init__(self, store: AsyncPostgresStore) -> None:
        """Initialize MemoryManager.

        Args:
            store: AsyncPostgresStore instance for long-term memory
        """
        self.store = store

    async def load_episodic(self, user_id: str) -> UserProfile:
        """Load user profile from store.

        Per architecture doc §2.4, loads from namespace=("profile", user_id).

        Args:
            user_id: User identifier

        Returns:
            UserProfile: Loaded profile or empty UserProfile if not found
        """
        item = await self.store.aget(
            namespace=("profile", user_id), key="episodic"
        )
        if item is None:
            return UserProfile()
        return UserProfile(**item.value)

    async def save_episodic(self, user_id: str, data: UserProfile) -> None:
        """Save user profile to store.

        P0: No-op (stub implementation).

        Args:
            user_id: User identifier
            data: UserProfile to save
        """
        # P0: Don't write to store yet
        pass

    def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
        """Build ephemeral injection text for System Prompt.

        Per architecture doc §2.4 and §1.4 Ephemeral strategy.

        Args:
            ctx: MemoryContext containing user profile

        Returns:
            str: Injection text (empty if no preferences)
        """
        if not ctx.episodic.preferences:
            return ""

        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[用户画像]\n" + "\n".join(lines)

    # ----- Legacy methods (deprecated, kept for compatibility) -----

    async def get_user_context(self, user_id: str) -> MemoryContext | None:
        """Legacy: Get user profile context.

        Deprecated: Use load_episodic instead.
        """
        profile = await self.load_episodic(user_id)
        return MemoryContext(episodic=profile) if profile.user_id else None

    async def update_context(self, user_id: str, updates: dict) -> None:
        """Legacy: Update user profile context.

        Deprecated: Use save_episodic instead.
        """
        pass

    async def add_episodic(self, data: EpisodicData) -> None:
        """Legacy: Add episodic memory record.

        Deprecated: This will be implemented in P2.
        """
        pass
