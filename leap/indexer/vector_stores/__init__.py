"""Vector stores module for LEAP Indexer.

This module provides vector store functionality using various backends.
"""

from leap.indexer.config import IndexerConfig, VectorStoreType

from .base import Document, SearchResult, VectorStore
from .chromadb import ChromaDBVectorStore

__all__ = [
    "VectorStore",
    "Document",
    "SearchResult",
    "ChromaDBVectorStore",
    "get_vector_store",
]


def get_vector_store(config: IndexerConfig) -> VectorStore:
    """Factory function to create a vector store based on configuration.

    Args:
        config: Indexer configuration

    Returns:
        Vector store instance

    Raises:
        ValueError: If the vector store type is not supported
    """
    if config.vector_store == VectorStoreType.CHROMADB:
        return ChromaDBVectorStore(config.chromadb_path)
    elif config.vector_store == VectorStoreType.QDRANT:
        # Import here to avoid dependency issues if qdrant is not installed
        from .qdrant import QdrantVectorStore

        return QdrantVectorStore(config.qdrant_url, config.qdrant_api_key)
    else:
        raise ValueError(f"Unsupported vector store: {config.vector_store}")
