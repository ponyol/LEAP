"""
VictoriaLogs client for fetching logs.

This module provides an async HTTP client for querying VictoriaLogs API.
"""

import json

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from leap.search_tester.models import VictoriaLog
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class VictoriaLogsClient:
    """
    Async client for VictoriaLogs HTTP API.

    Supports querying logs with LogsQL queries and automatic retry logic
    for network errors.

    Example:
        >>> client = VictoriaLogsClient("http://localhost:9428")
        >>> logs = await client.query_logs(
        ...     query="error",
        ...     start="2025-11-17T00:00:00Z",
        ...     end="2025-11-17T23:59:59Z",
        ...     limit=100,
        ... )
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
    ) -> None:
        """
        Initialize VictoriaLogs client.

        Args:
            base_url: VictoriaLogs API base URL (e.g., http://localhost:9428)
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

    async def __aenter__(self) -> "VictoriaLogsClient":
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
    async def query_logs(
        self,
        query: str,
        start: str,
        end: str,
        limit: int,
    ) -> list[VictoriaLog]:
        """
        Query logs from VictoriaLogs using LogsQL.

        Automatically retries up to 4 times with exponential backoff
        on network errors (2s, 4s, 8s, 16s).

        Args:
            query: LogsQL query string (e.g., "_stream:{app='frontend'} AND error")
            start: Start time in RFC3339 format (e.g., "2025-11-17T00:00:00Z")
            end: End time in RFC3339 format (e.g., "2025-11-17T23:59:59Z")
            limit: Maximum number of logs to return

        Returns:
            List of VictoriaLog objects

        Raises:
            httpx.HTTPError: If the request fails after all retries
            httpx.TimeoutException: If the request times out after all retries
            ValueError: If the response format is invalid

        Example:
            >>> logs = await client.query_logs(
            ...     query='_stream:{namespace="app"} AND error',
            ...     start="2025-11-17T00:00:00Z",
            ...     end="2025-11-17T23:59:59Z",
            ...     limit=100,
            ... )
        """
        url = f"{self.base_url}/select/logsql/query"

        # Build query parameters
        params = {
            "query": query,
            "start": start,
            "end": end,
            "limit": str(limit),
        }

        logger.debug(
            f"Querying VictoriaLogs: {url}",
            extra={"query": query, "start": start, "end": end, "limit": limit},
        )

        # Make request (GET is default, but POST also supported)
        response = await self.client.get(url, params=params)

        # Check for errors
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"VictoriaLogs HTTP error: {e.response.status_code}",
                extra={"response_text": e.response.text[:500]},
            )
            raise

        # Parse response
        # VictoriaLogs returns JSONL (one JSON object per line)
        logs = []
        response_text = response.text.strip()

        if not response_text:
            logger.info("VictoriaLogs returned empty response")
            return []

        # Parse each line as JSON
        for line_num, line in enumerate(response_text.split("\n"), start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                log = VictoriaLog.from_json(data)
                logs.append(log)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON on line {line_num}: {e}",
                    extra={"line": line[:200]},
                )
                continue
            except Exception as e:
                logger.warning(
                    f"Failed to create VictoriaLog from line {line_num}: {e}",
                    extra={"line": line[:200]},
                )
                continue

        logger.info(
            f"Fetched {len(logs)} logs from VictoriaLogs",
            extra={"query": query, "limit": limit, "actual_count": len(logs)},
        )

        return logs

    async def health_check(self) -> bool:
        """
        Check if VictoriaLogs is reachable.

        Returns:
            True if VictoriaLogs responds to health check, False otherwise

        Example:
            >>> if await client.health_check():
            ...     print("VictoriaLogs is healthy")
        """
        try:
            # VictoriaLogs health endpoint
            url = f"{self.base_url}/health"
            response = await self.client.get(url, timeout=5.0)
            response.raise_for_status()
            logger.debug("VictoriaLogs health check passed")
            return True
        except Exception as e:
            logger.warning(f"VictoriaLogs health check failed: {e}")
            return False
