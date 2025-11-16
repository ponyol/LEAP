"""Unit tests for analyzer configuration."""

import os
import pytest
from leap.analyzer.config import AnalyzerConfig


class TestAnalyzerConfig:
    """Test AnalyzerConfig model and validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AnalyzerConfig()

        assert config.provider == "anthropic"
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.concurrency == 10
        assert config.max_retries == 3
        assert config.timeout == 60
        assert config.language == "en"
        assert config.enable_cache is True

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = AnalyzerConfig(
            provider="ollama",
            model="llama3:8b",
            concurrency=20,
            language="ru",
            enable_cache=False
        )

        assert config.provider == "ollama"
        assert config.model == "llama3:8b"
        assert config.concurrency == 20
        assert config.language == "ru"
        assert config.enable_cache is False

    def test_concurrency_validation(self):
        """Test that concurrency is validated."""
        with pytest.raises(Exception):
            AnalyzerConfig(concurrency=0)  # Too low

        with pytest.raises(Exception):
            AnalyzerConfig(concurrency=100)  # Too high

    def test_api_base_validation(self):
        """Test that api_base must start with http."""
        with pytest.raises(Exception):
            AnalyzerConfig(
                provider="ollama",
                api_base="localhost:11434"  # Missing http://
            )

        # Valid URLs should pass
        config = AnalyzerConfig(
            provider="ollama",
            api_base="http://localhost:11434"
        )
        assert config.api_base == "http://localhost:11434"

    def test_from_env_anthropic(self, monkeypatch):
        """Test loading Anthropic config from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        config = AnalyzerConfig.from_env(provider="anthropic")

        assert config.provider == "anthropic"
        assert config.api_key == "test-key-123"

    def test_from_env_bedrock(self, monkeypatch):
        """Test loading Bedrock config from environment."""
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("AWS_PROFILE", "my-profile")

        config = AnalyzerConfig.from_env(provider="bedrock")

        assert config.provider == "bedrock"
        assert config.aws_region == "eu-west-1"
        assert config.aws_profile == "my-profile"

    def test_from_env_ollama(self, monkeypatch):
        """Test loading Ollama config from environment."""
        monkeypatch.setenv("OLLAMA_API_BASE", "http://192.168.1.100:11434")

        config = AnalyzerConfig.from_env(provider="ollama")

        assert config.provider == "ollama"
        assert config.api_base == "http://192.168.1.100:11434"

    def test_from_env_ollama_default(self):
        """Test Ollama uses default URL if not set."""
        config = AnalyzerConfig.from_env(provider="ollama")

        assert config.api_base == "http://localhost:11434"

    def test_from_env_lmstudio_default(self):
        """Test LMStudio uses default URL if not set."""
        config = AnalyzerConfig.from_env(provider="lmstudio")

        assert config.api_base == "http://localhost:1234"

    def test_from_env_with_overrides(self, monkeypatch):
        """Test that CLI overrides take precedence over environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")

        config = AnalyzerConfig.from_env(
            provider="anthropic",
            api_key="cli-key",  # Override from CLI
            concurrency=25
        )

        assert config.api_key == "cli-key"  # CLI wins
        assert config.concurrency == 25

    def test_validate_provider_config_anthropic_missing_key(self):
        """Test validation fails if Anthropic key is missing."""
        config = AnalyzerConfig(provider="anthropic", api_key=None)

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            config.validate_provider_config()

    def test_validate_provider_config_anthropic_with_key(self):
        """Test validation passes if Anthropic key is provided."""
        config = AnalyzerConfig(provider="anthropic", api_key="test-key")

        # Should not raise
        config.validate_provider_config()

    def test_validate_provider_config_bedrock_missing_region(self):
        """Test validation fails if Bedrock region is missing."""
        config = AnalyzerConfig(provider="bedrock", aws_region=None)

        with pytest.raises(ValueError, match="AWS_REGION"):
            config.validate_provider_config()

    def test_validate_provider_config_ollama_missing_base(self):
        """Test validation fails if Ollama api_base is missing."""
        config = AnalyzerConfig(provider="ollama", api_base=None)

        with pytest.raises(ValueError, match="OLLAMA_API_BASE"):
            config.validate_provider_config()

    def test_validate_provider_config_lmstudio_missing_base(self):
        """Test validation fails if LMStudio api_base is missing."""
        config = AnalyzerConfig(provider="lmstudio", api_base=None)

        with pytest.raises(ValueError, match="LMSTUDIO_API_BASE"):
            config.validate_provider_config()
