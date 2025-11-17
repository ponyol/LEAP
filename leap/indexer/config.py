"""Configuration for LEAP Indexer.

This module defines the configuration models for the log indexer,
including vector store settings and embedding provider settings.
"""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class VectorStoreType(str, Enum):
    """Supported vector store types."""

    CHROMADB = "chromadb"
    QDRANT = "qdrant"


class EmbeddingModelType(str, Enum):
    """Supported embedding model types."""

    SENTENCE_TRANSFORMERS = "sentence-transformers"


class IndexerConfig(BaseModel):
    """Configuration for the log indexer.

    Attributes:
        vector_store: Type of vector store to use
        embedding_model: Type of embedding model to use
        embedding_model_name: Name of the embedding model
        chromadb_path: Path to ChromaDB storage (for ChromaDB only)
        qdrant_url: Qdrant server URL (for Qdrant only)
        qdrant_api_key: Qdrant API key (optional, for Qdrant Cloud)
        batch_size: Batch size for embedding generation
        show_progress: Whether to show progress bar
    """

    vector_store: VectorStoreType = Field(
        default=VectorStoreType.CHROMADB,
        description="Vector store type (chromadb or qdrant)",
    )
    embedding_model: EmbeddingModelType = Field(
        default=EmbeddingModelType.SENTENCE_TRANSFORMERS,
        description="Embedding model type",
    )
    embedding_model_name: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="Name of the embedding model",
    )

    # ChromaDB settings
    chromadb_path: Path = Field(
        default=Path(".leap_data/chromadb"),
        description="Path to ChromaDB storage directory",
    )

    # Qdrant settings
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL",
    )
    qdrant_api_key: str | None = Field(
        default=None,
        description="Qdrant API key (optional, for Qdrant Cloud)",
    )

    # Processing settings
    batch_size: int = Field(
        default=32,
        description="Batch size for embedding generation",
        ge=1,
        le=128,
    )
    show_progress: bool = Field(
        default=True,
        description="Show progress bar during indexing",
    )

    model_config = {"frozen": True}
