"""
Go AST parser wrapper for extracting log statements.

This module provides a Python wrapper around the standalone Go parser
that uses the go/parser and go/ast packages.
"""

import json
import subprocess
from pathlib import Path

from leap.parsers.base import BaseParser
from leap.schemas import RawLogEntry
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class GoParser(BaseParser):
    """
    Parser for extracting log statements from Go source code.

    This parser invokes a standalone Go binary that uses the native
    go/parser and go/ast packages to extract logging statements.

    Handles:
    - Standard log package (log.Print, log.Fatal, etc.)
    - Structured logging libraries (zerolog, logrus, etc.)
    """

    # Path to the Go parser binary
    _PARSER_DIR = Path(__file__).parent / "go_parser"
    _PARSER_BINARY = _PARSER_DIR / "go_parser"

    @classmethod
    def ensure_parser_built(cls) -> None:
        """
        Ensure the Go parser binary is built.

        Raises:
            RuntimeError: If the binary cannot be built
        """
        if cls._PARSER_BINARY.exists():
            return

        logger.info("Building Go parser binary...")

        try:
            # Build the Go parser
            subprocess.run(
                ["go", "build", "-o", str(cls._PARSER_BINARY), "."],
                cwd=str(cls._PARSER_DIR),
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Go parser binary built successfully")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to build Go parser: {e.stderr}"
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError(
                "Go compiler not found. Please install Go: https://golang.org/dl/"
            ) from e

    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """
        Parse a Go file and extract all log statements.

        Args:
            file_path: Path to the Go source file

        Returns:
            List of RawLogEntry objects for each log statement found

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If the parser binary cannot be built or executed
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Ensure parser binary is built
        self.ensure_parser_built()

        try:
            # Run the Go parser
            result = subprocess.run(
                [str(self._PARSER_BINARY), str(file_path)],
                capture_output=True,
                text=True,
                check=True,
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

        except subprocess.CalledProcessError as e:
            logger.error(
                f"Go parser failed for {file_path}: {e.stderr}",
                extra={"context": {"file": str(file_path), "error": e.stderr}},
            )
            # Don't raise, just return empty list (parser might fail on invalid Go)
            return []
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse Go parser output: {e}",
                extra={"context": {"file": str(file_path), "output": result.stdout}},
            )
            return []

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """Return supported file extensions for Go."""
        return {".go"}

    @staticmethod
    def get_language_name() -> str:
        """Return the language name."""
        return "go"
