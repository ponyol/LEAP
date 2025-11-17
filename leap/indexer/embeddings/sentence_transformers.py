"""Sentence Transformers embedding provider.

This module implements the embedding provider using the sentence-transformers library.
"""

from sentence_transformers import SentenceTransformer

from .base import EmbeddingProvider


class SentenceTransformersEmbeddings(EmbeddingProvider):
    """Embedding provider using Sentence Transformers.

    Uses the sentence-transformers library to generate embeddings.
    Supports multilingual models like paraphrase-multilingual-MiniLM-L12-v2.

    Attributes:
        model: The loaded SentenceTransformer model
        model_name: Name of the model being used
    """

    def __init__(self, model_name: str) -> None:
        """Initialize the Sentence Transformers provider.

        Args:
            model_name: Name of the Sentence Transformers model
                       (e.g., 'paraphrase-multilingual-MiniLM-L12-v2')
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors (one per document)
        """
        # Convert numpy arrays to lists
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector for the query
        """
        embedding = self.model.encode(text, show_progress_bar=False)
        result: list[float] = embedding.tolist()
        return result

    def get_dimension(self) -> int:
        """Get the dimension of the embedding vectors.

        Returns:
            Dimension of the embedding vectors
        """
        # Get dimension from model's configuration
        dimension: int = self.model.get_sentence_embedding_dimension()
        return dimension
