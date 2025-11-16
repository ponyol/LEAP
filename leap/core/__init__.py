"""
Core functionality for LEAP.

This module exposes the public API for file discovery and result aggregation.
"""

from .aggregator import aggregate_results, load_raw_logs, merge_results
from .discovery import detect_language, discover_files, filter_changed_files

__all__ = [
    "discover_files",
    "filter_changed_files",
    "detect_language",
    "aggregate_results",
    "load_raw_logs",
    "merge_results",
]
