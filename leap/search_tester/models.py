"""
Data models for LEAP Search Tester.

This module defines the data structures used throughout the search testing pipeline.
"""

import statistics
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class VictoriaLog:
    """
    Represents a log entry from VictoriaLogs.

    Attributes:
        msg: The log message content (_msg field)
        time: Timestamp in RFC3339 format (_time field)
        stream: Stream labels as dict (_stream field parsed)
        extra_fields: Any additional fields from the log entry
    """

    msg: str
    time: str
    stream: dict[str, str]
    extra_fields: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "VictoriaLog":
        """
        Parse VictoriaLog from JSON response.

        Args:
            data: Raw JSON object from VictoriaLogs API

        Returns:
            VictoriaLog instance

        Example:
            >>> data = {
            ...     "_msg": "Error occurred",
            ...     "_time": "2025-11-17T10:30:00Z",
            ...     "_stream": '{"namespace":"app","pod":"api-123"}',
            ...     "level": "error"
            ... }
            >>> log = VictoriaLog.from_json(data)
        """
        msg = data.get("_msg", "")
        time = data.get("_time", "")

        # Parse _stream field (can be a dict or JSON string)
        stream_raw = data.get("_stream", {})
        if isinstance(stream_raw, str):
            import json

            try:
                stream = json.loads(stream_raw)
            except json.JSONDecodeError:
                stream = {}
        else:
            stream = stream_raw

        # Collect extra fields (exclude _msg, _time, _stream)
        extra_fields = {
            k: v for k, v in data.items() if not k.startswith("_")
        }

        return cls(
            msg=msg,
            time=time,
            stream=stream,
            extra_fields=extra_fields,
        )


@dataclass
class SearchResponse:
    """
    Response from LEAP search backend.

    Attributes:
        results: List of search result objects
        total_found: Total number of results found
        search_time_ms: Search time in milliseconds
    """

    results: list[dict[str, Any]]
    total_found: int
    search_time_ms: float


@dataclass
class RipgrepMatch:
    """
    A match found by ripgrep in source code.

    Attributes:
        file_path: Path to the file containing the match
        line_number: Line number of the match
        line_text: The actual line content
        column: Column number of the match (optional)
    """

    file_path: str
    line_number: int
    line_text: str
    column: int | None = None

    @classmethod
    def from_ripgrep_json(cls, data: dict[str, Any]) -> "RipgrepMatch":
        """
        Parse RipgrepMatch from ripgrep's JSON output.

        Args:
            data: JSON object from ripgrep --json output

        Returns:
            RipgrepMatch instance

        Example:
            >>> data = {
            ...     "type": "match",
            ...     "data": {
            ...         "path": {"text": "src/db.py"},
            ...         "line_number": 156,
            ...         "lines": {"text": "logger.error('Failed to connect')"},
            ...     }
            ... }
            >>> match = RipgrepMatch.from_ripgrep_json(data)
        """
        match_data = data.get("data", {})
        path = match_data.get("path", {}).get("text", "")
        line_number = match_data.get("line_number", 0)
        line_text = match_data.get("lines", {}).get("text", "").strip()

        # Extract column from submatches if available
        submatches = match_data.get("submatches", [])
        column = submatches[0].get("start") if submatches else None

        return cls(
            file_path=path,
            line_number=line_number,
            line_text=line_text,
            column=column,
        )


@dataclass
class TestResult:
    """
    Result of testing a single log entry.

    Attributes:
        log_message: Original log message from VictoriaLogs
        victoria_timestamp: Timestamp from VictoriaLogs
        victoria_stream: Stream labels from VictoriaLogs

        search_found: Whether the log was found by search backend
        search_response_time_ms: Search API response time
        search_results: List of search results (if found)
        best_match_score: Score of best match (if found)

        ripgrep_found: Whether the log was found by ripgrep
        ripgrep_file: File path where ripgrep found the log
        ripgrep_line: Line number where ripgrep found the log
        ripgrep_match: Matched line text from ripgrep
        ripgrep_similarity: Similarity score between log and code

        status: Overall status (found/fallback_found/not_found)
        is_false_negative: True if found by ripgrep but not by search
    """

    log_message: str
    victoria_timestamp: str
    victoria_stream: dict[str, str]

    search_found: bool
    search_response_time_ms: float
    search_results: list[dict[str, Any]] | None
    best_match_score: float | None

    ripgrep_found: bool
    ripgrep_file: str | None = None
    ripgrep_line: int | None = None
    ripgrep_match: str | None = None
    ripgrep_similarity: float | None = None

    status: Literal["found", "fallback_found", "not_found"] = "not_found"
    is_false_negative: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "log_message": self.log_message,
            "victoria_timestamp": self.victoria_timestamp,
            "victoria_stream": self.victoria_stream,
            "search_found": self.search_found,
            "search_response_time_ms": self.search_response_time_ms,
            "search_results": self.search_results,
            "best_match_score": self.best_match_score,
            "ripgrep_found": self.ripgrep_found,
            "ripgrep_file": self.ripgrep_file,
            "ripgrep_line": self.ripgrep_line,
            "ripgrep_match": self.ripgrep_match,
            "ripgrep_similarity": self.ripgrep_similarity,
            "status": self.status,
            "is_false_negative": self.is_false_negative,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestResult":
        """Create TestResult from dictionary."""
        return cls(**data)


@dataclass
class TestMetrics:
    """
    Aggregated metrics from search testing.

    Attributes:
        total_logs: Total number of logs tested

        found_by_search: Number of logs found by search backend
        found_by_ripgrep_only: Number found by ripgrep but not search
        not_found: Number not found anywhere

        hit_rate: Percentage found by search (0.0 - 1.0)
        false_negative_rate: Percentage found by ripgrep only (0.0 - 1.0)
        miss_rate: Percentage not found anywhere (0.0 - 1.0)

        avg_response_time_ms: Average search response time
        min_response_time_ms: Minimum response time
        max_response_time_ms: Maximum response time
        p50_response_time_ms: Median response time
        p95_response_time_ms: 95th percentile response time
        p99_response_time_ms: 99th percentile response time

        avg_match_score: Average match score for found results
        total_duration_seconds: Total test duration
    """

    total_logs: int

    found_by_search: int
    found_by_ripgrep_only: int
    not_found: int

    hit_rate: float
    false_negative_rate: float
    miss_rate: float

    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float

    avg_match_score: float | None
    total_duration_seconds: float

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        return sorted_data[min(index, len(sorted_data) - 1)]

    @classmethod
    def from_results(
        cls,
        results: list[TestResult],
        total_duration_seconds: float,
    ) -> "TestMetrics":
        """
        Calculate metrics from test results.

        Args:
            results: List of test results
            total_duration_seconds: Total time taken for tests

        Returns:
            TestMetrics instance with calculated statistics
        """
        total = len(results)
        found_by_search = sum(1 for r in results if r.search_found)
        found_by_ripgrep_only = sum(1 for r in results if r.is_false_negative)
        not_found = sum(1 for r in results if r.status == "not_found")

        # Calculate response time statistics
        response_times = [
            r.search_response_time_ms for r in results if r.search_found
        ]

        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = cls._percentile(response_times, 0.95)
            p99_response_time = cls._percentile(response_times, 0.99)
        else:
            avg_response_time = 0.0
            min_response_time = 0.0
            max_response_time = 0.0
            p50_response_time = 0.0
            p95_response_time = 0.0
            p99_response_time = 0.0

        # Calculate match score statistics
        match_scores = [
            r.best_match_score
            for r in results
            if r.best_match_score is not None
        ]
        avg_match_score = (
            statistics.mean(match_scores) if match_scores else None
        )

        return cls(
            total_logs=total,
            found_by_search=found_by_search,
            found_by_ripgrep_only=found_by_ripgrep_only,
            not_found=not_found,
            hit_rate=found_by_search / total if total > 0 else 0.0,
            false_negative_rate=(
                found_by_ripgrep_only / total if total > 0 else 0.0
            ),
            miss_rate=not_found / total if total > 0 else 0.0,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            avg_match_score=avg_match_score,
            total_duration_seconds=total_duration_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_logs": self.total_logs,
            "found_by_search": self.found_by_search,
            "found_by_ripgrep_only": self.found_by_ripgrep_only,
            "not_found": self.not_found,
            "hit_rate": self.hit_rate,
            "false_negative_rate": self.false_negative_rate,
            "miss_rate": self.miss_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "p50_response_time_ms": self.p50_response_time_ms,
            "p95_response_time_ms": self.p95_response_time_ms,
            "p99_response_time_ms": self.p99_response_time_ms,
            "avg_match_score": self.avg_match_score,
            "total_duration_seconds": self.total_duration_seconds,
        }
