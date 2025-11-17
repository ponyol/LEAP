"""Tests for Go parser."""

import tempfile
from pathlib import Path

import pytest

from leap.parsers.go_parser import GoParser


class TestGoParser:
    """Test suite for GoParser."""

    @pytest.fixture
    def parser(self) -> GoParser:
        """Create a parser instance."""
        return GoParser()

    def test_simple_logging(self, parser: GoParser) -> None:
        """Test extraction of simple log call."""
        code = '''
package main

import "log"

func main() {
    log.Println("Application started")
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".go", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) >= 1
            assert any("Application started" in e.log_template for e in entries)
            assert all(e.language == "go" for e in entries)

        finally:
            temp_path.unlink()

    def test_empty_file(self, parser: GoParser) -> None:
        """Test parsing empty Go file."""
        code = '''package main

func main() {
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".go", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert entries == []

        finally:
            temp_path.unlink()

    def test_nonexistent_file(self, parser: GoParser) -> None:
        """Test parsing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/file.go"))

    def test_supported_extensions(self) -> None:
        """Test supported file extensions."""
        extensions = GoParser.get_supported_extensions()
        assert ".go" in extensions

    def test_language_name(self) -> None:
        """Test language name."""
        assert GoParser.get_language_name() == "go"

    def test_multiple_log_calls(self, parser: GoParser) -> None:
        """Test extraction of multiple log calls."""
        code = '''
package main

import "log"

func processData() {
    log.Println("Processing started")
    log.Printf("Processing item")
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".go", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert len(entries) >= 1
            assert all(e.language == "go" for e in entries)

        finally:
            temp_path.unlink()
