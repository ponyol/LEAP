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
                file_path="/app/main.py",
                line_number=10,
                log_statement='logger.info("Application started")',
                log_level="INFO",
                log_message="Application started",
            ),
            RawLogEntry(
                file_path="/app/db.py",
                line_number=25,
                log_statement='logger.error("Database connection failed")',
                log_level="ERROR",
                log_message="Database connection failed",
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

    def test_aggregate_without_validation(
        self, tmp_path: Path, sample_entries: list[RawLogEntry]
    ) -> None:
        """Test aggregating without validation."""
        output_file = tmp_path / "raw_logs.json"

        aggregate_results(sample_entries, output_file, validate=False)

        assert output_file.exists()

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

    def test_aggregate_json_formatting(
        self, tmp_path: Path, sample_entries: list[RawLogEntry]
    ) -> None:
        """Test that output JSON is properly formatted."""
        output_file = tmp_path / "raw_logs.json"

        aggregate_results(sample_entries, output_file)

        # Read as text to check formatting
        content = output_file.read_text()

        # Should have indentation (pretty printed)
        assert "  " in content  # 2-space indent
        assert "\n" in content  # Newlines

    def test_aggregate_unicode_handling(self, tmp_path: Path) -> None:
        """Test that unicode characters are preserved."""
        entries = [
            RawLogEntry(
                file_path="/app/main.py",
                line_number=1,
                log_statement='logger.info("你好世界 🎉")',
                log_level="INFO",
                log_message="你好世界 🎉",
            ),
        ]

        output_file = tmp_path / "raw_logs.json"
        aggregate_results(entries, output_file)

        # Verify unicode is preserved (not escaped)
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "你好世界" in data[0]["log_message"]
        assert "🎉" in data[0]["log_message"]


class TestLoadRawLogs:
    """Tests for load_raw_logs function."""

    def test_load_valid_file(self, tmp_path: Path) -> None:
        """Test loading valid raw_logs.json file."""
        input_file = tmp_path / "raw_logs.json"

        # Create test file
        data = [
            {
                "file_path": "/app/main.py",
                "line_number": 10,
                "log_statement": 'logger.info("test")',
                "log_level": "INFO",
                "log_message": "test",
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

    def test_load_invalid_entry(self, tmp_path: Path) -> None:
        """Test loading file with invalid entry (missing required fields)."""
        input_file = tmp_path / "raw_logs.json"

        # Missing required fields
        data = [{"file_path": "/app/main.py"}]  # Missing line_number, etc.

        with open(input_file, "w") as f:
            json.dump(data, f)

        with pytest.raises(ValidationError):
            load_raw_logs(input_file)

    def test_load_preserves_all_fields(self, tmp_path: Path) -> None:
        """Test that loading preserves all entry fields."""
        input_file = tmp_path / "raw_logs.json"

        data = [
            {
                "file_path": "/app/main.py",
                "line_number": 10,
                "log_statement": 'logger.info("test", extra={"key": "value"})',
                "log_level": "INFO",
                "log_message": "test",
                "variables": {"key": "value"},
                "codebase": "my-app",
                "language": "python",
            },
        ]

        with open(input_file, "w") as f:
            json.dump(data, f)

        entries = load_raw_logs(input_file)

        assert entries[0].file_path == "/app/main.py"
        assert entries[0].variables == {"key": "value"}
        assert entries[0].codebase == "my-app"
        assert entries[0].language == "python"


class TestMergeResults:
    """Tests for merge_results function."""

    def test_merge_with_existing(self, tmp_path: Path) -> None:
        """Test merging new entries with existing file."""
        existing_file = tmp_path / "raw_logs.json"

        # Create existing file
        existing_data = [
            {
                "file_path": "/app/old.py",
                "line_number": 5,
                "log_statement": 'logger.info("old")',
                "log_level": "INFO",
                "log_message": "old",
            },
        ]

        with open(existing_file, "w") as f:
            json.dump(existing_data, f)

        # New entries
        new_entries = [
            RawLogEntry(
                file_path="/app/new.py",
                line_number=10,
                log_statement='logger.info("new")',
                log_level="INFO",
                log_message="new",
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
                file_path="/app/new.py",
                line_number=10,
                log_statement='logger.info("new")',
                log_level="INFO",
                log_message="new",
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
                "file_path": "/app/old.py",
                "line_number": 5,
                "log_statement": 'logger.info("old")',
                "log_level": "INFO",
                "log_message": "old",
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
                file_path="/app/new.py",
                line_number=10,
                log_statement='logger.info("new")',
                log_level="INFO",
                log_message="new",
            ),
        ]

        # Should not raise, just use new entries
        merged = merge_results(existing_file, new_entries)

        assert len(merged) == 1
        assert merged[0].file_path == "/app/new.py"

    def test_merge_preserves_order(self, tmp_path: Path) -> None:
        """Test that merge preserves order (existing first, then new)."""
        existing_file = tmp_path / "raw_logs.json"

        existing_data = [
            {
                "file_path": "/app/file1.py",
                "line_number": 1,
                "log_statement": "log1",
                "log_level": "INFO",
                "log_message": "msg1",
            },
            {
                "file_path": "/app/file2.py",
                "line_number": 2,
                "log_statement": "log2",
                "log_level": "INFO",
                "log_message": "msg2",
            },
        ]

        with open(existing_file, "w") as f:
            json.dump(existing_data, f)

        new_entries = [
            RawLogEntry(
                file_path="/app/file3.py",
                line_number=3,
                log_statement="log3",
                log_level="INFO",
                log_message="msg3",
            ),
        ]

        merged = merge_results(existing_file, new_entries)

        assert len(merged) == 3
        assert merged[0].file_path == "/app/file1.py"
        assert merged[1].file_path == "/app/file2.py"
        assert merged[2].file_path == "/app/file3.py"

    def test_merge_allows_duplicates(self, tmp_path: Path) -> None:
        """Test that merge allows duplicates (duplicate detection is downstream)."""
        existing_file = tmp_path / "raw_logs.json"

        # Same entry in both existing and new
        entry_data = {
            "file_path": "/app/main.py",
            "line_number": 10,
            "log_statement": "logger.info('test')",
            "log_level": "INFO",
            "log_message": "test",
        }

        with open(existing_file, "w") as f:
            json.dump([entry_data], f)

        new_entries = [RawLogEntry(**entry_data)]

        merged = merge_results(existing_file, new_entries)

        # Should have duplicate
        assert len(merged) == 2
        assert merged[0].file_path == merged[1].file_path
        assert merged[0].line_number == merged[1].line_number
