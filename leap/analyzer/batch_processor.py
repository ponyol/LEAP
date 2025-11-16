"""Batch processing utilities for parallel LLM requests."""

import asyncio
import logging
from asyncio import Semaphore
from collections.abc import Callable
from typing import Any, TypeVar

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class ProgressTracker:
    """Track and report progress for batch processing using rich."""

    def __init__(self, total: int, show_progress: bool = True):
        """Initialize progress tracker.

        Args:
            total: Total number of items to process
            show_progress: Whether to show progress bar
        """
        self.total = total
        self.completed = 0
        self.failed = 0
        self.show_progress = show_progress
        self._lock = asyncio.Lock()
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None

        if show_progress:
            self.progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("•"),
                TextColumn("[red]Failed: {task.fields[failed]}"),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("/"),
                TimeRemainingColumn(),
            )
            self.progress.start()
            self.task_id = self.progress.add_task(
                "Analyzing...",
                total=total,
                failed=0
            )

    async def increment(self, success: bool = True) -> None:
        """Increment progress counter.

        Args:
            success: Whether the item was processed successfully
        """
        async with self._lock:
            self.completed += 1
            if not success:
                self.failed += 1

            if self.show_progress and self.progress and self.task_id is not None:
                self.progress.update(
                    self.task_id,
                    advance=1,
                    failed=self.failed
                )

    def finish(self) -> None:
        """Stop the progress display."""
        if self.show_progress and self.progress:
            self.progress.stop()


async def process_batch(
    items: list[T],
    processor: Callable[[T], Any],
    concurrency: int = 10,
    show_progress: bool = True,
    on_error: str = "continue"
) -> list[R | None]:
    """Process items in parallel with concurrency limit.

    This function processes a list of items concurrently, with a maximum
    number of concurrent tasks. It provides progress tracking and error
    handling.

    Args:
        items: List of items to process
        processor: Async function to process each item (must return awaitable)
        concurrency: Maximum number of concurrent tasks
        show_progress: Whether to show progress updates
        on_error: How to handle errors ("continue" or "raise")
            - "continue": Log error and continue with next items
            - "raise": Stop processing and raise the first error

    Returns:
        List of results (same order as input items)
        If on_error="continue", failed items will have None as result

    Raises:
        Exception: If on_error="raise" and any item fails

    Example:
        ```python
        async def analyze(entry):
            # ... analysis logic
            return result

        results = await process_batch(
            log_entries,
            analyze,
            concurrency=20,
            show_progress=True
        )
        ```
    """
    if not items:
        return []

    total = len(items)
    semaphore = Semaphore(concurrency)
    progress = ProgressTracker(total, show_progress)
    results: list[R | None] = [None] * total  # Pre-allocate results list

    async def process_with_limit(index: int, item: T) -> None:
        """Process single item with semaphore limit and progress tracking."""
        async with semaphore:
            try:
                result = await processor(item)
                results[index] = result
                await progress.increment(success=True)

            except Exception as e:
                logger.error(
                    f"Error processing item {index + 1}/{total}: {e}",
                    exc_info=True
                )
                await progress.increment(success=False)

                if on_error == "raise":
                    raise
                else:
                    # on_error == "continue": keep None in results
                    results[index] = None

    # Create tasks for all items with their indices
    tasks = [
        process_with_limit(i, item)
        for i, item in enumerate(items)
    ]

    # Execute all tasks
    try:
        await asyncio.gather(*tasks)
    finally:
        progress.finish()

    return results


async def process_batch_with_retry(
    items: list[T],
    processor: Callable[[T], Any],
    concurrency: int = 10,
    max_retries: int = 3,
    show_progress: bool = True
) -> tuple[list[R | None], list[tuple[int, T, Exception | None]]]:
    """Process items with automatic retry on failure.

    This is similar to process_batch, but automatically retries failed items
    up to max_retries times.

    Args:
        items: List of items to process
        processor: Async function to process each item
        concurrency: Maximum concurrent tasks
        max_retries: Maximum retry attempts per item
        show_progress: Whether to show progress

    Returns:
        Tuple of (successful_results, failed_items)
        - successful_results: List of results (None for failed items)
        - failed_items: List of (index, item, last_exception) for failed items

    Example:
        ```python
        results, failures = await process_batch_with_retry(
            log_entries,
            analyze,
            concurrency=10,
            max_retries=3
        )

        if failures:
            print(f"{len(failures)} items failed after {max_retries} retries")
        ```
    """
    if not items:
        return [], []

    total = len(items)
    semaphore = Semaphore(concurrency)
    progress = ProgressTracker(total, show_progress)
    results: list[R | None] = [None] * total
    failed_items: list[tuple[int, T, Exception | None]] = []

    async def process_with_retry(index: int, item: T) -> None:
        """Process item with retry logic."""
        async with semaphore:
            last_error = None

            for attempt in range(max_retries):
                try:
                    result = await processor(item)
                    results[index] = result
                    await progress.increment(success=True)
                    return  # Success

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Item {index + 1}/{total} failed "
                        f"(attempt {attempt + 1}/{max_retries}): {e}"
                    )

                    if attempt < max_retries - 1:
                        # Wait before retry (exponential backoff)
                        await asyncio.sleep(2 ** attempt)

            # All retries exhausted
            logger.error(
                f"Item {index + 1}/{total} failed after {max_retries} attempts"
            )
            failed_items.append((index, item, last_error))
            await progress.increment(success=False)

    # Create tasks
    tasks = [
        process_with_retry(i, item)
        for i, item in enumerate(items)
    ]

    # Execute
    try:
        await asyncio.gather(*tasks)
    finally:
        progress.finish()

    return results, failed_items
