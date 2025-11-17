"""Main indexer module for LEAP.

This module provides the core indexing functionality to load analyzed logs
and index them into a vector database for semantic search.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeRemainingColumn

from leap.indexer.config import IndexerConfig
from leap.indexer.embeddings import get_embedding_provider
from leap.indexer.language_detector import Language, detect_language_for_log_entry
from leap.indexer.vector_stores import Document, get_vector_store

console = Console()


class IndexingStats:
    """Statistics for an indexing operation.

    Attributes:
        total_logs: Total number of logs processed
        ru_logs: Number of Russian logs
        en_logs: Number of English logs
        duration_seconds: Duration of the indexing operation
        collections_created: List of collection names created
    """

    def __init__(self) -> None:
        """Initialize indexing statistics."""
        self.total_logs = 0
        self.ru_logs = 0
        self.en_logs = 0
        self.duration_seconds = 0.0
        self.collections_created: list[str] = []


class LogIndexer:
    """Indexes analyzed logs into a vector database.

    This class orchestrates the indexing process:
    1. Load analyzed logs from JSON
    2. Detect language for each log
    3. Generate embeddings
    4. Store in vector database (separate collections per language)

    Attributes:
        config: Indexer configuration
        embeddings: Embedding provider instance
        vector_store: Vector store instance
    """

    def __init__(self, config: IndexerConfig) -> None:
        """Initialize the log indexer.

        Args:
            config: Indexer configuration
        """
        self.config = config
        self.embeddings = get_embedding_provider(config)
        self.vector_store = get_vector_store(config)

    def index_file(
        self,
        input_path: Path,
        codebase_name: str,
    ) -> IndexingStats:
        """Index logs from an analyzed_logs.json file.

        Args:
            input_path: Path to analyzed_logs.json
            codebase_name: Name of the codebase (e.g., 'backend-python')

        Returns:
            Indexing statistics

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If input file is invalid
        """
        start_time = datetime.now()
        stats = IndexingStats()

        # Load logs
        logs = self._load_logs(input_path)
        stats.total_logs = len(logs)

        # Separate logs by language
        ru_logs: list[dict[str, Any]] = []
        en_logs: list[dict[str, Any]] = []

        for log in logs:
            language = detect_language_for_log_entry(
                log["log_template"],
                log.get("analysis"),
            )
            if language == Language.RUSSIAN:
                ru_logs.append(log)
            else:
                en_logs.append(log)

        stats.ru_logs = len(ru_logs)
        stats.en_logs = len(en_logs)

        # Print language detection results
        if self.config.show_progress:
            console.print(
                f"✓ Detected {stats.ru_logs} Russian logs, {stats.en_logs} English logs"
            )

        # Index logs by language
        if ru_logs:
            collection_name = f"logs_ru_{codebase_name}"
            self._index_logs(ru_logs, collection_name, Language.RUSSIAN)
            stats.collections_created.append(collection_name)

        if en_logs:
            collection_name = f"logs_en_{codebase_name}"
            self._index_logs(en_logs, collection_name, Language.ENGLISH)
            stats.collections_created.append(collection_name)

        # Calculate duration
        end_time = datetime.now()
        stats.duration_seconds = (end_time - start_time).total_seconds()

        return stats

    def _load_logs(self, input_path: Path) -> list[dict[str, Any]]:
        """Load logs from analyzed_logs.json.

        Args:
            input_path: Path to analyzed_logs.json

        Returns:
            List of log dictionaries

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If input file is invalid JSON
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        try:
            with open(input_path, encoding="utf-8") as f:
                data = json.load(f)

            # Support both array format and object with "logs" key
            if isinstance(data, list):
                logs_list: list[dict[str, Any]] = data
                return logs_list
            elif isinstance(data, dict) and "logs" in data:
                logs_list_from_dict: list[dict[str, Any]] = data["logs"]
                return logs_list_from_dict
            else:
                raise ValueError(
                    "Invalid format: expected array or object with 'logs' key"
                )

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

    def _index_logs(
        self,
        logs: list[dict[str, Any]],
        collection_name: str,
        language: Language,
    ) -> None:
        """Index a list of logs into a collection.

        Args:
            logs: List of log dictionaries
            collection_name: Name of the collection
            language: Language of the logs
        """
        # Create collection
        dimension = self.embeddings.get_dimension()
        self.vector_store.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            metadata={"language": language.value},
        )

        if self.config.show_progress:
            console.print(f"✓ Creating collection: {collection_name}")

        # Process logs in batches
        if self.config.show_progress:
            progress: Progress | None = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("•"),
                TextColumn("{task.completed}/{task.total}"),
                TimeRemainingColumn(),
            )
            task: TaskID | None = None
        else:
            progress = None
            task = None

        if progress:
            task = progress.add_task(
                f"Indexing {language.value} logs...",
                total=len(logs),
            )

        try:
            if progress:
                progress.start()

            for i in range(0, len(logs), self.config.batch_size):
                batch = logs[i : i + self.config.batch_size]
                self._index_batch(batch, collection_name)

                if progress and task is not None:
                    progress.update(task, advance=len(batch))

        finally:
            if progress:
                progress.stop()

    def _index_batch(
        self,
        logs: list[dict[str, Any]],
        collection_name: str,
    ) -> None:
        """Index a batch of logs.

        Args:
            logs: List of log dictionaries
            collection_name: Name of the collection
        """
        # Prepare documents
        documents: list[Document] = []
        texts: list[str] = []

        for log in logs:
            # Generate document ID (hash of source_file + log_template)
            source_file = log.get("source_file", "unknown")
            log_template = log.get("log_template", "")
            doc_id = self._generate_document_id(source_file, log_template)

            # Combine log_template and analysis for embedding
            combined_text = log_template
            if log.get("analysis"):
                combined_text = f"{log_template}\n{log['analysis']}"

            # Extract metadata
            metadata = {
                "log_template": log_template,
                "analysis": log.get("analysis", ""),
                "severity": log.get("severity", "INFO"),
                "suggested_action": log.get("suggested_action", ""),
                "source_file": source_file,
                "line_number": log.get("line_number", 0),
                "indexed_at": datetime.now().isoformat(),
            }

            # Parse source_file to extract file_path
            if ":" in source_file:
                file_path = source_file.split(":")[0]
                metadata["file_path"] = file_path

            doc = Document(id=doc_id, text=combined_text, metadata=metadata)
            documents.append(doc)
            texts.append(combined_text)

        # Generate embeddings
        embeddings = self.embeddings.embed_documents(texts)

        # Add to vector store
        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=documents,
            embeddings=embeddings,
        )

    def _generate_document_id(self, source_file: str, log_template: str) -> str:
        """Generate a unique document ID.

        Uses SHA256 hash of source_file + log_template.

        Args:
            source_file: Source file path
            log_template: Log template

        Returns:
            Unique document ID
        """
        content = f"{source_file}::{log_template}"
        return hashlib.sha256(content.encode()).hexdigest()
