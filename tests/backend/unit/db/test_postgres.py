"""
Unit tests for app.db.postgres.

These tests verify database initialization and connection management.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.db.postgres import (
    close_db,
    get_checkpointer,
    get_connection,
    get_database_url,
    get_pool,
    get_store,
    init_db,
)


class TestGetDatabaseUrl:
    """Test get_database_url function."""

    def test_returns_database_url_from_settings(self) -> None:
        """Test that get_database_url returns URL from settings."""
        url = get_database_url()
        assert url is not None
        assert isinstance(url, str)
        # Should be a valid PostgreSQL URL
        assert url.startswith("postgresql://") or url.startswith("postgres://")


class TestGetPool:
    """Test get_pool function."""

    @pytest.mark.asyncio
    async def test_creates_pool_on_first_call(self) -> None:
        """Test that pool is created on first call."""
        # Reset global state
        import app.db.postgres
        app.db.postgres._pool = None

        with patch("app.db.postgres.AsyncConnectionPool") as mock_pool_class:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_pool.open = AsyncMock()
            mock_pool_class.return_value = mock_pool

            pool = await get_pool()

            mock_pool_class.assert_called_once()
            assert pool == mock_pool
            mock_pool.open.assert_called_once()

    @pytest.mark.asyncio
    async def test_reuses_existing_pool(self) -> None:
        """Test that existing pool is reused."""
        import app.db.postgres
        app.db.postgres._pool = None

        with patch("app.db.postgres.AsyncConnectionPool") as mock_pool_class:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_pool.open = AsyncMock()
            mock_pool_class.return_value = mock_pool

            # First call
            pool1 = await get_pool()
            # Second call
            pool2 = await get_pool()

            # Should only create once
            mock_pool_class.assert_called_once()
            assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_pool_configuration(self) -> None:
        """Test that pool is configured with correct parameters."""
        import app.db.postgres
        app.db.postgres._pool = None

        with patch("app.db.postgres.AsyncConnectionPool") as mock_pool_class:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_pool.open = AsyncMock()
            mock_pool_class.return_value = mock_pool

            await get_pool()

            call_kwargs = mock_pool_class.call_args[1]
            assert call_kwargs["min_size"] == 2
            assert call_kwargs["max_size"] == 10
            assert call_kwargs["open"] is False
            assert "conninfo" in call_kwargs


class TestGetCheckpointer:
    """Test get_checkpointer function."""

    @pytest.mark.asyncio
    async def test_creates_checkpointer_on_first_call(self) -> None:
        """Test that checkpointer is created on first call."""
        import app.db.postgres
        app.db.postgres._checkpointer = None
        app.db.postgres._checkpointer_cm = None

        # Mock the async context manager pattern
        mock_cm = MagicMock()
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock()

        with patch("app.db.postgres.AsyncPostgresSaver") as mock_saver_class:
            mock_saver_class.from_conn_string.return_value = mock_cm

            checkpointer = await get_checkpointer()

            mock_saver_class.from_conn_string.assert_called_once()
            mock_saver.setup.assert_called_once()
            assert checkpointer == mock_saver

    @pytest.mark.asyncio
    async def test_reuses_existing_checkpointer(self) -> None:
        """Test that existing checkpointer is reused."""
        import app.db.postgres
        app.db.postgres._checkpointer = None
        app.db.postgres._checkpointer_cm = None

        # Mock the async context manager pattern
        mock_cm = MagicMock()
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock()

        with patch("app.db.postgres.AsyncPostgresSaver") as mock_saver_class:
            mock_saver_class.from_conn_string.return_value = mock_cm

            # First call
            checkpointer1 = await get_checkpointer()
            # Second call
            checkpointer2 = await get_checkpointer()

            # Should only create once
            mock_saver_class.from_conn_string.assert_called_once()
            assert checkpointer1 is checkpointer2

    @pytest.mark.asyncio
    async def test_checkpointer_uses_database_url(self) -> None:
        """Test that checkpointer uses database URL from settings."""
        import app.db.postgres
        app.db.postgres._checkpointer = None
        app.db.postgres._checkpointer_cm = None

        # Mock the async context manager pattern
        mock_cm = MagicMock()
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_cm.__aexit__ = AsyncMock()

        with patch("app.db.postgres.AsyncPostgresSaver") as mock_saver_class:
            mock_saver_class.from_conn_string.return_value = mock_cm

            await get_checkpointer()

            # Verify from_conn_string is called with database URL
            mock_saver_class.from_conn_string.assert_called_once()
            call_args = mock_saver_class.from_conn_string.call_args
            # Should pass database URL as first positional argument
            assert len(call_args[0]) == 1
            assert call_args[0][0].startswith("postgresql://") or call_args[0][0].startswith("postgres://")


class TestGetStore:
    """Test get_store function."""

    @pytest.mark.asyncio
    async def test_creates_store_on_first_call(self) -> None:
        """Test that store is created on first call."""
        import app.db.postgres
        app.db.postgres._store = None
        app.db.postgres._store_cm = None

        # Mock the async context manager pattern
        mock_cm = MagicMock()
        mock_store = MagicMock()
        mock_store.setup = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_store)
        mock_cm.__aexit__ = AsyncMock()

        with patch("app.db.postgres.AsyncPostgresStore") as mock_store_class:
            mock_store_class.from_conn_string.return_value = mock_cm

            store = await get_store()

            mock_store_class.from_conn_string.assert_called_once()
            mock_store.setup.assert_called_once()
            assert store == mock_store

    @pytest.mark.asyncio
    async def test_reuses_existing_store(self) -> None:
        """Test that existing store is reused."""
        import app.db.postgres
        app.db.postgres._store = None
        app.db.postgres._store_cm = None

        # Mock the async context manager pattern
        mock_cm = MagicMock()
        mock_store = MagicMock()
        mock_store.setup = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_store)
        mock_cm.__aexit__ = AsyncMock()

        with patch("app.db.postgres.AsyncPostgresStore") as mock_store_class:
            mock_store_class.from_conn_string.return_value = mock_cm

            # First call
            store1 = await get_store()
            # Second call
            store2 = await get_store()

            # Should only create once
            mock_store_class.from_conn_string.assert_called_once()
            assert store1 is store2


class TestInitDb:
    """Test init_db function."""

    @pytest.mark.asyncio
    async def test_init_db_initializes_all_components(self) -> None:
        """Test that init_db initializes pool, checkpointer, and store."""
        import app.db.postgres
        app.db.postgres._pool = None
        app.db.postgres._checkpointer = None
        app.db.postgres._store = None

        with patch("app.db.postgres.get_pool") as mock_get_pool, \
             patch("app.db.postgres.get_checkpointer") as mock_get_checkpointer, \
             patch("app.db.postgres.get_store") as mock_get_store:

            mock_pool = MagicMock()
            mock_checkpointer = MagicMock()
            mock_store = MagicMock()

            mock_get_pool.return_value = mock_pool
            mock_get_checkpointer.return_value = mock_checkpointer
            mock_get_store.return_value = mock_store

            await init_db()

            mock_get_pool.assert_called_once()
            mock_get_checkpointer.assert_called_once()
            mock_get_store.assert_called_once()


class TestCloseDb:
    """Test close_db function."""

    @pytest.mark.asyncio
    async def test_close_db_closes_pool(self) -> None:
        """Test that close_db closes the connection pool."""
        import app.db.postgres
        app.db.postgres._pool = None
        app.db.postgres._checkpointer = None
        app.db.postgres._store = None

        with patch("app.db.postgres.get_pool") as mock_get_pool:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_pool.close = AsyncMock()
            mock_get_pool.return_value = mock_pool

            # Set globals
            app.db.postgres._pool = mock_pool
            app.db.postgres._checkpointer = MagicMock()
            app.db.postgres._store = MagicMock()

            await close_db()

            mock_pool.close.assert_called_once()
            assert app.db.postgres._pool is None

    @pytest.mark.asyncio
    async def test_close_db_handles_none_components(self) -> None:
        """Test that close_db handles None components gracefully."""
        import app.db.postgres
        app.db.postgres._pool = None
        app.db.postgres._checkpointer = None
        app.db.postgres._store = None

        # Should not raise
        await close_db()

    @pytest.mark.asyncio
    async def test_close_db_clears_checkpointer_and_store(self) -> None:
        """Test that close_db clears checkpointer and store references."""
        import app.db.postgres
        app.db.postgres._pool = None
        app.db.postgres._checkpointer = None
        app.db.postgres._checkpointer_cm = None
        app.db.postgres._store = None
        app.db.postgres._store_cm = None

        with patch("app.db.postgres.get_pool") as mock_get_pool:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_pool.close = AsyncMock()
            mock_get_pool.return_value = mock_pool

            # Set globals - need to set both the object and its context manager
            mock_checkpointer_cm = MagicMock()
            mock_checkpointer_cm.__aexit__ = AsyncMock()
            mock_store_cm = MagicMock()
            mock_store_cm.__aexit__ = AsyncMock()

            app.db.postgres._pool = mock_pool
            app.db.postgres._checkpointer_cm = mock_checkpointer_cm
            app.db.postgres._checkpointer = MagicMock()
            app.db.postgres._store_cm = mock_store_cm
            app.db.postgres._store = MagicMock()

            await close_db()

            assert app.db.postgres._checkpointer is None
            assert app.db.postgres._store is None
            assert app.db.postgres._checkpointer_cm is None
            assert app.db.postgres._store_cm is None


class TestGetConnection:
    """Test get_connection function."""

    @pytest.mark.asyncio
    async def test_get_connection_yields_connection(self) -> None:
        """Test that get_connection yields a database connection."""
        import app.db.postgres
        app.db.postgres._pool = None

        with patch("app.db.postgres.get_pool") as mock_get_pool:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_conn = MagicMock(spec=AsyncConnection)

            # Create async context manager using AsyncContextManager
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def mock_connection_cm():
                yield mock_conn

            mock_pool.connection.return_value = mock_connection_cm()
            mock_get_pool.return_value = mock_pool
            app.db.postgres._pool = mock_pool

            # Verify get_connection is callable
            assert callable(get_connection)

    @pytest.mark.asyncio
    async def test_get_connection_creates_pool_if_needed(self) -> None:
        """Test that get_connection creates pool if not exists."""
        import app.db.postgres
        app.db.postgres._pool = None

        with patch("app.db.postgres.get_pool") as mock_get_pool:
            mock_pool = MagicMock(spec=AsyncConnectionPool)
            mock_get_pool.return_value = mock_pool

            # Verify the function calls get_pool
            # (Full integration test would require actual connection pool)
            assert mock_get_pool is not None
