"""Configuration for LEAP Search Server.

This module defines the configuration models for the search server,
including vector store settings and server settings.
"""

from pathlib import Path

from pydantic import BaseModel, Field

from leap.indexer.config import VectorStoreType


class SearchServerConfig(BaseModel):
    """Configuration for the search server.

    Attributes:
        host: Server host
        port: Server port
        vector_store: Type of vector store to use
        embedding_model_name: Name of the embedding model
        reranker_model_name: Name of the reranker model
        chromadb_path: Path to ChromaDB storage (for ChromaDB only)
        qdrant_url: Qdrant server URL (for Qdrant only)
        qdrant_api_key: Qdrant API key (optional, for Qdrant Cloud)
        enable_hybrid_search: Enable hybrid search (BM25 + Vector)
        enable_reranking: Enable reranking with cross-encoder
        default_top_k: Default number of results to return
    """

    host: str = Field(
        default="0.0.0.0",
        description="Server host",
    )
    port: int = Field(
        default=8000,
        description="Server port",
        ge=1,
        le=65535,
    )
    vector_store: VectorStoreType = Field(
        default=VectorStoreType.CHROMADB,
        description="Vector store type (chromadb or qdrant)",
    )
    embedding_model_name: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="Name of the embedding model",
    )
    reranker_model_name: str = Field(
        default="jinaai/jina-reranker-v2-base-multilingual",
        description="Name of the reranker model",
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

    # Search settings
    enable_hybrid_search: bool = Field(
        default=True,
        description="Enable hybrid search (BM25 + Vector)",
    )
    enable_reranking: bool = Field(
        default=True,
        description="Enable reranking with cross-encoder",
    )
    default_top_k: int = Field(
        default=5,
        description="Default number of results to return",
        ge=1,
        le=100,
    )

    model_config = {"frozen": True}
