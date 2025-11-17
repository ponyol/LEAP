"""Tests for base parser functionality."""

from pathlib import Path

import pytest

from leap.parsers.base import BaseParser
from leap.schemas import RawLogEntry


class ConcreteParser(BaseParser):
    """Concrete implementation of BaseParser for testing."""

    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """Minimal implementation for testing."""
        return []

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """Return test extensions."""
        return {".test"}

    @staticmethod
    def get_language_name() -> str:
        """Return test language name."""
        return "test"


class TestBaseParser:
    """Tests for BaseParser abstract class."""

    def test_extract_code_context_basic(self) -> None:
        """Test basic code context extraction."""
        parser = ConcreteParser()
        source_lines = [
            "def foo():",
            "    x = 1",
            "    print(x)",
            "    return x",
        ]

        context = parser._extract_code_context(source_lines, 0, 4)

        assert context == "def foo():\n    x = 1\n    print(x)\n    return x"

    def test_extract_code_context_partial(self) -> None:
        """Test extracting a subset of lines."""
        parser = ConcreteParser()
        source_lines = [
            "line 1",
            "line 2",
            "line 3",
            "line 4",
            "line 5",
        ]

        context = parser._extract_code_context(source_lines, 1, 4)

        assert context == "line 2\nline 3\nline 4"

    def test_extract_code_context_single_line(self) -> None:
        """Test extracting a single line."""
        parser = ConcreteParser()
        source_lines = ["only line"]

        context = parser._extract_code_context(source_lines, 0, 1)

        assert context == "only line"

    def test_extract_code_context_empty_source(self) -> None:
        """Test extraction from empty source returns empty string."""
        parser = ConcreteParser()
        source_lines: list[str] = []

        context = parser._extract_code_context(source_lines, 0, 1)

        assert context == ""

    def test_extract_code_context_negative_start(self) -> None:
        """Test extraction with negative start line returns empty string."""
        parser = ConcreteParser()
        source_lines = ["line 1", "line 2"]

        context = parser._extract_code_context(source_lines, -1, 2)

        assert context == ""

    def test_extract_code_context_end_beyond_bounds(self) -> None:
        """Test extraction with end beyond source length returns empty string."""
        parser = ConcreteParser()
        source_lines = ["line 1", "line 2"]

        context = parser._extract_code_context(source_lines, 0, 10)

        assert context == ""

    def test_extract_code_context_preserves_indentation(self) -> None:
        """Test that indentation is preserved."""
        parser = ConcreteParser()
        source_lines = [
            "if True:",
            "    if False:",
            "        print('nested')",
        ]

        context = parser._extract_code_context(source_lines, 0, 3)

        assert "    if False:" in context
        assert "        print('nested')" in context

    def test_get_supported_extensions(self) -> None:
        """Test that get_supported_extensions works."""
        assert ConcreteParser.get_supported_extensions() == {".test"}

    def test_get_language_name(self) -> None:
        """Test that get_language_name works."""
        assert ConcreteParser.get_language_name() == "test"
