"""Tests for search_tester client modules using mocks."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
