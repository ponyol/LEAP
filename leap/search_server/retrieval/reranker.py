"""Re-ranker for search results.

This module provides re-ranking functionality using a cross-encoder model
to improve search result relevance.
"""

from sentence_transformers import CrossEncoder


class Reranker:
    """Re-ranks search results using a cross-encoder model.

    Uses a cross-encoder model (e.g., jina-reranker-v2-base-multilingual)
    to re-score query-document pairs and improve ranking.

    Attributes:
        model: The loaded CrossEncoder model
        model_name: Name of the model being used
    """

    def __init__(self, model_name: str) -> None:
        """Initialize the reranker.

        Args:
            model_name: Name of the cross-encoder model
                       (e.g., 'jinaai/jina-reranker-v2-base-multilingual')
        """
        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Re-rank documents based on relevance to query.

        Args:
            query: Search query
            documents: List of document texts
            top_k: Optional limit on number of results to return

        Returns:
            List of (index, score) tuples, sorted by score (descending)
            where index is the position in the original documents list
        """
        if not documents:
            return []

        # Create query-document pairs
        pairs = [(query, doc) for doc in documents]

        # Get scores from cross-encoder
        scores = self.model.predict(pairs)

        # Create (index, score) tuples and sort by score
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top_k if specified
        if top_k is not None:
            return indexed_scores[:top_k]

        return indexed_scores
