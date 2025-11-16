"""
Base parser interface for LEAP language parsers.

This module defines the abstract interface that all language-specific parsers
must implement. This ensures consistency across Python, Go, Ruby, and JS/TS parsers.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from leap.schemas import RawLogEntry


class BaseParser(ABC):
    """
    Abstract base class for language-specific log extractors.

    Each parser implementation must:
    1. Parse the source file into an AST
    2. Walk the AST to find log statements
    3. Extract the log template and surrounding context
    4. Return a list of RawLogEntry objects

    Implementations should handle language-specific logging patterns:
    - Python: logging.*, logger.*, self.log.*, etc.
    - Go: log.*, zerologger.*, etc.
    - Ruby: Rails.logger.*, logger.*, etc.
    - JS/TS: console.*, winston.*, pino.*, etc.
    """

    @abstractmethod
    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """
        Parse a single source file and extract all log statements.

        Args:
            file_path: Absolute path to the source file to parse

        Returns:
            A list of RawLogEntry objects, one for each log statement found.
            Returns an empty list if no log statements are found.

        Raises:
            FileNotFoundError: If the file does not exist
            SyntaxError: If the file contains syntax errors (invalid code)
            ValueError: If the file is empty or unreadable
        """
        pass

    @staticmethod
    @abstractmethod
    def get_supported_extensions() -> set[str]:
        """
        Return the set of file extensions this parser supports.

        Returns:
            A set of file extensions (e.g., {".py"} for Python parser)
        """
        pass

    @staticmethod
    @abstractmethod
    def get_language_name() -> str:
        """
        Return the language name for this parser.

        Returns:
            Language name (e.g., "python", "go", "ruby", "javascript", "typescript")
        """
        pass

    def _extract_code_context(
        self, source_lines: list[str], start_line: int, end_line: int
    ) -> str:
        """
        Extract code context from source lines.

        Helper method to extract a block of code (e.g., a function or if-statement)
        surrounding the log statement. This context is crucial for LLM analysis.

        Args:
            source_lines: List of all source code lines
            start_line: Starting line number (0-indexed)
            end_line: Ending line number (0-indexed, exclusive)

        Returns:
            The code block as a string, preserving indentation
        """
        if not source_lines or start_line < 0 or end_line > len(source_lines):
            return ""

        # Extract the lines and join them
        context_lines = source_lines[start_line:end_line]
        return "\n".join(context_lines)
