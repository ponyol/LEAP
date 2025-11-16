"""
LEAP - Log Extraction & Analysis Pipeline.

This package provides a CLI tool and library for extracting log statements
from source code across multiple programming languages (Python, Go, Ruby, JS/TS).

Main components:
- cli: Command-line interface
- parsers: Language-specific AST parsers
- core: File discovery and result aggregation
- schemas: Data models for log entries
- utils: Utilities (logging, etc.)

Public API (for use as a library):
"""

from leap.core import (
    aggregate_results,
    detect_language,
    discover_files,
    filter_changed_files,
    load_raw_logs,
    merge_results,
)
from leap.parsers import BaseParser, PythonParser
from leap.schemas import AnalyzedLogEntry, RawLogEntry

__version__ = "0.1.0"

__all__ = [
    # Schemas
    "RawLogEntry",
    "AnalyzedLogEntry",
    # Parsers
    "BaseParser",
    "PythonParser",
    # Core
    "discover_files",
    "filter_changed_files",
    "detect_language",
    "aggregate_results",
    "load_raw_logs",
    "merge_results",
]
