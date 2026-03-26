"""Memory manager - P0 implementation per architecture doc §2.4."""

from langgraph.store.postgres import AsyncPostgresStore

from app.memory.processors import (
    BaseInjectionProcessor,
    EpisodicProcessor,
    ProceduralProcessor,
)
from app.memory.schemas import EpisodicData, MemoryContext, UserProfile


class MemoryManager:
    """Memory manager for long-term memory (user profiles).

    P0 Implementation:
    - load_episodic: Loads user profile from store (returns empty if not found)
    - save_episodic: No-op (P0 stub — P2 will implement with dirty flag)
    - build_injection_parts: Iterates processors for ephemeral injection
    - build_ephemeral_prompt: Deprecated wrapper (delegates to EpisodicProcessor)
    - load_procedural / save_procedural: Load/save workflow SOPs

    P2 Future:
    - Implement save_episodic with dirty flag optimization
    - Implement preference extraction from interactions
    """

    def __init__(
        self,
        store: AsyncPostgresStore,
        processors: list[BaseInjectionProcessor] | None = None,
    ) -> None:
        """Initialize MemoryManager.

        Args:
            store: AsyncPostgresStore instance for long-term memory
            processors: Injection processors in injection order.
                Defaults to [EpisodicProcessor(), ProceduralProcessor()].
                Pass a custom list to add or replace processors.
        """
        self.store = store
        self.processors = processors or [EpisodicProcessor(), ProceduralProcessor()]

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
        """Build episodic injection text (deprecated — use build_injection_parts).

        Kept for backward compatibility with existing tests.
        Delegates to EpisodicProcessor.
        """
        return EpisodicProcessor().build_prompt(ctx)

    def build_injection_parts(self, ctx: MemoryContext) -> dict[str, str]:
        """Iterate all injection processors, returning {slot_name: text}.

        Order is determined by self.processors list order (affects injection order).
        To add a new memory type, register a new processor — no changes needed here.

        Returns:
            dict[str, str]: slot_name → injection text (may be "" if nothing to inject)
        """
        return {p.slot_name: p.build_prompt(ctx) for p in self.processors}

    async def load_procedural(self, user_id: str) -> dict:
        """Load procedural memory from store.

        Namespace: ("profile", user_id), Key: "procedural".

        Returns:
            dict: {workflows: {name: instruction, ...}} or empty dict
        """
        item = await self.store.aget(
            namespace=("profile", user_id), key="procedural"
        )
        return item.value if item is not None else {}

    async def save_procedural(self, user_id: str, data: dict) -> None:
        """Save procedural memory to store (merge semantics).

        Args:
            user_id: User identifier
            data: Procedural record dict to merge into existing data
        """
        existing = await self.load_procedural(user_id)
        existing.update(data)
        await self.store.aput(
            namespace=("profile", user_id),
            key="procedural",
            value=existing,
        )

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
