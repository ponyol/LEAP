"""Qdrant vector store implementation.

This module implements the vector store interface using Qdrant.
"""

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .base import Document, SearchResult, VectorStore


class QdrantVectorStore(VectorStore):
    """Vector store implementation using Qdrant.

    Qdrant is a production-ready vector database that can run as a separate service.
    Supports better compression and performance compared to ChromaDB.

    Attributes:
        client: Qdrant client instance
        url: Qdrant server URL
    """

    def __init__(self, url: str, api_key: str | None = None) -> None:
        """Initialize Qdrant vector store.

        Args:
            url: Qdrant server URL (e.g., 'http://localhost:6333')
            api_key: Optional API key for Qdrant Cloud
        """
        self.url = url
        self.client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=60,
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
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
        )

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection.

        Args:
            collection_name: Name of the collection to delete
        """
        try:
            self.client.delete_collection(collection_name=collection_name)
        except Exception:
            # Collection doesn't exist, ignore
            pass

    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists.

        Args:
            collection_name: Name of the collection

        Returns:
            True if collection exists, False otherwise
        """
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

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
            ValueError: If documents/embeddings length mismatch
        """
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")

        # Prepare points for Qdrant
        points = []
        for doc, embedding in zip(documents, embeddings, strict=True):
            point = PointStruct(
                id=hash(doc.id) % (2**63),  # Convert string ID to int
                vector=embedding,
                payload={
                    "id": doc.id,
                    "text": doc.text,
                    **doc.metadata,
                },
            )
            points.append(point)

        # Upload in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch,
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
            filters: Optional metadata filters

        Returns:
            List of search results, sorted by similarity (descending)
        """
        # Convert filters to Qdrant format if provided
        qdrant_filter = None
        if filters:
            # NOTE: This is a simplified filter conversion
            # For production, implement proper filter mapping
            qdrant_filter = filters

        # Search
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
        ).points

        # Convert to SearchResult objects
        search_results = []
        for result in results:
            payload = result.payload or {}
            doc = Document(
                id=payload.get("id", ""),
                text=payload.get("text", ""),
                metadata={k: v for k, v in payload.items() if k not in ["id", "text"]},
            )
            # Qdrant returns similarity score (higher is better)
            search_results.append(SearchResult(document=doc, score=result.score))

        return search_results

    def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get statistics about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection statistics
        """
        collection_info = self.client.get_collection(collection_name=collection_name)

        return {
            "name": collection_name,
            "document_count": collection_info.points_count,
            "metadata": {},
        }

    def list_collections(self) -> list[str]:
        """List all available collections.

        Returns:
            List of collection names
        """
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]
