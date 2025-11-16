"""Amazon Bedrock provider implementation."""

import json
import logging
from typing import Any

from .base import (
    LLMProvider,
    ProviderError,
    ProviderTimeoutError,
    ProviderAuthError,
    ProviderRateLimitError
)

logger = logging.getLogger(__name__)


class BedrockProvider(LLMProvider):
    """Provider implementation for Amazon Bedrock.

    This provider supports Claude models via AWS Bedrock.
    Requires AWS credentials configured via:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS credentials file (~/.aws/credentials)
    - IAM role (when running on AWS)

    Recommended models:
    - anthropic.claude-3-5-sonnet-20241022-v2:0
    - anthropic.claude-3-opus-20240229-v1:0
    - anthropic.claude-3-haiku-20240307-v1:0
    """

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str | None = None,
        timeout: int = 60
    ):
        """Initialize Bedrock provider.

        Args:
            region: AWS region (default: us-east-1)
            profile: AWS profile name (optional)
            timeout: Request timeout in seconds

        Raises:
            ImportError: If boto3 is not installed
        """
        self.region = region
        self.profile = profile
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of Bedrock client."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise ImportError(
                    "boto3 required for Bedrock provider. "
                    "Install with: pip install boto3"
                )

            # Configure boto3 session
            session_kwargs = {}
            if self.profile:
                session_kwargs["profile_name"] = self.profile

            session = boto3.Session(**session_kwargs)

            # Create Bedrock runtime client
            config = Config(
                region_name=self.region,
                connect_timeout=self.timeout,
                read_timeout=self.timeout,
                retries={"max_attempts": 0}  # We handle retries ourselves
            )

            self._client = session.client(
                "bedrock-runtime",
                config=config
            )

        return self._client

    def _format_bedrock_request(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float
    ) -> dict[str, Any]:
        """Format request for Bedrock API.

        Bedrock requires different request formats for different model families.
        Claude models use the Messages API format.
        """
        # For Claude models (Anthropic)
        if "anthropic" in model or "claude" in model:
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        else:
            raise ValueError(f"Unsupported model family for Bedrock: {model}")

    def _parse_bedrock_response(self, response_body: dict[str, Any]) -> str:
        """Parse response from Bedrock API.

        Args:
            response_body: Parsed JSON response from Bedrock

        Returns:
            Extracted text content

        Raises:
            ProviderError: If response format is unexpected
        """
        # Claude models response format
        if "content" in response_body:
            content = response_body["content"]
            if isinstance(content, list) and len(content) > 0:
                return str(content[0].get("text", ""))

        raise ProviderError(f"Unexpected response format: {response_body}")

    async def complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> str:
        """Generate completion using Bedrock API.

        Args:
            prompt: The prompt text
            model: Model identifier (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Text response from model

        Raises:
            ProviderAuthError: If AWS credentials are invalid
            ProviderTimeoutError: If request times out
            ProviderError: For other API errors
        """
        client = self._get_client()

        # Format request for Bedrock
        body = self._format_bedrock_request(prompt, model, max_tokens, temperature)

        try:
            # Note: boto3 is synchronous, so we wrap in executor
            # For true async, would need aioboto3
            import asyncio
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(
                    modelId=model,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            return self._parse_bedrock_response(response_body)

        except Exception as e:
            error_msg = str(e).lower()

            if "credentials" in error_msg or "unauthorized" in error_msg:
                raise ProviderAuthError(f"AWS credentials invalid: {e}")
            elif "timeout" in error_msg:
                raise ProviderTimeoutError(f"Request timed out: {e}")
            elif "throttling" in error_msg or "rate" in error_msg:
                raise ProviderRateLimitError(f"Rate limit exceeded: {e}")
            else:
                raise ProviderError(f"Bedrock API error: {e}")

    async def health_check(self) -> bool:
        """Verify Bedrock is accessible and credentials are valid.

        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            # Make a minimal test request with Haiku (cheapest)
            response = await self.complete(
                prompt="Test",
                model="anthropic.claude-3-haiku-20240307-v1:0",
                max_tokens=10,
                temperature=0.0
            )
            return bool(response)

        except ProviderAuthError:
            logger.error("Bedrock health check failed: Invalid AWS credentials")
            return False
        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            return False
