"""
File discovery and language detection for LEAP.

This module handles:
1. Recursive scanning of directories to find source files
2. Language detection based on file extensions
3. Filtering files by language
4. Support for incremental analysis (changed files only)
"""

from pathlib import Path
from typing import Literal

from leap.utils.logger import get_logger

logger = get_logger(__name__)

LanguageType = Literal["python", "go", "ruby", "javascript", "typescript"]


# Mapping of file extensions to languages
EXTENSION_TO_LANGUAGE: dict[str, LanguageType] = {
    ".py": "python",
    ".go": "go",
    ".rb": "ruby",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}


def discover_files(
    root_path: Path,
    languages: set[LanguageType] | None = None,
    exclude_patterns: set[str] | None = None,
) -> dict[LanguageType, list[Path]]:
    """
    Recursively discover source files in a directory tree.

    Args:
        root_path: Root directory to scan
        languages: Set of languages to include (None = all supported languages)
        exclude_patterns: Set of glob patterns to exclude (e.g., {"*/test/*", "*/vendor/*"})

    Returns:
        Dictionary mapping language to list of file paths

    Raises:
        FileNotFoundError: If root_path doesn't exist
        ValueError: If root_path is not a directory
    """
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")

    if not root_path.is_dir():
        raise ValueError(f"Path is not a directory: {root_path}")

    # Default exclusions (common directories to skip)
    default_excludes = {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".tox",
        "vendor",  # Go vendor directory
        "Godeps",  # Go dependencies
    }

    if exclude_patterns:
        default_excludes.update(exclude_patterns)

    # Determine which extensions to look for
    if languages:
        target_extensions = {
            ext for ext, lang in EXTENSION_TO_LANGUAGE.items() if lang in languages
        }
    else:
        target_extensions = set(EXTENSION_TO_LANGUAGE.keys())

    # Scan directory tree
    discovered: dict[LanguageType, list[Path]] = {}

    for file_path in root_path.rglob("*"):
        # Skip if not a file
        if not file_path.is_file():
            continue

        # Skip if in excluded directory
        if _should_exclude(file_path, root_path, default_excludes):
            continue

        # Check if extension matches
        extension = file_path.suffix.lower()
        if extension not in target_extensions:
            continue

        # Add to discovered files
        language = EXTENSION_TO_LANGUAGE[extension]
        if language not in discovered:
            discovered[language] = []

        discovered[language].append(file_path)

    # Log discovery results
    total_files = sum(len(files) for files in discovered.values())
    logger.info(
        f"Discovered {total_files} files across {len(discovered)} languages",
        extra={"context": {"root_path": str(root_path), "files_by_language": {lang: len(files) for lang, files in discovered.items()}}},
    )

    return discovered


def filter_changed_files(
    all_files: dict[LanguageType, list[Path]], changed_file_paths: list[Path]
) -> dict[LanguageType, list[Path]]:
    """
    Filter discovered files to only include changed files.

    This is used for incremental analysis in CI/CD pipelines.

    Args:
        all_files: All discovered files (from discover_files)
        changed_file_paths: List of files that have changed (from git diff)

    Returns:
        Filtered dictionary containing only changed files
    """
    # Convert changed paths to a set for O(1) lookup
    changed_set = set(changed_file_paths)

    filtered: dict[LanguageType, list[Path]] = {}

    for language, file_list in all_files.items():
        changed_in_language = [f for f in file_list if f in changed_set]
        if changed_in_language:
            filtered[language] = changed_in_language

    return filtered


def detect_language(file_path: Path) -> LanguageType | None:
    """
    Detect the programming language of a file based on its extension.

    Args:
        file_path: Path to the source file

    Returns:
        The detected language, or None if not supported
    """
    extension = file_path.suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(extension)


def _should_exclude(file_path: Path, root_path: Path, exclude_patterns: set[str]) -> bool:
    """
    Check if a file should be excluded based on exclude patterns.

    Args:
        file_path: The file to check
        root_path: The root directory being scanned
        exclude_patterns: Set of directory names to exclude

    Returns:
        True if the file should be excluded, False otherwise
    """
    try:
        # Get relative path from root
        relative_path = file_path.relative_to(root_path)

        # Check if any parent directory matches an exclude pattern
        for part in relative_path.parts:
            if part in exclude_patterns:
                return True

        return False
    except ValueError:
        # File is not relative to root_path, exclude it
        return True
