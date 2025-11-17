"""Tests for Ruby parser."""

import tempfile
from pathlib import Path

import pytest

from leap.parsers.ruby_parser import RubyParser


class TestRubyParser:
    """Test suite for RubyParser."""

    @pytest.fixture
    def parser(self) -> RubyParser:
        """Create a parser instance."""
        return RubyParser()

    def test_logger_info(self, parser: RubyParser) -> None:
        """Test extraction of logger.info call."""
        code = '''
def main
    logger.info("Application started")
    logger.error("An error occurred")
end
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) >= 1
            assert any("Application started" in e.log_template for e in entries)
            assert all(e.language == "ruby" for e in entries)

        finally:
            temp_path.unlink()

    def test_empty_file(self, parser: RubyParser) -> None:
        """Test parsing empty Ruby file."""
        code = '''
def main
end
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rb", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert entries == []

        finally:
            temp_path.unlink()

    def test_nonexistent_file(self, parser: RubyParser) -> None:
        """Test parsing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/file.rb"))

    def test_supported_extensions(self) -> None:
        """Test supported file extensions."""
        extensions = RubyParser.get_supported_extensions()
        assert ".rb" in extensions

    def test_language_name(self) -> None:
        """Test language name."""
        assert RubyParser.get_language_name() == "ruby"
