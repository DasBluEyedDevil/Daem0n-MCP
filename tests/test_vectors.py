"""Tests for the vector embeddings module."""

import pytest
from devilmcp import vectors


class TestVectorAvailability:
    """Test vector availability detection."""

    def test_is_available_returns_bool(self):
        """is_available should return a boolean."""
        result = vectors.is_available()
        assert isinstance(result, bool)


class TestVectorIndex:
    """Test the VectorIndex class."""

    def test_create_empty_index(self):
        """Can create an empty vector index."""
        index = vectors.VectorIndex()
        assert len(index) == 0

    def test_search_empty_returns_empty(self):
        """Search on empty index returns empty list."""
        index = vectors.VectorIndex()
        results = index.search("test query")
        assert results == []


class TestHybridSearch:
    """Test the hybrid search combining TF-IDF and vectors."""

    def test_hybrid_fallback_to_tfidf(self):
        """Hybrid search falls back to TF-IDF when vectors unavailable."""
        from devilmcp.similarity import TFIDFIndex

        tfidf = TFIDFIndex()
        tfidf.add_document(1, "JWT authentication for API security")
        tfidf.add_document(2, "Database migration and schema changes")

        hybrid = vectors.HybridSearch(tfidf)
        results = hybrid.search("API authentication")

        # Should get TF-IDF results
        assert len(results) >= 1
        # Doc 1 should match
        doc_ids = [r[0] for r in results]
        assert 1 in doc_ids


class TestEncodeDecode:
    """Test vector encoding and decoding."""

    def test_encode_returns_none_when_unavailable(self):
        """encode returns None when vectors not available."""
        if not vectors.is_available():
            result = vectors.encode("test text")
            assert result is None

    def test_decode_empty_returns_none(self):
        """decode returns None for empty bytes."""
        result = vectors.decode(b"")
        assert result is None

    def test_decode_none_returns_none(self):
        """decode returns None for None input."""
        result = vectors.decode(None)
        assert result is None


class TestCosineSimWithoutVectors:
    """Test cosine similarity when numpy not available."""

    def test_cosine_returns_zero_when_unavailable(self):
        """cosine_similarity returns 0.0 when numpy not available."""
        if not vectors.is_available():
            result = vectors.cosine_similarity([1, 2, 3], [1, 2, 3])
            # Without numpy, should return 0
            assert result == 0.0


class TestGlobalVectorIndex:
    """Test the global vector index singleton."""

    def test_get_vector_index_returns_index(self):
        """get_vector_index returns a VectorIndex."""
        vectors.reset_vector_index()
        index = vectors.get_vector_index()
        assert isinstance(index, vectors.VectorIndex)

    def test_get_vector_index_returns_same_instance(self):
        """get_vector_index returns the same instance."""
        vectors.reset_vector_index()
        index1 = vectors.get_vector_index()
        index2 = vectors.get_vector_index()
        assert index1 is index2

    def test_reset_clears_index(self):
        """reset_vector_index clears the global index."""
        vectors.reset_vector_index()
        index1 = vectors.get_vector_index()
        vectors.reset_vector_index()
        index2 = vectors.get_vector_index()
        assert index1 is not index2
