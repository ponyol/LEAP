"""Tests for indexer.embeddings module."""

import pytest

from leap.indexer.embeddings.base import EmbeddingModel
from leap.indexer.embeddings.sentence_transformers import SentenceTransformerEmbedding


class TestEmbeddingModelBase:
    """Tests for base EmbeddingModel interface."""

    def test_embedding_model_is_abstract(self) -> None:
        """Test that EmbeddingModel cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingModel()  # type: ignore[abstract]


class TestSentenceTransformerEmbedding:
    """Tests for SentenceTransformerEmbedding implementation."""

    @pytest.fixture
    def model(self) -> SentenceTransformerEmbedding:
        """Create SentenceTransformerEmbedding with small model for testing."""
        # Use a small model for testing
        return SentenceTransformerEmbedding(model_name="all-MiniLM-L6-v2")

    def test_initialization(self) -> None:
        """Test model initialization."""
        model = SentenceTransformerEmbedding(model_name="all-MiniLM-L6-v2")

        assert model.model_name == "all-MiniLM-L6-v2"
        assert model.model is not None

    def test_embed_text(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding single text."""
        text = "This is a test sentence for embedding."

        embedding = model.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_batch(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding batch of texts."""
        texts = [
            "First sentence",
            "Second sentence",
            "Third sentence",
        ]

        embeddings = model.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) > 0 for emb in embeddings)

    def test_embed_empty_string(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding empty string."""
        embedding = model.embed_text("")

        assert isinstance(embedding, list)
        assert len(embedding) > 0  # Model should still return embedding

    def test_embed_empty_batch(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding empty batch."""
        embeddings = model.embed_batch([])

        assert embeddings == []

    def test_get_dimension(self, model: SentenceTransformerEmbedding) -> None:
        """Test getting embedding dimension."""
        dimension = model.get_dimension()

        assert isinstance(dimension, int)
        assert dimension > 0
        # all-MiniLM-L6-v2 has 384 dimensions
        assert dimension == 384

    def test_embedding_consistency(
        self, model: SentenceTransformerEmbedding
    ) -> None:
        """Test that same text produces same embedding."""
        text = "Test consistency"

        embedding1 = model.embed_text(text)
        embedding2 = model.embed_text(text)

        # Should be identical
        assert embedding1 == embedding2

    def test_batch_vs_single_embedding(
        self, model: SentenceTransformerEmbedding
    ) -> None:
        """Test that batch embedding gives same results as single embeddings."""
        texts = ["First text", "Second text"]

        # Embed individually
        single_embeddings = [model.embed_text(text) for text in texts]

        # Embed as batch
        batch_embeddings = model.embed_batch(texts)

        # Should be very similar (allowing for tiny floating point differences)
        assert len(single_embeddings) == len(batch_embeddings)
        for single, batch in zip(single_embeddings, batch_embeddings):
            assert len(single) == len(batch)
            # Check first few dimensions are very close
            for s, b in zip(single[:10], batch[:10]):
                assert abs(s - b) < 0.0001

    def test_different_texts_different_embeddings(
        self, model: SentenceTransformerEmbedding
    ) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "The cat sat on the mat"
        text2 = "The dog ran through the park"

        embedding1 = model.embed_text(text1)
        embedding2 = model.embed_text(text2)

        # Should be different
        assert embedding1 != embedding2

    def test_similar_texts_similar_embeddings(
        self, model: SentenceTransformerEmbedding
    ) -> None:
        """Test that similar texts produce similar embeddings."""
        text1 = "The cat sat on the mat"
        text2 = "A cat is sitting on a mat"

        embedding1 = model.embed_text(text1)
        embedding2 = model.embed_text(text2)

        # Calculate cosine similarity
        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            magnitude_a = sum(x * x for x in a) ** 0.5
            magnitude_b = sum(x * x for x in b) ** 0.5
            return dot_product / (magnitude_a * magnitude_b)

        similarity = cosine_similarity(embedding1, embedding2)

        # Similar texts should have high cosine similarity (> 0.5)
        assert similarity > 0.5

    def test_long_text_embedding(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding very long text."""
        long_text = " ".join(["This is a sentence."] * 100)

        embedding = model.embed_text(long_text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384  # Dimension should be consistent

    def test_special_characters(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding text with special characters."""
        text = "Hello! @#$%^&*() 你好 🎉"

        embedding = model.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0

    def test_numeric_text(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding purely numeric text."""
        text = "12345 67890"

        embedding = model.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0

    def test_batch_size_larger_than_default(
        self, model: SentenceTransformerEmbedding
    ) -> None:
        """Test embedding batch larger than typical batch size."""
        # Create 100 texts
        texts = [f"Text number {i}" for i in range(100)]

        embeddings = model.embed_batch(texts, batch_size=32)

        assert len(embeddings) == 100
        assert all(len(emb) == 384 for emb in embeddings)

    def test_custom_batch_size(self, model: SentenceTransformerEmbedding) -> None:
        """Test embedding with custom batch size."""
        texts = [f"Text {i}" for i in range(10)]

        # Use small batch size
        embeddings = model.embed_batch(texts, batch_size=2)

        assert len(embeddings) == 10
        assert all(isinstance(emb, list) for emb in embeddings)

    def test_normalization(self, model: SentenceTransformerEmbedding) -> None:
        """Test that embeddings are normalized (unit vectors)."""
        text = "Test normalization"

        embedding = model.embed_text(text)

        # Calculate magnitude
        magnitude = sum(x * x for x in embedding) ** 0.5

        # Should be very close to 1.0 (normalized)
        assert abs(magnitude - 1.0) < 0.001
