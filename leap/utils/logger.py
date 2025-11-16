"""
Structured JSON logging for LEAP.

This module provides structured logging in JSON format, as per CLAUDE.md guidelines.
All log output is in JSON format for easy parsing in production environments.
"""

import json
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs in JSON format.

    Each log record is converted to a JSON object with the following fields:
    - timestamp: ISO 8601 formatted timestamp
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message
    - context: Additional context (if provided)
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted log string
        """
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra context from the record
        if hasattr(record, "context"):
            log_data["context"] = record.context

        return json.dumps(log_data, ensure_ascii=False)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get or create a structured JSON logger.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding multiple handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create handler that writes to stderr
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    # Use JSON formatter
    formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger
