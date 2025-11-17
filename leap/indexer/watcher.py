"""File watcher for automatic reindexing.

This module provides functionality to watch analyzed_logs.json files
and automatically reindex them when they change.
"""

import time
from pathlib import Path

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from leap.indexer.config import IndexerConfig
from leap.indexer.indexer import LogIndexer

console = Console()


class LogFileHandler(FileSystemEventHandler):
    """Handles file system events for analyzed_logs.json.

    Attributes:
        file_path: Path to the file being watched
        codebase_name: Name of the codebase
        indexer: LogIndexer instance
        debounce_seconds: Seconds to wait before reindexing after change
        last_modified: Timestamp of last modification
    """

    def __init__(
        self,
        file_path: Path,
        codebase_name: str,
        indexer: LogIndexer,
        debounce_seconds: float = 2.0,
    ) -> None:
        """Initialize the file handler.

        Args:
            file_path: Path to the file to watch
            codebase_name: Name of the codebase
            indexer: LogIndexer instance
            debounce_seconds: Seconds to wait before reindexing
        """
        self.file_path = file_path
        self.codebase_name = codebase_name
        self.indexer = indexer
        self.debounce_seconds = debounce_seconds
        self.last_modified = 0.0

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event.

        Args:
            event: File system event
        """
        # Only process events for our target file
        if event.src_path != str(self.file_path):
            return

        # Debounce: ignore if modified too recently
        current_time = time.time()
        if current_time - self.last_modified < self.debounce_seconds:
            return

        self.last_modified = current_time

        # Reindex
        console.print()
        console.print(f"[yellow]File changed: {self.file_path}[/yellow]")
        console.print("[blue]Reindexing...[/blue]")

        try:
            stats = self.indexer.index_file(
                input_path=self.file_path,
                codebase_name=self.codebase_name,
            )

            console.print()
            console.print("[bold green]Reindexing Complete![/bold green]")
            console.print(f"  Total logs: {stats.total_logs}")
            console.print(f"  Russian logs: {stats.ru_logs}")
            console.print(f"  English logs: {stats.en_logs}")
            console.print(f"  Duration: {stats.duration_seconds:.1f}s")
            console.print()

        except Exception as e:
            console.print(f"[bold red]Reindexing failed:[/bold red] {e}")
            console.print()


def watch_file(
    file_path: Path,
    codebase_name: str,
    config: IndexerConfig,
) -> None:
    """Watch a file for changes and reindex automatically.

    Args:
        file_path: Path to the file to watch
        codebase_name: Name of the codebase
        config: Indexer configuration
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Create indexer
    indexer = LogIndexer(config)

    # Initial indexing
    console.print("[bold blue]LEAP - Watch Mode[/bold blue]")
    console.print(f"Watching: {file_path}")
    console.print(f"Codebase: {codebase_name}")
    console.print()
    console.print("[blue]Performing initial indexing...[/blue]")

    stats = indexer.index_file(
        input_path=file_path,
        codebase_name=codebase_name,
    )

    console.print()
    console.print("[bold green]Initial Indexing Complete![/bold green]")
    console.print(f"  Total logs: {stats.total_logs}")
    console.print(f"  Russian logs: {stats.ru_logs}")
    console.print(f"  English logs: {stats.en_logs}")
    console.print(f"  Duration: {stats.duration_seconds:.1f}s")
    console.print()
    console.print("[yellow]Watching for changes... (Press Ctrl+C to stop)[/yellow]")
    console.print()

    # Setup watcher
    event_handler = LogFileHandler(
        file_path=file_path.resolve(),
        codebase_name=codebase_name,
        indexer=indexer,
    )

    observer = Observer()
    observer.schedule(
        event_handler,
        path=str(file_path.parent),
        recursive=False,
    )

    # Start watching
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]Stopping watcher...[/yellow]")
        observer.stop()

    observer.join()
    console.print("[green]Watcher stopped.[/green]")
