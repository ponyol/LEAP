"""Tests for core.aggregator module."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from leap.core.aggregator import aggregate_results, load_raw_logs, merge_results
from leap.schemas import RawLogEntry


class TestAggregateResults:
    """Tests for aggregate_results function."""

    @pytest.fixture
    def sample_entries(self) -> list[RawLogEntry]:
        """Create sample log entries for testing."""
        return [
            RawLogEntry(
                language="python",
                file_path="/app/main.py",
                line_number=10,
                log_level="INFO",
                log_template="Application started",
                code_context='def main():\n    logger.info("Application started")',
            ),
            RawLogEntry(
                language="python",
                file_path="/app/db.py",
                line_number=25,
                log_level="ERROR",
                log_template="Database connection failed",
                code_context='def connect():\n    logger.error("Database connection failed")',
            ),
        ]

    def test_aggregate_basic(
        self, tmp_path: Path, sample_entries: list[RawLogEntry]
    ) -> None:
        """Test basic aggregation and file writing."""
        output_file = tmp_path / "raw_logs.json"

        aggregate_results(sample_entries, output_file)

        # File should exist
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["file_path"] == "/app/main.py"
        assert data[0]["line_number"] == 10
        assert data[1]["file_path"] == "/app/db.py"

    def test_aggregate_creates_parent_directories(
        self, tmp_path: Path, sample_entries: list[RawLogEntry]
    ) -> None:
        """Test that aggregate creates parent directories if needed."""
        output_file = tmp_path / "nested" / "path" / "raw_logs.json"

        aggregate_results(sample_entries, output_file)

        assert output_file.exists()
        assert output_file.parent.exists()

    def test_aggregate_empty_list(self, tmp_path: Path) -> None:
        """Test aggregating empty list of entries."""
        output_file = tmp_path / "raw_logs.json"

        aggregate_results([], output_file)

        # File should exist with empty array
        with open(output_file) as f:
            data = json.load(f)

        assert data == []

    def test_aggregate_overwrites_existing(
        self, tmp_path: Path, sample_entries: list[RawLogEntry]
    ) -> None:
        """Test that aggregate overwrites existing file."""
        output_file = tmp_path / "raw_logs.json"

        # Write first time
        aggregate_results([sample_entries[0]], output_file)

        # Write again with different data
        aggregate_results([sample_entries[1]], output_file)

        # Should only have second entry
        with open(output_file) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["file_path"] == "/app/db.py"


class TestLoadRawLogs:
    """Tests for load_raw_logs function."""

    def test_load_valid_file(self, tmp_path: Path) -> None:
        """Test loading valid raw_logs.json file."""
        input_file = tmp_path / "raw_logs.json"

        # Create test file
        data = [
            {
                "language": "python",
                "file_path": "/app/main.py",
                "line_number": 10,
                "log_level": "INFO",
                "log_template": "test",
                "code_context": "def test(): pass",
            },
        ]

        with open(input_file, "w") as f:
            json.dump(data, f)

        # Load
        entries = load_raw_logs(input_file)

        assert len(entries) == 1
        assert entries[0].file_path == "/app/main.py"
        assert entries[0].line_number == 10

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading file that doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_raw_logs(nonexistent)

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading file with invalid JSON."""
        input_file = tmp_path / "invalid.json"
        input_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            load_raw_logs(input_file)

    def test_load_empty_array(self, tmp_path: Path) -> None:
        """Test loading file with empty array."""
        input_file = tmp_path / "raw_logs.json"
        input_file.write_text("[]")

        entries = load_raw_logs(input_file)

        assert entries == []


class TestMergeResults:
    """Tests for merge_results function."""

    def test_merge_with_existing(self, tmp_path: Path) -> None:
        """Test merging new entries with existing file."""
        existing_file = tmp_path / "raw_logs.json"

        # Create existing file
        existing_data = [
            {
                "language": "python",
                "file_path": "/app/old.py",
                "line_number": 5,
                "log_level": "INFO",
                "log_template": "old",
                "code_context": "# old",
            },
        ]

        with open(existing_file, "w") as f:
            json.dump(existing_data, f)

        # New entries
        new_entries = [
            RawLogEntry(
                language="python",
                file_path="/app/new.py",
                line_number=10,
                log_level="INFO",
                log_template="new",
                code_context="# new",
            ),
        ]

        # Merge
        merged = merge_results(existing_file, new_entries)

        assert len(merged) == 2
        assert merged[0].file_path == "/app/old.py"
        assert merged[1].file_path == "/app/new.py"

    def test_merge_no_existing_file(self, tmp_path: Path) -> None:
        """Test merging when existing file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"

        new_entries = [
            RawLogEntry(
                language="python",
                file_path="/app/new.py",
                line_number=10,
                log_level="INFO",
                log_template="new",
                code_context="# new",
            ),
        ]

        merged = merge_results(nonexistent, new_entries)

        # Should return only new entries
        assert len(merged) == 1
        assert merged[0].file_path == "/app/new.py"

    def test_merge_with_empty_new_entries(self, tmp_path: Path) -> None:
        """Test merging with empty new entries list."""
        existing_file = tmp_path / "raw_logs.json"

        existing_data = [
            {
                "language": "python",
                "file_path": "/app/old.py",
                "line_number": 5,
                "log_level": "INFO",
                "log_template": "old",
                "code_context": "# old",
            },
        ]

        with open(existing_file, "w") as f:
            json.dump(existing_data, f)

        merged = merge_results(existing_file, [])

        # Should return existing entries
        assert len(merged) == 1
        assert merged[0].file_path == "/app/old.py"

    def test_merge_with_invalid_existing_file(self, tmp_path: Path) -> None:
        """Test merging when existing file is invalid (falls back to new entries)."""
        existing_file = tmp_path / "raw_logs.json"
        existing_file.write_text("{ invalid json }")

        new_entries = [
            RawLogEntry(
                language="python",
                file_path="/app/new.py",
                line_number=10,
                log_level="INFO",
                log_template="new",
                code_context="# new",
            ),
        ]

        # Should not raise, just use new entries
        merged = merge_results(existing_file, new_entries)

        assert len(merged) == 1
        assert merged[0].file_path == "/app/new.py"
