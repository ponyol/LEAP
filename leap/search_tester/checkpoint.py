"""
Checkpoint management for resuming interrupted tests.

This module provides checkpoint save/load functionality to resume
tests that were interrupted (Ctrl+C, crashes, etc.).
"""

import json
from pathlib import Path
from typing import Any

from leap.search_tester.models import TestResult
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class TestCheckpoint:
    """
    Manages checkpoint data for resuming interrupted tests.

    The checkpoint stores:
    - Test configuration
    - Completed log indices
    - Partial results

    Example:
        >>> checkpoint = TestCheckpoint(Path(".checkpoint.json"))
        >>> checkpoint.add_result(0, test_result)
        >>> checkpoint.save()
        >>>
        >>> # Later...
        >>> checkpoint = TestCheckpoint.load(Path(".checkpoint.json"))
        >>> if checkpoint.is_completed(5):
        ...     print("Log 5 already tested")
    """

    def __init__(
        self,
        checkpoint_file: Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize checkpoint.

        Args:
            checkpoint_file: Path to checkpoint JSON file
            metadata: Test configuration metadata
        """
        self.checkpoint_file = checkpoint_file
        self.metadata = metadata or {}
        self.completed_indices: set[int] = set()
        self.partial_results: dict[int, TestResult] = {}

    def add_result(self, index: int, result: TestResult) -> None:
        """
        Add a completed test result.

        Args:
            index: Log index
            result: Test result
        """
        self.completed_indices.add(index)
        self.partial_results[index] = result

    def is_completed(self, index: int) -> bool:
        """
        Check if a log index has been tested.

        Args:
            index: Log index

        Returns:
            True if already tested
        """
        return index in self.completed_indices

    def get_result(self, index: int) -> TestResult | None:
        """
        Get result for a specific index.

        Args:
            index: Log index

        Returns:
            TestResult if exists, None otherwise
        """
        return self.partial_results.get(index)

    def save(self) -> None:
        """
        Save checkpoint to disk.

        The checkpoint file is saved as JSON with metadata and results.
        """
        try:
            data = {
                "metadata": self.metadata,
                "completed_indices": list(self.completed_indices),
                "partial_results": {
                    str(idx): result.to_dict()
                    for idx, result in self.partial_results.items()
                },
            }

            # Write atomically (write to temp file, then rename)
            temp_file = self.checkpoint_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.checkpoint_file)

            logger.debug(
                f"Checkpoint saved: {len(self.completed_indices)} results",
                extra={"checkpoint_file": str(self.checkpoint_file)},
            )

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            raise

    @classmethod
    def load(cls, checkpoint_file: Path) -> "TestCheckpoint":
        """
        Load checkpoint from disk.

        Args:
            checkpoint_file: Path to checkpoint JSON file

        Returns:
            TestCheckpoint instance

        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
            ValueError: If checkpoint file is invalid

        Example:
            >>> checkpoint = TestCheckpoint.load(Path(".checkpoint.json"))
            >>> print(f"Resuming from {len(checkpoint.completed_indices)} results")
        """
        if not checkpoint_file.exists():
            raise FileNotFoundError(
                f"Checkpoint file not found: {checkpoint_file}"
            )

        try:
            with open(checkpoint_file, encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = cls(
                checkpoint_file=checkpoint_file,
                metadata=data.get("metadata", {}),
            )

            checkpoint.completed_indices = set(
                data.get("completed_indices", [])
            )

            # Restore partial results
            partial_results_data = data.get("partial_results", {})
            for idx_str, result_data in partial_results_data.items():
                idx = int(idx_str)
                result = TestResult.from_dict(result_data)
                checkpoint.partial_results[idx] = result

            logger.info(
                f"Checkpoint loaded: {len(checkpoint.completed_indices)} completed",
                extra={"checkpoint_file": str(checkpoint_file)},
            )

            return checkpoint

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            raise ValueError(f"Invalid checkpoint file: {e}") from e

    def delete(self) -> None:
        """
        Delete checkpoint file.

        Call this after successfully completing all tests.
        """
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
                logger.debug(
                    "Checkpoint deleted",
                    extra={"checkpoint_file": str(self.checkpoint_file)},
                )
        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")

    def progress(self) -> float:
        """
        Get progress percentage (0.0 - 1.0).

        Note: This requires knowing the total number of logs,
        which should be stored in metadata.

        Returns:
            Progress as float (0.0 - 1.0)
        """
        total = int(self.metadata.get("total_logs", 0))
        if total == 0:
            return 0.0

        return len(self.completed_indices) / total

    def __len__(self) -> int:
        """Return number of completed tests."""
        return len(self.completed_indices)

    def __contains__(self, index: int) -> bool:
        """Check if index is completed (supports 'in' operator)."""
        return self.is_completed(index)
