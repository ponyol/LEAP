"""
Result aggregation for LEAP.

This module aggregates log entries from multiple parsers and generates
the standardized raw_logs.json output file.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from leap.schemas import RawLogEntry
from leap.utils.logger import get_logger

logger = get_logger(__name__)


def aggregate_results(
    log_entries: list[RawLogEntry], output_path: Path, validate: bool = True
) -> None:
    """
    Aggregate log entries and write to raw_logs.json.

    Args:
        log_entries: List of all extracted log entries from all parsers
        output_path: Path where raw_logs.json should be written
        validate: Whether to validate entries before writing (default: True)

    Raises:
        ValidationError: If validate=True and any entry is invalid
        OSError: If unable to write to output_path
    """
    if validate:
        _validate_entries(log_entries)

    # Convert to JSON-serializable format
    data = [entry.model_dump(mode="json") for entry in log_entries]

    # Write to file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Successfully wrote {len(log_entries)} log entries to {output_path}",
            extra={"context": {"output_path": str(output_path), "entry_count": len(log_entries)}},
        )

    except OSError as e:
        logger.error(
            f"Failed to write output file: {e}",
            extra={"context": {"output_path": str(output_path), "error": str(e)}},
        )
        raise


def load_raw_logs(input_path: Path) -> list[RawLogEntry]:
    """
    Load and validate raw_logs.json file.

    This is useful for downstream components (analyzer, indexer) that
    consume the raw_logs.json output.

    Args:
        input_path: Path to raw_logs.json file

    Returns:
        List of validated RawLogEntry objects

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValidationError: If file contains invalid entries
        json.JSONDecodeError: If file is not valid JSON
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValidationError("Expected JSON array at root level")

    # Parse and validate each entry
    entries = [RawLogEntry(**item) for item in data]

    logger.info(
        f"Loaded {len(entries)} log entries from {input_path}",
        extra={"context": {"input_path": str(input_path), "entry_count": len(entries)}},
    )

    return entries


def merge_results(existing_path: Path, new_entries: list[RawLogEntry]) -> list[RawLogEntry]:
    """
    Merge new log entries with existing raw_logs.json.

    This is useful for incremental updates where we want to add newly
    discovered logs to an existing output file.

    Args:
        existing_path: Path to existing raw_logs.json
        new_entries: New entries to merge

    Returns:
        Combined list of all entries (existing + new)

    NOTE: This performs simple concatenation. Duplicate detection
    (same file/line) is left to downstream components.
    """
    if not existing_path.exists():
        logger.info("No existing file found, using only new entries")
        return new_entries

    try:
        existing_entries = load_raw_logs(existing_path)
        merged = existing_entries + new_entries

        logger.info(
            f"Merged {len(existing_entries)} existing + {len(new_entries)} new = {len(merged)} total entries",
            extra={
                "context": {
                    "existing_count": len(existing_entries),
                    "new_count": len(new_entries),
                    "total_count": len(merged),
                }
            },
        )

        return merged

    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning(
            f"Failed to load existing file, using only new entries: {e}",
            extra={"context": {"existing_path": str(existing_path), "error": str(e)}},
        )
        return new_entries


def _validate_entries(entries: list[RawLogEntry]) -> None:
    """
    Validate a list of log entries.

    Args:
        entries: List of entries to validate

    Raises:
        ValidationError: If any entry is invalid
    """
    for i, entry in enumerate(entries):
        try:
            # Pydantic models are already validated on construction,
            # but we can do additional checks here if needed
            if not entry.file_path:
                raise ValidationError(f"Entry {i}: file_path is empty")
            if entry.line_number <= 0:
                raise ValidationError(f"Entry {i}: invalid line_number {entry.line_number}")
        except Exception as e:
            logger.error(
                f"Validation failed for entry {i}: {e}",
                extra={"context": {"entry_index": i, "error": str(e)}},
            )
            raise
