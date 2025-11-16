"""
Main CLI entry point for LEAP (Log Extraction & Analysis Pipeline).

This module provides the command-line interface for the leap-cli tool.
"""

from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from leap.core import aggregate_results, discover_files, filter_changed_files
from leap.parsers import BaseParser, GoParser, JSParser, PythonParser, RubyParser
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

        console.print("[bold blue]LEAP - Log Extraction & Analysis Pipeline[/bold blue]")
        console.print(f"Scanning: {root_path}")

        # Step 1: Discover files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Discovering source files...", total=None)

            # Filter by languages if specified
            language_filter: set[Literal["python", "go", "ruby", "javascript", "typescript"]] | None = None
            if languages:
                # Validate and convert language names
                valid_languages = {"python", "go", "ruby", "javascript", "typescript"}
                temp_filter = set()
                for lang in languages:
                    if lang.lower() not in valid_languages:
                        console.print(
                            f"[bold red]Error:[/bold red] Invalid language '{lang}'. "
                            f"Valid options: {', '.join(sorted(valid_languages))}"
                        )
                        raise typer.Exit(1)
                    temp_filter.add(lang.lower())
                # Cast is safe because we've validated all values
                language_filter = cast(set[Literal["python", "go", "ruby", "javascript", "typescript"]], temp_filter)

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
            # Parse Python files
            if "python" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['python'])} Python file(s)...", total=None
                )
                python_entries = _parse_files(discovered["python"], PythonParser(), "Python")
                all_log_entries.extend(python_entries)
                progress.update(task, completed=True)

            # Parse Go files
            if "go" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['go'])} Go file(s)...", total=None
                )
                try:
                    go_entries = _parse_files(discovered["go"], GoParser(), "Go")
                    all_log_entries.extend(go_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

            # Parse Ruby files
            if "ruby" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['ruby'])} Ruby file(s)...", total=None
                )
                try:
                    ruby_entries = _parse_files(discovered["ruby"], RubyParser(), "Ruby")
                    all_log_entries.extend(ruby_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

            # Parse JavaScript/TypeScript files
            if "javascript" in discovered or "typescript" in discovered:
                js_files = discovered.get("javascript", [])
                ts_files = discovered.get("typescript", [])
                all_js_files = js_files + ts_files

                task = progress.add_task(
                    f"Parsing {len(all_js_files)} JS/TS file(s)...", total=None
                )
                try:
                    js_entries = _parse_files(all_js_files, JSParser(), "JavaScript/TypeScript")
                    all_log_entries.extend(js_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

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
        raise typer.Exit(1) from None


def _parse_files(file_paths: list[Path], parser: BaseParser, language_name: str) -> list[RawLogEntry]:
    """
    Parse files and extract log entries using a given parser.

    Args:
        file_paths: List of file paths to parse
        parser: Parser instance to use
        language_name: Name of the language (for logging)

    Returns:
        List of all extracted log entries
    """
    all_entries: list[RawLogEntry] = []

    for file_path in file_paths:
        try:
            entries = parser.parse_file(file_path)
            all_entries.extend(entries)
        except SyntaxError as e:
            logger.warning(
                f"Skipping {language_name} file with syntax errors: {file_path}",
                extra={"context": {"file": str(file_path), "error": str(e)}},
            )
            continue
        except Exception as e:
            logger.error(
                f"Failed to parse {language_name} file: {file_path}",
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
