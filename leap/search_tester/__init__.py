"""
LEAP Search Tester - Search Quality Validation Tool.

This module provides tools for testing the quality and relevance
of the LEAP search system by comparing VictoriaLogs data against
the search backend and using ripgrep as a fallback.

Example Usage:
    >>> from leap.search_tester import (
    ...     SearchTesterConfig,
    ...     VictoriaLogsClient,
    ...     SearchBackendClient,
    ...     RipgrepFallback,
    ...     SearchTester,
    ... )
    >>> from pathlib import Path
    >>>
    >>> # Create clients
    >>> victoria_client = VictoriaLogsClient("http://localhost:9428")
    >>> search_client = SearchBackendClient("http://localhost:8000")
    >>> ripgrep = RipgrepFallback(Path("/home/user/project"))
    >>>
    >>> # Create tester
    >>> tester = SearchTester(victoria_client, search_client, ripgrep)
    >>>
    >>> # Fetch and test logs
    >>> logs = await victoria_client.query_logs(...)
    >>> results, metrics = await tester.run_tests(logs)
"""

from leap.search_tester.checkpoint import TestCheckpoint
from leap.search_tester.config import SearchTesterConfig
from leap.search_tester.models import (
    RipgrepMatch,
    SearchResponse,
    TestMetrics,
    TestResult,
    VictoriaLog,
)
from leap.search_tester.outputs import (
    display_summary,
    generate_csv_output,
    generate_json_output,
    generate_markdown_report,
)
from leap.search_tester.ripgrep_fallback import RipgrepFallback
from leap.search_tester.search_client import SearchBackendClient
from leap.search_tester.tester import SearchTester
from leap.search_tester.victoria_client import VictoriaLogsClient

__all__ = [
    # Configuration
    "SearchTesterConfig",
    # Clients
    "VictoriaLogsClient",
    "SearchBackendClient",
    "RipgrepFallback",
    # Main orchestrator
    "SearchTester",
    # Data models
    "VictoriaLog",
    "SearchResponse",
    "RipgrepMatch",
    "TestResult",
    "TestMetrics",
    # Outputs
    "generate_json_output",
    "generate_markdown_report",
    "generate_csv_output",
    "display_summary",
    # Checkpoint
    "TestCheckpoint",
]
