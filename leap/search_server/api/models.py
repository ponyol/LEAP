"""Pydantic models for API requests and responses.

This module defines the data models used by the search server API.
"""

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search request model.

    Attributes:
        query: Search query text
        codebase: Optional codebase name to filter by
        language: Language filter (auto, ru, en)
        top_k: Number of results to return
        filters: Optional metadata filters
    """

    query: str = Field(
        ...,
        description="Search query text",
        min_length=1,
    )
    codebase: str | None = Field(
        default=None,
        description="Codebase name to filter by (e.g., 'backend-python')",
    )
    language: str = Field(
        default="auto",
        description="Language filter: 'auto', 'ru', or 'en'",
    )
    top_k: int = Field(
        default=5,
        description="Number of results to return",
        ge=1,
        le=100,
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filters (e.g., {'severity': ['ERROR', 'CRITICAL']})",
    )


class SearchResultItem(BaseModel):
    """A single search result item.

    Attributes:
        id: Document ID
        log_template: Original log template
        analysis: LLM analysis of the log
        severity: Log severity level
        source_file: Source file location
        codebase_name: Codebase name
        language: Language (ru/en)
        score: Similarity/relevance score
        metadata: Additional metadata
    """

    id: str = Field(description="Document ID")
    log_template: str = Field(description="Original log template")
    analysis: str = Field(description="LLM analysis of the log")
    severity: str = Field(description="Log severity level")
    source_file: str = Field(description="Source file location")
    codebase_name: str = Field(description="Codebase name")
    language: str = Field(description="Language (ru/en)")
    score: float = Field(description="Similarity/relevance score", ge=0.0, le=1.0)
    suggested_action: str = Field(default="", description="Suggested action for operators")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Search response model.

    Attributes:
        results: List of search results
        total_found: Total number of results found
        search_time_ms: Search time in milliseconds
    """

    results: list[SearchResultItem] = Field(
        default_factory=list,
        description="List of search results",
    )
    total_found: int = Field(
        description="Total number of results found",
        ge=0,
    )
    search_time_ms: float = Field(
        description="Search time in milliseconds",
        ge=0.0,
    )


class CodebaseInfo(BaseModel):
    """Information about a codebase.

    Attributes:
        name: Codebase name
        total_logs: Total number of logs
        ru_logs: Number of Russian logs
        en_logs: Number of English logs
        last_indexed: Last indexing timestamp (ISO format)
    """

    name: str = Field(description="Codebase name")
    total_logs: int = Field(description="Total number of logs", ge=0)
    ru_logs: int = Field(description="Number of Russian logs", ge=0)
    en_logs: int = Field(description="Number of English logs", ge=0)
    last_indexed: str | None = Field(
        default=None,
        description="Last indexing timestamp (ISO format)",
    )


class CodebasesResponse(BaseModel):
    """Response containing list of codebases.

    Attributes:
        codebases: List of codebase information
    """

    codebases: list[CodebaseInfo] = Field(
        default_factory=list,
        description="List of codebase information",
    )


class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Service status (ok, error)
        vector_store: Vector store type
        models_loaded: Whether models are loaded
    """

    status: str = Field(
        description="Service status (ok, error)",
    )
    vector_store: str = Field(
        description="Vector store type",
    )
    models_loaded: bool = Field(
        description="Whether models are loaded",
    )
