"""Tests for core.discovery module."""

import tempfile
from pathlib import Path

import pytest

from leap.core.discovery import (
    EXTENSION_TO_LANGUAGE,
    detect_language,
    discover_files,
    filter_changed_files,
)


class TestDiscoverFiles:
    """Tests for discover_files function."""

    def test_discover_files_basic(self, tmp_path: Path) -> None:
        """Test basic file discovery."""
        # Create test files
        (tmp_path / "test.py").touch()
        (tmp_path / "main.go").touch()
        (tmp_path / "app.rb").touch()
        (tmp_path / "index.js").touch()

        result = discover_files(tmp_path)

        assert "python" in result
        assert "go" in result
        assert "ruby" in result
        assert "javascript" in result
        assert len(result["python"]) == 1
        assert len(result["go"]) == 1
        assert len(result["ruby"]) == 1
        assert len(result["javascript"]) == 1

    def test_discover_files_with_subdirectories(self, tmp_path: Path) -> None:
        """Test discovery in nested directories."""
        # Create nested structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "src" / "utils" / "helper.py").touch()
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test.py").touch()

        result = discover_files(tmp_path)

        assert "python" in result
        assert len(result["python"]) == 3

    def test_discover_files_exclude_patterns(self, tmp_path: Path) -> None:
        """Test exclusion of specific directories."""
        # Create structure with excluded dirs
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "package.js").touch()
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config.py").touch()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cache.py").touch()

        result = discover_files(tmp_path)

        # Should only find main.py, others are excluded
        assert "python" in result
        assert len(result["python"]) == 1
        assert result["python"][0].name == "main.py"

    def test_discover_files_custom_exclude(self, tmp_path: Path) -> None:
        """Test custom exclude patterns."""
        # Create files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").touch()
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test.py").touch()

        result = discover_files(tmp_path, exclude_patterns={"tests"})

        # Should only find main.py, tests excluded
        assert "python" in result
        assert len(result["python"]) == 1
        assert result["python"][0].name == "main.py"

    def test_discover_files_language_filter(self, tmp_path: Path) -> None:
        """Test filtering by specific languages."""
        # Create files of different languages
        (tmp_path / "test.py").touch()
        (tmp_path / "main.go").touch()
        (tmp_path / "app.rb").touch()

        result = discover_files(tmp_path, languages={"python", "go"})

        # Should only find Python and Go files
        assert "python" in result
        assert "go" in result
        assert "ruby" not in result

    def test_discover_files_nonexistent_path(self) -> None:
        """Test discovery with nonexistent path."""
        with pytest.raises(FileNotFoundError):
            discover_files(Path("/nonexistent/path"))

    def test_discover_files_not_a_directory(self, tmp_path: Path) -> None:
        """Test discovery when path is a file, not directory."""
        file_path = tmp_path / "test.txt"
        file_path.touch()

        with pytest.raises(ValueError, match="not a directory"):
            discover_files(file_path)

    def test_discover_files_no_source_files(self, tmp_path: Path) -> None:
        """Test discovery in directory with no source files."""
        # Create only non-source files
        (tmp_path / "README.md").touch()
        (tmp_path / "data.txt").touch()

        result = discover_files(tmp_path)

        assert result == {}

    def test_discover_files_typescript_files(self, tmp_path: Path) -> None:
        """Test discovery of TypeScript files."""
        (tmp_path / "app.ts").touch()
        (tmp_path / "component.tsx").touch()

        result = discover_files(tmp_path)

        assert "typescript" in result
        assert len(result["typescript"]) == 2

    def test_discover_files_jsx_files(self, tmp_path: Path) -> None:
        """Test discovery of JSX files."""
        (tmp_path / "App.jsx").touch()

        result = discover_files(tmp_path)

        assert "javascript" in result
        assert len(result["javascript"]) == 1

    def test_discover_files_mixed_case_extensions(self, tmp_path: Path) -> None:
        """Test that file extensions are case-insensitive."""
        (tmp_path / "Test.PY").touch()
        (tmp_path / "Main.GO").touch()

        result = discover_files(tmp_path)

        assert "python" in result
        assert "go" in result

    def test_discover_files_excludes_vendor_dir(self, tmp_path: Path) -> None:
        """Test that vendor directory is excluded by default."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.go").touch()
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "pkg.go").touch()

        result = discover_files(tmp_path)

        assert "go" in result
        assert len(result["go"]) == 1
        assert result["go"][0].name == "main.go"


class TestFilterChangedFiles:
    """Tests for filter_changed_files function."""

    def test_filter_changed_files_basic(self, tmp_path: Path) -> None:
        """Test basic filtering of changed files."""
        # Create file structure
        file1 = tmp_path / "src" / "main.py"
        file2 = tmp_path / "src" / "utils.py"
        file3 = tmp_path / "tests" / "test.py"

        all_files = {
            "python": [file1, file2, file3],
        }
        changed = [file1, file3]

        result = filter_changed_files(all_files, changed)

        assert "python" in result
        assert len(result["python"]) == 2
        assert file1 in result["python"]
        assert file3 in result["python"]
        assert file2 not in result["python"]

    def test_filter_changed_files_no_changes(self, tmp_path: Path) -> None:
        """Test filtering when no files have changed."""
        file1 = tmp_path / "main.py"

        all_files = {
            "python": [file1],
        }
        changed: list[Path] = []

        result = filter_changed_files(all_files, changed)

        assert result == {}

    def test_filter_changed_files_all_changed(self, tmp_path: Path) -> None:
        """Test filtering when all files have changed."""
        file1 = tmp_path / "main.py"
        file2 = tmp_path / "utils.py"

        all_files = {
            "python": [file1, file2],
        }
        changed = [file1, file2]

        result = filter_changed_files(all_files, changed)

        assert "python" in result
        assert len(result["python"]) == 2

    def test_filter_changed_files_multiple_languages(self, tmp_path: Path) -> None:
        """Test filtering across multiple languages."""
        py_file = tmp_path / "main.py"
        go_file = tmp_path / "main.go"
        rb_file = tmp_path / "app.rb"

        all_files = {
            "python": [py_file],
            "go": [go_file],
            "ruby": [rb_file],
        }
        changed = [py_file, go_file]  # Changed Python and Go, not Ruby

        result = filter_changed_files(all_files, changed)

        assert "python" in result
        assert "go" in result
        assert "ruby" not in result


class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_detect_python(self) -> None:
        """Test detection of Python files."""
        assert detect_language(Path("test.py")) == "python"
        assert detect_language(Path("src/main.py")) == "python"

    def test_detect_go(self) -> None:
        """Test detection of Go files."""
        assert detect_language(Path("main.go")) == "go"

    def test_detect_ruby(self) -> None:
        """Test detection of Ruby files."""
        assert detect_language(Path("app.rb")) == "ruby"

    def test_detect_javascript(self) -> None:
        """Test detection of JavaScript files."""
        assert detect_language(Path("app.js")) == "javascript"
        assert detect_language(Path("component.jsx")) == "javascript"

    def test_detect_typescript(self) -> None:
        """Test detection of TypeScript files."""
        assert detect_language(Path("app.ts")) == "typescript"
        assert detect_language(Path("component.tsx")) == "typescript"

    def test_detect_unsupported_extension(self) -> None:
        """Test detection of unsupported file types."""
        assert detect_language(Path("README.md")) is None
        assert detect_language(Path("data.json")) is None
        assert detect_language(Path("config.yaml")) is None

    def test_detect_no_extension(self) -> None:
        """Test detection of files without extension."""
        assert detect_language(Path("Makefile")) is None
        assert detect_language(Path("README")) is None

    def test_detect_case_insensitive(self) -> None:
        """Test that detection is case-insensitive."""
        assert detect_language(Path("Test.PY")) == "python"
        assert detect_language(Path("Main.GO")) == "go"
        assert detect_language(Path("App.RB")) == "ruby"


class TestExtensionToLanguageMapping:
    """Tests for EXTENSION_TO_LANGUAGE constant."""

    def test_all_extensions_mapped(self) -> None:
        """Test that common extensions are mapped."""
        assert ".py" in EXTENSION_TO_LANGUAGE
        assert ".go" in EXTENSION_TO_LANGUAGE
        assert ".rb" in EXTENSION_TO_LANGUAGE
        assert ".js" in EXTENSION_TO_LANGUAGE
        assert ".jsx" in EXTENSION_TO_LANGUAGE
        assert ".ts" in EXTENSION_TO_LANGUAGE
        assert ".tsx" in EXTENSION_TO_LANGUAGE

    def test_expected_language_values(self) -> None:
        """Test that languages are correctly mapped."""
        assert EXTENSION_TO_LANGUAGE[".py"] == "python"
        assert EXTENSION_TO_LANGUAGE[".go"] == "go"
        assert EXTENSION_TO_LANGUAGE[".rb"] == "ruby"
        assert EXTENSION_TO_LANGUAGE[".js"] == "javascript"
        assert EXTENSION_TO_LANGUAGE[".jsx"] == "javascript"
        assert EXTENSION_TO_LANGUAGE[".ts"] == "typescript"
        assert EXTENSION_TO_LANGUAGE[".tsx"] == "typescript"
