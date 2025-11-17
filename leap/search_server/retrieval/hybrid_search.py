"""Hybrid search combining BM25 and vector search.

This module provides hybrid search functionality that combines
keyword-based search (BM25) with semantic vector search.
"""


from rank_bm25 import BM25Okapi

from leap.indexer.vector_stores import SearchResult


class HybridSearcher:
    """Combines BM25 and vector search for better results.

    Uses a weighted combination of BM25 (keyword) and vector (semantic) search
    to leverage both approaches.

    Attributes:
        bm25_weight: Weight for BM25 scores (default: 0.5)
        vector_weight: Weight for vector scores (default: 0.5)
    """

    def __init__(
        self,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> None:
        """Initialize hybrid searcher.

        Args:
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector scores (0-1)
        """
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight

    def search(
        self,
        query: str,
        vector_results: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Perform hybrid search.

        Args:
            query: Search query
            vector_results: Results from vector search
            top_k: Number of results to return

        Returns:
            List of search results, re-ranked using hybrid scoring
        """
        if not vector_results:
            return []

        # Extract documents and create BM25 index
        documents = [r.document.text for r in vector_results]
        tokenized_docs = [doc.lower().split() for doc in documents]
        bm25 = BM25Okapi(tokenized_docs)

        # Get BM25 scores
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)

        # Normalize BM25 scores to [0, 1]
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        normalized_bm25 = [s / max_bm25 for s in bm25_scores]

        # Combine scores (vector scores are already in [0, 1])
        hybrid_scores = []
        for i, result in enumerate(vector_results):
            hybrid_score = (
                self.bm25_weight * normalized_bm25[i]
                + self.vector_weight * result.score
            )
            hybrid_scores.append((i, hybrid_score))

        # Sort by hybrid score and take top_k
        hybrid_scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in hybrid_scores[:top_k]]

        # Return re-ranked results
        reranked_results = []
        for _, (orig_idx, score) in zip(top_indices, hybrid_scores[:top_k], strict=True):
            result = vector_results[orig_idx]
            # Update score to hybrid score
            result.score = score
            reranked_results.append(result)

        return reranked_results
