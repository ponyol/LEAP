"""
JavaScript/TypeScript AST parser wrapper for extracting log statements.

This module provides a Python wrapper around the standalone Node.js parser
that uses acorn and @typescript-eslint/parser.
"""

import json
import subprocess
from pathlib import Path

from leap.parsers.base import BaseParser
from leap.schemas import RawLogEntry
from leap.utils.logger import get_logger

logger = get_logger(__name__)


class JSParser(BaseParser):
    """
    Parser for extracting log statements from JavaScript/TypeScript source code.

    This parser invokes a standalone Node.js script that uses acorn (for JS)
    and @typescript-eslint/parser (for TS) to extract logging statements.

    Handles:
    - console.log, console.error, console.warn, etc.
    - winston logger
    - pino logger
    - bunyan logger
    - log4js logger
    - Custom logger instances
    """

    # Path to the JS parser script
    _PARSER_DIR = Path(__file__).parent / "js_parser"
    _PARSER_SCRIPT = _PARSER_DIR / "parser.js"
    _DEPENDENCIES_INSTALLED = False

    @classmethod
    def check_node_available(cls) -> bool:
        """
        Check if Node.js is available.

        Returns:
            True if Node.js is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            # Check if version is >= 18
            version = result.stdout.decode().strip()
            major_version = int(version.lstrip('v').split('.')[0])
            return major_version >= 18
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return False

    @classmethod
    def ensure_dependencies_installed(cls) -> None:
        """
        Ensure Node.js dependencies are installed.

        Raises:
            RuntimeError: If dependencies cannot be installed
        """
        if cls._DEPENDENCIES_INSTALLED:
            return

        # Check if node_modules exists
        node_modules = cls._PARSER_DIR / "node_modules"
        if node_modules.exists():
            cls._DEPENDENCIES_INSTALLED = True
            return

        logger.info("Installing JavaScript parser dependencies...")

        try:
            # Install dependencies
            subprocess.run(
                ["npm", "install", "--silent"],
                cwd=str(cls._PARSER_DIR),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            cls._DEPENDENCIES_INSTALLED = True
            logger.info("JavaScript parser dependencies installed successfully")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("npm install timed out") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to install JavaScript parser dependencies: {e.stderr}"
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError(
                "npm not found. Please install Node.js: https://nodejs.org/"
            ) from e

    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """
        Parse a JavaScript/TypeScript file and extract all log statements.

        Args:
            file_path: Path to the JS/TS source file

        Returns:
            List of RawLogEntry objects for each log statement found

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If Node.js is not available or dependencies cannot be installed
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if Node.js is available
        if not self.check_node_available():
            raise RuntimeError(
                "Node.js >= 18 not found. Please install Node.js: https://nodejs.org/"
            )

        # Ensure dependencies are installed
        self.ensure_dependencies_installed()

        try:
            # Run the Node.js parser
            result = subprocess.run(
                ["node", str(self._PARSER_SCRIPT), str(file_path)],
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
                f"JavaScript parser timed out for {file_path}",
                extra={"context": {"file": str(file_path)}},
            )
            return []
        except subprocess.CalledProcessError as e:
            logger.error(
                f"JavaScript parser failed for {file_path}: {e.stderr}",
                extra={"context": {"file": str(file_path), "error": e.stderr}},
            )
            # Don't raise, just return empty list (parser might fail on invalid JS/TS)
            return []
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JavaScript parser output: {e}",
                extra={"context": {"file": str(file_path), "output": result.stdout}},
            )
            return []

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """Return supported file extensions for JavaScript/TypeScript."""
        return {".js", ".jsx", ".ts", ".tsx"}

    @staticmethod
    def get_language_name() -> str:
        """Return the language name."""
        # Note: This returns "javascript" but the actual entries will have
        # either "javascript" or "typescript" based on the file extension
        return "javascript"
