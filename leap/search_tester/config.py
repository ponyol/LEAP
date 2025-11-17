"""
Configuration for LEAP Search Tester.

This module defines the configuration schema for the search testing command.
"""

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchTesterConfig(BaseModel):
    """
    Configuration for search quality testing.

    All parameters are validated using Pydantic to ensure type safety
    and provide clear error messages for invalid inputs.
    """

    # VictoriaLogs settings
    victoria_url: HttpUrl = Field(
        ...,
        description="VictoriaLogs API endpoint URL",
        examples=["http://localhost:9428", "https://victoria.example.com:9428"],
    )

    query: str = Field(
        ...,
        min_length=1,
        description="LogsQL query to fetch logs",
        examples=[
            '_stream:{namespace="app"} AND error',
            '_msg:~"database|timeout" AND level:error',
        ],
    )

    # Search backend settings
    search_url: HttpUrl = Field(
        ...,
        description="LEAP search backend URL",
        examples=["http://localhost:8000", "https://search.example.com"],
    )

    codebase: str | None = Field(
        None,
        description="Codebase name to filter search results",
        examples=["backend-python", "frontend-react"],
    )

    # Source code settings
    source_path: Path = Field(
        ...,
        description="Path to source code for ripgrep fallback",
    )

    # Query parameters
    limit: int = Field(
        100,
        ge=1,
        le=10000,
        description="Maximum number of logs to test",
    )

    start_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ),
        description="Query start time (RFC3339)",
    )

    end_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(
            hour=23, minute=59, second=59, microsecond=999999
        ),
        description="Query end time (RFC3339)",
    )

    # Performance settings
    concurrency: int = Field(
        5,
        ge=1,
        le=50,
        description="Maximum concurrent search requests",
    )

    timeout: int = Field(
        30,
        ge=5,
        le=300,
        description="Request timeout in seconds",
    )

    # Output settings
    output: Path = Field(
        Path("test_results.json"),
        description="JSON output file path",
    )

    report: Path = Field(
        Path("test_report.md"),
        description="Markdown report file path",
    )

    csv: Path = Field(
        Path("test_metrics.csv"),
        description="CSV metrics file path",
    )

    # Resume capability
    resume: bool = Field(
        False,
        description="Resume from checkpoint if available",
    )

    checkpoint_file: Path = Field(
        Path(".leap_test_checkpoint.json"),
        description="Checkpoint file for resume",
    )

    # Logging
    verbose: bool = Field(
        False,
        description="Enable verbose debug logging",
    )

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, v: Path) -> Path:
        """Validate that source path exists and is a directory."""
        if not v.exists():
            raise ValueError(f"Source path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Source path is not a directory: {v}")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_timezone(cls, v: datetime) -> datetime:
        """Ensure datetime has timezone info."""
        if v.tzinfo is None:
            # Assume UTC if no timezone
            return v.replace(tzinfo=timezone.utc)
        return v

    def get_start_date_rfc3339(self) -> str:
        """Get start date in RFC3339 format for VictoriaLogs."""
        return self.start_date.isoformat()

    def get_end_date_rfc3339(self) -> str:
        """Get end date in RFC3339 format for VictoriaLogs."""
        return self.end_date.isoformat()

    class Config:
        """Pydantic configuration."""

        # Allow arbitrary types (Path, HttpUrl)
        arbitrary_types_allowed = True
