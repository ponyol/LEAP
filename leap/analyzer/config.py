"""Configuration management for LEAP Analyzer."""

import os
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_core import ValidationInfo


class AnalyzerConfig(BaseModel):
    """Configuration for LEAP Analyzer.

    This configuration defines all parameters needed for the LLM-based
    log analysis, including provider selection, API credentials, processing
    parameters, and output options.
    """

    # LLM Provider Configuration
    provider: Literal["anthropic", "bedrock", "ollama", "lmstudio"] = Field(
        default="anthropic",
        description="LLM provider to use for analysis"
    )
    model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Model name/identifier for the selected provider"
    )

    # API Configuration
    api_key: str | None = Field(
        default=None,
        description="API key for cloud providers (Anthropic, Bedrock)"
    )
    api_base: str | None = Field(
        default=None,
        description="Base URL for local providers (Ollama, LMStudio)"
    )

    # AWS Bedrock Specific
    aws_region: str | None = Field(
        default=None,
        description="AWS region for Bedrock"
    )
    aws_profile: str | None = Field(
        default=None,
        description="AWS profile name for Bedrock"
    )

    # Processing Configuration
    concurrency: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of concurrent LLM requests"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed requests"
    )
    timeout: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Request timeout in seconds"
    )

    # Output Configuration
    language: Literal["en", "ru"] = Field(
        default="en",
        description="Language for analysis output"
    )

    # Custom Prompt Paths
    analysis_prompt_path: str | None = Field(
        default=None,
        description="Path to custom analysis prompt template"
    )
    severity_prompt_path: str | None = Field(
        default=None,
        description="Path to custom severity classification prompt"
    )
    action_prompt_path: str | None = Field(
        default=None,
        description="Path to custom suggested action prompt"
    )

    # Caching Configuration
    enable_cache: bool = Field(
        default=True,
        description="Enable caching for duplicate log entries"
    )

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Ensure api_base has correct format for local providers."""
        if v and not v.startswith("http"):
            raise ValueError("api_base must start with http:// or https://")
        return v

    @classmethod
    def from_env(cls, **overrides: Any) -> "AnalyzerConfig":
        """Create configuration from environment variables with CLI overrides.

        Environment variables:
        - ANTHROPIC_API_KEY: API key for Anthropic
        - AWS_REGION: AWS region for Bedrock
        - AWS_PROFILE: AWS profile for Bedrock
        - OLLAMA_API_BASE: Base URL for Ollama (default: http://localhost:11434)
        - LMSTUDIO_API_BASE: Base URL for LMStudio (default: http://localhost:1234)

        Args:
            **overrides: CLI arguments that override environment variables

        Returns:
            Configured AnalyzerConfig instance
        """
        # Load from environment
        env_config = {}

        # Provider-specific environment variables
        provider = overrides.get("provider", "anthropic")

        if provider == "anthropic":
            env_config["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "bedrock":
            env_config["aws_region"] = os.getenv("AWS_REGION", "us-east-1")
            env_config["aws_profile"] = os.getenv("AWS_PROFILE")
        elif provider == "ollama":
            env_config["api_base"] = os.getenv(
                "OLLAMA_API_BASE", "http://localhost:11434"
            )
        elif provider == "lmstudio":
            env_config["api_base"] = os.getenv(
                "LMSTUDIO_API_BASE", "http://localhost:1234"
            )

        # Merge environment config with overrides (overrides take precedence)
        final_config = {**env_config, **overrides}

        return cls(**final_config)

    def validate_provider_config(self) -> None:
        """Validate that required configuration exists for the selected provider.

        Raises:
            ValueError: If required configuration is missing
        """
        if self.provider == "anthropic":
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required for Anthropic provider"
                )
        elif self.provider == "bedrock":
            if not self.aws_region:
                raise ValueError(
                    "AWS_REGION environment variable or --aws-region is required for Bedrock"
                )
        elif self.provider in ("ollama", "lmstudio"):
            if not self.api_base:
                raise ValueError(
                    f"{self.provider.upper()}_API_BASE must be configured"
                )
