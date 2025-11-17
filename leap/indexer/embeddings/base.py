"""Base interface for embedding providers.

This module defines the abstract interface that all embedding providers must implement.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    All embedding providers must implement this interface to generate
    embeddings for text documents.
    """

    @abstractmethod
    def __init__(self, model_name: str) -> None:
        """Initialize the embedding provider.

        Args:
            model_name: Name of the embedding model to use
        """
        pass

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors (one per document)
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector for the query
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimension of the embedding vectors.

        Returns:
            Dimension of the embedding vectors
        """
        pass
