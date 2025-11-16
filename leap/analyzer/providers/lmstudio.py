"""LM Studio local LLM provider implementation."""

import logging
from typing import Any

from .base import (
    LLMProvider,
    ProviderError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    """Provider implementation for LM Studio local models.

    LM Studio provides an OpenAI-compatible API for local models.
    Default endpoint: http://localhost:1234/v1

    Supports any model loaded in LM Studio:
    - Meta Llama models
    - Mistral models
    - CodeLlama models
    - And many more from HuggingFace

    Download LM Studio: https://lmstudio.ai
    """

    def __init__(
        self,
        api_base: str = "http://localhost:1234",
        timeout: int = 60
    ):
        """Initialize LM Studio provider.

        Args:
            api_base: Base URL for LM Studio server (without /v1)
            timeout: Request timeout in seconds
        """
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of httpx client."""
        if self._client is None:
            try:
                import httpx
            except ImportError:
                raise ImportError(
                    "httpx required for LM Studio provider. "
                    "Install with: pip install httpx"
                )

            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=f"{self.api_base}/v1"
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
        """Generate completion using LM Studio OpenAI-compatible API.

        Args:
            prompt: The prompt text
            model: Model identifier (can be any string if only one model loaded)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional OpenAI-compatible parameters

        Returns:
            Text response from model

        Raises:
            ProviderTimeoutError: If request times out
            ProviderError: For other API errors
        """
        client = self._get_client()

        # LM Studio uses OpenAI-compatible chat completions API
        url = "/chat/completions"

        # Build request payload (OpenAI format)
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }

        # Add any additional parameters
        if kwargs:
            payload.update(kwargs)

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract message from OpenAI response format
            if "choices" in data and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                return str(message.get("content", ""))
            else:
                raise ProviderError(f"Unexpected response format: {data}")

        except Exception as e:
            error_msg = str(e).lower()

            if "timeout" in error_msg:
                raise ProviderTimeoutError(f"LM Studio request timed out: {e}")
            elif "connection" in error_msg:
                raise ProviderError(
                    f"Cannot connect to LM Studio at {self.api_base}. "
                    f"Is LM Studio running with server enabled? Error: {e}"
                )
            else:
                raise ProviderError(f"LM Studio API error: {e}")

    async def health_check(self) -> bool:
        """Verify LM Studio is running and accessible.

        Returns:
            True if LM Studio is healthy, False otherwise
        """
        try:
            client = self._get_client()

            # Try to list models as a health check
            response = await client.get("/models")
            return bool(response.status_code == 200)

        except Exception as e:
            logger.error(f"LM Studio health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models in LM Studio.

        Returns:
            List of model identifiers

        Raises:
            ProviderError: If listing fails
        """
        try:
            client = self._get_client()
            response = await client.get("/models")
            response.raise_for_status()

            data = response.json()
            models = data.get("data", [])
            return [model.get("id") for model in models]

        except Exception as e:
            raise ProviderError(f"Failed to list LM Studio models: {e}")

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
