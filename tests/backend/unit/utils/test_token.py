"""
Unit tests for app.utils.token.

Tests token counting and budget management functionality.
"""
import pytest


class TestCountTokens:
    """Test count_tokens function."""

    def test_count_tokens_returns_integer(self) -> None:
        """Test that count_tokens returns an integer."""
        from app.utils.token import count_tokens

        result = count_tokens("Hello, world!")
        assert isinstance(result, int)

    def test_count_tokens_empty_text(self) -> None:
        """Test count_tokens with empty text."""
        from app.utils.token import count_tokens

        result = count_tokens("")
        assert result == 0

    def test_count_tokens_simple_text(self) -> None:
        """Test count_tokens with simple English text."""
        from app.utils.token import count_tokens

        result = count_tokens("Hello, world!")
        # "Hello, world!" should be more than 0 tokens
        assert result > 0

    def test_count_tokens_chinese_text(self) -> None:
        """Test count_tokens with Chinese text."""
        from app.utils.token import count_tokens

        result = count_tokens("你好世界")
        assert result > 0

    def test_count_tokens_with_different_model(self) -> None:
        """Test count_tokens with different model."""
        from app.utils.token import count_tokens

        result = count_tokens("Hello", model="gpt-3.5-turbo")
        assert result > 0


class TestTokenBudget:
    """Test TokenBudget class."""

    def test_token_budget_initialization(self) -> None:
        """Test TokenBudget initializes with correct defaults."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        assert budget.total_budget == 32000
        assert budget.system_prompt == 2000
        assert budget.tools_schema == 3000
        assert budget.few_shot == 2000
        assert budget.long_memory == 1000
        assert budget.short_memory == 8000
        assert budget.current_input == 2000
        assert budget.reserved == 14000

    def test_token_budget_custom_total(self) -> None:
        """Test TokenBudget with custom total budget."""
        from app.utils.token import TokenBudget

        budget = TokenBudget(total_budget=128000)
        assert budget.total_budget == 128000

    def test_get_available_for_history(self) -> None:
        """Test get_available_for_history returns correct value."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # Available = total - (system + tools + few_shot + long_memory + current_input + reserved)
        # Available = 32000 - (2000 + 3000 + 2000 + 1000 + 2000 + 14000)
        # Available = 32000 - 24000 = 8000
        available = budget.get_available_for_history()
        assert available == 8000

    def test_should_truncate_history_false(self) -> None:
        """Test should_truncate_history returns False when within budget."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 5000 tokens < 8000 available, should not truncate
        assert budget.should_truncate_history(5000) is False

    def test_should_truncate_history_true(self) -> None:
        """Test should_truncate_history returns True when over budget."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 10000 tokens > 8000 available, should truncate
        assert budget.should_truncate_history(10000) is True

    def test_should_truncate_history_exact_boundary(self) -> None:
        """Test should_truncate_history at exact boundary."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # Exactly 8000 tokens, should not truncate
        assert budget.should_truncate_history(8000) is False


class TestTokenBudgetAdvanced:
    """Test advanced TokenBudget functionality."""

    def test_calculate_overflow_amount(self) -> None:
        """Test calculating overflow amount when over budget."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 10000 tokens - 8000 available = 2000 overflow
        overflow = budget.calculate_overflow(10000)
        assert overflow == 2000

    def test_calculate_overflow_no_overflow(self) -> None:
        """Test calculate_overflow when within budget."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 5000 tokens < 8000 available, no overflow
        overflow = budget.calculate_overflow(5000)
        assert overflow == 0

    def test_truncate_history_by_percentage(self) -> None:
        """Test truncating history by percentage."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 10000 tokens, need to remove 2000 (20%)
        new_count = budget.truncate_to_fit(10000)
        # Should truncate to 8000 (available budget)
        assert new_count == 8000

    def test_truncate_history_no_truncate_needed(self) -> None:
        """Test truncate_to_fit when no truncation needed."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        # 5000 tokens < 8000 available, no change
        new_count = budget.truncate_to_fit(5000)
        assert new_count == 5000

    def test_get_allocation_summary(self) -> None:
        """Test getting allocation summary."""
        from app.utils.token import TokenBudget

        budget = TokenBudget()
        summary = budget.get_allocation_summary()

        assert isinstance(summary, dict)
        assert "system_prompt" in summary
        assert "tools_schema" in summary
        assert "few_shot" in summary
        assert "long_memory" in summary
        assert "short_memory" in summary
        assert "current_input" in summary
        assert "reserved" in summary
        assert "available_for_history" in summary
        assert summary["available_for_history"] == 8000

    def test_custom_budget_allocation(self) -> None:
        """Test TokenBudget with custom allocations."""
        from app.utils.token import TokenBudget

        budget = TokenBudget(total_budget=128000)
        budget.system_prompt = 4000
        budget.tools_schema = 6000

        available = budget.get_available_for_history()
        # 128000 - (4000 + 6000 + 2000 + 1000 + 2000 + 14000) = 99000
        assert available == 99000
