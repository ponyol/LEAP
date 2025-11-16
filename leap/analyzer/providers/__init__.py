"""LLM provider factory and public API."""

# Import config for type hints
from typing import TYPE_CHECKING

from .anthropic import AnthropicProvider
from .base import (
    LLMProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .bedrock import BedrockProvider
from .lmstudio import LMStudioProvider
from .ollama import OllamaProvider

if TYPE_CHECKING:
    from ..config import AnalyzerConfig


def get_provider(config: "AnalyzerConfig") -> LLMProvider:
    """Factory function to create LLM provider based on configuration.

    Args:
        config: Analyzer configuration with provider settings

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not recognized or configuration is invalid
    """
    provider_name = config.provider.lower()

    if provider_name == "anthropic":
        return AnthropicProvider(
            api_key=config.api_key,
            timeout=config.timeout
        )

    elif provider_name == "bedrock":
        return BedrockProvider(
            region=config.aws_region or "us-east-1",
            profile=config.aws_profile,
            timeout=config.timeout
        )

    elif provider_name == "ollama":
        return OllamaProvider(
            api_base=config.api_base or "http://localhost:11434",
            timeout=config.timeout
        )

    elif provider_name == "lmstudio":
        return LMStudioProvider(
            api_base=config.api_base or "http://localhost:1234",
            timeout=config.timeout
        )

    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Supported providers: anthropic, bedrock, ollama, lmstudio"
        )


__all__ = [
    # Base classes
    "LLMProvider",
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderAuthError",
    "ProviderRateLimitError",

    # Provider implementations
    "AnthropicProvider",
    "BedrockProvider",
    "OllamaProvider",
    "LMStudioProvider",

    # Factory
    "get_provider",
]
