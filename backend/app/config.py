"""
Application Configuration using Pydantic Settings.

Environment variables are loaded from .env file.
"""
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    """Supported LLM providers."""
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_db",
        description="PostgreSQL connection URL (uses psycopg3)",
    )

    # LLM Provider Selection
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OLLAMA,
        description="Primary LLM provider to use",
    )

    # Ollama Configuration
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama service URL",
    )
    ollama_model: str = Field(
        default="glm4:latest",
        description="Ollama model name",
    )
    ollama_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Ollama sampling temperature",
    )
    ollama_timeout: int = Field(
        default=300,
        ge=1,
        description="Ollama request timeout in seconds (default: 5 minutes)",
    )

    # DeepSeek Configuration
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API key",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL",
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek model name",
    )
    deepseek_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="DeepSeek sampling temperature",
    )
    deepseek_timeout: int = Field(
        default=120,
        ge=1,
        description="DeepSeek request timeout in seconds (default: 2 minutes)",
    )

    # Zhipu AI Configuration
    zhipu_api_key: str = Field(
        default="",
        description="Zhipu AI API key",
    )
    zhipu_model: str = Field(
        default="glm-4-flash",
        description="Zhipu AI model name",
    )
    zhipu_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Zhipu AI sampling temperature",
    )

    # OpenAI Configuration (also used for DeepSeek compatibility)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (or DeepSeek key for compatibility)",
    )
    openai_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="OpenAI API base URL",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name",
    )
    openai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="OpenAI sampling temperature",
    )
    openai_timeout: int = Field(
        default=120,
        ge=1,
        description="OpenAI request timeout in seconds (default: 2 minutes)",
    )

    # Anthropic Configuration
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key",
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model name",
    )
    anthropic_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Anthropic sampling temperature",
    )
    anthropic_timeout: int = Field(
        default=120,
        ge=1,
        description="Anthropic request timeout in seconds (default: 2 minutes)",
    )
    anthropic_max_tokens: int = Field(
        default=8192,
        ge=1,
        description="Anthropic max tokens to generate",
    )

    # Tools API
    tavily_api_key: str = Field(
        default="",
        description="Tavily search API key",
    )

    # Skills Directory
    skills_dir: str = Field(
        default="~/.agents/skills",
        description="Skills 目录路径（支持 ~ 展开）。原默认值为 ../skills，升级时请确认 .env 配置。",
    )

    # Skill Invocation Mode
    skill_invocation_mode: Literal["hint", "force"] = Field(
        default="hint",
        description="skill 调用模式：hint（软提示引导 LLM）| force（强制注入，待开发）",
    )

    # Workspace / project root — relative paths in read_file resolve against this
    workspace_dir: str = Field(
        default="",
        description="Project root directory for resolving relative file paths. Defaults to parent of backend/.",
    )

    # Application
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    debug: bool = Field(
        default=False,
        description="Debug mode",
    )

    # Server timeout settings
    http_timeout: int = Field(
        default=300,
        ge=1,
        description="HTTP request timeout in seconds (default: 5 minutes)",
    )
    keep_alive_timeout: int = Field(
        default=5,
        ge=1,
        description="Keep-alive timeout in seconds",
    )

    # CORS
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins",
    )

    # Token Budget Configuration
    token_model_context_window: int = Field(
        default=200_000,
        description="Model context window size (tokens)",
    )
    token_working_budget: int = Field(
        default=32_768,
        description="Agent working budget (tokens)",
    )
    token_max_output: int = Field(
        default=8_192,
        description="Standard output max tokens",
    )
    token_slot_output: int = Field(
        default=8_192,
        description="Output reserve slot (tokens)",
    )
    token_slot_system: int = Field(
        default=2_000,
        description="System Prompt + Few-shot slot (tokens)",
    )
    token_slot_active_skill: int = Field(
        default=0,
        description="Active Skill slot (tokens)",
    )
    token_slot_few_shot: int = Field(
        default=0,
        description="Few-shot slot (tokens)",
    )
    token_slot_rag: int = Field(
        default=0,
        description="RAG background knowledge slot (tokens)",
    )
    token_slot_episodic: int = Field(
        default=500,
        description="Episodic memory slot (tokens)",
    )
    token_slot_procedural: int = Field(
        default=0,
        description="Procedural memory slot (tokens)",
    )
    token_slot_tools: int = Field(
        default=1_200,
        description="Tools schema slot (tokens)",
    )
    token_autocompact_buffer_ratio: float = Field(
        default=0.165,
        ge=0.0,
        le=1.0,
        description="Reserved buffer ratio before auto-compaction",
    )

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience export
settings = get_settings()
