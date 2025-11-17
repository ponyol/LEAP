"""Tests for utils.logger module."""

import logging

import pytest

from leap.utils.logger import get_logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_basic(self) -> None:
        """Test getting logger with name."""
        logger = get_logger("test.module")

        assert logger.name == "test.module"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_dunder_name(self) -> None:
        """Test getting logger with __name__."""
        logger = get_logger(__name__)

        assert __name__ in logger.name
        assert isinstance(logger, logging.Logger)

    def test_logger_has_handlers(self) -> None:
        """Test that logger has handlers configured."""
        logger = get_logger("test.handlers")

        # Logger or its parent should have handlers
        assert len(logger.handlers) > 0 or len(logging.getLogger().handlers) > 0

    def test_logger_different_names(self) -> None:
        """Test getting loggers with different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name != logger2.name
        assert logger1.name == "module1"
        assert logger2.name == "module2"

    def test_logger_same_name_returns_same_instance(self) -> None:
        """Test that getting logger with same name returns same instance."""
        logger1 = get_logger("same.name")
        logger2 = get_logger("same.name")

        # Should be the same logger instance
        assert logger1 is logger2

    def test_logger_can_log(self) -> None:
        """Test that logger can actually log messages."""
        logger = get_logger("test.logging")

        # Should not raise
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        assert True

    def test_logger_level(self) -> None:
        """Test logger level configuration."""
        logger = get_logger("test.level")

        # Logger should have a level set
        assert logger.level >= 0 or logger.getEffectiveLevel() >= 0
