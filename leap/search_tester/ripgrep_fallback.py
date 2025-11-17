"""
Ripgrep fallback for finding logs in source code.

This module provides intelligent fallback search using ripgrep when
logs are not found in the search backend.
"""

import asyncio
import json
import re
from pathlib import Path

from leap.search_tester.models import RipgrepMatch
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class RipgrepFallback:
    """
    Fallback search using ripgrep in source code.

    When a log is not found by the search backend, this class attempts
    to find it in the source code using ripgrep with intelligent keyword
    extraction and similarity scoring.

    Example:
        >>> fallback = RipgrepFallback(Path("/home/user/my-project"))
        >>> keywords = fallback.extract_keywords("Failed to connect timeout=30s")
        >>> matches = await fallback.search_in_code(keywords)
        >>> if matches:
        ...     similarity = fallback.calculate_similarity(
        ...         "Failed to connect timeout=30s",
        ...         matches[0].line_text
        ...     )
    """

    def __init__(self, source_path: Path, timeout: int = 10) -> None:
        """
        Initialize ripgrep fallback.

        Args:
            source_path: Path to source code directory
            timeout: Timeout for ripgrep commands in seconds (default: 10)
        """
        self.source_path = source_path
        self.timeout = timeout

        # Common stopwords to exclude
        self.stopwords = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "this",
            "that",
            "have",
            "has",
            "been",
            "will",
            "would",
            "could",
            "should",
        }

    def extract_keywords(self, log_message: str) -> list[str]:
        """
        Extract searchable keywords from log message.

        This function removes dynamic content (timestamps, IPs, UUIDs, etc.)
        and extracts meaningful keywords that can be used to search in code.

        Args:
            log_message: Original log message

        Returns:
            List of unique keywords (lowercase)

        Example:
            >>> keywords = fallback.extract_keywords(
            ...     "2025-11-17 10:30:00 Failed to connect to database timeout=30s"
            ... )
            >>> print(keywords)
            ['failed', 'connect', 'database', 'timeout']
        """
        text = log_message

        # 1. Remove timestamps (various formats)
        # ISO8601: 2025-11-17T10:30:00.123Z
        text = re.sub(
            r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?Z?", "", text
        )
        # Unix timestamps (10-13 digits)
        text = re.sub(r"\b\d{10,13}\b", "", text)
        # Date-only: 2025-11-17
        text = re.sub(r"\d{4}-\d{2}-\d{2}", "", text)
        # Time-only: 10:30:00
        text = re.sub(r"\d{2}:\d{2}:\d{2}", "", text)

        # 2. Remove IP addresses
        text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "", text)

        # 3. Remove UUIDs
        text = re.sub(
            r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # 4. Remove common numeric patterns (port numbers, IDs, etc.)
        # Keep numbers that are part of identifiers (e.g., "http2", "ipv4")
        text = re.sub(r"\b\d+\b", "", text)

        # 5. Remove common URL/path components
        text = re.sub(r"https?://[^\s]+", "", text)
        text = re.sub(r"/[a-zA-Z0-9/_.-]+", "", text)

        # 6. Extract words (alphanumeric + underscore)
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text)

        # 7. Also extract camelCase and snake_case patterns
        # CamelCase: DatabaseConnection -> ["database", "connection"]
        camel_case_words = []
        for word in words:
            # Split CamelCase
            parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", word)
            camel_case_words.extend(parts)

        words.extend(camel_case_words)

        # 8. Filter words
        keywords = []
        for word in words:
            word_lower = word.lower()

            # Skip short words (< 3 chars)
            if len(word_lower) < 3:
                continue

            # Skip stopwords
            if word_lower in self.stopwords:
                continue

            # Skip common log level names (they're too generic)
            if word_lower in {"info", "warn", "debug", "error", "trace"}:
                continue

            keywords.append(word_lower)

        # 9. Return unique keywords
        return list(dict.fromkeys(keywords))  # Preserves order

    async def search_in_code(
        self,
        keywords: list[str],
        max_results: int = 10,
    ) -> list[RipgrepMatch]:
        """
        Search for keywords in source code using ripgrep.

        Args:
            keywords: List of keywords to search
            max_results: Maximum matches to return per keyword

        Returns:
            List of RipgrepMatch objects

        Example:
            >>> keywords = ["failed", "connect", "database"]
            >>> matches = await fallback.search_in_code(keywords, max_results=5)
            >>> for match in matches:
            ...     print(f"{match.file_path}:{match.line_number}")
        """
        if not keywords:
            logger.debug("No keywords to search")
            return []

        # Build regex pattern: match lines containing ALL keywords (case-insensitive)
        # Use word boundaries to avoid partial matches
        # Example: (?=.*\bfailed\b)(?=.*\bconnect\b)(?=.*\bdatabase\b)
        pattern_parts = [f"(?=.*\\b{re.escape(kw)}\\b)" for kw in keywords]
        pattern = "".join(pattern_parts) + ".*"

        # Build ripgrep command
        cmd = [
            "rg",
            "--json",  # JSON output for easy parsing
            "--ignore-case",  # Case-insensitive search
            "--max-count",
            str(max_results),  # Limit results per file
            "--type-add",
            "code:*.{py,go,js,ts,rb,java,c,cpp,rs}",  # Common code extensions
            "--type",
            "code",  # Only search in code files
            pattern,
            str(self.source_path),
        ]

        logger.debug(
            f"Running ripgrep: {' '.join(cmd[:5])}...",
            extra={"keywords": keywords, "source_path": str(self.source_path)},
        )

        try:
            # Run ripgrep
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait with timeout
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )

            # Parse ripgrep JSON output
            matches = []
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue

                try:
                    data = json.loads(line)

                    # Only process "match" type entries
                    if data.get("type") == "match":
                        match = RipgrepMatch.from_ripgrep_json(data)
                        matches.append(match)

                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse ripgrep JSON line: {line[:100]}")
                    continue
                except Exception as e:
                    logger.debug(f"Failed to create RipgrepMatch: {e}")
                    continue

            logger.debug(
                f"Ripgrep found {len(matches)} matches",
                extra={"keywords": keywords, "match_count": len(matches)},
            )

            return matches

        except TimeoutError:
            logger.warning(
                f"Ripgrep timeout after {self.timeout}s",
                extra={"keywords": keywords},
            )
            return []

        except FileNotFoundError:
            logger.error("ripgrep (rg) not found in PATH. Please install ripgrep.")
            return []

        except Exception as e:
            logger.error(
                f"Ripgrep search failed: {e}",
                extra={"keywords": keywords},
            )
            return []

    def calculate_similarity(
        self,
        log_message: str,
        code_line: str,
    ) -> float:
        """
        Calculate similarity between log message and code line.

        Uses Jaccard similarity on word sets (intersection / union).

        Args:
            log_message: Original log message
            code_line: Line from source code

        Returns:
            Similarity score (0.0 - 1.0)

        Example:
            >>> similarity = fallback.calculate_similarity(
            ...     "Failed to connect to database",
            ...     "logger.error('Failed to connect to database server')"
            ... )
            >>> print(f"{similarity:.2f}")  # e.g., 0.80
        """
        # Extract words from both strings (length >= 3)
        log_words = set(
            re.findall(r"\b[a-zA-Z]{3,}\b", log_message.lower())
        )
        code_words = set(
            re.findall(r"\b[a-zA-Z]{3,}\b", code_line.lower())
        )

        if not log_words or not code_words:
            return 0.0

        # Jaccard similarity: |A ∩ B| / |A ∪ B|
        intersection = len(log_words & code_words)
        union = len(log_words | code_words)

        similarity = intersection / union if union > 0 else 0.0

        logger.debug(
            f"Similarity: {similarity:.3f}",
            extra={
                "log_words": len(log_words),
                "code_words": len(code_words),
                "intersection": intersection,
                "union": union,
            },
        )

        return similarity

    async def find_best_match(
        self,
        log_message: str,
        max_results: int = 10,
    ) -> tuple[RipgrepMatch | None, float]:
        """
        Find the best matching code line for a log message.

        Convenience method that combines keyword extraction, search,
        and similarity scoring.

        Args:
            log_message: Log message to search for
            max_results: Maximum ripgrep results to consider

        Returns:
            Tuple of (best_match, similarity_score) or (None, 0.0) if not found

        Example:
            >>> match, similarity = await fallback.find_best_match(
            ...     "Failed to connect to database timeout=30s"
            ... )
            >>> if match:
            ...     print(f"Found at {match.file_path}:{match.line_number}")
            ...     print(f"Similarity: {similarity:.2f}")
        """
        # Extract keywords
        keywords = self.extract_keywords(log_message)

        if not keywords:
            logger.debug("No keywords extracted from log message")
            return None, 0.0

        # Search in code
        matches = await self.search_in_code(keywords, max_results=max_results)

        if not matches:
            logger.debug("No matches found by ripgrep")
            return None, 0.0

        # Find best match by similarity
        best_match = None
        best_similarity = 0.0

        for match in matches:
            similarity = self.calculate_similarity(
                log_message,
                match.line_text,
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = match

        logger.debug(
            f"Best match similarity: {best_similarity:.3f}",
            extra={
                "file": best_match.file_path if best_match else None,
                "line": best_match.line_number if best_match else None,
            },
        )

        return best_match, best_similarity
