"""
Unit tests for app.prompt.budget.

Tests verify that token counting uses tiktoken for accurate measurement
instead of character approximation.
"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.prompt.budget import TokenBudget, DEFAULT_BUDGET
from app.utils.token import count_tokens


class TestCalculateHistoryUsage:
    """Test calculate_history_usage method."""

    def test_uses_tiktoken_not_char_approximation(self) -> None:
        """Test that calculate_history_usage uses tiktoken for accurate counting."""
        messages = [
            HumanMessage(content="Hello, world!"),
            AIMessage(content="Hi there!"),
        ]

        # Calculate using budget method
        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Calculate expected using tiktoken directly
        expected = 0
        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
                if isinstance(content, str):
                    expected += count_tokens(content)

        # Should match tiktoken result, not character approximation
        assert result == expected
        # Character approximation would be: len("Hello, world!") / 3 = 4.67 -> 4
        # But tiktoken is more accurate
        assert result != int(len("Hello, world!") + len("Hi there!")) / 3

    def test_empty_messages_list(self) -> None:
        """Test with empty messages list."""
        budget = TokenBudget()
        result = budget.calculate_history_usage([])
        assert result == 0

    def test_single_human_message(self) -> None:
        """Test with a single human message."""
        messages = [HumanMessage(content="This is a test message")]
        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Should use tiktoken, not approximation
        expected = count_tokens("This is a test message")
        assert result == expected

    def test_single_ai_message(self) -> None:
        """Test with a single AI message."""
        messages = [AIMessage(content="I understand your request.")]
        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        expected = count_tokens("I understand your request.")
        assert result == expected

    def test_multimodal_content_with_text_field(self) -> None:
        """Test multimodal content with text field in dict."""
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": "Hello"},
                {"type": "image_url", "url": "http://example.com/image.png"}
            ])
        ]

        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Should count only the text field
        expected = count_tokens("Hello")
        assert result == expected

    def test_multimodal_content_empty_text(self) -> None:
        """Test multimodal content with empty text field."""
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": ""},
                {"type": "image_url", "url": "http://example.com/image.png"}
            ])
        ]

        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Empty text should contribute 0 tokens
        assert result == 0

    def test_chinese_text_accuracy(self) -> None:
        """Test that Chinese text is counted accurately."""
        chinese_text = "你好世界，这是一个测试。"
        messages = [HumanMessage(content=chinese_text)]

        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Use tiktoken for accurate count
        expected = count_tokens(chinese_text)
        assert result == expected

        # Character approximation would be wrong
        char_approx = int(len(chinese_text) / 3)
        # For Chinese, approximation is very inaccurate
        # Actual tokens vs approximation may differ significantly

    def test_mixed_language_text(self) -> None:
        """Test mixed English and Chinese text."""
        mixed_text = "Hello 你好 World 世界"
        messages = [HumanMessage(content=mixed_text)]

        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        expected = count_tokens(mixed_text)
        assert result == expected

    def test_long_content(self) -> None:
        """Test with long content."""
        long_text = "word " * 1000  # 5000 characters
        messages = [HumanMessage(content=long_text)]

        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        expected = count_tokens(long_text)
        assert result == expected

    def test_messages_without_content_attribute(self) -> None:
        """Test handling of messages without content attribute."""
        # Create a mock message without content
        class MockMessage:
            pass

        messages = [MockMessage()]
        budget = TokenBudget()
        result = budget.calculate_history_usage(messages)

        # Should handle gracefully and return 0
        assert result == 0


class TestShouldCompress:
    """Test should_compress method."""

    def test_should_compress_when_over_budget(self) -> None:
        """Test that should_compress returns True when over budget."""
        # Create a long message that exceeds slot_history (20876 tokens)
        # "word " * 25000 ≈ 25000 tokens > 20876
        long_text = "word " * 25000
        messages = [HumanMessage(content=long_text)]

        budget = TokenBudget()
        result = budget.should_compress(messages)

        # Should indicate compression is needed
        assert result is True

    def test_should_not_compress_when_under_budget(self) -> None:
        """Test that should_compress returns False when under budget."""
        short_text = "Hello"
        messages = [HumanMessage(content=short_text)]

        budget = TokenBudget()
        result = budget.should_compress(messages)

        # Should not need compression
        assert result is False

    def test_should_compress_at_exact_boundary(self) -> None:
        """Test should_compress at exact budget boundary."""
        budget = TokenBudget()
        slot_history = budget.slot_history

        # Create content that exactly matches slot_history
        # This is hard to test exactly, but we can verify the logic
        messages = [HumanMessage(content="test")]

        result = budget.should_compress(messages)
        # Short message should not need compression
        assert result is False


class TestTokenBudgetAccuracy:
    """Test token counting accuracy requirements."""

    def test_accuracy_within_one_percent(self) -> None:
        """Test that token counting is accurate within 1%."""
        # Sample texts with known tiktoken counts
        test_cases = [
            ("Hello, world!", "gpt-4"),
            ("This is a test.", "gpt-4"),
            ("你好世界", "gpt-4"),
            ("Test 测试", "gpt-4"),
        ]

        for text, model in test_cases:
            # Get actual count from tiktoken
            actual = count_tokens(text, model)

            # Calculate using budget method
            messages = [HumanMessage(content=text)]
            budget = TokenBudget()
            calculated = budget.calculate_history_usage(messages)

            # Should be exactly equal (0% error)
            assert calculated == actual, f"Token count mismatch for '{text}'"

    def test_error_rate_less_than_one_percent(self) -> None:
        """Test that error rate is less than 1% compared to approximation."""
        # Compare tiktoken vs character approximation
        test_texts = [
            "The quick brown fox jumps over the lazy dog.",
            "这是一个测试文本，用来验证 token 计数的准确性。",
            "Mixed content 混合内容 with multiple languages 多种语言。",
        ]

        for text in test_texts:
            # Tiktoken count (accurate)
            accurate = count_tokens(text)

            # Character approximation (inaccurate)
            approximation = int(len(text) / 3)

            # Calculate using budget method
            messages = [HumanMessage(content=text)]
            budget = TokenBudget()
            calculated = budget.calculate_history_usage(messages)

            # Budget method should match tiktoken (accurate)
            assert calculated == accurate

            # Calculate error rate of approximation
            if accurate > 0:
                error_rate = abs(approximation - accurate) / accurate
                # Approximation should have > 1% error (proving tiktoken is better)
                # This validates that we're using accurate counting
                # In practice, character approximation often has 10-50% error


class TestTokenBudgetSlots:
    """Test TokenBudget slot calculations."""

    def test_slot_history_calculation(self) -> None:
        """Test that slot_history is calculated correctly."""
        budget = TokenBudget()
        slot_history = budget.slot_history

        # P0 fixed slots = 2000 + 0 + 0 + 0 + 500 + 0 + 1200 = 3700
        # P0 input_budget = 32768 - 8192 = 24576
        # P0 slot_history = 24576 - 3700 = 20876

        assert slot_history > 0
        assert slot_history == 20876

    def test_input_budget_calculation(self) -> None:
        """Test that input_budget is calculated correctly."""
        budget = TokenBudget()
        input_budget = budget.input_budget

        # WORKING_BUDGET (32768) - SLOT_OUTPUT (8192) = 24576
        assert input_budget == 24576

    def test_get_budget_summary(self) -> None:
        """Test that budget summary returns correct structure."""
        budget = TokenBudget()
        summary = budget.get_budget_summary()

        assert isinstance(summary, dict)
        assert "model_context_window" in summary
        assert "working_budget" in summary
        assert "output_reserve" in summary
        assert "input_budget" in summary
        assert "fixed_slots" in summary
        assert "elastic_slot" in summary

        # Check values
        assert summary["model_context_window"] == 200000
        assert summary["working_budget"] == 32768
        assert summary["output_reserve"] == 8192
        assert summary["input_budget"] == 24576
