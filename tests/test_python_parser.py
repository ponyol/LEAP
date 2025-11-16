"""
Unit tests for the Python AST parser.
"""

import tempfile
from pathlib import Path

import pytest

from leap.parsers import PythonParser
from leap.schemas import RawLogEntry


class TestPythonParser:
    """Test suite for PythonParser."""

    @pytest.fixture
    def parser(self) -> PythonParser:
        """Create a parser instance."""
        return PythonParser()

    def test_simple_logging_info(self, parser: PythonParser) -> None:
        """Test extraction of simple logging.info call."""
        code = '''
import logging

def test_function():
    logging.info("User logged in")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 1
            entry = entries[0]

            assert entry.language == "python"
            assert entry.log_level == "info"
            assert "User logged in" in entry.log_template
            assert "logging.info" in entry.code_context

        finally:
            temp_path.unlink()

    def test_logger_instance(self, parser: PythonParser) -> None:
        """Test extraction from logger instance (logger.error)."""
        code = '''
import logging

logger = logging.getLogger(__name__)

def process_data():
    logger.error("Processing failed")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 1
            entry = entries[0]

            assert entry.language == "python"
            assert entry.log_level == "error"
            assert "Processing failed" in entry.log_template

        finally:
            temp_path.unlink()

    def test_fstring_logging(self, parser: PythonParser) -> None:
        """Test extraction of f-string log messages."""
        code = '''
import logging

def get_user(user_id):
    logging.warning(f"User {user_id} not found")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 1
            entry = entries[0]

            assert entry.language == "python"
            assert entry.log_level == "warn"
            assert "user_id" in entry.log_template.lower()

        finally:
            temp_path.unlink()

    def test_class_method_logging(self, parser: PythonParser) -> None:
        """Test extraction from class methods using self.logger."""
        code = '''
import logging

class UserService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_user(self, username):
        self.logger.info(f"Creating user: {username}")
        self.logger.debug("User created successfully")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 2

            # First log: info level
            assert entries[0].log_level == "info"
            assert "username" in entries[0].log_template.lower()

            # Second log: debug level
            assert entries[1].log_level == "debug"
            assert "created successfully" in entries[1].log_template.lower()

        finally:
            temp_path.unlink()

    def test_exception_logging(self, parser: PythonParser) -> None:
        """Test extraction of logger.exception calls."""
        code = '''
import logging

logger = logging.getLogger(__name__)

def risky_operation():
    try:
        pass
    except Exception as e:
        logger.exception("Operation failed")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 1
            entry = entries[0]

            # exception() is treated as error-level
            assert entry.log_level == "error"
            assert "Operation failed" in entry.log_template

        finally:
            temp_path.unlink()

    def test_multiple_log_levels(self, parser: PythonParser) -> None:
        """Test extraction of various log levels."""
        code = '''
import logging

def test():
    logging.debug("Debug message")
    logging.info("Info message")
    logging.warning("Warning message")
    logging.error("Error message")
    logging.critical("Critical message")
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)

            assert len(entries) == 5

            levels = [e.log_level for e in entries]
            assert "debug" in levels
            assert "info" in levels
            assert "warn" in levels
            assert "error" in levels
            assert "fatal" in levels  # critical -> fatal

        finally:
            temp_path.unlink()

    def test_empty_file(self, parser: PythonParser) -> None:
        """Test parsing an empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert len(entries) == 0

        finally:
            temp_path.unlink()

    def test_file_without_logging(self, parser: PythonParser) -> None:
        """Test parsing a file with no logging statements."""
        code = '''
def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = parser.parse_file(temp_path)
            assert len(entries) == 0

        finally:
            temp_path.unlink()

    def test_syntax_error(self, parser: PythonParser) -> None:
        """Test that syntax errors are properly raised."""
        code = '''
def broken_function(
    # Missing closing parenthesis
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(SyntaxError):
                parser.parse_file(temp_path)

        finally:
            temp_path.unlink()

    def test_nonexistent_file(self, parser: PythonParser) -> None:
        """Test that FileNotFoundError is raised for missing files."""
        fake_path = Path("/nonexistent/file.py")

        with pytest.raises(FileNotFoundError):
            parser.parse_file(fake_path)

    def test_supported_extensions(self) -> None:
        """Test that parser returns correct supported extensions."""
        extensions = PythonParser.get_supported_extensions()
        assert extensions == {".py"}

    def test_language_name(self) -> None:
        """Test that parser returns correct language name."""
        assert PythonParser.get_language_name() == "python"
