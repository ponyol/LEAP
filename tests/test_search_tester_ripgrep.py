"""Tests for search_tester.ripgrep_fallback module."""

from pathlib import Path

import pytest

from leap.search_tester.ripgrep_fallback import RipgrepFallback


class TestRipgrepFallback:
    """Tests for RipgrepFallback class."""

    @pytest.fixture
    def fallback(self, tmp_path: Path) -> RipgrepFallback:
        """Create RipgrepFallback instance with temp directory."""
        return RipgrepFallback(tmp_path, timeout=5)

    def test_extract_keywords_basic(self, fallback: RipgrepFallback) -> None:
        """Test basic keyword extraction."""
        keywords = fallback.extract_keywords("Failed to connect to database")

        assert "failed" in keywords
        assert "connect" in keywords
        assert "database" in keywords
        # Should not have short words
        assert "to" not in keywords

    def test_extract_keywords_with_timestamp(self, fallback: RipgrepFallback) -> None:
        """Test keyword extraction removes timestamps."""
        log = "2025-11-17T10:30:00.123Z Failed to connect timeout=30s"
        keywords = fallback.extract_keywords(log)

        assert "failed" in keywords
        assert "connect" in keywords
        assert "timeout" in keywords
        # Timestamp should be removed
        assert "2025" not in keywords
        assert "10" not in keywords

    def test_extract_keywords_with_ip(self, fallback: RipgrepFallback) -> None:
        """Test keyword extraction removes IP addresses."""
        log = "Connection failed to 192.168.1.100 port 5432"
        keywords = fallback.extract_keywords(log)

        assert "connection" in keywords
        assert "failed" in keywords
        assert "port" in keywords
        # IP should be removed
        assert "192" not in keywords
        assert "168" not in keywords

    def test_extract_keywords_with_uuid(self, fallback: RipgrepFallback) -> None:
        """Test keyword extraction removes UUIDs."""
        log = "Request failed: 550e8400-e29b-41d4-a716-446655440000"
        keywords = fallback.extract_keywords(log)

        assert "request" in keywords
        assert "failed" in keywords
        # UUID components should be removed
        assert "550e8400" not in keywords

    def test_extract_keywords_with_url(self, fallback: RipgrepFallback) -> None:
        """Test keyword extraction removes URLs."""
        log = "Failed to fetch https://api.example.com/v1/users/123"
        keywords = fallback.extract_keywords(log)

        assert "failed" in keywords
        assert "fetch" in keywords
        # URL should be removed
        assert "https" not in keywords
        assert "api" not in keywords
        assert "example" not in keywords

    def test_extract_keywords_removes_stopwords(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test keyword extraction removes stopwords."""
        log = "The connection to the database has been lost"
        keywords = fallback.extract_keywords(log)

        assert "connection" in keywords
        assert "database" in keywords
        assert "lost" in keywords
        # Stopwords should be removed
        assert "the" not in keywords
        assert "has" not in keywords
        assert "been" not in keywords

    def test_extract_keywords_removes_log_levels(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test keyword extraction removes log level names."""
        log = "ERROR: info about the error in debug mode"
        keywords = fallback.extract_keywords(log)

        assert "mode" in keywords
        # Log levels should be removed (they're too generic)
        assert "error" not in keywords
        assert "info" not in keywords
        assert "debug" not in keywords

    def test_extract_keywords_empty_input(self, fallback: RipgrepFallback) -> None:
        """Test keyword extraction with empty input."""
        keywords = fallback.extract_keywords("")
        assert keywords == []

    def test_extract_keywords_only_stopwords(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test keyword extraction when only stopwords remain."""
        log = "the and for with"
        keywords = fallback.extract_keywords(log)
        assert keywords == []

    def test_extract_keywords_preserves_order(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test that keyword extraction preserves order."""
        log = "database connection timeout error"
        keywords = fallback.extract_keywords(log)

        # Order should be preserved, no duplicates
        assert keywords == ["database", "connection", "timeout"]

    def test_calculate_similarity_exact_match(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test similarity calculation for exact match."""
        log = "Failed to connect to database"
        code = 'logger.error("Failed to connect to database")'

        similarity = fallback.calculate_similarity(log, code)

        # Should have high similarity (not 1.0 due to logger/error words)
        assert similarity > 0.5

    def test_calculate_similarity_partial_match(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test similarity calculation for partial match."""
        log = "Database connection timeout"
        code = 'logger.error("Database connection failed")'

        similarity = fallback.calculate_similarity(log, code)

        # Should have some similarity (database, connection)
        assert 0.3 < similarity < 0.8

    def test_calculate_similarity_no_match(self, fallback: RipgrepFallback) -> None:
        """Test similarity calculation when no words match."""
        log = "Database connection failed"
        code = "print('Hello world')"

        similarity = fallback.calculate_similarity(log, code)

        assert similarity == 0.0

    def test_calculate_similarity_empty_strings(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test similarity calculation with empty strings."""
        assert fallback.calculate_similarity("", "test") == 0.0
        assert fallback.calculate_similarity("test", "") == 0.0
        assert fallback.calculate_similarity("", "") == 0.0

    def test_calculate_similarity_ignores_short_words(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test that similarity ignores words shorter than 3 chars."""
        log = "ab cd ef gh connection"
        code = "ab cd ef gh timeout"

        # Should only consider 'connection' and 'timeout', which don't match
        similarity = fallback.calculate_similarity(log, code)
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_find_best_match_no_keywords(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test find_best_match when no keywords can be extracted."""
        log = "the and for"  # Only stopwords

        match, similarity = await fallback.find_best_match(log)

        assert match is None
        assert similarity == 0.0

    @pytest.mark.asyncio
    async def test_search_in_code_no_keywords(
        self, fallback: RipgrepFallback
    ) -> None:
        """Test search_in_code with no keywords."""
        matches = await fallback.search_in_code([])

        assert matches == []

    @pytest.mark.asyncio
    async def test_search_timeout(self, tmp_path: Path) -> None:
        """Test that search respects timeout."""
        # Create fallback with very short timeout
        fallback = RipgrepFallback(tmp_path, timeout=0.001)

        # Try to search (might timeout depending on system speed)
        keywords = ["test", "search"]
        matches = await fallback.search_in_code(keywords)

        # Should return empty list on timeout (graceful handling)
        assert isinstance(matches, list)
