"""
Data schemas for LEAP log entries.

This module defines the standardized format for extracted log statements
as specified in TechnicalSpecification.md section 5.1.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RawLogEntry(BaseModel):
    """
    Represents a single extracted log statement from source code.

    This is the core output format produced by all language parsers
    and aggregated into raw_logs.json.

    Attributes:
        language: The source language (python, go, ruby, javascript, typescript)
        file_path: Relative path to the source file
        line_number: Line number where the log statement appears
        log_level: The log level (debug, info, warn, error, fatal), if discernible
        log_template: The actual log message template (may include variables)
        code_context: Surrounding code block (function/if-statement) for LLM analysis
    """

    language: Literal["python", "go", "ruby", "javascript", "typescript"]
    file_path: str = Field(..., min_length=1, description="Relative path to source file")
    line_number: int = Field(..., gt=0, description="Line number (1-indexed)")
    log_level: str | None = Field(
        default=None, description="Log level if discernible (debug/info/warn/error/fatal)"
    )
    log_template: str = Field(..., min_length=1, description="The log message template")
    code_context: str = Field(
        ..., min_length=1, description="Surrounding code block for context"
    )

    model_config = ConfigDict(
        frozen=True,  # Immutable (FP principle)
        str_strip_whitespace=False,  # Preserve code formatting
    )


class AnalyzedLogEntry(BaseModel):
    """
    Represents an analyzed log entry with LLM-generated explanation.

    This is the output format of the analyzer component (leap-analyzer),
    as specified in TechnicalSpecification.md section 5.2.

    NOTE: This schema is defined here for completeness but will be used
    by the analyzer component, not the extractor.

    Attributes:
        log_template: The log message template
        analysis: LLM-generated explanation of why this log occurs
        language: Source language
        source_file: File path and line number (format: "path/to/file.py:42")
    """

    log_template: str = Field(..., min_length=1)
    analysis: str = Field(..., min_length=1, description="LLM-generated explanation")
    language: Literal["python", "go", "ruby", "javascript", "typescript"]
    source_file: str = Field(
        ..., pattern=r"^.+:\d+$", description="Format: 'path/to/file.py:42'"
    )

    model_config = ConfigDict(
        frozen=True,  # Immutable (FP principle)
    )
