"""Tests for search_tester.config module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from leap.search_tester.config import SearchTesterConfig


class TestSearchTesterConfig:
    """Tests for SearchTesterConfig model."""

    def test_minimal_valid_config(self, tmp_path: Path) -> None:
        """Test creating config with minimal required fields."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query='_stream:{namespace="app"}',
            search_url="http://localhost:8000",
            source_path=source_path,
        )

        assert str(config.victoria_url) == "http://localhost:9428/"
        assert config.query == '_stream:{namespace="app"}'
        assert str(config.search_url) == "http://localhost:8000/"
        assert config.source_path == source_path
        assert config.limit == 100  # default
        assert config.concurrency == 5  # default

    def test_full_config(self, tmp_path: Path) -> None:
        """Test creating config with all fields."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        start = datetime(2025, 11, 17, 0, 0, 0, tzinfo=UTC)
        end = datetime(2025, 11, 17, 23, 59, 59, tzinfo=UTC)

        config = SearchTesterConfig(
            victoria_url="https://victoria.example.com:9428",
            query='_msg:~"error|timeout"',
            search_url="https://search.example.com",
            codebase="my-backend",
            source_path=source_path,
            limit=500,
            start_date=start,
            end_date=end,
            concurrency=10,
            timeout=60,
            output=Path("results.json"),
            report=Path("report.md"),
            csv=Path("metrics.csv"),
            resume=True,
            checkpoint_file=Path(".checkpoint.json"),
            verbose=True,
        )

        assert config.codebase == "my-backend"
        assert config.limit == 500
        assert config.concurrency == 10
        assert config.timeout == 60
        assert config.resume is True
        assert config.verbose is True

    def test_invalid_victoria_url(self, tmp_path: Path) -> None:
        """Test validation fails with invalid VictoriaLogs URL."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        with pytest.raises(ValidationError) as exc_info:
            SearchTesterConfig(
                victoria_url="not-a-url",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
            )

        errors = exc_info.value.errors()
        assert any("victoria_url" in str(e) for e in errors)

    def test_invalid_search_url(self, tmp_path: Path) -> None:
        """Test validation fails with invalid search URL."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        with pytest.raises(ValidationError) as exc_info:
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="invalid-url",
                source_path=source_path,
            )

        errors = exc_info.value.errors()
        assert any("search_url" in str(e) for e in errors)

    def test_empty_query(self, tmp_path: Path) -> None:
        """Test validation fails with empty query."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        with pytest.raises(ValidationError) as exc_info:
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="",  # Empty query
                search_url="http://localhost:8000",
                source_path=source_path,
            )

        errors = exc_info.value.errors()
        assert any("query" in str(e) for e in errors)

    def test_source_path_not_exists(self) -> None:
        """Test validation fails when source path doesn't exist."""
        with pytest.raises(ValidationError) as exc_info:
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=Path("/nonexistent/path"),
            )

        errors = exc_info.value.errors()
        assert any("Source path does not exist" in str(e) for e in errors)

    def test_source_path_not_directory(self, tmp_path: Path) -> None:
        """Test validation fails when source path is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(ValidationError) as exc_info:
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=file_path,
            )

        errors = exc_info.value.errors()
        assert any("Source path is not a directory" in str(e) for e in errors)

    def test_limit_validation(self, tmp_path: Path) -> None:
        """Test limit must be within valid range."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        # Valid limits
        config1 = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            limit=1,  # minimum
        )
        assert config1.limit == 1

        config2 = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            limit=10000,  # maximum
        )
        assert config2.limit == 10000

        # Invalid: too small
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                limit=0,
            )

        # Invalid: too large
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                limit=20000,
            )

    def test_concurrency_validation(self, tmp_path: Path) -> None:
        """Test concurrency must be within valid range."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        # Valid
        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            concurrency=25,
        )
        assert config.concurrency == 25

        # Invalid: too small
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                concurrency=0,
            )

        # Invalid: too large
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                concurrency=100,
            )

    def test_timeout_validation(self, tmp_path: Path) -> None:
        """Test timeout must be within valid range."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        # Valid
        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            timeout=60,
        )
        assert config.timeout == 60

        # Invalid: too small
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                timeout=1,
            )

        # Invalid: too large
        with pytest.raises(ValidationError):
            SearchTesterConfig(
                victoria_url="http://localhost:9428",
                query="test",
                search_url="http://localhost:8000",
                source_path=source_path,
                timeout=500,
            )

    def test_default_dates(self, tmp_path: Path) -> None:
        """Test that default dates are set to today."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
        )

        # Check that start_date is today at 00:00:00
        assert config.start_date.hour == 0
        assert config.start_date.minute == 0
        assert config.start_date.second == 0

        # Check that end_date is today at 23:59:59
        assert config.end_date.hour == 23
        assert config.end_date.minute == 59
        assert config.end_date.second == 59

    def test_timezone_validation(self, tmp_path: Path) -> None:
        """Test that timezone is added to naive datetime."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        # Create naive datetime (no timezone)
        naive_dt = datetime(2025, 11, 17, 12, 0, 0)

        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            start_date=naive_dt,
            end_date=naive_dt,
        )

        # Should have UTC timezone added
        assert config.start_date.tzinfo == UTC
        assert config.end_date.tzinfo == UTC

    def test_rfc3339_formatting(self, tmp_path: Path) -> None:
        """Test RFC3339 date formatting for VictoriaLogs."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        start = datetime(2025, 11, 17, 10, 30, 0, tzinfo=UTC)
        end = datetime(2025, 11, 17, 20, 45, 30, tzinfo=UTC)

        config = SearchTesterConfig(
            victoria_url="http://localhost:9428",
            query="test",
            search_url="http://localhost:8000",
            source_path=source_path,
            start_date=start,
            end_date=end,
        )

        start_rfc3339 = config.get_start_date_rfc3339()
        end_rfc3339 = config.get_end_date_rfc3339()

        assert start_rfc3339 == "2025-11-17T10:30:00+00:00"
        assert end_rfc3339 == "2025-11-17T20:45:30+00:00"
