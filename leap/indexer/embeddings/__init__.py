"""Embeddings module for LEAP Indexer.

This module provides embedding generation functionality using various providers.
"""

from leap.indexer.config import EmbeddingModelType, IndexerConfig

from .base import EmbeddingProvider
from .sentence_transformers import SentenceTransformersEmbeddings

__all__ = [
    "EmbeddingProvider",
    "SentenceTransformersEmbeddings",
    "get_embedding_provider",
]


def get_embedding_provider(config: IndexerConfig) -> EmbeddingProvider:
    """Factory function to create an embedding provider based on configuration.

    Args:
        config: Indexer configuration

    Returns:
        Embedding provider instance

    Raises:
        ValueError: If the embedding model type is not supported
    """
    if config.embedding_model == EmbeddingModelType.SENTENCE_TRANSFORMERS:
        return SentenceTransformersEmbeddings(config.embedding_model_name)
    else:
        raise ValueError(f"Unsupported embedding model: {config.embedding_model}")
