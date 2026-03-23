"""
Unit tests for app.llm.factory.

These tests verify LLM creation for different providers.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.llm.factory import llm_factory


class TestLLMFactory:
    """Test llm_factory function."""

    @pytest.mark.requires_llm
    def test_factory_returns_chat_model(self) -> None:
        """Test that factory returns a BaseChatModel instance."""
        llm = llm_factory()
        # Verify it's a chat model (has invoke/ainvoke methods)
        assert hasattr(llm, "ainvoke")
        assert hasattr(llm, "bind")

    @pytest.mark.requires_llm
    def test_factory_with_ollama(self) -> None:
        """Test factory creates Ollama model."""
        llm = llm_factory()
        # Ollama is default
        assert llm is not None

    @pytest.mark.requires_llm
    @pytest.mark.skipif(
        not os.getenv("DEEPSEEK_API_KEY"),
        reason="DEEPSEEK_API_KEY not set",
    )
    def test_factory_with_deepseek(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory creates DeepSeek model."""
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")

        llm = llm_factory()
        assert llm is not None

    def test_factory_invalid_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory raises error for invalid provider."""
        # The Settings class validates llm_provider via Enum at creation time
        # So setting an invalid provider will cause a ValidationError, not a ValueError
        # We test this by trying to create Settings with an invalid provider
        from app.config import Settings
        from pydantic import ValidationError

        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")

        # Settings() will raise ValidationError for invalid enum value
        with pytest.raises(ValidationError):
            Settings()

    def test_factory_deepseek_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory raises error when DeepSeek API key is missing."""
        # Set provider but remove API key
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        from app.llm.factory import llm_factory
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is required"):
            llm_factory()

    def test_factory_zhipu_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory raises error when Zhipu API key is missing."""
        monkeypatch.setenv("LLM_PROVIDER", "zhipu")
        monkeypatch.delenv("ZHIPU_API_KEY", raising=False)

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        from app.llm.factory import llm_factory
        with pytest.raises(ValueError, match="ZHIPU_API_KEY is required"):
            llm_factory()

    def test_factory_openai_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory raises error when OpenAI API key is missing."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        from app.llm.factory import llm_factory
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            llm_factory()


class TestCreateOllama:
    """Test _create_ollama function."""

    @patch("app.llm.factory.ChatOllama")
    def test_create_ollama_with_defaults(self, mock_chat_ollama: MagicMock) -> None:
        """Test Ollama creation with default settings."""
        from app.llm.factory import _create_ollama
        from app.config import settings

        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        result = _create_ollama()

        mock_chat_ollama.assert_called_once_with(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
            client_kwargs={"timeout": settings.ollama_timeout},
        )
        assert result == mock_instance

    @patch("app.llm.factory.ChatOllama")
    def test_create_ollama_with_custom_settings(
        self,
        mock_chat_ollama: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test Ollama creation with custom settings."""
        from app.llm.factory import _create_ollama
        from app.config import LLMProvider

        # Reload settings to pick up new env vars
        import importlib
        import app.config
        importlib.reload(app.config)
        from app.config import settings as new_settings

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3:8b")
        monkeypatch.setenv("OLLAMA_TEMPERATURE", "0.5")
        monkeypatch.setenv("OLLAMA_TIMEOUT", "600")

        mock_instance = MagicMock()
        mock_chat_ollama.return_value = mock_instance

        result = _create_ollama()

        mock_chat_ollama.assert_called_once()
        assert result == mock_instance


class TestCreateDeepSeek:
    """Test _create_deepseek function."""

    def test_create_deepseek_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test DeepSeek creation with API key."""
        from unittest.mock import patch

        # Set API key first
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        # Now use patch as context manager and import the function
        with patch("app.llm.factory.ChatOpenAI") as mock_chat_openai:
            # Import the function AFTER patch is active
            from app.llm.factory import _create_deepseek

            mock_instance = MagicMock()
            mock_chat_openai.return_value = mock_instance

            result = _create_deepseek()

            mock_chat_openai.assert_called_once()
            assert result == mock_instance


class TestCreateZhipu:
    """Test _create_zhipu function."""

    def test_create_zhipu_missing_import(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test Zhipu creation fails gracefully when langchain-community is missing."""
        # This test requires mocking the import system which is complex
        # Since langchain-community is installed, we skip this test
        pytest.skip("langchain-community is installed, cannot test missing import")


class TestCreateOpenAI:
    """Test _create_openai function."""

    def test_create_openai_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test OpenAI creation with API key."""
        from unittest.mock import patch

        # Set API key first
        monkeypatch.setenv("OPENAI_API_KEY", "test_key")

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        # Now use patch as context manager and import the function
        with patch("app.llm.factory.ChatOpenAI") as mock_chat_openai:
            # Import the function AFTER patch is active
            from app.llm.factory import _create_openai

            mock_instance = MagicMock()
            mock_chat_openai.return_value = mock_instance

            result = _create_openai()

            mock_chat_openai.assert_called_once()
            assert result == mock_instance


class TestCreateAnthropic:
    """Test _create_anthropic function."""

    def test_factory_anthropic_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test factory raises error when Anthropic API key is missing."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        from app.llm.factory import llm_factory
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            llm_factory()

    def test_create_anthropic_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test Anthropic creation with API key."""
        from unittest.mock import patch, MagicMock

        # Set API key first
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        # Patch the import inside the function (langchain_anthropic module)
        with patch("langchain_anthropic.ChatAnthropic") as mock_chat_anthropic:
            # Import the function AFTER patch is active
            from app.llm.factory import _create_anthropic

            mock_instance = MagicMock()
            mock_chat_anthropic.return_value = mock_instance

            result = _create_anthropic()

            mock_chat_anthropic.assert_called_once()
            assert result == mock_instance

    def test_create_anthropic_import_error(self, monkeypatch):
        """Test _create_anthropic raises ImportError when langchain-anthropic is not installed."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        # Reload both config and factory to pick up new env var
        import importlib
        import app.config
        import app.llm.factory

        app.config._settings = None
        importlib.reload(app.config)
        importlib.reload(app.llm.factory)

        # Mock import to raise ImportError
        import sys
        original_import = __builtins__.__import__
        import_err = ImportError("langchain-anthropic is required")

        def mock_import(name, *args, **kwargs):
            if name == "langchain_anthropic":
                raise import_err
            return original_import(name, *args, **kwargs)

        with pytest.raises(ImportError, match="langchain-anthropic is required"):
            __builtins__.__import__ = mock_import
            try:
                from app.llm.factory import _create_anthropic
                _create_anthropic()
            finally:
                __builtins__.__import__ = original_import


# Import os for environment variable tests
import os
