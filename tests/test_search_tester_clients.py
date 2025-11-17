"""Tests for search_tester client modules using mocks."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from leap.search_tester.search_client import SearchBackendClient
from leap.search_tester.victoria_client import VictoriaLogsClient


class TestVictoriaLogsClient:
    """Tests for VictoriaLogsClient with mocks."""

    @pytest.mark.asyncio
    async def test_query_logs_success(self) -> None:
        """Test successful log query."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock httpx response
        mock_response = MagicMock()
        mock_response.text = '{"_msg":"test log","_time":"2025-11-17T10:00:00Z","_stream":{}}\n'

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            logs = await client.query_logs(
                query="test",
                start="2025-11-17T00:00:00Z",
                end="2025-11-17T23:59:59Z",
                limit=100,
            )

        assert len(logs) == 1
        assert logs[0].msg == "test log"

    @pytest.mark.asyncio
    async def test_query_logs_empty_response(self) -> None:
        """Test query with empty response."""
        client = VictoriaLogsClient("http://localhost:9428")

        mock_response = MagicMock()
        mock_response.text = ""

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            logs = await client.query_logs(
                query="test",
                start="2025-11-17T00:00:00Z",
                end="2025-11-17T23:59:59Z",
                limit=100,
            )

        assert logs == []

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        """Test closing client."""
        client = VictoriaLogsClient("http://localhost:9428")

        with patch.object(client.client, "aclose", new=AsyncMock()) as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test using client as async context manager."""
        async with VictoriaLogsClient("http://localhost:9428") as client:
            assert client is not None
            assert isinstance(client, VictoriaLogsClient)

    @pytest.mark.asyncio
    async def test_query_logs_http_error(self) -> None:
        """Test query with HTTP error response."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(httpx.HTTPStatusError):
                await client.query_logs(
                    query="test", start="2025-11-17T00:00:00Z", end="2025-11-17T23:59:59Z", limit=100
                )

    @pytest.mark.asyncio
    async def test_query_logs_invalid_json_line(self) -> None:
        """Test query with invalid JSON in response."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock response with one valid and one invalid JSON line
        mock_response = MagicMock()
        mock_response.text = (
            '{"_msg":"valid log","_time":"2025-11-17T10:00:00Z","_stream":{}}\n'
            '{invalid json here}\n'
            '{"_msg":"another valid","_time":"2025-11-17T11:00:00Z","_stream":{}}'
        )

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            logs = await client.query_logs(
                query="test", start="2025-11-17T00:00:00Z", end="2025-11-17T23:59:59Z", limit=100
            )

        # Should skip the invalid line and return 2 valid logs
        assert len(logs) == 2
        assert logs[0].msg == "valid log"
        assert logs[1].msg == "another valid"

    @pytest.mark.asyncio
    async def test_query_logs_with_empty_lines(self) -> None:
        """Test query with empty lines in response."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock response with empty lines
        mock_response = MagicMock()
        mock_response.text = (
            '{"_msg":"log 1","_time":"2025-11-17T10:00:00Z","_stream":{}}\n'
            '\n'
            '{"_msg":"log 2","_time":"2025-11-17T11:00:00Z","_stream":{}}\n'
            '   \n'
        )

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            logs = await client.query_logs(
                query="test", start="2025-11-17T00:00:00Z", end="2025-11-17T23:59:59Z", limit=100
            )

        # Should skip empty lines and return 2 logs
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock healthy response
        mock_response = MagicMock()

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test health check with exception."""
        client = VictoriaLogsClient("http://localhost:9428")

        # Mock network error
        with patch.object(
            client.client, "get", new=AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        ):
            result = await client.health_check()

        assert result is False


class TestSearchBackendClient:
    """Tests for SearchBackendClient with mocks."""

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        """Test successful search."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total": 5,
            "results": [
                {"id": "1", "text": "match 1", "score": 0.9},
                {"id": "2", "text": "match 2", "score": 0.8},
            ],
        }

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            response = await client.search("test query", top_k=5)

        # Client uses len(results), not API's "total" field
        assert response.total_found == 2
        assert len(response.results) == 2
        assert response.search_time_ms > 0

    @pytest.mark.asyncio
    async def test_search_empty_results(self) -> None:
        """Test search with no results."""
        client = SearchBackendClient("http://localhost:8000")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total": 0,
            "results": [],
        }

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            response = await client.search("no match", top_k=5)

        assert response.total_found == 0
        assert response.results == []

    @pytest.mark.asyncio
    async def test_search_with_codebase(self) -> None:
        """Test search with codebase filter."""
        client = SearchBackendClient("http://localhost:8000")

        mock_response = MagicMock()
        mock_response.json.return_value = {"total": 1, "results": []}

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.search("test", top_k=5, codebase="my-backend")

            # Verify codebase was passed
            call_args = mock_post.call_args
            assert call_args[1]["json"]["codebase"] == "my-backend"

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        """Test closing client."""
        client = SearchBackendClient("http://localhost:8000")

        with patch.object(client.client, "aclose", new=AsyncMock()) as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test using client as async context manager."""
        async with SearchBackendClient("http://localhost:8000") as client:
            assert client is not None
            assert isinstance(client, SearchBackendClient)

    @pytest.mark.asyncio
    async def test_search_http_error(self) -> None:
        """Test search with HTTP error response."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(httpx.HTTPStatusError):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_search_invalid_json_response(self) -> None:
        """Test search with invalid JSON response."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(client.client, "post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(ValueError, match="Invalid JSON response"):
                await client.search("test query")

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock healthy response
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self) -> None:
        """Test health check with non-ok status."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock unhealthy response
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "degraded"}

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test health check with exception."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock network error
        with patch.object(
            client.client, "get", new=AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        ):
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_list_codebases_success(self) -> None:
        """Test successful codebases listing."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "codebases": [
                {"name": "backend", "total_logs": 1000},
                {"name": "frontend", "total_logs": 500},
            ]
        }

        with patch.object(client.client, "get", new=AsyncMock(return_value=mock_response)):
            codebases = await client.list_codebases()

        assert len(codebases) == 2
        assert codebases[0]["name"] == "backend"
        assert codebases[1]["name"] == "frontend"

    @pytest.mark.asyncio
    async def test_list_codebases_failure(self) -> None:
        """Test codebases listing with error."""
        client = SearchBackendClient("http://localhost:8000")

        # Mock network error
        with patch.object(
            client.client, "get", new=AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        ):
            with pytest.raises(httpx.ConnectError):
                await client.list_codebases()
