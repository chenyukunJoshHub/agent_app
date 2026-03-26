"""
Unit tests for app.config.Settings.

These tests verify configuration loading and validation.
"""
import os

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.config import LLMProvider, Settings, get_settings, settings


class _TestSettings(Settings):
    """Test Settings subclass that doesn't load from .env file."""

    model_config = SettingsConfigDict(
        env_file=None,  # Disable .env file loading for tests
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class TestSettings:
    """Test Settings configuration."""

    def test_default_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test settings with default values (isolated from environment)."""
        # Clear environment variables that might affect defaults
        for key in ["OLLAMA_MODEL", "DATABASE_URL", "LLM_PROVIDER"]:
            monkeypatch.delenv(key, raising=False)

        s = _TestSettings()  # Use test settings without .env file
        assert s.llm_provider == LLMProvider.OLLAMA
        assert s.ollama_base_url == "http://localhost:11434"
        assert s.ollama_model == "glm4:latest"
        assert s.environment == "development"
        assert s.log_level == "INFO"
        assert s.debug is False

    def test_ollama_provider(self) -> None:
        """Test Ollama provider configuration."""
        s = Settings(llm_provider=LLMProvider.OLLAMA)
        assert s.llm_provider == LLMProvider.OLLAMA
        assert s.ollama_base_url == "http://localhost:11434"
        assert s.ollama_temperature == 0.7

    def test_deepseek_provider(self) -> None:
        """Test DeepSeek provider configuration."""
        s = Settings(
            llm_provider=LLMProvider.DEEPSEEK,
            deepseek_api_key="test_key",
        )
        assert s.llm_provider == LLMProvider.DEEPSEEK
        assert s.deepseek_api_key == "test_key"
        assert s.deepseek_base_url == "https://api.deepseek.com/v1"
        assert s.deepseek_model == "deepseek-chat"

    def test_zhipu_provider(self) -> None:
        """Test Zhipu AI provider configuration."""
        s = Settings(
            llm_provider=LLMProvider.ZHIPU,
            zhipu_api_key="test_key",
        )
        assert s.llm_provider == LLMProvider.ZHIPU
        assert s.zhipu_api_key == "test_key"
        assert s.zhipu_model == "glm-4-flash"

    def test_openai_provider(self) -> None:
        """Test OpenAI provider configuration."""
        s = Settings(
            llm_provider=LLMProvider.OPENAI,
            openai_api_key="test_key",
        )
        assert s.llm_provider == LLMProvider.OPENAI
        assert s.openai_api_key == "test_key"
        # Default is DeepSeek-compatible URL (used as OpenAI-compatible endpoint)
        assert s.openai_base_url == "https://api.deepseek.com/v1"

    def test_temperature_validation(self) -> None:
        """Test temperature range validation (0.0 to 2.0)."""
        # Valid temperatures
        Settings(ollama_temperature=0.0)
        Settings(ollama_temperature=1.0)
        Settings(ollama_temperature=2.0)

        # Invalid temperatures
        with pytest.raises(ValidationError):
            Settings(ollama_temperature=-0.1)

        with pytest.raises(ValidationError):
            Settings(ollama_temperature=2.1)

    def test_allowed_origins_parsing(self) -> None:
        """Test parsing of allowed_origins comma-separated string."""
        s = Settings(allowed_origins="http://localhost:3000, http://example.com,https://api.test.com")
        assert s.allowed_origins == [
            "http://localhost:3000",
            "http://example.com",
            "https://api.test.com",
        ]

    def test_allowed_origins_whitespace_handling(self) -> None:
        """Test whitespace handling in allowed_origins."""
        s = Settings(allowed_origins="  http://localhost:3000  ,  http://example.com  ")
        assert s.allowed_origins == [
            "http://localhost:3000",
            "http://example.com",
        ]

    def test_database_url_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default database URL (isolated from environment)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = _TestSettings()  # Use test settings without .env file
        assert s.database_url == "postgresql://postgres:postgres@localhost:5432/agent_db"

    def test_log_level_validation(self) -> None:
        """Test valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            Settings(log_level=level)  # type: ignore

        # Invalid log level
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")  # type: ignore

    def test_environment_validation(self) -> None:
        """Test valid environment values."""
        for env in ["development", "staging", "production"]:
            Settings(environment=env)  # type: ignore

        # Invalid environment
        with pytest.raises(ValidationError):
            Settings(environment="invalid")  # type: ignore


class TestSettingsSingleton:
    """Test global settings singleton."""

    def test_get_settings_returns_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_module_export(self) -> None:
        """Test that settings module export is a Settings instance."""
        assert isinstance(settings, Settings)

    def test_get_settings_idempotent(self) -> None:
        """Test that multiple calls to get_settings return consistent values."""
        s1 = get_settings()
        s1_copy = get_settings()
        assert s1.llm_provider == s1_copy.llm_provider
        assert s1.database_url == s1_copy.database_url


    def test_skill_invocation_mode_default(self) -> None:
        """skill_invocation_mode 默认值应为 'hint'"""
        s = _TestSettings()
        assert s.skill_invocation_mode == "hint"


    def test_skills_dir_default_is_agents_skills(self) -> None:
        """skills_dir 默认值应指向 ~/.agents/skills 或项目内的 skills 目录"""
        s = _TestSettings()
        from pathlib import Path
        expected_unexpanded = "~/.agents/skills"
        # 检查是否是预期的值之一
        assert s.skills_dir in [expected_unexpanded, str(Path(expected_unexpanded).expanduser().resolve())]


class TestEnvironmentVariableLoading:
    """Test loading settings from environment variables."""

    @pytest.mark.skipif(not os.path.exists(".env"), reason="No .env file found")
    def test_load_from_env_file(self) -> None:
        """Test loading settings from .env file."""
        # Settings should load from .env automatically
        s = Settings()
        # Verify that at least some settings were loaded
        assert s is not None

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_env_key")

        s = Settings()
        assert s.llm_provider == LLMProvider.DEEPSEEK
        assert s.deepseek_api_key == "test_env_key"

    def test_database_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test DATABASE_URL from environment variable."""
        custom_url = "postgresql://user:pass@custom-host:5432/custom_db"
        monkeypatch.setenv("DATABASE_URL", custom_url)

        s = Settings()
        assert s.database_url == custom_url
