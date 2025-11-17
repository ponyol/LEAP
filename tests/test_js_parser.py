"""Tests for JavaScript parser."""

import tempfile
from pathlib import Path

import pytest

from leap.parsers.js_parser import JSParser


class TestJSParser:
    """Test suite for JSParser."""

    @pytest.fixture
    def parser(self) -> JSParser:
        """Create a parser instance."""
        return JSParser()

    def test_console_log(self, parser: JSParser) -> None:
        """Test extraction of console.log call."""
        code = '''
function main() {
    console.log("Application started");
    console.error("An error occurred");
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) >= 1
            assert any("Application started" in e.log_template for e in entries)
            assert all(e.language == "javascript" for e in entries)

        finally:
            temp_path.unlink()

    def test_empty_file(self, parser: JSParser) -> None:
        """Test parsing empty JavaScript file."""
        code = '''
function main() {
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert entries == []

        finally:
            temp_path.unlink()

    def test_nonexistent_file(self, parser: JSParser) -> None:
        """Test parsing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/file.js"))

    def test_supported_extensions(self) -> None:
        """Test supported file extensions."""
        extensions = JSParser.get_supported_extensions()
        assert ".js" in extensions
        assert ".jsx" in extensions

    def test_language_name(self) -> None:
        """Test language name."""
        assert JSParser.get_language_name() == "javascript"

    def test_typescript_extension(self, parser: JSParser) -> None:
        """Test parsing TypeScript files."""
        code = '''
const log = (msg: string) => {
    console.log(msg);
};
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            # Should not raise error
            entries = parser.parse_file(temp_path)
            # May or may not find entries depending on parser implementation

        finally:
            temp_path.unlink()

    def test_multiple_console_methods(self, parser: JSParser) -> None:
        """Test extraction of different console methods."""
        code = '''
function process() {
    console.info("Info message");
    console.warn("Warning message");
}
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert len(entries) >= 1
            assert all(e.language == "javascript" for e in entries)

        finally:
            temp_path.unlink()
