"""
Unit tests for app.tools.token.

These tests verify the token_counter tool functionality.
"""
import json



class TestTokenCounterTool:
    """Test token_counter tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.token import token_counter

        assert token_counter.name == "token_counter"
        assert token_counter.description is not None
        assert "token" in token_counter.description.lower()
        # Should include usage guidance
        assert "适用" in token_counter.description or "计算" in token_counter.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.token import token_counter

        schema = token_counter.args_schema
        assert schema is not None
        # Should have 'text' and 'model' arguments
        assert "text" in schema.model_fields
        assert "model" in schema.model_fields

    def test_token_counter_with_gpt4(self) -> None:
        """Test token_counter with GPT-4 model."""
        from app.tools.token import token_counter

        test_text = "Hello, world!"
        result = token_counter.invoke({"text": test_text, "model": "gpt-4"})

        # Should return JSON string
        assert isinstance(result, str)
        data = json.loads(result)
        assert "count" in data
        assert "model" in data
        assert data["model"] == "gpt-4"
        assert data["count"] > 0

    def test_token_counter_with_claude(self) -> None:
        """Test token_counter with Claude model."""
        from app.tools.token import token_counter

        test_text = "Hello, world!"
        result = token_counter.invoke({"text": test_text, "model": "claude-3-sonnet"})

        # Should return JSON string
        assert isinstance(result, str)
        data = json.loads(result)
        assert "count" in data
        assert "model" in data
        assert data["model"] == "claude-3-sonnet"
        assert data["count"] > 0

    def test_token_counter_default_model(self) -> None:
        """Test token_counter uses default model when not specified."""
        from app.tools.token import token_counter

        test_text = "Hello, world!"
        result = token_counter.invoke({"text": test_text})

        # Should use default model (gpt-4)
        data = json.loads(result)
        assert "model" in data
        assert data["count"] > 0

    def test_token_counter_empty_text(self) -> None:
        """Test token_counter with empty text."""
        from app.tools.token import token_counter

        result = token_counter.invoke({"text": "", "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] == 0

    def test_token_counter_long_text(self) -> None:
        """Test token_counter with long text."""
        from app.tools.token import token_counter

        # Create a long text (1000 words)
        long_text = " ".join(["word"] * 1000)
        result = token_counter.invoke({"text": long_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0
        # Should have more tokens than words for English
        assert data["count"] >= 1000

    def test_token_counter_chinese_text(self) -> None:
        """Test token_counter with Chinese text."""
        from app.tools.token import token_counter

        chinese_text = "你好世界，这是一个测试文本。"
        result = token_counter.invoke({"text": chinese_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0
        # Chinese characters typically use more tokens
        assert data["count"] > 0

    def test_token_counter_multilingual_text(self) -> None:
        """Test token_counter with multilingual text."""
        from app.tools.token import token_counter

        multilingual_text = """
        English: Hello World
        Chinese: 你好世界
        Japanese: こんにちは
        Korean: 안녕하세요
        Emoji: 🎉🚀🔥
        """
        result = token_counter.invoke({"text": multilingual_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0

    def test_token_counter_code_text(self) -> None:
        """Test token_counter with code text."""
        from app.tools.token import token_counter

        code_text = """
        def hello_world():
            print("Hello, World!")
            return True
        """
        result = token_counter.invoke({"text": code_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0

    def test_token_counter_special_characters(self) -> None:
        """Test token_counter with special characters."""
        from app.tools.token import token_counter

        special_text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = token_counter.invoke({"text": special_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0

    def test_token_counter_returns_json_string(self) -> None:
        """Test that token_counter returns valid JSON string."""
        from app.tools.token import token_counter

        test_text = "Test"
        result = token_counter.invoke({"text": test_text, "model": "gpt-4"})

        # Should be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_token_counter_different_models(self) -> None:
        """Test token_counter with different models."""
        from app.tools.token import token_counter

        test_text = "Hello, world!"

        models = ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "claude-3-opus"]

        for model in models:
            result = token_counter.invoke({"text": test_text, "model": model})
            data = json.loads(result)
            assert data["model"] == model
            assert data["count"] > 0

    def test_token_counter_newlines_and_whitespace(self) -> None:
        """Test token_counter handles newlines and whitespace."""
        from app.tools.token import token_counter

        text_with_whitespace = """
        Line 1

        Line 3    (with tabs and    spaces)
        """
        result = token_counter.invoke({"text": text_with_whitespace, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0

    def test_token_counter_json_content(self) -> None:
        """Test token_counter with JSON content."""
        from app.tools.token import token_counter

        json_content = '{"key": "value", "number": 42, "nested": {"a": 1}}'
        result = token_counter.invoke({"text": json_content, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0


class TestTokenCounterToolEdgeCases:
    """Test token_counter tool edge cases."""

    def test_token_counter_description_clarity(self) -> None:
        """Test that tool description is clear and helpful."""
        from app.tools.token import token_counter

        desc = token_counter.description.lower()
        # Should mention what it's for
        assert any(keyword in desc for keyword in ["token", "计数", "计算"])

    def test_token_counter_model_validation(self) -> None:
        """Test token_counter validates model parameter."""
        from app.tools.token import token_counter

        # Invalid model should still work (fallback to default)
        test_text = "Hello"
        result = token_counter.invoke({"text": test_text, "model": "invalid-model"})

        # Should return result with default encoding
        data = json.loads(result)
        assert "count" in data

    def test_token_counter_unicode_emoji(self) -> None:
        """Test token_counter with Unicode emoji."""
        from app.tools.token import token_counter

        emoji_text = "🎉🚀🔥💻📱🌟⭐💡🎯📊🔬"
        result = token_counter.invoke({"text": emoji_text, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0

    def test_token_counter_very_long_single_word(self) -> None:
        """Test token_counter with very long single word."""
        from app.tools.token import token_counter

        long_word = "a" * 1000
        result = token_counter.invoke({"text": long_word, "model": "gpt-4"})

        data = json.loads(result)
        assert data["count"] > 0
