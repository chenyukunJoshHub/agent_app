"""
Integration tests for database constraints (Phase 2.4).

Tests verify that CHECK constraints, indexes, and RLS policies are correctly applied.
"""
import pytest

from app.db.postgres import get_checkpointer, get_store


@pytest.mark.asyncio
class TestDatabaseConstraints:
    """Test CHECK constraints on agent_traces table."""

    async def test_latency_positive_constraint(self, async_db_connection):
        """Test that negative latency is rejected."""
        checkpointer = await get_checkpointer()

        # Try to insert a trace with negative latency
        with pytest.raises(Exception) as exc_info:
            async with checkpointer.conn.transaction():
                await checkpointer.conn.execute(
                    """
                    INSERT INTO agent_traces
                    (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                    VALUES
                    ('test-session', 'test-user', 'test', 'answer', -100, 'stop')
                    """
                )

        # Should fail with constraint violation
        assert 'chk_latency_ms_positive' in str(exc_info.value) or 'violates' in str(exc_info.value).lower()

    async def test_finish_reason_valid_constraint(self, async_db_connection):
        """Test that invalid finish_reason is rejected."""
        checkpointer = await get_checkpointer()

        # Try to insert a trace with invalid finish_reason
        with pytest.raises(Exception) as exc_info:
            async with checkpointer.conn.transaction():
                await checkpointer.conn.execute(
                    """
                    INSERT INTO agent_traces
                    (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                    VALUES
                    ('test-session', 'test-user', 'test', 'answer', 100, 'invalid_reason')
                    """
                )

        # Should fail with constraint violation
        assert 'chk_finish_reason_valid' in str(exc_info.value) or 'violates' in str(exc_info.value).lower()

    async def test_valid_finish_reason_accepted(self, async_db_connection):
        """Test that valid finish_reason values are accepted."""
        checkpointer = await get_checkpointer()

        valid_reasons = ['stop', 'length', 'tool_calls', 'content_filter', 'error', 'interrupted']

        for reason in valid_reasons:
            async with checkpointer.conn.transaction():
                await checkpointer.conn.execute(
                    """
                    INSERT INTO agent_traces
                    (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                    VALUES
                    ($1, 'test-user', 'test', 'answer', 100, $2)
                    """,
                    f'test-session-{reason}', reason
                )

        # If we get here, all valid reasons were accepted
        assert True

    async def test_user_input_max_length_constraint(self, async_db_connection):
        """Test that user_input longer than 10K characters is rejected."""
        checkpointer = await get_checkpointer()

        # Create a string longer than 10K characters
        long_input = 'a' * 10001

        with pytest.raises(Exception) as exc_info:
            async with checkpointer.conn.transaction():
                await checkpointer.conn.execute(
                    """
                    INSERT INTO agent_traces
                    (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                    VALUES
                    ('test-session', 'test-user', $1, 'answer', 100, 'stop')
                    """,
                    long_input
                )

        # Should fail with constraint violation
        assert 'chk_user_input_max_length' in str(exc_info.value) or 'violates' in str(exc_info.value).lower()

    async def test_final_answer_max_length_constraint(self, async_db_connection):
        """Test that final_answer longer than 50K characters is rejected."""
        checkpointer = await get_checkpointer()

        # Create a string longer than 50K characters
        long_answer = 'a' * 50001

        with pytest.raises(Exception) as exc_info:
            async with checkpointer.conn.transaction():
                await checkpointer.conn.execute(
                    """
                    INSERT INTO agent_traces
                    (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
                    VALUES
                    ('test-session', 'test-user', 'test', $1, 100, 'stop')
                    """,
                    long_answer
                )

        # Should fail with constraint violation
        assert 'chk_final_answer_max_length' in str(exc_info.value) or 'violates' in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestDatabaseIndexes:
    """Test that performance indexes exist."""

    async def test_composite_index_exists(self, async_db_connection):
        """Test that composite indexes exist."""
        checkpointer = await get_checkpointer()

        # Check for composite index
        result = await checkpointer.conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE tablename = 'agent_traces'
            AND indexname = 'idx_agent_traces_user_session_created'
            """
        )

        assert result == 1, "Composite index idx_agent_traces_user_session_created should exist"

    async def test_gin_indexes_exist(self, async_db_connection):
        """Test that GIN indexes exist for JSONB fields."""
        checkpointer = await get_checkpointer()

        # Check for GIN indexes
        result = await checkpointer.conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'agent_traces'
            AND indexname LIKE '%_tool_calls%'
            ORDER BY indexname
            """
        )

        index_names = [row['indexname'] for row in result]
        assert 'idx_agent_traces_tool_calls' in index_names
        assert 'idx_agent_traces_tool_calls_path' in index_names

    async def test_partial_indexes_exist(self, async_db_connection):
        """Test that partial indexes exist."""
        checkpointer = await get_checkpointer()

        # Check for partial indexes
        result = await checkpointer.conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'agent_traces'
            AND indexname IN (
                'idx_agent_traces_errors',
                'idx_agent_traces_high_latency',
                'idx_agent_traces_recent'
            )
            ORDER BY indexname
            """
        )

        index_names = [row['indexname'] for row in result]
        assert len(index_names) == 3, "All 3 partial indexes should exist"


@pytest.mark.asyncio
class TestRowLevelSecurity:
    """Test RLS policies."""

    async def test_rls_enabled(self, async_db_connection):
        """Test that RLS is enabled on agent_traces."""
        checkpointer = await get_checkpointer()

        # Check if RLS is enabled
        result = await checkpointer.conn.fetchval(
            """
            SELECT relrowsecurity
            FROM pg_class
            WHERE relname = 'agent_traces'
            """
        )

        assert result is True, "RLS should be enabled on agent_traces"

    async def test_rls_policies_exist(self, async_db_connection):
        """Test that RLS policies exist."""
        checkpointer = await get_checkpointer()

        # Check for RLS policies
        result = await checkpointer.conn.fetch(
            """
            SELECT policyname
            FROM pg_policies
            WHERE tablename = 'agent_traces'
            ORDER BY policyname
            """
        )

        policy_names = [row['policyname'] for row in result]

        # Should have policies for SELECT, INSERT, UPDATE, DELETE
        assert 'agent_traces_select_own' in policy_names
        assert 'agent_traces_insert_own' in policy_names
        assert 'agent_traces_update_own' in policy_names
        assert 'agent_traces_delete_own' in policy_names

    async def test_set_user_context_function_exists(self, async_db_connection):
        """Test that set_user_context function exists."""
        checkpointer = await get_checkpointer()

        # Check for function
        result = await checkpointer.conn.fetchval(
            """
            SELECT COUNT(*)
            FROM pg_proc
            WHERE proname = 'set_user_context'
            """
        )

        assert result == 1, "set_user_context function should exist"

    async def test_rls_isolation(self, async_db_connection):
        """Test that RLS isolates user data."""
        checkpointer = await get_checkpointer()
        store = await get_store()

        # Insert a trace for user1
        await checkpointer.conn.execute(
            """
            INSERT INTO agent_traces
            (session_id, user_id, user_input, final_answer, latency_ms, finish_reason)
            VALUES
            ('session-1', 'user-1', 'test input', 'test answer', 100, 'stop')
            """
        )

        # Set user context to user-2
        await checkpointer.conn.execute("SELECT set_user_context('user-2')")

        # Try to select user-1's data
        result = await checkpointer.conn.fetchval(
            """
            SELECT COUNT(*)
            FROM agent_traces
            WHERE user_id = 'user-1'
            """
        )

        # Should return 0 because user-2 cannot see user-1's data
        assert result == 0, "User should not be able to see other users' data"

        # Clean up
        await checkpointer.conn.execute("SELECT set_user_context('dev_user')")
        await checkpointer.conn.execute("DELETE FROM agent_traces WHERE session_id = 'session-1'")
