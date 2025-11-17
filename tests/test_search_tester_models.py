"""Tests for search_tester.models module."""

import statistics
from datetime import UTC, datetime

import pytest

from leap.search_tester.models import (
    RipgrepMatch,
    SearchResponse,
    TestMetrics,
    TestResult,
    VictoriaLog,
)


class TestVictoriaLog:
    """Tests for VictoriaLog model."""

    def test_from_json_valid(self) -> None:
        """Test creating VictoriaLog from valid JSON."""
        json_data = {
            "_msg": "Failed to connect to database",
            "_time": "2025-11-17T10:30:00.123456789Z",
            "_stream": {"namespace": "app", "pod": "backend-1"},
        }

        log = VictoriaLog.from_json(json_data)

        assert log.msg == "Failed to connect to database"
        assert log.time == "2025-11-17T10:30:00.123456789Z"
        assert log.stream == {"namespace": "app", "pod": "backend-1"}

    def test_from_json_minimal(self) -> None:
        """Test creating VictoriaLog with minimal required fields."""
        json_data = {
            "_msg": "test message",
        }

        log = VictoriaLog.from_json(json_data)

        assert log.msg == "test message"
        assert log.time == ""
        assert log.stream == {}

    def test_to_dict(self) -> None:
        """Test converting VictoriaLog to dict."""
        log = VictoriaLog(
            msg="test message",
            time="2025-11-17T10:30:00Z",
            stream={"app": "backend"},
        )

        result = log.to_dict()

        assert result == {
            "msg": "test message",
            "time": "2025-11-17T10:30:00Z",
            "stream": {"app": "backend"},
        }


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_basic_response(self) -> None:
        """Test basic search response."""
        response = SearchResponse(
            total_found=5,
            results=[
                {"id": "1", "score": 0.95, "text": "match 1"},
                {"id": "2", "score": 0.85, "text": "match 2"},
            ],
            search_time_ms=42.5,
        )

        assert response.total_found == 5
        assert len(response.results) == 2
        assert response.search_time_ms == 42.5

    def test_empty_results(self) -> None:
        """Test search response with no results."""
        response = SearchResponse(
            total_found=0,
            results=[],
            search_time_ms=10.0,
        )

        assert response.total_found == 0
        assert response.results == []


class TestRipgrepMatch:
    """Tests for RipgrepMatch model."""

    def test_from_ripgrep_json(self) -> None:
        """Test parsing ripgrep JSON output."""
        rg_json = {
            "type": "match",
            "data": {
                "path": {"text": "src/main.py"},
                "lines": {"text": 'logger.error("Failed to connect")'},
                "line_number": 42,
                "absolute_offset": 1234,
                "submatches": [{"match": {"text": "Failed"}, "start": 14, "end": 20}],
            },
        }

        match = RipgrepMatch.from_ripgrep_json(rg_json)

        assert match.file_path == "src/main.py"
        assert match.line_text == 'logger.error("Failed to connect")'
        assert match.line_number == 42

    def test_to_dict(self) -> None:
        """Test converting RipgrepMatch to dict."""
        match = RipgrepMatch(
            file_path="src/app.py",
            line_number=10,
            line_text="print('hello')",
        )

        result = match.to_dict()

        assert result == {
            "file_path": "src/app.py",
            "line_number": 10,
            "line_text": "print('hello')",
            "column": None,
        }


class TestTestResult:
    """Tests for TestResult model."""

    def test_found_by_search(self) -> None:
        """Test result when log is found by search."""
        result = TestResult(
            log_message="Failed to connect",
            victoria_timestamp="2025-11-17T10:30:00Z",
            victoria_stream={"app": "backend"},
            search_found=True,
            search_response_time_ms=45.0,
            search_results=[{"id": "1", "score": 0.95}],
            best_match_score=0.95,
            ripgrep_found=False,
            status="found",
            is_false_negative=False,
        )

        assert result.status == "found"
        assert result.search_found is True
        assert result.is_false_negative is False
        assert result.best_match_score == 0.95

    def test_found_by_ripgrep_only(self) -> None:
        """Test result when log is found only by ripgrep (false negative)."""
        result = TestResult(
            log_message="Database timeout",
            victoria_timestamp="2025-11-17T10:30:00Z",
            victoria_stream={"app": "backend"},
            search_found=False,
            search_response_time_ms=0.0,
            search_results=None,
            best_match_score=None,
            ripgrep_found=True,
            ripgrep_file="src/db.py",
            ripgrep_line=123,
            ripgrep_match='logger.error("Database timeout")',
            ripgrep_similarity=0.85,
            status="fallback_found",
            is_false_negative=True,
        )

        assert result.status == "fallback_found"
        assert result.is_false_negative is True
        assert result.ripgrep_found is True
        assert result.ripgrep_similarity == 0.85

    def test_not_found_anywhere(self) -> None:
        """Test result when log is not found anywhere."""
        result = TestResult(
            log_message="Dynamic message with UUID",
            victoria_timestamp="2025-11-17T10:30:00Z",
            victoria_stream={},
            search_found=False,
            search_response_time_ms=0.0,
            search_results=None,
            best_match_score=None,
            ripgrep_found=False,
            status="not_found",
            is_false_negative=False,
        )

        assert result.status == "not_found"
        assert result.search_found is False
        assert result.ripgrep_found is False

    def test_to_dict(self) -> None:
        """Test converting TestResult to dict."""
        result = TestResult(
            log_message="test",
            victoria_timestamp="2025-11-17T10:30:00Z",
            victoria_stream={},
            search_found=True,
            search_response_time_ms=50.0,
            search_results=[],
            best_match_score=0.9,
            ripgrep_found=False,
            status="found",
            is_false_negative=False,
        )

        data = result.to_dict()

        assert data["log_message"] == "test"
        assert data["search_found"] is True
        assert data["status"] == "found"
        assert "victoria_timestamp" in data


class TestTestMetrics:
    """Tests for TestMetrics model."""

    def test_from_results_basic(self) -> None:
        """Test calculating metrics from results."""
        results = [
            TestResult(
                log_message="msg1",
                victoria_timestamp="",
                victoria_stream={},
                search_found=True,
                search_response_time_ms=100.0,
                search_results=[],
                best_match_score=0.9,
                ripgrep_found=False,
                status="found",
                is_false_negative=False,
            ),
            TestResult(
                log_message="msg2",
                victoria_timestamp="",
                victoria_stream={},
                search_found=True,
                search_response_time_ms=200.0,
                search_results=[],
                best_match_score=0.8,
                ripgrep_found=False,
                status="found",
                is_false_negative=False,
            ),
            TestResult(
                log_message="msg3",
                victoria_timestamp="",
                victoria_stream={},
                search_found=False,
                search_response_time_ms=0.0,
                search_results=None,
                best_match_score=None,
                ripgrep_found=True,
                status="fallback_found",
                is_false_negative=True,
            ),
            TestResult(
                log_message="msg4",
                victoria_timestamp="",
                victoria_stream={},
                search_found=False,
                search_response_time_ms=0.0,
                search_results=None,
                best_match_score=None,
                ripgrep_found=False,
                status="not_found",
                is_false_negative=False,
            ),
        ]

        metrics = TestMetrics.from_results(results, total_duration_seconds=10.0)

        assert metrics.total_logs == 4
        assert metrics.found_by_search == 2
        assert metrics.found_by_ripgrep_only == 1
        assert metrics.not_found == 1
        assert metrics.hit_rate == 0.5  # 2/4
        assert metrics.false_negative_rate == 0.25  # 1/4
        assert metrics.miss_rate == 0.25  # 1/4
        assert metrics.avg_response_time_ms == 150.0  # (100+200)/2
        assert abs(metrics.avg_match_score - 0.85) < 0.001  # (0.9+0.8)/2 with float tolerance

    def test_from_results_all_found(self) -> None:
        """Test metrics when all logs are found by search."""
        results = [
            TestResult(
                log_message=f"msg{i}",
                victoria_timestamp="",
                victoria_stream={},
                search_found=True,
                search_response_time_ms=float(i * 10),
                search_results=[],
                best_match_score=0.9,
                ripgrep_found=False,
                status="found",
                is_false_negative=False,
            )
            for i in range(1, 11)  # 10 results
        ]

        metrics = TestMetrics.from_results(results, total_duration_seconds=5.0)

        assert metrics.total_logs == 10
        assert metrics.found_by_search == 10
        assert metrics.found_by_ripgrep_only == 0
        assert metrics.not_found == 0
        assert metrics.hit_rate == 1.0
        assert metrics.false_negative_rate == 0.0
        assert metrics.miss_rate == 0.0

    def test_from_results_empty(self) -> None:
        """Test metrics with no results."""
        metrics = TestMetrics.from_results([], total_duration_seconds=1.0)

        assert metrics.total_logs == 0
        assert metrics.found_by_search == 0
        assert metrics.hit_rate == 0.0
        assert metrics.avg_response_time_ms == 0.0

    def test_percentiles(self) -> None:
        """Test percentile calculations."""
        # Create results with known response times: 10, 20, 30, ..., 100
        results = [
            TestResult(
                log_message=f"msg{i}",
                victoria_timestamp="",
                victoria_stream={},
                search_found=True,
                search_response_time_ms=float(i * 10),
                search_results=[],
                best_match_score=0.9,
                ripgrep_found=False,
                status="found",
                is_false_negative=False,
            )
            for i in range(1, 11)  # 10, 20, 30, ..., 100
        ]

        metrics = TestMetrics.from_results(results, total_duration_seconds=1.0)

        assert metrics.min_response_time_ms == 10.0
        assert metrics.max_response_time_ms == 100.0
        assert metrics.p50_response_time_ms == statistics.median([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])

    def test_to_dict(self) -> None:
        """Test converting metrics to dict."""
        metrics = TestMetrics(
            total_logs=100,
            found_by_search=80,
            found_by_ripgrep_only=15,
            not_found=5,
            hit_rate=0.8,
            false_negative_rate=0.15,
            miss_rate=0.05,
            avg_response_time_ms=45.0,
            p50_response_time_ms=40.0,
            p95_response_time_ms=90.0,
            p99_response_time_ms=150.0,
            min_response_time_ms=10.0,
            max_response_time_ms=200.0,
            avg_match_score=0.85,
            total_duration_seconds=60.0,
        )

        data = metrics.to_dict()

        assert data["total_logs"] == 100
        assert data["hit_rate"] == 0.8
        assert data["avg_response_time_ms"] == 45.0
        assert "p50_response_time_ms" in data
        assert "total_duration_seconds" in data
