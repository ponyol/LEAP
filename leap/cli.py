"""
Main CLI entry point for LEAP (Log Extraction & Analysis Pipeline).

This module provides the command-line interface for the leap-cli tool.
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from leap.core import aggregate_results, discover_files, filter_changed_files
from leap.parsers import PythonParser
from leap.schemas import RawLogEntry
from leap.utils.logger import get_logger

app = typer.Typer(
    name="leap",
    help="Log Extraction & Analysis Pipeline - Extract log statements from source code",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)


@app.command()
def extract(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the repository or source directory to scan",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for raw_logs.json",
        ),
    ] = Path("raw_logs.json"),
    files: Annotated[
        list[Path] | None,
        typer.Option(
            "--files",
            "-f",
            help="Process only specific files (for incremental analysis)",
        ),
    ] = None,
    languages: Annotated[
        list[str] | None,
        typer.Option(
            "--language",
            "-l",
            help="Filter by language (python, go, ruby, javascript, typescript)",
        ),
    ] = None,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            "-m",
            help="Merge results with existing output file",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """
    Extract log statements from source code.

    Recursively scans the specified directory, identifies source files,
    and extracts all logging statements using language-specific AST parsers.

    Examples:

        # Extract from entire repository
        leap extract /path/to/repo

        # Extract only Python files
        leap extract /path/to/repo --language python

        # Extract from specific files (incremental)
        leap extract /path/to/repo --files src/main.py --files src/utils.py

        # Merge with existing results
        leap extract /path/to/repo --merge --output existing_logs.json
    """
    try:
        # Convert path to absolute
        root_path = path.resolve()

        console.print(f"[bold blue]LEAP - Log Extraction & Analysis Pipeline[/bold blue]")
        console.print(f"Scanning: {root_path}")

        # Step 1: Discover files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Discovering source files...", total=None)

            # Filter by languages if specified
            language_filter = None
            if languages:
                # Validate and convert language names
                valid_languages = {"python", "go", "ruby", "javascript", "typescript"}
                language_filter = set()
                for lang in languages:
                    if lang.lower() not in valid_languages:
                        console.print(
                            f"[bold red]Error:[/bold red] Invalid language '{lang}'. "
                            f"Valid options: {', '.join(sorted(valid_languages))}"
                        )
                        raise typer.Exit(1)
                    language_filter.add(lang.lower())  # type: ignore

            discovered = discover_files(root_path, languages=language_filter)

            # Filter by specific files if provided
            if files:
                # Convert file paths to absolute
                file_paths = [f.resolve() for f in files]
                discovered = filter_changed_files(discovered, file_paths)

            progress.update(task, completed=True)

        # Check if any files were found
        total_files = sum(len(file_list) for file_list in discovered.values())
        if total_files == 0:
            console.print("[yellow]No source files found.[/yellow]")
            raise typer.Exit(0)

        console.print(f"Found {total_files} source file(s)")
        for lang, file_list in discovered.items():
            console.print(f"  - {lang}: {len(file_list)} file(s)")

        # Step 2: Parse files
        all_log_entries: list[RawLogEntry] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Currently only Python parser is implemented
            if "python" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['python'])} Python file(s)...", total=None
                )
                python_entries = _parse_python_files(discovered["python"])
                all_log_entries.extend(python_entries)
                progress.update(task, completed=True)

            # TODO: Add other language parsers
            for lang in discovered:
                if lang != "python":
                    console.print(
                        f"[yellow]Warning: {lang} parser not yet implemented, skipping[/yellow]"
                    )

        console.print(f"Extracted {len(all_log_entries)} log statement(s)")

        # Step 3: Aggregate and write results
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Writing output...", total=None)

            # Merge with existing file if requested
            if merge and output.exists():
                from leap.core.aggregator import merge_results

                all_log_entries = merge_results(output, all_log_entries)

            aggregate_results(all_log_entries, output)
            progress.update(task, completed=True)

        console.print(f"[bold green]Success![/bold green] Output written to: {output}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        logger.error(f"CLI error: {e}", exc_info=True)
        raise typer.Exit(1)


def _parse_python_files(file_paths: list[Path]) -> list[RawLogEntry]:
    """
    Parse Python files and extract log entries.

    Args:
        file_paths: List of Python file paths to parse

    Returns:
        List of all extracted log entries
    """
    parser = PythonParser()
    all_entries: list[RawLogEntry] = []

    for file_path in file_paths:
        try:
            entries = parser.parse_file(file_path)
            all_entries.extend(entries)
        except SyntaxError as e:
            logger.warning(
                f"Skipping file with syntax errors: {file_path}",
                extra={"context": {"file": str(file_path), "error": str(e)}},
            )
            continue
        except Exception as e:
            logger.error(
                f"Failed to parse file: {file_path}",
                extra={"context": {"file": str(file_path), "error": str(e)}},
            )
            continue

    return all_entries


@app.command()
def version() -> None:
    """Display version information."""
    console.print("[bold]LEAP CLI[/bold] version 0.1.0")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
