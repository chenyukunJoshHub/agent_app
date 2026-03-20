"""
Application configuration using Pydantic Settings
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Multi-Tool AI Agent"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # LLM Configuration
    llm_provider: Literal["anthropic", "ollama", "openai"] = "anthropic"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 8192

    # Token Budget
    max_context_tokens: int = 200000  # Claude 3.5 Sonnet max
    working_budget: int = 32000
    short_memory_slot: int = 4000
    long_memory_slot: int = 6000
    tool_output_slot: int = 8000

    # Memory
    short_memory_ttl: int = 86400  # 24 hours
    long_memory_namespace: str = "user_profiles"

    # Skills
    project_skills_dir: Path = Field(default_factory=lambda: Path("skills"))
    global_skills_dir: Path = Field(default_factory=lambda: Path.home() / ".agents" / "skills")
    skill_hot_reload: bool = True

    # Tools
    tavily_api_key: str = ""
    read_file_allowed_dirs: list[str] = Field(default_factory=list)
    tool_timeout: int = 30

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    enable_rls: bool = True

    # Observability
    enable_sse: bool = True
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
