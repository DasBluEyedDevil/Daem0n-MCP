"""
Qdrant Vector Store - Persistent vector storage backend for Daem0n-MCP.

This module provides:
- Persistent vector storage using Qdrant (local mode, no server required)
- Metadata filtering for efficient memory retrieval
- Replaces the in-memory VectorIndex from vectors.py for production use

The store uses sentence-transformers all-MiniLM-L6-v2 embeddings (384 dimensions)
with cosine similarity for semantic matching.
"""

import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """
    Vector storage backend using Qdrant.

    Provides persistent vector storage with metadata filtering capabilities.
    Uses local file-based mode (no server needed for single-user scenarios).
    """

    COLLECTION_MEMORIES = "daem0n_memories"
    COLLECTION_CODE = "daem0n_code_entities"  # Reserved for Phase 2

    def __init__(self, path: str = "./storage/qdrant"):
        """
        Initialize the Qdrant vector store.

        Args:
            path: Directory path for local Qdrant storage.
                  Uses file-based mode (no server required).
        """
        logger.info(f"Initializing Qdrant vector store at: {path}")
        self.client = QdrantClient(path=path)
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """Ensure required collections exist with proper configuration."""
        collections = [c.name for c in self.client.get_collections().collections]

        if self.COLLECTION_MEMORIES not in collections:
            logger.info(f"Creating collection: {self.COLLECTION_MEMORIES}")
            self.client.create_collection(
                collection_name=self.COLLECTION_MEMORIES,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 output dimension
                    distance=Distance.COSINE
                )
            )

    def upsert_memory(
        self,
        memory_id: int,
        embedding: list[float],
        metadata: dict
    ) -> None:
        """
        Store or update a memory's vector embedding.

        Args:
            memory_id: Unique identifier for the memory (from SQLite).
            embedding: Vector embedding (384 dimensions from sentence-transformers).
            metadata: Payload data including category, tags, file_path, worked, etc.
        """
        self.client.upsert(
            collection_name=self.COLLECTION_MEMORIES,
            points=[PointStruct(
                id=memory_id,
                vector=embedding,
                payload=metadata
            )]
        )

    def search(
        self,
        query_vector: list[float],
        limit: int = 20,
        category_filter: Optional[list[str]] = None,
        tags_filter: Optional[list[str]] = None,
        file_path: Optional[str] = None
    ) -> list[tuple[int, float]]:
        """
        Search for similar memories with optional metadata filtering.

        Args:
            query_vector: Query embedding vector (384 dimensions).
            limit: Maximum number of results to return.
            category_filter: Filter to memories in these categories.
            tags_filter: Filter to memories with any of these tags.
            file_path: Filter to memories associated with this file path.

        Returns:
            List of (memory_id, similarity_score) tuples, sorted by score descending.
        """
        from qdrant_client.models import FieldCondition, MatchAny, MatchValue

        filters = []
        if category_filter:
            filters.append(
                FieldCondition(key="category", match=MatchAny(any=category_filter))
            )
        if tags_filter:
            filters.append(
                FieldCondition(key="tags", match=MatchAny(any=tags_filter))
            )
        if file_path:
            filters.append(
                FieldCondition(key="file_path", match=MatchValue(value=file_path))
            )

        results = self.client.search(
            collection_name=self.COLLECTION_MEMORIES,
            query_vector=query_vector,
            query_filter=Filter(must=filters) if filters else None,
            limit=limit
        )

        return [(hit.id, hit.score) for hit in results]

    def delete_memory(self, memory_id: int) -> None:
        """
        Remove a memory's vector from the store.

        Args:
            memory_id: The memory ID to delete.
        """
        self.client.delete(
            collection_name=self.COLLECTION_MEMORIES,
            points_selector=[memory_id]
        )

    def get_count(self) -> int:
        """
        Get the number of vectors in the memories collection.

        Returns:
            Count of stored memory vectors.
        """
        info = self.client.get_collection(self.COLLECTION_MEMORIES)
        return info.points_count

    def close(self) -> None:
        """Close the Qdrant client connection."""
        self.client.close()
