"""Tests for indexer.vector_stores module."""

from pathlib import Path

import pytest

from leap.indexer.vector_stores.base import Document, SearchResult, VectorStore
from leap.indexer.vector_stores.chromadb import ChromaDBVectorStore


class TestDocument:
    """Tests for Document dataclass."""

    def test_create_document(self) -> None:
        """Test creating a document."""
        doc = Document(
            id="doc1",
            text="This is test content",
            metadata={"source": "test", "category": "example"},
        )

        assert doc.id == "doc1"
        assert doc.text == "This is test content"
        assert doc.metadata["source"] == "test"
        assert doc.metadata["category"] == "example"

    def test_document_empty_metadata(self) -> None:
        """Test document with empty metadata."""
        doc = Document(id="doc1", text="Content", metadata={})

        assert doc.metadata == {}

    def test_document_with_complex_metadata(self) -> None:
        """Test document with complex metadata."""
        doc = Document(
            id="doc1",
            text="Content",
            metadata={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "number": 42,
                "bool": True,
            },
        )

        assert doc.metadata["nested"]["key"] == "value"
        assert doc.metadata["list"] == [1, 2, 3]
        assert doc.metadata["number"] == 42
        assert doc.metadata["bool"] is True


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self) -> None:
        """Test creating a search result."""
        doc = Document(id="doc1", text="Content", metadata={"key": "value"})
        result = SearchResult(document=doc, score=0.95)

        assert result.document == doc
        assert result.score == 0.95

    def test_search_result_ordering(self) -> None:
        """Test that search results can be sorted by score."""
        doc1 = Document(id="1", text="Content", metadata={})
        doc2 = Document(id="2", text="Content", metadata={})
        doc3 = Document(id="3", text="Content", metadata={})

        results = [
            SearchResult(doc1, 0.5),
            SearchResult(doc2, 0.9),
            SearchResult(doc3, 0.7),
        ]

        # Sort by score descending
        sorted_results = sorted(results, key=lambda r: r.score, reverse=True)

        assert sorted_results[0].document.id == "2"
        assert sorted_results[1].document.id == "3"
        assert sorted_results[2].document.id == "1"


class TestVectorStoreBase:
    """Tests for base VectorStore interface."""

    def test_vector_store_is_abstract(self) -> None:
        """Test that VectorStore cannot be instantiated directly."""
        with pytest.raises(TypeError):
            VectorStore()  # type: ignore[abstract]


class TestChromaDBVectorStore:
    """Tests for ChromaDBVectorStore implementation."""

    @pytest.fixture
    def vector_store(self, tmp_path: Path) -> ChromaDBVectorStore:
        """Create ChromaDB vector store with temp directory."""
        persist_dir = tmp_path / "chromadb"
        return ChromaDBVectorStore(persist_directory=persist_dir)

    @pytest.fixture
    def sample_documents(self) -> list[Document]:
        """Create sample documents for testing."""
        return [
            Document(
                id="doc1",
                text="The quick brown fox jumps over the lazy dog",
                metadata={"category": "animals", "language": "en"},
            ),
            Document(
                id="doc2",
                text="Python is a popular programming language",
                metadata={"category": "programming", "language": "en"},
            ),
            Document(
                id="doc3",
                text="Machine learning is a subset of artificial intelligence",
                metadata={"category": "ai", "language": "en"},
            ),
        ]

    @pytest.fixture
    def sample_embeddings(self) -> list[list[float]]:
        """Create sample embeddings (simple vectors for testing)."""
        return [
            [0.1, 0.2, 0.3],  # doc1
            [0.4, 0.5, 0.6],  # doc2
            [0.7, 0.8, 0.9],  # doc3
        ]

    def test_initialization(self, tmp_path: Path) -> None:
        """Test vector store initialization."""
        persist_dir = tmp_path / "test_chromadb"
        store = ChromaDBVectorStore(persist_directory=persist_dir)

        assert store.persist_directory == persist_dir
        assert persist_dir.exists()
        assert store.client is not None

    def test_create_collection(self, vector_store: ChromaDBVectorStore) -> None:
        """Test creating a collection."""
        vector_store.create_collection(
            collection_name="test_collection",
            dimension=384,
            metadata={"description": "Test collection"},
        )

        assert vector_store.collection_exists("test_collection")

    def test_create_collection_recreates_existing(
        self, vector_store: ChromaDBVectorStore
    ) -> None:
        """Test that creating collection deletes existing one."""
        # Create collection
        vector_store.create_collection("test_collection", dimension=384)

        # Create again (should delete and recreate)
        vector_store.create_collection("test_collection", dimension=384)

        # Should still exist
        assert vector_store.collection_exists("test_collection")

    def test_delete_collection(self, vector_store: ChromaDBVectorStore) -> None:
        """Test deleting a collection."""
        vector_store.create_collection("test_collection", dimension=384)
        assert vector_store.collection_exists("test_collection")

        vector_store.delete_collection("test_collection")

        assert not vector_store.collection_exists("test_collection")

    def test_delete_nonexistent_collection(
        self, vector_store: ChromaDBVectorStore
    ) -> None:
        """Test deleting collection that doesn't exist (should not raise)."""
        # Should not raise exception
        vector_store.delete_collection("nonexistent_collection")

    def test_collection_exists(self, vector_store: ChromaDBVectorStore) -> None:
        """Test checking if collection exists."""
        assert not vector_store.collection_exists("test_collection")

        vector_store.create_collection("test_collection", dimension=384)

        assert vector_store.collection_exists("test_collection")

    def test_list_collections_empty(self, vector_store: ChromaDBVectorStore) -> None:
        """Test listing collections when none exist."""
        collections = vector_store.list_collections()

        assert collections == []

    def test_list_collections(self, vector_store: ChromaDBVectorStore) -> None:
        """Test listing collections."""
        vector_store.create_collection("collection1", dimension=384)
        vector_store.create_collection("collection2", dimension=384)

        collections = vector_store.list_collections()

        assert len(collections) == 2
        assert "collection1" in collections
        assert "collection2" in collections

    def test_add_documents(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test adding documents to collection."""
        vector_store.create_collection("test_collection", dimension=3)

        vector_store.add_documents(
            collection_name="test_collection",
            documents=sample_documents,
            embeddings=sample_embeddings,
        )

        # Verify collection has documents
        stats = vector_store.get_collection_stats("test_collection")
        assert stats["document_count"] == 3

    def test_add_documents_length_mismatch(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
    ) -> None:
        """Test that adding documents with mismatched embeddings raises error."""
        vector_store.create_collection("test_collection", dimension=3)

        # Provide fewer embeddings than documents
        embeddings = [[0.1, 0.2, 0.3]]

        with pytest.raises(ValueError, match="must match"):
            vector_store.add_documents(
                collection_name="test_collection",
                documents=sample_documents,
                embeddings=embeddings,
            )

    def test_search_documents(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test searching for similar documents."""
        vector_store.create_collection("test_collection", dimension=3)
        vector_store.add_documents(
            collection_name="test_collection",
            documents=sample_documents,
            embeddings=sample_embeddings,
        )

        # Search with query similar to first embedding
        query_embedding = [0.1, 0.2, 0.3]
        results = vector_store.search(
            collection_name="test_collection",
            query_embedding=query_embedding,
            top_k=2,
        )

        assert len(results) > 0
        assert len(results) <= 2
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_returns_correct_documents(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test that search returns documents with highest similarity."""
        vector_store.create_collection("test_collection", dimension=3)
        vector_store.add_documents(
            collection_name="test_collection",
            documents=sample_documents,
            embeddings=sample_embeddings,
        )

        # Query very similar to doc1's embedding
        query_embedding = [0.1, 0.2, 0.3]
        results = vector_store.search(
            collection_name="test_collection",
            query_embedding=query_embedding,
            top_k=1,
        )

        # Should return doc1 as most similar
        assert len(results) == 1
        assert results[0].document.id == "doc1"

    def test_search_with_top_k(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test that top_k limits number of results."""
        vector_store.create_collection("test_collection", dimension=3)
        vector_store.add_documents(
            collection_name="test_collection",
            documents=sample_documents,
            embeddings=sample_embeddings,
        )

        query_embedding = [0.5, 0.5, 0.5]

        # Test different top_k values
        results_1 = vector_store.search("test_collection", query_embedding, top_k=1)
        results_2 = vector_store.search("test_collection", query_embedding, top_k=2)
        results_all = vector_store.search("test_collection", query_embedding, top_k=10)

        assert len(results_1) == 1
        assert len(results_2) == 2
        assert len(results_all) == 3  # Only 3 documents exist

    def test_search_empty_collection(
        self, vector_store: ChromaDBVectorStore
    ) -> None:
        """Test searching in empty collection."""
        vector_store.create_collection("empty_collection", dimension=3)

        results = vector_store.search(
            collection_name="empty_collection",
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
        )

        assert results == []

    def test_get_collection_stats(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test getting collection statistics."""
        vector_store.create_collection(
            collection_name="test_collection",
            dimension=3,
            metadata={"description": "Test"},
        )
        vector_store.add_documents(
            collection_name="test_collection",
            documents=sample_documents,
            embeddings=sample_embeddings,
        )

        stats = vector_store.get_collection_stats("test_collection")

        assert stats["name"] == "test_collection"
        assert stats["document_count"] == 3
        assert "metadata" in stats

    def test_get_stats_empty_collection(
        self, vector_store: ChromaDBVectorStore
    ) -> None:
        """Test getting stats for empty collection."""
        vector_store.create_collection("empty_collection", dimension=3)

        stats = vector_store.get_collection_stats("empty_collection")

        assert stats["document_count"] == 0

    def test_persistence(self, tmp_path: Path) -> None:
        """Test that data persists across vector store instances."""
        persist_dir = tmp_path / "persist_test"

        # Create store and add data
        store1 = ChromaDBVectorStore(persist_directory=persist_dir)
        store1.create_collection("test_collection", dimension=3)
        store1.add_documents(
            collection_name="test_collection",
            documents=[Document(id="doc1", text="Test", metadata={})],
            embeddings=[[0.1, 0.2, 0.3]],
        )

        # Create new store instance (should load persisted data)
        store2 = ChromaDBVectorStore(persist_directory=persist_dir)

        # Should see the collection and document
        assert store2.collection_exists("test_collection")
        stats = store2.get_collection_stats("test_collection")
        assert stats["document_count"] == 1

    def test_multiple_collections(
        self,
        vector_store: ChromaDBVectorStore,
        sample_documents: list[Document],
        sample_embeddings: list[list[float]],
    ) -> None:
        """Test working with multiple collections."""
        # Create two collections
        vector_store.create_collection("collection1", dimension=3)
        vector_store.create_collection("collection2", dimension=3)

        # Add documents to each
        vector_store.add_documents(
            "collection1", sample_documents[:2], sample_embeddings[:2]
        )
        vector_store.add_documents(
            "collection2", sample_documents[2:], sample_embeddings[2:]
        )

        # Verify stats
        stats1 = vector_store.get_collection_stats("collection1")
        stats2 = vector_store.get_collection_stats("collection2")

        assert stats1["document_count"] == 2
        assert stats2["document_count"] == 1

        # Verify search works independently
        results1 = vector_store.search("collection1", [0.1, 0.2, 0.3], top_k=5)
        results2 = vector_store.search("collection2", [0.7, 0.8, 0.9], top_k=5)

        assert len(results1) == 2
        assert len(results2) == 1
