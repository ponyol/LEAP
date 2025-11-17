"""ChromaDB vector store implementation.

This module implements the vector store interface using ChromaDB.
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from .base import Document, SearchResult, VectorStore


class ChromaDBVectorStore(VectorStore):
    """Vector store implementation using ChromaDB.

    ChromaDB is an embedded vector database that requires no external services.
    Data is stored locally on disk.

    Attributes:
        client: ChromaDB client instance
        persist_directory: Path to ChromaDB storage directory
    """

    def __init__(self, persist_directory: Path) -> None:
        """Initialize ChromaDB vector store.

        Args:
            persist_directory: Path to ChromaDB storage directory
        """
        self.persist_directory = persist_directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.Client(
            Settings(
                persist_directory=str(persist_directory),
                anonymized_telemetry=False,
            )
        )

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a new collection.

        Args:
            collection_name: Name of the collection
            dimension: Dimension of the embedding vectors
            metadata: Optional metadata for the collection
        """
        # Delete collection if it exists (recreate)
        if self.collection_exists(collection_name):
            self.delete_collection(collection_name)

        # Create new collection
        self.client.create_collection(
            name=collection_name,
            metadata=metadata or {},
        )

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection.

        Args:
            collection_name: Name of the collection to delete
        """
        try:
            self.client.delete_collection(name=collection_name)
        except ValueError:
            # Collection doesn't exist, ignore
            pass

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists.

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists, False otherwise
        """
        collections = self.client.list_collections()
        return any(c.name == collection_name for c in collections)

    def add_documents(
        self,
        collection_name: str,
        documents: list[Document],
        embeddings: list[list[float]],
    ) -> None:
        """Add documents to a collection.

        Args:
            collection_name: Name of the collection
            documents: List of documents to add
            embeddings: List of embedding vectors (one per document)

        Raises:
            ValueError: If collection doesn't exist or documents/embeddings length mismatch
        """
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")

        collection = self.client.get_collection(name=collection_name)

        # Prepare data for ChromaDB
        ids = [doc.id for doc in documents]
        texts = [doc.text for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Add to collection
        # Note: ChromaDB type hints are overly strict. list[list[float]] is valid.
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            collection_name: Name of the collection
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters (ChromaDB where clause)

        Returns:
            List of search results, sorted by similarity (descending)
        """
        collection = self.client.get_collection(name=collection_name)

        # Query collection
        # Note: ChromaDB type hints are overly strict. list[list[float]] is valid.
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters,
        )

        # Convert to SearchResult objects
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                metadata_raw = results["metadatas"][0][i] if results["metadatas"] else {}
                # Convert chromadb metadata format to dict[str, Any]
                metadata: dict[str, Any] = dict(metadata_raw) if metadata_raw else {}

                doc = Document(
                    id=results["ids"][0][i],
                    text=results["documents"][0][i] if results["documents"] else "",
                    metadata=metadata,
                )
                # ChromaDB returns distances, convert to similarity score (1 - distance)
                # Distance is L2 distance, normalized to [0, 2]
                distance = results["distances"][0][i] if results["distances"] else 1.0
                score = 1.0 - (distance / 2.0)  # Convert to [0, 1] range
                search_results.append(SearchResult(document=doc, score=score))

        return search_results

    def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get statistics about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection statistics
        """
        collection = self.client.get_collection(name=collection_name)
        count = collection.count()

        return {
            "name": collection_name,
            "document_count": count,
            "metadata": collection.metadata,
        }

    def list_collections(self) -> list[str]:
        """List all available collections.

        Returns:
            List of collection names
        """
        collections = self.client.list_collections()
        return [c.name for c in collections]
