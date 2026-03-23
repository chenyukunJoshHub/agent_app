"""
Integration tests for migration files (Phase 2.4).

Tests verify that migration files exist and have valid SQL syntax.
"""
import os

import pytest


class TestMigrationFiles:
    """Test that migration files exist and are valid."""

    @pytest.fixture
    def migrations_dir(self):
        """Get the migrations directory path."""
        # Get the project root (backend/tests/integration -> backend -> project root)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(os.path.dirname(current_dir))
        project_root = os.path.dirname(backend_dir)
        return os.path.join(project_root, "supabase", "migrations")

    def test_003_constraints_migration_exists(self, migrations_dir):
        """Test that 003_add_constraints.sql exists."""
        migration_path = os.path.join(migrations_dir, "003_add_constraints.sql")
        assert os.path.exists(migration_path), f"Migration file not found: {migration_path}"

    def test_004_indexes_migration_exists(self, migrations_dir):
        """Test that 004_add_indexes.sql exists."""
        migration_path = os.path.join(migrations_dir, "004_add_indexes.sql")
        assert os.path.exists(migration_path), f"Migration file not found: {migration_path}"

    def test_005_rls_migration_exists(self, migrations_dir):
        """Test that 005_enable_rls.sql exists."""
        migration_path = os.path.join(migrations_dir, "005_enable_rls.sql")
        assert os.path.exists(migration_path), f"Migration file not found: {migration_path}"

    def test_003_constraints_content_valid(self, migrations_dir):
        """Test that 003_add_constraints.sql has valid content."""
        migration_path = os.path.join(migrations_dir, "003_add_constraints.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for key constraints
        assert 'chk_latency_ms_positive' in content
        assert 'chk_finish_reason_valid' in content
        assert 'chk_thought_chain_max_size' in content
        assert 'chk_tool_calls_max_size' in content
        assert 'chk_user_input_max_length' in content
        assert 'chk_final_answer_max_length' in content

        # Check for ALTER TABLE statements
        assert 'ALTER TABLE agent_traces' in content
        assert 'ADD CONSTRAINT' in content

    def test_004_indexes_content_valid(self, migrations_dir):
        """Test that 004_add_indexes.sql has valid content."""
        migration_path = os.path.join(migrations_dir, "004_add_indexes.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for composite indexes
        assert 'idx_agent_traces_user_session_created' in content
        assert 'idx_agent_traces_session_created_covering' in content
        assert 'idx_agent_traces_user_created' in content

        # Check for GIN indexes
        assert 'idx_agent_traces_tool_calls' in content
        assert 'idx_agent_traces_thought_chain' in content
        assert 'idx_agent_traces_token_usage' in content
        assert 'USING GIN' in content

        # Check for partial indexes
        assert 'idx_agent_traces_errors' in content
        assert 'idx_agent_traces_high_latency' in content
        assert 'idx_agent_traces_recent' in content
        assert 'WHERE' in content

        # Check for CREATE INDEX statements
        assert 'CREATE INDEX' in content

    def test_005_rls_content_valid(self, migrations_dir):
        """Test that 005_enable_rls.sql has valid content."""
        migration_path = os.path.join(migrations_dir, "005_enable_rls.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for RLS enable
        assert 'ENABLE ROW LEVEL SECURITY' in content

        # Check for policies
        assert 'CREATE POLICY' in content
        assert 'agent_traces_select_own' in content
        assert 'agent_traces_insert_own' in content
        assert 'agent_traces_update_own' in content
        assert 'agent_traces_delete_own' in content

        # Check for user context function
        assert 'set_user_context' in content
        assert 'app.user_id' in content
        assert 'current_setting' in content

    def test_003_constraints_sql_keywords(self, migrations_dir):
        """Test that 003_add_constraints.sql has valid SQL keywords."""
        migration_path = os.path.join(migrations_dir, "003_add_constraints.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for SQL keywords (basic syntax validation)
        assert 'ALTER TABLE' in content
        assert 'ADD CONSTRAINT' in content
        assert 'CHECK' in content
        assert 'IF NOT EXISTS' in content

    def test_004_indexes_sql_keywords(self, migrations_dir):
        """Test that 004_add_indexes.sql has valid SQL keywords."""
        migration_path = os.path.join(migrations_dir, "004_add_indexes.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for SQL keywords
        assert 'CREATE INDEX' in content
        assert 'IF NOT EXISTS' in content
        assert 'ON agent_traces' in content

    def test_005_rls_sql_keywords(self, migrations_dir):
        """Test that 005_enable_rls.sql has valid SQL keywords."""
        migration_path = os.path.join(migrations_dir, "005_enable_rls.sql")

        with open(migration_path, 'r') as f:
            content = f.read()

        # Check for SQL keywords
        assert 'ALTER TABLE' in content
        assert 'ENABLE ROW LEVEL SECURITY' in content
        assert 'CREATE POLICY' in content
        assert 'CREATE OR REPLACE FUNCTION' in content

    def test_migration_file_naming(self, migrations_dir):
        """Test that migration files follow naming convention."""
        files = os.listdir(migrations_dir)

        # Check for correct naming pattern
        assert '003_add_constraints.sql' in files
        assert '004_add_indexes.sql' in files
        assert '005_enable_rls.sql' in files

    def test_migration_comments_present(self, migrations_dir):
        """Test that migration files have comments."""
        for filename in ['003_add_constraints.sql', '004_add_indexes.sql', '005_enable_rls.sql']:
            migration_path = os.path.join(migrations_dir, filename)

            with open(migration_path, 'r') as f:
                content = f.read()

            # Check for comments (lines starting with --)
            assert '--' in content, f"Migration file {filename} should have comments"


class TestMigrationContentDetails:
    """Test specific content details in migrations."""

    @pytest.fixture
    def get_migration_content(self, migrations_dir):
        """Helper to read migration file content."""
        def _read(filename):
            path = os.path.join(migrations_dir, filename)
            with open(path, 'r') as f:
                return f.read()
        return _read

    @pytest.fixture
    def migrations_dir(self):
        """Get the migrations directory path."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(os.path.dirname(current_dir))
        project_root = os.path.dirname(backend_dir)
        return os.path.join(project_root, "supabase", "migrations")

    def test_constraints_valid_finish_reasons(self, migrations_dir, get_migration_content):
        """Test that all valid finish_reason values are included."""
        content = get_migration_content('003_add_constraints.sql')

        valid_reasons = [
            "'stop'",
            "'length'",
            "'tool_calls'",
            "'content_filter'",
            "'error'",
            "'interrupted'"
        ]

        for reason in valid_reasons:
            assert reason in content, f"Valid finish_reason {reason} should be in constraint"

    def test_constraints_size_limits(self, migrations_dir, get_migration_content):
        """Test that JSONB size limits are appropriate."""
        content = get_migration_content('003_add_constraints.sql')

        # Check for size limits
        assert '100000' in content  # 100KB for thought_chain
        assert '50000' in content   # 50KB for tool_calls
        assert '10000' in content   # 10KB for token_usage

    def test_indexes_covering_index_columns(self, migrations_dir, get_migration_content):
        """Test that covering index includes correct columns."""
        content = get_migration_content('004_add_indexes.sql')

        # Check for INCLUDE clause
        assert 'INCLUDE' in content

        # Check for included columns
        assert 'final_answer' in content
        assert 'latency_ms' in content
        assert 'finish_reason' in content
        assert 'thought_chain' in content
        assert 'tool_calls' in content

    def test_rls_dev_user_exception(self, migrations_dir, get_migration_content):
        """Test that RLS policies include dev_user exception."""
        content = get_migration_content('005_enable_rls.sql')

        # Check for dev_user exception
        assert "'dev_user'" in content
        assert 'OR' in content  # For the OR condition

    def test_rls_policy_types(self, migrations_dir, get_migration_content):
        """Test that all CRUD policies are present."""
        content = get_migration_content('005_enable_rls.sql')

        # Check for all policy types
        assert 'FOR SELECT' in content
        assert 'FOR INSERT' in content
        assert 'FOR UPDATE' in content
        assert 'FOR DELETE' in content
