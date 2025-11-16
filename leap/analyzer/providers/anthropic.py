"""Anthropic Claude provider implementation."""

import logging
import os
from typing import Any

from .base import (
    LLMProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Provider implementation for Anthropic Claude models.

    This provider supports all Claude models via the Anthropic API.
    Requires ANTHROPIC_API_KEY environment variable or api_key parameter.

    Recommended models:
    - claude-3-5-sonnet-20241022 (best for code analysis)
    - claude-3-opus-20240229 (highest quality)
    - claude-3-haiku-20240307 (fastest, cheapest)
    """

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (or use ANTHROPIC_API_KEY env var)
            timeout: Request timeout in seconds

        Raises:
            ValueError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise ImportError(
                    "anthropic package required for Anthropic provider. "
                    "Install with: pip install anthropic"
                ) from exc

            self._client = AsyncAnthropic(
                api_key=self.api_key,
                timeout=self.timeout
            )

        return self._client

    async def complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> str:
        """Generate completion using Anthropic API.

        Args:
            prompt: The prompt text
            model: Model identifier (e.g., "claude-3-5-sonnet-20241022")
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 = deterministic)
            **kwargs: Additional parameters (system, stop_sequences, etc.)

        Returns:
            Text response from Claude

        Raises:
            ProviderAuthError: If API key is invalid
            ProviderTimeoutError: If request times out
            ProviderRateLimitError: If rate limit is hit
            ProviderError: For other API errors
        """
        client = self._get_client()

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                **kwargs
            )

            # Extract text from response
            if response.content and len(response.content) > 0:
                return str(response.content[0].text)
            else:
                raise ProviderError("Empty response from Anthropic API")

        except Exception as e:
            # Map Anthropic exceptions to our custom exceptions
            error_msg = str(e).lower()

            if "authentication" in error_msg or "api key" in error_msg:
                raise ProviderAuthError(f"Authentication failed: {e}") from e
            elif "timeout" in error_msg:
                raise ProviderTimeoutError(f"Request timed out: {e}") from e
            elif "rate limit" in error_msg or "429" in error_msg:
                raise ProviderRateLimitError(f"Rate limit exceeded: {e}") from e
            else:
                raise ProviderError(f"Anthropic API error: {e}") from e

    async def health_check(self) -> bool:
        """Verify Anthropic API is accessible and credentials are valid.

        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Make a minimal test request
            response = await self.complete(
                prompt="Test",
                model="claude-3-haiku-20240307",  # Use cheapest model for health check
                max_tokens=10,
                temperature=0.0
            )
            return bool(response)

        except ProviderAuthError:
            logger.error("Anthropic health check failed: Invalid API key")
            return False
        except Exception as e:
            logger.error(f"Anthropic health check failed: {e}")
            return False
