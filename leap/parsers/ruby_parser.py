"""
Ruby AST parser wrapper for extracting log statements.

This module provides a Python wrapper around the standalone Ruby parser
that uses the Ripper module.
"""

import json
import subprocess
from pathlib import Path

from leap.parsers.base import BaseParser
from leap.schemas import RawLogEntry
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class RubyParser(BaseParser):
    """
    Parser for extracting log statements from Ruby source code.

    This parser invokes a standalone Ruby script that uses the native
    Ripper module to extract logging statements.

    Handles:
    - Standard Logger class (logger.debug, logger.info, etc.)
    - Rails.logger
    - Custom logger instances
    """

    # Path to the Ruby parser script
    _PARSER_SCRIPT = Path(__file__).parent / "ruby_parser" / "parser.rb"

    @classmethod
    def check_ruby_available(cls) -> bool:
        """
        Check if Ruby is available.

        Returns:
            True if Ruby is available, False otherwise
        """
        try:
            subprocess.run(
                ["ruby", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """
        Parse a Ruby file and extract all log statements.

        Args:
            file_path: Path to the Ruby source file

        Returns:
            List of RawLogEntry objects for each log statement found

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If Ruby is not available
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if Ruby is available
        if not self.check_ruby_available():
            raise RuntimeError(
                "Ruby interpreter not found. Please install Ruby: https://www.ruby-lang.org/"
            )

        try:
            # Run the Ruby parser
            result = subprocess.run(
                ["ruby", str(self._PARSER_SCRIPT), str(file_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            # Parse JSON output
            data = json.loads(result.stdout)

            # Convert to RawLogEntry objects
            entries = []
            for item in data:
                entry = RawLogEntry(
                    language=item["language"],
                    file_path=item["file_path"],
                    line_number=item["line_number"],
                    log_level=item["log_level"],
                    log_template=item["log_template"],
                    code_context=item["code_context"],
                )
                entries.append(entry)

            return entries

        except subprocess.TimeoutExpired:
            logger.error(
                f"Ruby parser timed out for {file_path}",
                extra={"context": {"file": str(file_path)}},
            )
            return []
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Ruby parser failed for {file_path}: {e.stderr}",
                extra={"context": {"file": str(file_path), "error": e.stderr}},
            )
            # Don't raise, just return empty list (parser might fail on invalid Ruby)
            return []
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse Ruby parser output: {e}",
                extra={"context": {"file": str(file_path), "output": result.stdout}},
            )
            return []

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """Return supported file extensions for Ruby."""
        return {".rb"}

    @staticmethod
    def get_language_name() -> str:
        """Return the language name."""
        return "ruby"
