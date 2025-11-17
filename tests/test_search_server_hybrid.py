"""Tests for search_server.hybrid_search module."""

from typing import Any

import pytest

from leap.indexer.vector_stores.base import Document, SearchResult
from leap.search_server.hybrid_search import (
    HybridSearcher,
    hybrid_rank_fusion,
    normalize_scores,
)


class TestHybridRankFusion:
    """Tests for hybrid_rank_fusion function."""

    def test_rank_fusion_basic(self) -> None:
        """Test basic rank fusion with two result sets."""
        # Create two sets of search results
        semantic_results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
            {"id": "doc3", "text": "text3"},
        ]

        keyword_results = [
            {"id": "doc2", "text": "text2"},  # Overlap with semantic
            {"id": "doc4", "text": "text4"},
            {"id": "doc1", "text": "text1"},  # Overlap with semantic
        ]

        fused = hybrid_rank_fusion(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            k=60,  # RRF constant
            alpha=0.5,  # Equal weight
        )

        # Should combine both result sets
        assert len(fused) <= 5  # At most 5 unique documents
        assert all("id" in result for result in fused)

    def test_rank_fusion_semantic_weight(self) -> None:
        """Test rank fusion with higher semantic weight."""
        semantic_results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
        ]

        keyword_results = [
            {"id": "doc3", "text": "text3"},
            {"id": "doc4", "text": "text4"},
        ]

        # Alpha = 1.0 means only semantic results
        fused = hybrid_rank_fusion(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            k=60,
            alpha=1.0,
        )

        # Should only have semantic results (or heavily weighted)
        result_ids = [r["id"] for r in fused]
        assert "doc1" in result_ids
        assert "doc2" in result_ids

    def test_rank_fusion_keyword_weight(self) -> None:
        """Test rank fusion with higher keyword weight."""
        semantic_results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
        ]

        keyword_results = [
            {"id": "doc3", "text": "text3"},
            {"id": "doc4", "text": "text4"},
        ]

        # Alpha = 0.0 means only keyword results
        fused = hybrid_rank_fusion(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            k=60,
            alpha=0.0,
        )

        # Should only have keyword results (or heavily weighted)
        result_ids = [r["id"] for r in fused]
        assert "doc3" in result_ids
        assert "doc4" in result_ids

    def test_rank_fusion_empty_semantic(self) -> None:
        """Test rank fusion with empty semantic results."""
        keyword_results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
        ]

        fused = hybrid_rank_fusion(
            semantic_results=[],
            keyword_results=keyword_results,
            k=60,
            alpha=0.5,
        )

        # Should return keyword results
        assert len(fused) == 2
        result_ids = [r["id"] for r in fused]
        assert "doc1" in result_ids
        assert "doc2" in result_ids

    def test_rank_fusion_empty_keyword(self) -> None:
        """Test rank fusion with empty keyword results."""
        semantic_results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
        ]

        fused = hybrid_rank_fusion(
            semantic_results=semantic_results,
            keyword_results=[],
            k=60,
            alpha=0.5,
        )

        # Should return semantic results
        assert len(fused) == 2
        result_ids = [r["id"] for r in fused]
        assert "doc1" in result_ids
        assert "doc2" in result_ids

    def test_rank_fusion_both_empty(self) -> None:
        """Test rank fusion with both result sets empty."""
        fused = hybrid_rank_fusion(
            semantic_results=[],
            keyword_results=[],
            k=60,
            alpha=0.5,
        )

        assert fused == []

    def test_rank_fusion_overlapping_results(self) -> None:
        """Test rank fusion correctly handles overlapping documents."""
        # Same documents in both lists
        results = [
            {"id": "doc1", "text": "text1"},
            {"id": "doc2", "text": "text2"},
        ]

        fused = hybrid_rank_fusion(
            semantic_results=results,
            keyword_results=results,
            k=60,
            alpha=0.5,
        )

        # Should not duplicate documents
        result_ids = [r["id"] for r in fused]
        assert len(result_ids) == len(set(result_ids))  # All unique

    def test_rank_fusion_preserves_metadata(self) -> None:
        """Test that rank fusion preserves document metadata."""
        semantic_results = [
            {"id": "doc1", "text": "text1", "metadata": {"key": "value"}},
        ]

        keyword_results = [
            {"id": "doc2", "text": "text2", "path": "/path/to/file"},
        ]

        fused = hybrid_rank_fusion(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            k=60,
            alpha=0.5,
        )

        # Find doc1 in results
        doc1 = next((r for r in fused if r["id"] == "doc1"), None)
        assert doc1 is not None
        assert "metadata" in doc1
        assert doc1["metadata"]["key"] == "value"


class TestNormalizeScores:
    """Tests for normalize_scores function."""

    def test_normalize_basic(self) -> None:
        """Test basic score normalization."""
        results = [
            {"id": "doc1", "score": 0.9},
            {"id": "doc2", "score": 0.5},
            {"id": "doc3", "score": 0.1},
        ]

        normalized = normalize_scores(results)

        # All scores should be between 0 and 1
        assert all(0 <= r["score"] <= 1 for r in normalized)

        # Highest score should be 1.0
        assert normalized[0]["score"] == 1.0

        # Lowest score should be 0.0
        assert normalized[2]["score"] == 0.0

        # Middle score should be in between
        assert 0 < normalized[1]["score"] < 1

    def test_normalize_equal_scores(self) -> None:
        """Test normalization when all scores are equal."""
        results = [
            {"id": "doc1", "score": 0.5},
            {"id": "doc2", "score": 0.5},
            {"id": "doc3", "score": 0.5},
        ]

        normalized = normalize_scores(results)

        # When all equal, should all be 0.0 (min-max normalization)
        assert all(r["score"] == 0.0 for r in normalized)

    def test_normalize_single_result(self) -> None:
        """Test normalization with single result."""
        results = [{"id": "doc1", "score": 0.7}]

        normalized = normalize_scores(results)

        # Single result should be normalized to 0.0
        assert normalized[0]["score"] == 0.0

    def test_normalize_empty_results(self) -> None:
        """Test normalization with empty results."""
        results: list[dict[str, Any]] = []

        normalized = normalize_scores(results)

        assert normalized == []

    def test_normalize_preserves_order(self) -> None:
        """Test that normalization preserves result order."""
        results = [
            {"id": "doc3", "score": 0.1},
            {"id": "doc1", "score": 0.9},
            {"id": "doc2", "score": 0.5},
        ]

        normalized = normalize_scores(results)

        # Order should be preserved
        assert normalized[0]["id"] == "doc3"
        assert normalized[1]["id"] == "doc1"
        assert normalized[2]["id"] == "doc2"

    def test_normalize_preserves_other_fields(self) -> None:
        """Test that normalization preserves non-score fields."""
        results = [
            {"id": "doc1", "score": 0.9, "text": "content1", "metadata": {"key": "value"}},
            {"id": "doc2", "score": 0.1, "text": "content2"},
        ]

        normalized = normalize_scores(results)

        assert normalized[0]["text"] == "content1"
        assert normalized[0]["metadata"]["key"] == "value"
        assert normalized[1]["text"] == "content2"


class TestHybridSearcher:
    """Tests for HybridSearcher class."""

    @pytest.fixture
    def mock_vector_store(self) -> Any:
        """Create mock vector store."""

        class MockVectorStore:
            def search(
                self, collection_name: str, query_embedding: list[float], top_k: int = 5, filters: dict[str, Any] | None = None
            ) -> list[SearchResult]:
                # Return mock semantic results
                return [
                    SearchResult(
                        document=Document(
                            id="sem_doc1",
                            text="Semantic result 1",
                            metadata={"score": 0.95},
                        ),
                        score=0.95,
                    ),
                    SearchResult(
                        document=Document(
                            id="sem_doc2",
                            text="Semantic result 2",
                            metadata={"score": 0.85},
                        ),
                        score=0.85,
                    ),
                ]

        return MockVectorStore()

    @pytest.fixture
    def mock_embedding_model(self) -> Any:
        """Create mock embedding model."""

        class MockEmbeddingModel:
            def embed_text(self, text: str) -> list[float]:
                # Return simple embedding
                return [0.1, 0.2, 0.3]

            def get_dimension(self) -> int:
                return 3

        return MockEmbeddingModel()

    @pytest.fixture
    def mock_keyword_retriever(self) -> Any:
        """Create mock BM25 retriever."""

        class MockRetriever:
            def get_relevant_documents(self, query: str) -> list[Any]:
                # Return mock keyword results
                class MockDoc:
                    def __init__(self, page_content: str, metadata: dict[str, Any]):
                        self.page_content = page_content
                        self.metadata = metadata

                return [
                    MockDoc("Keyword result 1", {"id": "kw_doc1", "score": 0.9}),
                    MockDoc("Keyword result 2", {"id": "kw_doc2", "score": 0.7}),
                ]

        return MockRetriever()

    def test_initialization(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test HybridSearcher initialization."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
        )

        assert searcher.vector_store == mock_vector_store
        assert searcher.embedding_model == mock_embedding_model
        assert searcher.collection_name == "test_collection"
        assert searcher.alpha == 0.5  # Default

    def test_search_basic(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test basic hybrid search."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
        )

        results = searcher.search(query="test query", top_k=5)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, dict) for r in results)

    def test_search_with_custom_alpha(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test search with custom alpha (semantic weight)."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
            alpha=0.8,  # Favor semantic
        )

        results = searcher.search(query="test query", top_k=5)

        assert len(results) > 0

    def test_search_semantic_only(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test search with alpha=1.0 (semantic only)."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
            alpha=1.0,
        )

        results = searcher.search(query="test query", top_k=5)

        # Should have semantic results
        result_ids = [r["id"] for r in results]
        assert "sem_doc1" in result_ids or "sem_doc2" in result_ids

    def test_search_keyword_only(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test search with alpha=0.0 (keyword only)."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
            alpha=0.0,
        )

        results = searcher.search(query="test query", top_k=5)

        # Should have keyword results
        result_ids = [r["id"] for r in results]
        assert "kw_doc1" in result_ids or "kw_doc2" in result_ids

    def test_search_empty_query(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test search with empty query."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
        )

        results = searcher.search(query="", top_k=5)

        # Should still return results (or empty list)
        assert isinstance(results, list)

    def test_search_top_k_limit(
        self,
        mock_vector_store: Any,
        mock_embedding_model: Any,
        mock_keyword_retriever: Any,
    ) -> None:
        """Test that top_k limits number of results."""
        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            embedding_model=mock_embedding_model,
            keyword_retriever=mock_keyword_retriever,
            collection_name="test_collection",
        )

        results = searcher.search(query="test query", top_k=2)

        # Should respect top_k limit
        assert len(results) <= 2
