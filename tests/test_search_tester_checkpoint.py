"""Tests for search_tester.checkpoint module."""

import json
from pathlib import Path

import pytest

from leap.search_tester.checkpoint import TestCheckpoint
from leap.search_tester.models import TestResult


class TestTestCheckpoint:
    """Tests for TestCheckpoint class."""

    @pytest.fixture
    def checkpoint_file(self, tmp_path: Path) -> Path:
        """Create temporary checkpoint file path."""
        return tmp_path / "checkpoint.json"

    @pytest.fixture
    def sample_result(self) -> TestResult:
        """Create sample test result."""
        return TestResult(
            log_message="Test message",
            victoria_timestamp="2025-11-17T10:30:00Z",
            victoria_stream={"app": "test"},
            search_found=True,
            search_response_time_ms=50.0,
            search_results=[{"id": "1", "score": 0.9}],
            best_match_score=0.9,
            ripgrep_found=False,
            status="found",
            is_false_negative=False,
        )

    def test_create_checkpoint(self, checkpoint_file: Path) -> None:
        """Test creating new checkpoint."""
        metadata = {"victoria_url": "http://localhost:9428", "total_logs": 100}
        checkpoint = TestCheckpoint(checkpoint_file, metadata)

        assert checkpoint.checkpoint_file == checkpoint_file
        assert checkpoint.metadata == metadata
        assert len(checkpoint.completed_indices) == 0
        assert len(checkpoint.partial_results) == 0

    def test_save_empty_checkpoint(self, checkpoint_file: Path) -> None:
        """Test saving empty checkpoint."""
        metadata = {"test": "value"}
        checkpoint = TestCheckpoint(checkpoint_file, metadata)
        checkpoint.save()

        assert checkpoint_file.exists()

        # Verify content
        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["metadata"] == metadata
        assert data["completed_indices"] == []
        assert data["partial_results"] == {}

    def test_save_with_results(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test saving checkpoint with results."""
        metadata = {"total_logs": 10}
        checkpoint = TestCheckpoint(checkpoint_file, metadata)

        # Add some results
        checkpoint.add_result(0, sample_result)
        checkpoint.add_result(5, sample_result)
        checkpoint.save()

        # Verify content
        with open(checkpoint_file) as f:
            data = json.load(f)

        assert set(data["completed_indices"]) == {0, 5}
        assert "0" in data["partial_results"]
        assert "5" in data["partial_results"]

    def test_load_checkpoint(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test loading existing checkpoint."""
        # Create and save checkpoint
        metadata = {"total_logs": 10}
        checkpoint1 = TestCheckpoint(checkpoint_file, metadata)
        checkpoint1.add_result(0, sample_result)
        checkpoint1.add_result(3, sample_result)
        checkpoint1.save()

        # Load checkpoint
        checkpoint2 = TestCheckpoint.load(checkpoint_file)

        assert checkpoint2 is not None
        assert checkpoint2.metadata == metadata
        assert checkpoint2.completed_indices == {0, 3}
        assert len(checkpoint2.partial_results) == 2

    def test_load_nonexistent_checkpoint(self, tmp_path: Path) -> None:
        """Test loading checkpoint that doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            TestCheckpoint.load(nonexistent)

    def test_load_invalid_json(self, checkpoint_file: Path) -> None:
        """Test loading checkpoint with invalid JSON."""
        checkpoint_file.write_text("{ invalid json }")

        with pytest.raises(ValueError):
            TestCheckpoint.load(checkpoint_file)

    def test_add_result(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test adding result to checkpoint."""
        checkpoint = TestCheckpoint(checkpoint_file, {})

        checkpoint.add_result(5, sample_result)

        assert 5 in checkpoint.completed_indices
        assert checkpoint.partial_results[5] == sample_result

    def test_is_completed(self, checkpoint_file: Path) -> None:
        """Test checking if index is completed."""
        checkpoint = TestCheckpoint(checkpoint_file, {})
        result = TestResult(
            log_message="test",
            victoria_timestamp="",
            victoria_stream={},
            search_found=True,
            search_response_time_ms=10.0,
            search_results=[],
            best_match_score=0.9,
            ripgrep_found=False,
            status="found",
            is_false_negative=False,
        )

        assert not checkpoint.is_completed(0)

        checkpoint.add_result(0, result)

        assert checkpoint.is_completed(0)
        assert not checkpoint.is_completed(1)

    def test_len_checkpoint(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test __len__ returns number of completed tests."""
        checkpoint = TestCheckpoint(checkpoint_file, {})

        assert len(checkpoint) == 0

        checkpoint.add_result(0, sample_result)
        assert len(checkpoint) == 1

        checkpoint.add_result(5, sample_result)
        assert len(checkpoint) == 2

    def test_save_and_load_roundtrip(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test that save and load preserves all data."""
        metadata = {
            "victoria_url": "http://localhost:9428",
            "query": "test query",
            "total_logs": 100,
        }

        # Create, populate, and save
        checkpoint1 = TestCheckpoint(checkpoint_file, metadata)
        checkpoint1.add_result(0, sample_result)
        checkpoint1.add_result(10, sample_result)
        checkpoint1.add_result(99, sample_result)
        checkpoint1.save()

        # Load
        checkpoint2 = TestCheckpoint.load(checkpoint_file)

        # Verify everything matches
        assert checkpoint2 is not None
        assert checkpoint2.metadata == metadata
        assert checkpoint2.completed_indices == {0, 10, 99}
        assert len(checkpoint2.partial_results) == 3

        # Verify results are correctly deserialized
        assert checkpoint2.partial_results[0].log_message == sample_result.log_message
        assert checkpoint2.partial_results[0].status == sample_result.status

    def test_multiple_saves(
        self, checkpoint_file: Path, sample_result: TestResult
    ) -> None:
        """Test saving checkpoint multiple times (incremental saves)."""
        checkpoint = TestCheckpoint(checkpoint_file, {"total_logs": 5})

        # Save after adding first result
        checkpoint.add_result(0, sample_result)
        checkpoint.save()

        # Load and verify
        loaded1 = TestCheckpoint.load(checkpoint_file)
        assert loaded1 is not None
        assert len(loaded1) == 1

        # Add more results and save again
        checkpoint.add_result(1, sample_result)
        checkpoint.add_result(2, sample_result)
        checkpoint.save()

        # Load and verify
        loaded2 = TestCheckpoint.load(checkpoint_file)
        assert loaded2 is not None
        assert len(loaded2) == 3
        assert loaded2.completed_indices == {0, 1, 2}
