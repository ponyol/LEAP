"""
Python AST parser for extracting log statements.

This parser uses Python's built-in `ast` module to parse Python source files
and extract logging statements. It handles various logging patterns:
- logging.debug/info/warning/error/critical
- logger.debug/info/warning/error/critical
- self.log.*, self.logger.*, app.logger.*
- Custom logger instances
"""

import ast
from pathlib import Path

from leap.parsers.base import BaseParser
from leap.schemas import RawLogEntry


class PythonParser(BaseParser):
    """
    Parser for extracting log statements from Python source code.

    This parser handles:
    - Standard logging module (logging.info, logging.error, etc.)
    - Logger instances (logger.info, self.logger.error, etc.)
    - F-strings and string formatting in log messages
    - Complex attribute chains (e.g., app.logger.info)
    """

    # Common logger names and logging module functions
    LOGGER_NAMES = {
        "logging",
        "logger",
        "log",
        "_logger",
        "_log",
    }

    # Mapping of logging function names to log levels
    LOG_LEVELS = {
        "debug": "debug",
        "info": "info",
        "warning": "warn",
        "warn": "warn",
        "error": "error",
        "critical": "fatal",
        "fatal": "fatal",
        "exception": "error",  # exception is error-level with traceback
    }

    def parse_file(self, file_path: Path) -> list[RawLogEntry]:
        """
        Parse a Python file and extract all log statements.

        Args:
            file_path: Path to the Python source file

        Returns:
            List of RawLogEntry objects for each log statement found

        Raises:
            FileNotFoundError: If file doesn't exist
            SyntaxError: If file contains invalid Python syntax
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read the source code
        source_code = file_path.read_text(encoding="utf-8")
        if not source_code.strip():
            return []

        # Parse into AST
        try:
            tree = ast.parse(source_code, filename=str(file_path))
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python syntax in {file_path}: {e}") from e

        # Split source into lines for context extraction
        source_lines = source_code.splitlines()

        # Walk the AST and collect log entries
        visitor = LogCallVisitor(file_path, source_lines)
        visitor.visit(tree)

        return visitor.log_entries

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """Return supported file extensions for Python."""
        return {".py"}

    @staticmethod
    def get_language_name() -> str:
        """Return the language name."""
        return "python"


class LogCallVisitor(ast.NodeVisitor):
    """
    AST visitor that identifies and extracts logging calls.

    This visitor walks through the Python AST and identifies function calls
    that match logging patterns (e.g., logger.info(), logging.error(), etc.).
    """

    # Common logger names and logging module functions
    LOGGER_NAMES = {
        "logging",
        "logger",
        "log",
        "_logger",
        "_log",
    }

    # Mapping of logging function names to log levels
    LOG_LEVELS = {
        "debug": "debug",
        "info": "info",
        "warning": "warn",
        "warn": "warn",
        "error": "error",
        "critical": "fatal",
        "fatal": "fatal",
        "exception": "error",  # exception is error-level with traceback
    }

    def __init__(self, file_path: Path, source_lines: list[str]) -> None:
        """
        Initialize the visitor.

        Args:
            file_path: Path to the source file being parsed
            source_lines: List of source code lines (for context extraction)
        """
        self.file_path = file_path
        self.source_lines = source_lines
        self.log_entries: list[RawLogEntry] = []
        self.current_function: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        self.current_class: ast.ClassDef | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition to track context."""
        old_function = self.current_function
        self.current_function = node
        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition to track context."""
        old_function = self.current_function
        self.current_function = node
        self.generic_visit(node)
        self.current_function = old_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition to track context."""
        old_class = self.current_class
        self.current_class = node
        self.generic_visit(node)
        self.current_class = old_class

    def visit_Call(self, node: ast.Call) -> None:
        """
        Visit function call nodes to identify logging calls.

        This method checks if a function call is a logging call by analyzing
        the call's attribute chain (e.g., logger.info, self.log.error, etc.).
        """
        if self._is_logging_call(node):
            log_entry = self._extract_log_entry(node)
            if log_entry:
                self.log_entries.append(log_entry)

        # Continue visiting child nodes
        self.generic_visit(node)

    def _is_logging_call(self, node: ast.Call) -> bool:
        """
        Determine if a Call node is a logging call.

        Checks for patterns like:
        - logging.info(...)
        - logger.error(...)
        - self.logger.debug(...)
        - app.log.warning(...)

        Args:
            node: AST Call node to check

        Returns:
            True if this is a logging call, False otherwise
        """
        func = node.func

        # Case 1: Direct call like logging.info()
        if isinstance(func, ast.Attribute):
            # Get the method name (e.g., "info", "error")
            method_name = func.attr.lower()

            # Check if it's a known log level
            if method_name not in self.LOG_LEVELS:
                return False

            # Check if the object is a logger (e.g., logging, logger, self.log)
            return self._is_logger_object(func.value)

        return False

    def _is_logger_object(self, node: ast.expr) -> bool:
        """
        Check if an AST node represents a logger object.

        Handles:
        - Simple names: logger, logging, log
        - Attributes: self.logger, app.log, self._logger
        - Chains: app.services.logger

        Args:
            node: AST expression node

        Returns:
            True if this represents a logger object
        """
        # Case 1: Simple name (e.g., "logger", "logging")
        if isinstance(node, ast.Name):
            return node.id.lower() in self.LOGGER_NAMES

        # Case 2: Attribute access (e.g., "self.logger", "app.log")
        if isinstance(node, ast.Attribute):
            attr_name = node.attr.lower()
            # Check if the attribute name is a logger name
            if attr_name in self.LOGGER_NAMES:
                return True
            # Recursively check the base object
            return self._is_logger_object(node.value)

        return False

    def _extract_log_entry(self, node: ast.Call) -> RawLogEntry | None:
        """
        Extract a RawLogEntry from a logging call node.

        Args:
            node: AST Call node representing a logging call

        Returns:
            RawLogEntry if extraction successful, None otherwise
        """
        # Get log level from the method name
        if not isinstance(node.func, ast.Attribute):
            return None

        method_name = node.func.attr.lower()
        log_level = self.LOG_LEVELS.get(method_name)

        # Get line number
        line_number = node.lineno

        # Extract log template (the message argument)
        log_template = self._extract_log_template(node)
        if not log_template:
            return None

        # Extract code context (the surrounding function or block)
        code_context = self._extract_context_for_node(node)

        return RawLogEntry(
            language="python",
            file_path=str(self.file_path),
            line_number=line_number,
            log_level=log_level,
            log_template=log_template,
            code_context=code_context,
        )

    def _extract_log_template(self, node: ast.Call) -> str | None:
        """
        Extract the log message template from the call arguments.

        Handles:
        - Simple strings: "User not found"
        - F-strings: f"User {uid} not found"
        - Format strings: "User {} not found".format(uid)
        - Concatenation: "User " + str(uid) + " not found"

        Args:
            node: AST Call node

        Returns:
            String representation of the log template, or None if not extractable
        """
        if not node.args:
            return None

        # The first argument is typically the message
        msg_node = node.args[0]

        # Convert the AST node back to source code
        return ast.unparse(msg_node)

    def _extract_context_for_node(self, node: ast.Call) -> str:
        """
        Extract code context surrounding a log call.

        Tries to extract the minimal meaningful context:
        1. The containing if/else/try/except block
        2. The containing function
        3. The containing class method
        4. Fall back to a few lines around the log call

        Args:
            node: AST Call node representing the log statement

        Returns:
            String containing the surrounding code context
        """
        # If we're inside a function, use the function as context
        if self.current_function:
            start_line = self.current_function.lineno - 1  # Convert to 0-indexed
            end_line = self.current_function.end_lineno or (start_line + 20)
            return self._extract_code_block(start_line, end_line)

        # Fall back to a window around the log call (5 lines before, 2 after)
        log_line = node.lineno - 1  # Convert to 0-indexed
        start_line = max(0, log_line - 5)
        end_line = min(len(self.source_lines), log_line + 3)

        return self._extract_code_block(start_line, end_line)

    def _extract_code_block(self, start_line: int, end_line: int) -> str:
        """
        Extract a block of code from source lines.

        Args:
            start_line: Starting line (0-indexed)
            end_line: Ending line (0-indexed, exclusive)

        Returns:
            Code block as a string
        """
        if start_line < 0 or end_line > len(self.source_lines):
            return ""

        return "\n".join(self.source_lines[start_line:end_line])
