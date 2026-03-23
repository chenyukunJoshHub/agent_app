"""
Interrupt Store for HIL (Human-in-the-Loop) state management.

Uses AsyncPostgresStore with namespace ("interrupts",) to persist
interrupt states across requests. Supports saving, retrieving, and deleting
interrupt data with automatic TTL (1 hour).
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.store.postgres import AsyncPostgresStore
from loguru import logger


class InterruptStore:
    """
    Store for managing HIL interrupt states.

    Uses AsyncPostgresStore with namespace isolation to persist interrupt
    data between the initial interrupt and user's resume decision.
    """

    def __init__(self, store: AsyncPostgresStore) -> None:
        """
        Initialize the interrupt store.

        Args:
            store: AsyncPostgresStore instance for persistence
        """
        self.store = store
        self.namespace = ("interrupts",)
        self.ttl_hours = 1  # Auto-delete after 1 hour
        logger.info("InterruptStore initialized")

    async def save_interrupt(
        self,
        session_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        """
        Save a new interrupt state.

        Args:
            session_id: Session identifier
            tool_name: Name of the tool being interrupted (e.g., "send_email")
            tool_args: Arguments passed to the tool

        Returns:
            str: Generated interrupt_id (UUID)
        """
        interrupt_id = str(uuid.uuid4())

        interrupt_data = {
            "interrupt_id": interrupt_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(hours=self.ttl_hours)
            ).isoformat(),
        }

        # Store with interrupt_id as the key
        await self.store.aput(
            namespace=self.namespace,
            key=interrupt_id,
            value=interrupt_data,
        )

        logger.info(
            f"Interrupt saved: {interrupt_id} for tool {tool_name} in session {session_id}"
        )
        return interrupt_id

    async def get_interrupt(self, interrupt_id: str) -> dict[str, Any] | None:
        """
        Retrieve an interrupt state by ID.

        Args:
            interrupt_id: Interrupt identifier (UUID)

        Returns:
            dict | None: Interrupt data if found, None otherwise
        """
        try:
            item = await self.store.aget(namespace=self.namespace, key=interrupt_id)

            if item is None:
                logger.warning(f"Interrupt not found: {interrupt_id}")
                return None

            # Item.value contains the stored data
            interrupt_data = item.value
            logger.debug(f"Interrupt retrieved: {interrupt_id}")
            return interrupt_data

        except Exception as e:
            logger.error(f"Error retrieving interrupt {interrupt_id}: {e}")
            return None

    async def delete_interrupt(self, interrupt_id: str) -> bool:
        """
        Delete an interrupt state after processing.

        Args:
            interrupt_id: Interrupt identifier (UUID)

        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            await self.store.adelete(namespace=self.namespace, key=interrupt_id)
            logger.info(f"Interrupt deleted: {interrupt_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting interrupt {interrupt_id}: {e}")
            return False

    async def update_interrupt_status(
        self, interrupt_id: str, status: str
    ) -> bool:
        """
        Update the status of an interrupt.

        Args:
            interrupt_id: Interrupt identifier (UUID)
            status: New status ("confirmed" | "rejected" | "expired")

        Returns:
            bool: True if updated, False otherwise
        """
        try:
            item = await self.store.aget(namespace=self.namespace, key=interrupt_id)

            if item is None:
                logger.warning(f"Cannot update status, interrupt not found: {interrupt_id}")
                return False

            # Update status and timestamp
            interrupt_data = item.value
            interrupt_data["status"] = status
            interrupt_data["updated_at"] = datetime.now(UTC).isoformat()

            await self.store.aput(
                namespace=self.namespace,
                key=interrupt_id,
                value=interrupt_data,
            )

            logger.info(f"Interrupt status updated: {interrupt_id} -> {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating interrupt status {interrupt_id}: {e}")
            return False

    async def get_pending_interrupts(self, session_id: str) -> list[dict[str, Any]]:
        """
        Get all pending interrupts for a session.

        Args:
            session_id: Session identifier

        Returns:
            list: List of pending interrupt data
        """
        # Note: AsyncPostgresStore doesn't support query by prefix directly
        # This method is a placeholder for future enhancement
        # For now, returns empty list as interrupts are accessed by ID
        logger.debug(f"Getting pending interrupts for session {session_id}")
        return []

    async def cleanup_expired_interrupts(self) -> int:
        """
        Clean up expired interrupts (older than TTL).

        Returns:
            int: Number of expired interrupts removed
        """
        # Note: AsyncPostgresStore doesn't support listing items
        # This would require a custom database query in P2
        # For P1, we rely on the TTL mechanism
        logger.debug("Cleanup called (no-op for P1)")
        return 0


# Global instance
_interrupt_store: InterruptStore | None = None


async def get_interrupt_store() -> InterruptStore:
    """
    Get or create the global InterruptStore instance.

    Returns:
        InterruptStore: Global interrupt store instance
    """
    global _interrupt_store

    if _interrupt_store is None:
        # Import here to avoid circular dependency
        from app.db.postgres import get_store

        store = await get_store()
        _interrupt_store = InterruptStore(store)
        logger.info("Global InterruptStore created")

    return _interrupt_store


__all__ = ["InterruptStore", "get_interrupt_store"]
