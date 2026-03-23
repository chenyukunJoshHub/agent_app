"""
LLM Factory for creating LangChain ChatModel instances.

Supports multiple providers:
- Ollama (local)
- DeepSeek (via OpenAI-compatible API)
- Zhipu AI (via langchain-community)
- OpenAI
- Anthropic

P0: Single provider only, no fallback mechanism.
"""
from langchain.chat_models.base import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr

from app.config import LLMProvider, settings


def llm_factory() -> BaseChatModel:
    """
    Create a ChatModel instance based on configured provider.

    P0: Returns single provider, no fallback.

    Returns:
        BaseChatModel: Configured LangChain ChatModel

    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    provider = settings.llm_provider
    logger.info(f"Creating LLM with provider: {provider}")

    match provider:
        case LLMProvider.OLLAMA:
            return _create_ollama()

        case LLMProvider.DEEPSEEK:
            return _create_deepseek()

        case LLMProvider.ZHIPU:
            return _create_zhipu()

        case LLMProvider.OPENAI:
            return _create_openai()

        case LLMProvider.ANTHROPIC:
            return _create_anthropic()

        case _:
            raise ValueError(f"Unsupported LLM provider: {provider}")


def _create_ollama() -> ChatOllama:
    """Create Ollama ChatModel."""
    logger.info(f"Initializing Ollama: {settings.ollama_base_url} / {settings.ollama_model} (timeout: {settings.ollama_timeout}s)")

    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=settings.ollama_temperature,
        client_kwargs={"timeout": settings.ollama_timeout},
        # Add profile for summarization middleware (context window size)
        # Typical values: glm4=128k, qwen3.5=32k
        profile={"max_input_tokens": 128000},
    )


def _create_deepseek() -> ChatOpenAI:
    """Create DeepSeek ChatModel (uses OpenAI-compatible API)."""
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek provider")

    logger.info(f"Initializing DeepSeek: {settings.deepseek_model} (timeout: {settings.deepseek_timeout}s)")

    return ChatOpenAI(
        api_key=SecretStr(settings.deepseek_api_key),
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        temperature=settings.deepseek_temperature,
        request_timeout=settings.deepseek_timeout,
    )


def _create_zhipu() -> BaseChatModel:
    """Create Zhipu AI ChatModel."""
    if not settings.zhipu_api_key:
        raise ValueError("ZHIPU_API_KEY is required for Zhipu provider")

    logger.info(f"Initializing Zhipu AI: {settings.zhipu_model}")

    # Import here to avoid hard dependency
    try:
        from langchain_community.chat_models import ChatZhipuAI
    except ImportError as e:
        raise ImportError(
            "langchain-community is required for Zhipu AI. "
            "Install it with: pip install langchain-community"
        ) from e

    return ChatZhipuAI(
        api_key=settings.zhipu_api_key,
        model=settings.zhipu_model,
        temperature=settings.zhipu_temperature,
    )


def _create_openai() -> ChatOpenAI:
    """Create OpenAI ChatModel."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI provider")

    logger.info(f"Initializing OpenAI: {settings.openai_model} (timeout: {settings.openai_timeout}s)")

    return ChatOpenAI(
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        request_timeout=settings.openai_timeout,
    )


def _create_anthropic() -> BaseChatModel:
    """Create Anthropic ChatModel."""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")

    logger.info(f"Initializing Anthropic: {settings.anthropic_model} (timeout: {settings.anthropic_timeout}s)")

    # Import here to avoid hard dependency
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as e:
        raise ImportError(
            "langchain-anthropic is required for Anthropic provider. "
            "Install it with: pip install langchain-anthropic"
        ) from e

    return ChatAnthropic(
        api_key=SecretStr(settings.anthropic_api_key),
        model=settings.anthropic_model,
        temperature=settings.anthropic_temperature,
        timeout=settings.anthropic_timeout,
        max_tokens=settings.anthropic_max_tokens,
    )


# Convenience export
__all__ = ["llm_factory", "BaseChatModel"]
