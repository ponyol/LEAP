"""
Main orchestrator for search quality testing.

This module coordinates VictoriaLogs fetching, search backend queries,
and ripgrep fallback to test search quality.
"""

import asyncio
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from leap.search_tester.models import (
    TestMetrics,
    TestResult,
    VictoriaLog,
)
from leap.search_tester.ripgrep_fallback import RipgrepFallback
from leap.search_tester.search_client import SearchBackendClient
from leap.search_tester.victoria_client import VictoriaLogsClient
from leap.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


class SearchTester:
    """
    Main orchestrator for search quality testing.

    Coordinates the entire testing pipeline:
    1. Fetch logs from VictoriaLogs
    2. Query search backend for each log
    3. Fallback to ripgrep if not found
    4. Calculate metrics and generate reports

    Example:
        >>> victoria_client = VictoriaLogsClient("http://localhost:9428")
        >>> search_client = SearchBackendClient("http://localhost:8000")
        >>> ripgrep = RipgrepFallback(Path("/home/user/project"))
        >>>
        >>> tester = SearchTester(victoria_client, search_client, ripgrep)
        >>> logs = await victoria_client.query_logs(...)
        >>> results, metrics = await tester.run_tests(logs)
    """

    def __init__(
        self,
        victoria_client: VictoriaLogsClient,
        search_client: SearchBackendClient,
        ripgrep_fallback: RipgrepFallback,
        concurrency: int = 5,
        codebase: str | None = None,
    ) -> None:
        """
        Initialize search tester.

        Args:
            victoria_client: Client for VictoriaLogs
            search_client: Client for LEAP search backend
            ripgrep_fallback: Fallback search with ripgrep
            concurrency: Maximum concurrent search requests (default: 5)
            codebase: Optional codebase filter for search
        """
        self.victoria_client = victoria_client
        self.search_client = search_client
        self.ripgrep_fallback = ripgrep_fallback
        self.concurrency = concurrency
        self.codebase = codebase
        self.semaphore = asyncio.Semaphore(concurrency)

        # Live statistics (updated during testing)
        self.stats = {
            "tested": 0,
            "found_by_search": 0,
            "found_by_ripgrep": 0,
            "not_found": 0,
            "total_response_time": 0.0,
        }

    async def test_single_log(
        self,
        log: VictoriaLog,
    ) -> TestResult:
        """
        Test a single log entry.

        Workflow:
        1. Try search backend first
        2. If not found, fallback to ripgrep
        3. Calculate similarity score

        Args:
            log: VictoriaLog to test

        Returns:
            TestResult with status and metrics
        """
        async with self.semaphore:
            # Update stats
            self.stats["tested"] += 1

            # 1. Try search backend
            try:
                search_response = await self.search_client.search(
                    query=log.msg,
                    top_k=5,
                    codebase=self.codebase,
                )

                self.stats["total_response_time"] += (
                    search_response.search_time_ms
                )

                if search_response.total_found > 0:
                    # Found by search! ✅
                    self.stats["found_by_search"] += 1

                    best_score = (
                        search_response.results[0].get("score", 1.0)
                        if search_response.results
                        else None
                    )

                    logger.debug(
                        f"✅ Found by search: {log.msg[:60]}",
                        extra={"score": best_score},
                    )

                    return TestResult(
                        log_message=log.msg,
                        victoria_timestamp=log.time,
                        victoria_stream=log.stream,
                        search_found=True,
                        search_response_time_ms=search_response.search_time_ms,
                        search_results=search_response.results,
                        best_match_score=best_score,
                        ripgrep_found=False,
                        status="found",
                        is_false_negative=False,
                    )

            except Exception as e:
                logger.warning(
                    f"Search failed for log: {e}",
                    extra={"log_message": log.msg[:100]},
                )

            # 2. Fallback to ripgrep
            try:
                best_match, similarity = await (
                    self.ripgrep_fallback.find_best_match(
                        log.msg,
                        max_results=10,
                    )
                )

                if best_match and similarity > 0.5:  # Threshold: 50%
                    # Found by ripgrep (potential false negative!) ⚠️
                    self.stats["found_by_ripgrep"] += 1

                    logger.warning(
                        f"⚠️  False negative: {log.msg[:60]}",
                        extra={
                            "file": best_match.file_path,
                            "line": best_match.line_number,
                            "similarity": similarity,
                        },
                    )

                    return TestResult(
                        log_message=log.msg,
                        victoria_timestamp=log.time,
                        victoria_stream=log.stream,
                        search_found=False,
                        search_response_time_ms=0.0,
                        search_results=None,
                        best_match_score=None,
                        ripgrep_found=True,
                        ripgrep_file=best_match.file_path,
                        ripgrep_line=best_match.line_number,
                        ripgrep_match=best_match.line_text,
                        ripgrep_similarity=similarity,
                        status="fallback_found",
                        is_false_negative=True,
                    )

            except Exception as e:
                logger.warning(
                    f"Ripgrep fallback failed: {e}",
                    extra={"log_message": log.msg[:100]},
                )

            # 3. Not found anywhere ❌
            self.stats["not_found"] += 1

            logger.debug(f"❌ Not found: {log.msg[:60]}")

            return TestResult(
                log_message=log.msg,
                victoria_timestamp=log.time,
                victoria_stream=log.stream,
                search_found=False,
                search_response_time_ms=0.0,
                search_results=None,
                best_match_score=None,
                ripgrep_found=False,
                status="not_found",
                is_false_negative=False,
            )

    def _create_stats_table(self, total_logs: int) -> Table:
        """Create a Rich table with live statistics."""
        table = Table(title="Live Statistics", show_header=False)

        table.add_row(
            "Tested:",
            f"{self.stats['tested']}/{total_logs}",
        )

        found_pct = (
            100 * self.stats["found_by_search"] / self.stats["tested"]
            if self.stats["tested"] > 0
            else 0
        )
        table.add_row(
            "✅ Found by Search:",
            f"{self.stats['found_by_search']} ({found_pct:.1f}%)",
        )

        ripgrep_pct = (
            100 * self.stats["found_by_ripgrep"] / self.stats["tested"]
            if self.stats["tested"] > 0
            else 0
        )
        table.add_row(
            "⚠️  Found by Ripgrep:",
            f"{self.stats['found_by_ripgrep']} ({ripgrep_pct:.1f}%)",
        )

        not_found_pct = (
            100 * self.stats["not_found"] / self.stats["tested"]
            if self.stats["tested"] > 0
            else 0
        )
        table.add_row(
            "❌ Not Found:",
            f"{self.stats['not_found']} ({not_found_pct:.1f}%)",
        )

        avg_time = (
            self.stats["total_response_time"] / self.stats["found_by_search"]
            if self.stats["found_by_search"] > 0
            else 0
        )
        table.add_row(
            "Avg Response Time:",
            f"{avg_time:.0f}ms",
        )

        return table

    async def run_tests(
        self,
        logs: list[VictoriaLog],
        show_progress: bool = True,
    ) -> tuple[list[TestResult], TestMetrics]:
        """
        Run tests on all logs with rich progress display.

        Args:
            logs: List of VictoriaLog objects to test
            show_progress: Whether to show progress bar (default: True)

        Returns:
            Tuple of (results, metrics)

        Example:
            >>> results, metrics = await tester.run_tests(logs)
            >>> print(f"Hit rate: {metrics.hit_rate:.1%}")
        """
        start_time = time.time()

        # Reset stats
        self.stats = {
            "tested": 0,
            "found_by_search": 0,
            "found_by_ripgrep": 0,
            "not_found": 0,
            "total_response_time": 0.0,
        }

        if not show_progress:
            # Simple mode without progress bar
            results = await asyncio.gather(
                *[self.test_single_log(log) for log in logs]
            )
        else:
            # Rich progress mode
            results = []

            # Create progress bar
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=console,
            )

            with Live(
                Panel.fit(
                    progress,
                    title="[bold cyan]Testing Search Quality[/bold cyan]",
                    border_style="cyan",
                ),
                console=console,
                refresh_per_second=4,
            ) as live:
                task = progress.add_task(
                    "[cyan]Testing logs...",
                    total=len(logs),
                )

                # Test logs with concurrency control
                async def test_with_update(log: VictoriaLog) -> TestResult:
                    result = await self.test_single_log(log)
                    progress.update(task, advance=1)

                    # Update live display with stats
                    live.update(
                        Panel.fit(
                            progress,
                            self._create_stats_table(len(logs)),
                            title="[bold cyan]Testing Search Quality[/bold cyan]",
                            border_style="cyan",
                        )
                    )

                    return result

                # Run all tests
                results = await asyncio.gather(
                    *[test_with_update(log) for log in logs]
                )

        # Calculate final metrics
        total_duration = time.time() - start_time
        metrics = TestMetrics.from_results(results, total_duration)

        logger.info(
            "Testing complete",
            extra={
                "total_logs": len(logs),
                "found_by_search": metrics.found_by_search,
                "found_by_ripgrep_only": metrics.found_by_ripgrep_only,
                "not_found": metrics.not_found,
                "hit_rate": metrics.hit_rate,
                "duration_seconds": total_duration,
            },
        )

        return results, metrics

    async def close(self) -> None:
        """Close all clients."""
        await self.victoria_client.close()
        await self.search_client.close()
