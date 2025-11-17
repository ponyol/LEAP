"""LEAP Search Server - Semantic search for analyzed logs.

This module provides a FastAPI-based search server for semantic search
across analyzed logs.
"""

from .config import SearchServerConfig
from .main import create_app

__all__ = [
    "SearchServerConfig",
    "create_app",
]
