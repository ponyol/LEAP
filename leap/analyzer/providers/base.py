"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Base exception for provider-related errors."""
    pass


class ProviderTimeoutError(ProviderError):
    """Exception raised when provider request times out."""
    pass


class ProviderRateLimitError(ProviderError):
    """Exception raised when provider rate limit is hit."""
    pass


class ProviderAuthError(ProviderError):
    """Exception raised when provider authentication fails."""
    pass


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    This interface defines the contract that all provider implementations
    must follow. It ensures consistent behavior across different LLM backends.

    Implementations must handle:
    - Authentication with the provider
    - Request formatting
    - Response parsing
    - Error handling and retries
    - Health checks
    """

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> str:
        """Generate completion from LLM.

        Args:
            prompt: The prompt text to send to the model
            model: Model identifier (provider-specific)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 = deterministic)
            **kwargs: Additional provider-specific parameters

        Returns:
            Raw text response from the model

        Raises:
            ProviderError: On API errors
            ProviderTimeoutError: On timeout
            ProviderRateLimitError: On rate limit
            ProviderAuthError: On authentication failure
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and configured correctly.

        This method should verify:
        - API credentials are valid
        - Network connectivity to provider
        - Provider service is responsive

        Returns:
            True if provider is healthy, False otherwise
        """
        pass

    async def complete_with_retry(
        self,
        prompt: str,
        model: str,
        max_retries: int = 3,
        **kwargs: Any
    ) -> str:
        """Complete with automatic retry on transient failures.

        This is a convenience method that wraps complete() with retry logic.
        It will retry on:
        - ProviderTimeoutError
        - ProviderRateLimitError
        - Generic ProviderError (non-auth)

        It will NOT retry on:
        - ProviderAuthError (permanent failure)

        Args:
            prompt: The prompt text
            model: Model identifier
            max_retries: Maximum number of retry attempts
            **kwargs: Additional parameters for complete()

        Returns:
            Response from LLM

        Raises:
            ProviderError: If all retries are exhausted
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.complete(prompt, model, **kwargs)
            except ProviderAuthError:
                # Don't retry authentication errors
                raise
            except (ProviderTimeoutError, ProviderRateLimitError, ProviderError) as e:
                last_error = e
                logger.warning(
                    f"Provider request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    # Simple exponential backoff: 2^attempt seconds
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                continue

        # All retries exhausted
        raise ProviderError(
            f"Failed after {max_retries} attempts. Last error: {last_error}"
        )

    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"<{self.__class__.__name__}>"
