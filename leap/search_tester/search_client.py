"""
LEAP Search Backend client.

This module provides an async HTTP client for querying the LEAP search API.
"""

import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from leap.search_tester.models import SearchResponse
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class SearchBackendClient:
    """
    Async client for LEAP search backend API.

    Provides methods for searching logs with automatic retry logic
    and response time measurement.

    Example:
        >>> client = SearchBackendClient("http://localhost:8000")
        >>> response = await client.search(
        ...     query="database connection error",
        ...     top_k=5,
        ...     codebase="backend-python",
        ... )
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
    ) -> None:
        """
        Initialize search backend client.

        Args:
            base_url: Search backend base URL (e.g., http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "SearchBackendClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    @retry(
        retry=retry_if_exception_type(
            (httpx.HTTPError, httpx.TimeoutException)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    async def search(
        self,
        query: str,
        top_k: int = 5,
        codebase: str | None = None,
        language: str = "auto",
    ) -> SearchResponse:
        """
        Search for logs in LEAP backend.

        Automatically retries up to 4 times with exponential backoff
        on network errors (2s, 4s, 8s, 16s).

        Args:
            query: Log message or search query
            top_k: Number of results to return (default: 5)
            codebase: Optional codebase filter
            language: Language filter ('auto', 'ru', 'en', default: 'auto')

        Returns:
            SearchResponse with results and timing information

        Raises:
            httpx.HTTPError: If the request fails after all retries
            httpx.TimeoutException: If the request times out after all retries

        Example:
            >>> response = await client.search(
            ...     query="Failed to connect to database",
            ...     top_k=5,
            ...     codebase="backend-python",
            ... )
            >>> print(f"Found {response.total_found} results")
        """
        url = f"{self.base_url}/api/search"

        # Build request payload
        payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "language": language,
        }

        if codebase:
            payload["codebase"] = codebase

        logger.debug(
            f"Searching LEAP backend: {url}",
            extra={"query": query[:100], "top_k": top_k, "codebase": codebase},
        )

        # Measure response time
        start_time = time.time()

        # Make request
        response = await self.client.post(url, json=payload)

        response_time_ms = (time.time() - start_time) * 1000

        # Check for errors
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Search backend HTTP error: {e.response.status_code}",
                extra={"response_text": e.response.text[:500]},
            )
            raise

        # Parse response
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to parse search response: {e}")
            raise ValueError(f"Invalid JSON response: {e}") from e

        # Extract results
        results = data.get("results", [])
        total_found = data.get("total_found", len(results))

        logger.debug(
            f"Search completed in {response_time_ms:.1f}ms",
            extra={
                "query": query[:100],
                "total_found": total_found,
                "response_time_ms": response_time_ms,
            },
        )

        return SearchResponse(
            results=results,
            total_found=total_found,
            search_time_ms=response_time_ms,
        )

    async def health_check(self) -> bool:
        """
        Check if search backend is reachable.

        Returns:
            True if backend responds to health check, False otherwise

        Example:
            >>> if await client.health_check():
            ...     print("Search backend is healthy")
        """
        try:
            url = f"{self.base_url}/api/health"
            response = await self.client.get(url, timeout=5.0)
            response.raise_for_status()

            data = response.json()
            status = data.get("status", "").lower()

            if status == "ok":
                logger.debug("Search backend health check passed")
                return True
            else:
                logger.warning(f"Search backend health check returned: {status}")
                return False

        except Exception as e:
            logger.warning(f"Search backend health check failed: {e}")
            return False

    async def list_codebases(self) -> list[dict[str, Any]]:
        """
        List available codebases in the search backend.

        Returns:
            List of codebase information dictionaries

        Raises:
            httpx.HTTPError: If the request fails

        Example:
            >>> codebases = await client.list_codebases()
            >>> for cb in codebases:
            ...     print(f"{cb['name']}: {cb['total_logs']} logs")
        """
        url = f"{self.base_url}/api/codebases"

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            data = response.json()
            codebases = data.get("codebases", [])

            logger.debug(f"Found {len(codebases)} codebases in search backend")
            return codebases

        except Exception as e:
            logger.error(f"Failed to list codebases: {e}")
            raise
