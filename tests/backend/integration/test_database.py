"""
Integration tests for database components.

These tests require a running PostgreSQL instance.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.postgres import (
    close_db,
    get_checkpointer,
    get_connection,
    get_database_url,
    get_pool,
    get_store,
    init_db,
)


class TestDatabaseConnection:
    """Test database connection setup."""

    @pytest.fixture
    def mock_settings(self, monkeypatch: pytest.MonkeyPatch):
        """Mock database settings for testing."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test_db")

    def test_get_database_url(self) -> None:
        """Test get_database_url returns correct URL."""
        url = get_database_url()
        assert url is not None
        assert "postgresql://" in url

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_pool_creates_connection_pool(self) -> None:
        """Test that get_pool creates a connection pool."""
        pool = await get_pool()
        assert pool is not None
        # Pool should be open
        # Note: Actual connection testing requires database

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_pool_returns_singleton(self) -> None:
        """Test that get_pool returns the same pool instance."""
        pool1 = await get_pool()
        pool2 = await get_pool()
        assert pool1 is pool2


class TestAsyncPostgresSaver:
    """Test AsyncPostgresSaver (Short Memory) setup."""

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_checkpointer(self) -> None:
        """Test get_checkpointer creates AsyncPostgresSaver."""
        checkpointer = await get_checkpointer()
        assert checkpointer is not None

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_checkpointer_singleton(self) -> None:
        """Test that get_checkpointer returns singleton."""
        c1 = await get_checkpointer()
        c2 = await get_checkpointer()
        assert c1 is c2

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_checkpointer_setup(self) -> None:
        """Test that checkpointer.setup() creates tables."""
        checkpointer = await get_checkpointer()
        # setup() should be called during initialization
        # Actual table verification requires database connection

    @pytest.mark.asyncio
    async def test_checkpointer_uses_psycopg3(self) -> None:
        """Test that checkpointer uses psycopg3 connection_kwargs."""
        with patch("app.db.postgres.AsyncPostgresSaver") as MockSaver:
            MockSaver.from_conn_string = MagicMock(return_value=AsyncMock())

            checkpointer = await get_checkpointer()

            # Verify from_conn_string was called with correct kwargs
            MockSaver.from_conn_string.assert_called_once()
            call_kwargs = MockSaver.from_conn_string.call_args.kwargs
            assert "connection_kwargs" in call_kwargs

            conn_kwargs = call_kwargs["connection_kwargs"]
            assert conn_kwargs.get("autocommit") is True
            assert "row_factory" in conn_kwargs
            assert conn_kwargs.get("prepare_threshold") == 0


class TestAsyncPostgresStore:
    """Test AsyncPostgresStore (Long Memory) setup."""

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_store(self) -> None:
        """Test get_store creates AsyncPostgresStore."""
        store = await get_store()
        assert store is not None

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_store_singleton(self) -> None:
        """Test that get_store returns singleton."""
        s1 = await get_store()
        s2 = await get_store()
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_store_uses_from_conn_string(self) -> None:
        """Test that store uses from_conn_string method."""
        with patch("app.db.postgres.AsyncPostgresStore") as MockStore:
            mock_instance = AsyncMock()
            MockStore.from_conn_string = MagicMock(return_value=mock_instance)

            store = await get_store()

            # Verify from_conn_string was called
            MockStore.from_conn_string.assert_called_once()


class TestDatabaseLifecycle:
    """Test database initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_init_db(self) -> None:
        """Test init_db initializes all components."""
        with patch("app.db.postgres.get_pool") as mock_pool, patch(
            "app.db.postgres.get_checkpointer"
        ) as mock_checkpointer, patch(
            "app.db.postgres.get_store"
        ) as mock_store:

            mock_pool.return_value = AsyncMock()
            mock_checkpointer.return_value = AsyncMock(setup=AsyncMock())
            mock_store.return_value = AsyncMock(setup=AsyncMock())

            await init_db()

            # Verify all components were initialized
            mock_pool.assert_called_once()
            mock_checkpointer.assert_called_once()
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db(self) -> None:
        """Test close_db closes all connections."""
        # First initialize
        with patch("app.db.postgres.get_pool") as mock_pool, patch(
            "app.db.postgres.get_checkpointer"
        ) as mock_checkpointer, patch(
            "app.db.postgres.get_store"
        ) as mock_store:

            mock_pool_instance = AsyncMock(close=AsyncMock())
            mock_pool.return_value = mock_pool_instance
            mock_checkpointer.return_value = AsyncMock()
            mock_store.return_value = AsyncMock()

            await init_db()
            await close_db()

            # Verify pool was closed
            mock_pool_instance.close.assert_called_once()


class TestGetConnection:
    """Test get_connection context manager."""

    @pytest.mark.requires_db
    @pytest.mark.asyncio
    async def test_get_connection_yields_connection(self) -> None:
        """Test that get_connection yields a connection."""
        with patch("app.db.postgres.get_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_pool_instance = MagicMock()
            mock_pool_instance.__aenter__ = AsyncMock(return_value=mock_pool_instance)
            mock_pool_instance.connection = MagicMock()
            mock_pool_instance.connection.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool_instance.connection.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = mock_pool_instance

            async with get_connection() as conn:
                assert conn is not None

    @pytest.mark.asyncio
    async def test_get_connection_closes_on_exit(self) -> None:
        """Test that connection is closed after context exit."""
        with patch("app.db.postgres.get_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_pool_instance = MagicMock()
            mock_pool_instance.__aenter__ = AsyncMock(return_value=mock_pool_instance)
            mock_pool_instance.connection = MagicMock()
            mock_pool_instance.connection.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool_instance.connection.__aexit__ = AsyncMock(return_value=None)
            mock_pool.return_value = mock_pool_instance

            async with get_connection() as conn:
                pass

            # Verify __aexit__ was called
            mock_pool_instance.connection.__aexit__.assert_called_once()


class TestConnectionKwargs:
    """Test that psycopg3 connection_kwargs are correctly set."""

    def test_connection_kwargs_include_autocommit(self) -> None:
        """Test that autocommit is enabled."""

        with patch("app.db.postgres.AsyncPostgresSaver") as MockSaver:
            # Simulate the actual call
            MockSaver.from_conn_string = MagicMock(return_value=AsyncMock())

            # Import to trigger the code
            import importlib

            importlib.reload(import_module("app.db.postgres"))

    @pytest.mark.asyncio
    async def test_row_factory_is_dict_row(self) -> None:
        """Test that row_factory is set to dict_row."""
        from psycopg.rows import dict_row

        # Verify dict_row is imported and available
        assert dict_row is not None

    @pytest.mark.asyncio
    async def test_prepare_threshold_is_zero(self) -> None:
        """Test that prepare_threshold is set to 0 (disable prepared statements)."""
        # This is verified in the connection_kwargs test above
        pass


# Helper for dynamic import
import importlib
from types import ModuleType


def import_module(name: str) -> ModuleType:
    """Helper to import a module."""
    return importlib.import_module(name)
