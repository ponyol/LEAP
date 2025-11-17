"""Base interface for vector stores.

This module defines the abstract interface that all vector stores must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class Document:
    """A document with text content and metadata.

    Attributes:
        id: Unique document identifier
        text: Text content of the document
        embedding: Embedding vector (optional, can be generated separately)
        metadata: Additional metadata for the document
    """

    def __init__(
        self,
        id: str,
        text: str,
        metadata: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> None:
        """Initialize a document.

        Args:
            id: Unique document identifier
            text: Text content
            metadata: Additional metadata
            embedding: Pre-computed embedding vector (optional)
        """
        self.id = id
        self.text = text
        self.metadata = metadata
        self.embedding = embedding


class SearchResult:
    """A search result with document and similarity score.

    Attributes:
        document: The matched document
        score: Similarity score (higher is better)
    """

    def __init__(self, document: Document, score: float) -> None:
        """Initialize a search result.

        Args:
            document: The matched document
            score: Similarity score
        """
        self.document = document
        self.score = score


class VectorStore(ABC):
    """Abstract base class for vector stores.

    All vector stores must implement this interface to store and search documents.
    """

    @abstractmethod
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
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection.

        Args:
            collection_name: Name of the collection to delete
        """
        pass

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists.

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists, False otherwise
        """
        pass

    @abstractmethod
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
        """
        pass

    @abstractmethod
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
            filters: Optional metadata filters

        Returns:
            List of search results, sorted by similarity (descending)
        """
        pass

    @abstractmethod
    def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get statistics about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection statistics (e.g., document count)
        """
        pass

    @abstractmethod
    def list_collections(self) -> list[str]:
        """List all available collections.

        Returns:
            List of collection names
        """
        pass
