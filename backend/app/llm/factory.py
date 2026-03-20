"""
LLM Factory - Multi-provider support with fallback mechanism
"""

from typing import Literal

from anthropic import AsyncAnthropic
from langchain.anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logger import loguru_logger


class LLMFactory:
    """Factory for creating LLM instances with fallback support"""

    def __init__(self) -> None:
        self._providers: dict[str, type[BaseChatModel]] = {
            "anthropic": ChatAnthropic,
            "ollama": ChatOllama,
            "openai": ChatOpenAI,
        }
        self._native_clients: dict[str, object] = {}

    def create_langchain_llm(
        self,
        provider: Literal["anthropic", "ollama", "openai"] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> BaseChatModel:
        """Create a LangChain chat model instance"""

        provider = provider or settings.llm_provider
        model = model or settings.default_model
        temperature = temperature or settings.temperature

        loguru_logger.info(f"Creating LLM: provider={provider}, model={model}")

        if provider == "anthropic":
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                anthropic_api_key=settings.anthropic_api_key or None,
                max_tokens=settings.max_tokens,
                **kwargs,
            )

        elif provider == "ollama":
            return ChatOllama(
                model=model or settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=temperature,
                **kwargs,
            )

        elif provider == "openai":
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                openai_api_key=settings.openai_api_key or None,
                max_tokens=settings.max_tokens,
                **kwargs,
            )

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def create_native_client(self, provider: Literal["anthropic", "openai"] | None = None):
        """Create native API client for direct API calls"""

        provider = provider or settings.llm_provider

        if provider == "anthropic":
            if "anthropic" not in self._native_clients:
                self._native_clients["anthropic"] = AsyncAnthropic(
                    api_key=settings.anthropic_api_key or None
                )
            return self._native_clients["anthropic"]

        elif provider == "openai":
            if "openai" not in self._native_clients:
                self._native_clients["openai"] = AsyncOpenAI(
                    api_key=settings.openai_api_key or None
                )
            return self._native_clients["openai"]

        else:
            raise ValueError(f"Native client not available for provider: {provider}")

    async def test_connection(self, provider: str | None = None) -> bool:
        """Test if the LLM provider is accessible"""

        provider = provider or settings.llm_provider

        try:
            if provider == "anthropic":
                client = self.create_native_client("anthropic")
                await client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}],
                )
                return True

            elif provider == "ollama":
                import httpx

                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{settings.ollama_base_url}/api/tags")
                    return response.status_code == 200

            elif provider == "openai":
                client = self.create_native_client("openai")
                await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10,
                )
                return True

        except Exception as e:
            loguru_logger.error(f"LLM connection test failed for {provider}: {e}")
            return False

        return False


# Global factory instance
llm_factory = LLMFactory()
