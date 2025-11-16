"""Ollama local LLM provider implementation."""

import json
import logging
from typing import Any

from .base import (
    LLMProvider,
    ProviderError,
    ProviderTimeoutError,
    ProviderAuthError,
)

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Provider implementation for Ollama local models.

    Ollama runs LLMs locally on your machine. No API keys required.
    Default endpoint: http://localhost:11434

    Popular models:
    - llama3:8b (recommended for code analysis)
    - codellama:7b (specialized for code)
    - mistral:7b (fast and capable)
    - llama3:70b (highest quality, requires more resources)

    Install Ollama: https://ollama.ai
    Pull models: ollama pull llama3:8b
    """

    def __init__(
        self,
        api_base: str = "http://localhost:11434",
        timeout: int = 60
    ):
        """Initialize Ollama provider.

        Args:
            api_base: Base URL for Ollama server
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
                    "httpx required for Ollama provider. "
                    "Install with: pip install httpx"
                )

            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=self.api_base
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
        """Generate completion using Ollama API.

        Args:
            prompt: The prompt text
            model: Model name (e.g., "llama3:8b")
            max_tokens: Maximum tokens in response (maps to num_predict)
            temperature: Sampling temperature
            **kwargs: Additional Ollama parameters

        Returns:
            Text response from model

        Raises:
            ProviderTimeoutError: If request times out
            ProviderError: For other API errors
        """
        client = self._get_client()

        # Ollama API endpoint
        url = "/api/generate"

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # We want the full response at once
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }

        # Add any additional options
        if kwargs:
            options: dict[str, Any] = payload["options"]
            options.update(kwargs)

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return str(data.get("response", ""))

        except Exception as e:
            error_msg = str(e).lower()

            if "timeout" in error_msg:
                raise ProviderTimeoutError(f"Ollama request timed out: {e}")
            elif "connection" in error_msg:
                raise ProviderError(
                    f"Cannot connect to Ollama at {self.api_base}. "
                    f"Is Ollama running? Error: {e}"
                )
            else:
                raise ProviderError(f"Ollama API error: {e}")

    async def health_check(self) -> bool:
        """Verify Ollama is running and accessible.

        Returns:
            True if Ollama is healthy, False otherwise
        """
        try:
            client = self._get_client()

            # Check if Ollama is running by hitting the root endpoint
            response = await client.get("/")
            return bool(response.status_code == 200)

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> list[str]:
        """List available models in Ollama.

        Returns:
            List of model names

        Raises:
            ProviderError: If listing fails
        """
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])
            return [model.get("name") for model in models]

        except Exception as e:
            raise ProviderError(f"Failed to list Ollama models: {e}")

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
