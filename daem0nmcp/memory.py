"""
Memory Manager - The core of Daem0nMCP's AI memory system.

This module handles:
- Storing memories (decisions, patterns, warnings, learnings)
- Semantic retrieval using TF-IDF similarity
- Time-based memory decay
- Conflict detection
- Outcome tracking for learning
"""

import logging
import os
import sys
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, or_, func, desc

from .database import DatabaseManager
from .models import Memory, MemoryRelationship
from .config import settings
from .similarity import (
    TFIDFIndex,
    extract_keywords,
    calculate_memory_decay,
    detect_conflict,
)
from .cache import get_recall_cache, make_cache_key
from . import vectors
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

# Valid relationship types for graph edges
VALID_RELATIONSHIPS = frozenset({
    "led_to",         # A caused or resulted in B
    "supersedes",     # A replaces B (B is now outdated)
    "depends_on",     # A requires B to be valid
    "conflicts_with", # A contradicts B
    "related_to",     # General association (weaker)
})

logger = logging.getLogger(__name__)

# =============================================================================
# Constants for scoring and relevance calculations
# =============================================================================

# Boost multipliers for memory relevance scoring
FAILED_DECISION_BOOST = 1.5  # Failed decisions are valuable warnings
WARNING_BOOST = 1.2  # Warnings get moderate boost


def _normalize_file_path(file_path: Optional[str], project_path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize a file path to both absolute and project-relative forms.

    On Windows, also case-folds for consistent matching.

    Args:
        file_path: The file path to normalize (can be absolute or relative)
        project_path: The project root path

    Returns:
        Tuple of (absolute_path, relative_path)
        Returns (None, None) if file_path is empty
    """
    if not file_path:
        return None, None

    path = Path(file_path)

    # Make absolute if not already
    if not path.is_absolute():
        path = Path(project_path) / path

    resolved = path.resolve()
    absolute = str(resolved)

    # Compute relative path from project root
    try:
        project_root = Path(project_path).resolve()
        relative = resolved.relative_to(project_root).as_posix()
    except ValueError:
        # Path is outside project root, keep a stable path for matching
        try:
            relative = os.path.relpath(resolved, start=project_root).replace("\\", "/")
        except ValueError:
            relative = resolved.as_posix()

    # Case-fold on Windows for consistent matching
    if sys.platform == 'win32':
        absolute = absolute.lower()
        relative = relative.lower()

    return absolute, relative


def _not_archived_condition():
    """Treat NULL archived values as not archived for legacy rows."""
    return or_(Memory.archived == False, Memory.archived.is_(None))  # noqa: E712


class MemoryManager:
    """
    Manages AI memories - storing, retrieving, and learning from them.

    Uses TF-IDF similarity for semantic matching instead of naive keyword overlap.
    Optionally uses vector embeddings for better semantic understanding.
    Applies memory decay to favor recent memories.
    Detects conflicts with existing memories.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._index: Optional[TFIDFIndex] = None
        self._index_loaded = False
        self._vectors_enabled = vectors.is_available()
        self._index_built_at: Optional[datetime] = None

        # Initialize Qdrant vector store if available
        self._qdrant = None
        if self._vectors_enabled:
            # Prefer database manager's storage path for Qdrant (co-locates with SQLite)
            # This ensures tests with temp storage get their own Qdrant instance
            qdrant_path = str(Path(db_manager.storage_path) / "qdrant")
            Path(qdrant_path).mkdir(parents=True, exist_ok=True)

            # Check if remote mode is configured (overrides local)
            if settings.qdrant_url:
                # Remote mode placeholder - not implemented yet
                logger.warning(
                    f"Qdrant remote mode (URL: {settings.qdrant_url}) not yet implemented. "
                    "Falling back to TF-IDF only for vector search."
                )
            else:
                try:
                    from .qdrant_store import QdrantVectorStore
                    self._qdrant = QdrantVectorStore(path=qdrant_path)
                    logger.info(f"Initialized Qdrant vector store at: {qdrant_path}")
                except RuntimeError as e:
                    error_str = str(e)
                    if "already accessed by another instance" in error_str:
                        # Common case: multiple Claude Code sessions for the same project
                        # TF-IDF fallback works well, so only log at INFO level
                        logger.info(
                            "Qdrant locked by another session (falling back to TF-IDF). "
                            "This is normal with multiple Claude Code sessions for the same project."
                        )
                    else:
                        # Unexpected error - log with full details
                        logger.warning(f"Could not initialize Qdrant (falling back to TF-IDF only): {e}")

    async def _check_index_freshness(self) -> bool:
        """
        Check if index needs rebuilding due to external DB changes.
        Returns True if index was rebuilt.
        """
        if not self._index_loaded:
            return False

        if await self.db.has_changes_since(self._index_built_at):
            logger.info("Database changed since index was built, rebuilding...")
            self._index_loaded = False
            self._index = None
            # Qdrant is persistent and doesn't need rebuilding
            await self._ensure_index()
            return True

        return False

    async def _ensure_index(self) -> TFIDFIndex:
        """Ensure the TF-IDF index is loaded with all memories."""
        if self._index is None:
            self._index = TFIDFIndex()

        if not self._index_loaded:
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Memory).where(_not_archived_condition())
                )
                memories = result.scalars().all()

                for mem in memories:
                    text = mem.content
                    if mem.rationale:
                        text += " " + mem.rationale
                    self._index.add_document(mem.id, text, mem.tags)
                    # Vectors are loaded from Qdrant (persistent), not SQLite

                self._index_loaded = True
                self._index_built_at = datetime.now(timezone.utc)
                qdrant_count = self._qdrant.get_count() if self._qdrant else 0
                logger.info(f"Loaded {len(memories)} memories into TF-IDF index ({qdrant_count} vectors in Qdrant)")

        return self._index

    def _hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        tfidf_threshold: float = 0.1,
        vector_threshold: float = 0.3
    ) -> List[Tuple[int, float]]:
        """
        Hybrid search combining TF-IDF and Qdrant vector similarity.

        Uses the same weighted combination as the original HybridSearch:
        final_score = (1 - 0.3) * tfidf_score + 0.3 * vector_score

        Args:
            query: Query text
            top_k: Maximum results
            tfidf_threshold: Minimum TF-IDF score
            vector_threshold: Minimum vector similarity score

        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        vector_weight = 0.3  # Same as HybridSearch.vector_weight

        # Get TF-IDF results
        tfidf_results = self._index.search(query, top_k=top_k * 2, threshold=tfidf_threshold)
        tfidf_scores = {doc_id: score for doc_id, score in tfidf_results}

        # If Qdrant is available, get vector results
        if self._qdrant and self._qdrant.get_count() > 0:
            # Encode query to vector
            query_embedding_bytes = vectors.encode(query)
            if query_embedding_bytes:
                query_vector = vectors.decode(query_embedding_bytes)
                if query_vector:
                    try:
                        qdrant_results = self._qdrant.search(
                            query_vector=query_vector,
                            limit=top_k * 2
                        )
                    except (ResponseHandlingException, UnexpectedResponse, RuntimeError) as e:
                        # Handle Qdrant API errors gracefully
                        logger.debug(f"Qdrant search failed, falling back to TF-IDF: {e}")
                        return tfidf_results[:top_k]

                    # Filter by threshold
                    vector_scores = {
                        doc_id: score for doc_id, score in qdrant_results
                        if score >= vector_threshold
                    }

                    # Combine scores
                    all_docs = set(tfidf_scores.keys()) | set(vector_scores.keys())
                    combined = []

                    for doc_id in all_docs:
                        tfidf_score = tfidf_scores.get(doc_id, 0.0)
                        vector_score = vector_scores.get(doc_id, 0.0)

                        # Weighted combination
                        final_score = (
                            (1 - vector_weight) * tfidf_score +
                            vector_weight * vector_score
                        )

                        combined.append((doc_id, final_score))

                    combined.sort(key=lambda x: x[1], reverse=True)
                    return combined[:top_k]

        # Fall back to TF-IDF only if no Qdrant or no vectors
        return tfidf_results[:top_k]

    async def remember(
        self,
        category: str,
        content: str,
        rationale: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        file_path: Optional[str] = None,
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a new memory with conflict detection.

        Args:
            category: One of 'decision', 'pattern', 'warning', 'learning'
            content: The actual content to remember
            rationale: Why this is important / the reasoning
            context: Structured context (files, alternatives, etc.)
            tags: Tags for retrieval
            file_path: Optional file path to associate this memory with
            project_path: Optional project root path for normalizing file paths

        Returns:
            The created memory as a dict, with any detected conflicts
        """
        valid_categories = {'decision', 'pattern', 'warning', 'learning'}
        if category not in valid_categories:
            return {"error": f"Invalid category. Must be one of: {valid_categories}"}

        # Extract keywords for backward compat (legacy search)
        keywords = extract_keywords(content, tags)
        if rationale:
            keywords = keywords + " " + extract_keywords(rationale)

        # Check for conflicts before storing
        conflicts = await self._check_conflicts(content, tags)

        # Semantic memories (patterns, warnings) are permanent - they don't decay
        # They represent project facts, not episodic events
        is_permanent = category in {'pattern', 'warning'}

        # Compute vector embedding if available
        text_for_embedding = content
        if rationale:
            text_for_embedding += " " + rationale
        vector_embedding = vectors.encode(text_for_embedding) if self._vectors_enabled else None

        # Normalize file path if provided
        file_path_abs = file_path
        file_path_rel = None
        if file_path and project_path:
            file_path_abs, file_path_rel = _normalize_file_path(file_path, project_path)

        memory = Memory(
            category=category,
            content=content,
            rationale=rationale,
            context=context or {},
            tags=tags or [],
            keywords=keywords.strip(),
            file_path=file_path_abs,
            file_path_relative=file_path_rel,
            is_permanent=is_permanent,
            vector_embedding=vector_embedding
        )

        async with self.db.get_session() as session:
            session.add(memory)
            await session.flush()
            memory_id = memory.id

            # Add to TF-IDF index
            index = await self._ensure_index()
            text = content
            if rationale:
                text += " " + rationale
            index.add_document(memory_id, text, tags)

            # Upsert to Qdrant if available
            if self._qdrant and vector_embedding:
                embedding_list = vectors.decode(vector_embedding)
                if embedding_list:
                    self._qdrant.upsert_memory(
                        memory_id=memory_id,
                        embedding=embedding_list,
                        metadata={
                            "category": category,
                            "tags": tags or [],
                            "file_path": file_path_abs,
                            "worked": None,  # Will be updated via record_outcome
                            "is_permanent": is_permanent
                        }
                    )

            logger.info(f"Stored {category}: {content[:50]}..." + (" [+qdrant]" if vector_embedding and self._qdrant else ""))

            result = {
                "id": memory_id,
                "category": category,
                "content": content,
                "rationale": rationale,
                "tags": tags or [],
                "file_path": file_path,
                "is_permanent": is_permanent,
                "created_at": memory.created_at.isoformat()
            }

            # Add conflict warnings if any
            if conflicts:
                result["conflicts"] = conflicts
                result["warning"] = f"Found {len(conflicts)} potential conflict(s) with existing memories"

        # Clear recall cache since memories changed
        get_recall_cache().clear()

        # Track in session state for enforcement
        if category == "decision" and project_path:
            try:
                from .enforcement import SessionManager
                session_mgr = SessionManager(self.db)
                await session_mgr.add_pending_decision(project_path, result["id"])
            except Exception as e:
                logger.debug(f"Session tracking failed (non-fatal): {e}")

        return result

    async def remember_batch(
        self,
        memories: List[Dict[str, Any]],
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store multiple memories in a single transaction.

        More efficient than calling remember() multiple times, especially for
        bootstrapping or bulk imports. All memories are stored atomically.

        Args:
            memories: List of memory dicts, each with:
                - category: One of 'decision', 'pattern', 'warning', 'learning'
                - content: The actual content to remember
                - rationale: (optional) Why this is important
                - tags: (optional) List of tags
                - file_path: (optional) Associated file path
            project_path: Project root path for normalizing file paths

        Returns:
            Summary dict with created_count, error_count, ids, and any errors
        """
        valid_categories = {'decision', 'pattern', 'warning', 'learning'}

        results = {
            "created_count": 0,
            "error_count": 0,
            "ids": [],
            "errors": []
        }

        if not memories:
            return results

        # Pre-validate all memories
        validated_memories = []
        for i, mem in enumerate(memories):
            category = mem.get("category")
            content = mem.get("content")

            if not category or category not in valid_categories:
                results["errors"].append({
                    "index": i,
                    "error": f"Invalid or missing category. Must be one of: {valid_categories}"
                })
                results["error_count"] += 1
                continue

            if not content or not content.strip():
                results["errors"].append({
                    "index": i,
                    "error": "Content is required and cannot be empty"
                })
                results["error_count"] += 1
                continue

            validated_memories.append((i, mem))

        if not validated_memories:
            return results

        # Ensure index is loaded before batch operation
        index = await self._ensure_index()

        async with self.db.get_session() as session:
            created_ids = []

            for i, mem in validated_memories:
                category = mem["category"]
                content = mem["content"]
                rationale = mem.get("rationale")
                tags = mem.get("tags") or []
                file_path = mem.get("file_path")
                context = mem.get("context") or {}

                try:
                    # Extract keywords
                    keywords = extract_keywords(content, tags)
                    if rationale:
                        keywords = keywords + " " + extract_keywords(rationale)

                    # Semantic memories are permanent
                    is_permanent = category in {'pattern', 'warning'}

                    # Compute vector embedding if available
                    text_for_embedding = content
                    if rationale:
                        text_for_embedding += " " + rationale
                    vector_embedding = vectors.encode(text_for_embedding) if self._vectors_enabled else None

                    # Normalize file path if provided
                    file_path_abs = file_path
                    file_path_rel = None
                    if file_path and project_path:
                        file_path_abs, file_path_rel = _normalize_file_path(file_path, project_path)

                    memory = Memory(
                        category=category,
                        content=content,
                        rationale=rationale,
                        context=context,
                        tags=tags,
                        keywords=keywords.strip(),
                        file_path=file_path_abs,
                        file_path_relative=file_path_rel,
                        is_permanent=is_permanent,
                        vector_embedding=vector_embedding
                    )

                    session.add(memory)
                    await session.flush()  # Get ID without committing

                    # Add to TF-IDF index
                    text = content
                    if rationale:
                        text += " " + rationale
                    index.add_document(memory.id, text, tags)

                    # Upsert to Qdrant if available
                    if self._qdrant and vector_embedding:
                        embedding_list = vectors.decode(vector_embedding)
                        if embedding_list:
                            self._qdrant.upsert_memory(
                                memory_id=memory.id,
                                embedding=embedding_list,
                                metadata={
                                    "category": category,
                                    "tags": tags,
                                    "file_path": file_path_abs,
                                    "worked": None,
                                    "is_permanent": is_permanent
                                }
                            )

                    created_ids.append(memory.id)
                    results["created_count"] += 1

                except Exception as e:
                    results["errors"].append({
                        "index": i,
                        "error": str(e)
                    })
                    results["error_count"] += 1

            # Transaction commits here when exiting context manager
            results["ids"] = created_ids

        # Track decisions in session state for enforcement (after commit)
        if project_path:
            try:
                from .enforcement import SessionManager
                session_mgr = SessionManager(self.db)

                decision_ids = [
                    created_ids[j]
                    for j, (i, mem) in enumerate(validated_memories)
                    if j < len(created_ids) and mem.get("category") == "decision"
                ]

                for decision_id in decision_ids:
                    await session_mgr.add_pending_decision(project_path, decision_id)
            except Exception as e:
                logger.debug(f"Session tracking failed (non-fatal): {e}")

        # Clear recall cache since memories changed
        if results['created_count'] > 0:
            get_recall_cache().clear()

        logger.info(
            f"Batch stored {results['created_count']} memories "
            f"({results['error_count']} errors)"
        )

        return results

    async def _check_conflicts(
        self,
        content: str,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Check for conflicts with existing memories using deep semantic search.

        Uses Qdrant vectors (if available) or TF-IDF to find semantically similar
        memories across the ENTIRE database, not just recent ones. This catches
        conflicts with decisions made long ago that might still be relevant.
        """
        await self._check_index_freshness()
        await self._ensure_index()

        # Use hybrid search (TF-IDF + Qdrant vectors if available)
        search_results = self._hybrid_search(content, top_k=50, tfidf_threshold=0.3)

        if not search_results:
            return []

        # Get IDs of similar memories
        similar_ids = [doc_id for doc_id, score in search_results if score >= 0.4]

        if not similar_ids:
            return []

        # Fetch full memory details only for similar ones
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory)
                .where(
                    Memory.id.in_(similar_ids),
                    _not_archived_condition()
                )
            )
            existing = [
                {
                    'id': m.id,
                    'content': m.content,
                    'category': m.category,
                    'worked': m.worked,
                    'outcome': m.outcome,
                    'tags': m.tags
                }
                for m in result.scalars().all()
            ]

        return detect_conflict(content, existing, similarity_threshold=0.5)

    def _truncate_content(self, content: str, max_length: int = 150) -> str:
        """Truncate content to max_length, adding ellipsis if truncated."""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    async def _increment_recall_counts(self, memory_ids: List[int]) -> None:
        """Increment recall_count for accessed memories (for saliency-based pruning)."""
        if not memory_ids:
            return

        async with self.db.get_session() as session:
            await session.execute(
                Memory.__table__.update()
                .where(Memory.id.in_(memory_ids))
                .values(recall_count=Memory.recall_count + 1)
            )

    async def recall(
        self,
        topic: str,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        file_path: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        project_path: Optional[str] = None,
        include_warnings: bool = True,
        decay_half_life_days: float = 30.0,
        include_linked: bool = False,
        condensed: bool = False  # Endless Mode compression
    ) -> Dict[str, Any]:
        """
        Recall memories relevant to a topic using semantic similarity.

        This is the core "active memory" function. It:
        1. Uses TF-IDF to find semantically similar memories
        2. Applies time decay to favor recent memories
        3. Boosts failed decisions (they're important warnings)
        4. Organizes by category

        Results are cached for 5 seconds to avoid repeated searches.
        Cache hits still update recall_count for saliency tracking.

        Pagination behavior:
        - offset/limit apply to the raw scored results BEFORE category distribution
        - The actual number of returned results may vary due to per-category limits
        - This design is intentional for efficiency (avoids fetching all memories just to paginate)
        - has_more indicates if there are more memories beyond offset+limit in the raw results

        Args:
            topic: What you're looking for
            categories: Limit to specific categories (default: all)
            tags: Filter to memories with these tags
            file_path: Filter to memories for this file
            offset: Number of results to skip (for pagination)
            limit: Max memories per category
            since: Only include memories created after this date
            until: Only include memories created before this date
            project_path: Optional project root for file path normalization
            include_warnings: Always include warnings even if not in categories
            decay_half_life_days: How quickly old memories lose relevance
            include_linked: If True, also search linked projects (read-only)
            condensed: If True, return compressed output (strips rationale, context,
                       truncates content). Reduces token usage by ~75%. Default: False.

        Returns:
            Dict with categorized memories and relevance scores
        """
        # Check cache first
        cache = get_recall_cache()
        cache_key = make_cache_key(
            topic, categories, tags, file_path, offset, limit,
            since.isoformat() if since else None,
            until.isoformat() if until else None,
            include_warnings, decay_half_life_days,
            include_linked,
            condensed  # Include condensed in cache key for separate caching
        )
        found, cached_result = cache.get(cache_key)
        if found and cached_result is not None:
            logger.debug(f"recall cache hit for topic: {topic[:50]}...")
            # Still update recall_count for saliency tracking (side effect)
            recalled_ids = [m['id'] for cat in ['decisions', 'patterns', 'warnings', 'learnings']
                           for m in cached_result.get(cat, [])]
            await self._increment_recall_counts(recalled_ids)
            return cached_result

        await self._check_index_freshness()
        await self._ensure_index()

        # Use hybrid search (TF-IDF + Qdrant vectors if available)
        search_results = self._hybrid_search(topic, top_k=limit * 4, tfidf_threshold=0.05)

        if not search_results and not include_linked:
            return {"memories": [], "message": "No relevant memories found", "topic": topic}

        # Get full memory objects (may be empty if include_linked is True but no local results)
        memory_ids = [doc_id for doc_id, _ in search_results] if search_results else []
        {doc_id: score for doc_id, score in search_results} if search_results else {}

        async with self.db.get_session() as session:
            # Build query with date filters at database level for performance
            query = select(Memory).where(
                Memory.id.in_(memory_ids),
                _not_archived_condition()
            )

            def _to_utc_naive(dt_value: datetime) -> datetime:
                if dt_value.tzinfo:
                    return dt_value.astimezone(timezone.utc).replace(tzinfo=None)
                return dt_value

            if since:
                query = query.where(Memory.created_at >= _to_utc_naive(since))

            if until:
                query = query.where(Memory.created_at <= _to_utc_naive(until))

            result = await session.execute(query)
            memories = {m.id: m for m in result.scalars().all()}

        # Filter by tags if specified
        if tags:
            memories = {
                mid: mem for mid, mem in memories.items()
                if mem.tags and any(t in mem.tags for t in tags)
            }

        # Filter by file_path if specified
        if file_path:
            normalized_abs = None
            normalized_rel = None
            if project_path:
                normalized_abs, normalized_rel = _normalize_file_path(file_path, project_path)

            normalized_filter = file_path.replace('\\', '/')
            if normalized_abs:
                normalized_abs = normalized_abs.replace('\\', '/')
            if normalized_rel:
                normalized_rel = normalized_rel.replace('\\', '/')

            def _matches_path(mem: Memory) -> bool:
                mem_abs = mem.file_path.replace('\\', '/') if mem.file_path else ""
                mem_rel = mem.file_path_relative.replace('\\', '/') if getattr(mem, "file_path_relative", None) else ""

                if normalized_abs and mem_abs == normalized_abs:
                    return True
                if normalized_rel and mem_rel == normalized_rel:
                    return True
                if mem_abs and (mem_abs.endswith(normalized_filter) or normalized_filter.endswith(mem_abs)):
                    return True
                if mem_rel and (mem_rel.endswith(normalized_filter) or normalized_filter.endswith(mem_rel)):
                    return True
                return False

            memories = {
                mid: mem for mid, mem in memories.items()
                if _matches_path(mem)
            }

        # Score with decay and organize
        scored_memories = []
        for mem_id, base_score in (search_results or []):
            mem = memories.get(mem_id)
            if not mem:
                continue

            # Apply category filter
            if categories:
                cats = list(categories)
                if include_warnings and 'warning' not in cats:
                    cats.append('warning')
                if mem.category not in cats:
                    continue

            # Calculate final score with decay
            # Permanent memories (patterns, warnings) don't decay - they're project facts
            if getattr(mem, 'is_permanent', False) or mem.category in {'pattern', 'warning'}:
                decay = 1.0  # No decay for semantic memories
            else:
                decay = calculate_memory_decay(mem.created_at, decay_half_life_days)

            final_score = base_score * decay

            # Boost failed decisions - they're valuable warnings
            if mem.worked is False:
                final_score *= FAILED_DECISION_BOOST

            # Boost warnings
            if mem.category == 'warning':
                final_score *= WARNING_BOOST

            scored_memories.append((mem, final_score, base_score, decay))

        # Sort by final score
        scored_memories.sort(key=lambda x: x[1], reverse=True)

        # Count total before pagination
        total_count = len(scored_memories)

        # Apply pagination (offset and limit)
        paginated_memories = scored_memories[offset:offset + limit * 4]  # limit * 4 to allow distribution across categories

        # Organize by category
        by_category = {
            'decisions': [],
            'patterns': [],
            'warnings': [],
            'learnings': []
        }

        for mem, final_score, base_score, decay in paginated_memories:
            cat_key = mem.category + 's'  # decision -> decisions
            if cat_key in by_category and len(by_category[cat_key]) < limit:
                # Build memory dict - condensed mode strips verbose fields
                if condensed:
                    mem_dict = {
                        'id': mem.id,
                        'content': self._truncate_content(mem.content),
                        'rationale': None,
                        'context': None,
                        'tags': mem.tags,
                        'relevance': round(final_score, 3),
                        'outcome': mem.outcome,
                        'worked': mem.worked,
                        'created_at': mem.created_at.isoformat()
                    }
                else:
                    mem_dict = {
                        'id': mem.id,
                        'content': mem.content,
                        'rationale': mem.rationale,
                        'context': mem.context,
                        'tags': mem.tags,
                        'relevance': round(final_score, 3),
                        'semantic_match': round(base_score, 3),
                        'recency_weight': round(decay, 3),
                        'outcome': mem.outcome,
                        'worked': mem.worked,
                        'created_at': mem.created_at.isoformat()
                    }

                # Add warning annotation for failed decisions
                if mem.worked is False:
                    mem_dict['_warning'] = f"⚠️ This approach FAILED: {mem.outcome or 'no details recorded'}"

                by_category[cat_key].append(mem_dict)

        total = sum(len(v) for v in by_category.values())

        # Generate summary
        summary_parts = []
        if by_category['warnings']:
            summary_parts.append(f"{len(by_category['warnings'])} warnings")
        if any(m.get('worked') is False for cat in by_category.values() for m in cat):
            failed_count = sum(1 for cat in by_category.values() for m in cat if m.get('worked') is False)
            summary_parts.append(f"{failed_count} failed approaches to avoid")
        if by_category['patterns']:
            summary_parts.append(f"{len(by_category['patterns'])} patterns to follow")

        # Increment recall_count for accessed memories (saliency tracking)
        recalled_ids = [m['id'] for cat in by_category.values() for m in cat]
        await self._increment_recall_counts(recalled_ids)

        result = {
            'topic': topic,
            'found': total,
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'has_more': offset + limit < total_count,
            'summary': " | ".join(summary_parts) if summary_parts else None,
            **by_category
        }

        # Aggregate from linked projects if requested
        if include_linked and project_path:
            from .links import LinkManager
            link_mgr = LinkManager(self.db)

            try:
                linked_managers = await link_mgr.get_linked_db_managers(project_path)

                for linked_path, linked_db in linked_managers:
                    try:
                        linked_memory = MemoryManager(linked_db)
                        linked_result = await linked_memory.recall(
                            topic=topic,
                            categories=categories,
                            tags=tags,
                            file_path=file_path,
                            offset=0,
                            # Limit linked project results to balance with main project
                            limit=limit // 2 if limit > 1 else 1,
                            since=since,
                            until=until,
                            project_path=linked_path,
                            include_warnings=include_warnings,
                            decay_half_life_days=decay_half_life_days,
                            include_linked=False  # Don't recurse
                        )

                        # Merge results, tagging with source
                        for category in ["decisions", "patterns", "warnings", "learnings"]:
                            if category in linked_result:
                                for memory in linked_result[category]:
                                    memory["_from_linked"] = linked_path
                                    result.setdefault(category, []).append(memory)
                    except Exception as e:
                        logger.warning(f"Could not recall from linked project {linked_path}: {e}")
            except Exception as e:
                logger.warning(f"Could not get linked projects: {e}")

        # Cache the result
        cache.set(cache_key, result)

        return result

    async def record_outcome(
        self,
        memory_id: int,
        outcome: str,
        worked: bool
    ) -> Dict[str, Any]:
        """
        Record the outcome of a decision/pattern to learn from it.

        Failed outcomes are especially valuable - they become implicit warnings
        that get boosted in future recalls.

        Args:
            memory_id: The memory to update
            outcome: What actually happened
            worked: Did it work out?

        Returns:
            Updated memory with any auto-generated warnings
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()

            if not memory:
                return {"error": f"Memory {memory_id} not found"}

            memory.outcome = outcome
            memory.worked = worked
            memory.updated_at = datetime.now(timezone.utc)

            # Update Qdrant metadata with worked status
            if self._qdrant and memory.vector_embedding:
                embedding_list = vectors.decode(memory.vector_embedding)
                if embedding_list:
                    self._qdrant.upsert_memory(
                        memory_id=memory_id,
                        embedding=embedding_list,
                        metadata={
                            "category": memory.category,
                            "tags": memory.tags or [],
                            "file_path": memory.file_path,
                            "worked": worked,
                            "is_permanent": memory.is_permanent
                        }
                    )

            response = {
                "id": memory_id,
                "content": memory.content,
                "outcome": outcome,
                "worked": worked,
            }

            # If it failed, suggest creating an explicit warning
            if not worked:
                response["suggestion"] = {
                    "action": "consider_warning",
                    "message": "This failure will boost this memory in future recalls. Consider also creating an explicit warning with more context.",
                    "example": f'remember("warning", "Avoid: {memory.content[:50]}...", rationale="{outcome}")'
                }
                logger.info(f"Memory {memory_id} marked as failed - will be boosted as warning")

            response["message"] = (
                "Outcome recorded - this failure will inform future recalls"
                if not worked else
                "Outcome recorded successfully"
            )

            # Remove from pending decisions
            try:
                from .enforcement import SessionManager
                session_mgr = SessionManager(self.db)
                # Use current working directory as project_path since it's not passed in
                project_path = os.getcwd()
                await session_mgr.remove_pending_decision(project_path, memory_id)
            except Exception as e:
                logger.debug(f"Session tracking failed (non-fatal): {e}")

            # Clear recall cache since memory outcome changed (affects scoring)
            get_recall_cache().clear()

            return response

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics with learning insights."""
        async with self.db.get_session() as session:
            # Count by category
            result = await session.execute(
                select(Memory.category, func.count(Memory.id))
                .group_by(Memory.category)
            )
            by_category = {row[0]: row[1] for row in result.all()}

            # Count outcomes
            result = await session.execute(
                select(func.count(Memory.id))
                .where(Memory.worked == True)  # noqa: E712
            )
            worked = result.scalar() or 0

            result = await session.execute(
                select(func.count(Memory.id))
                .where(Memory.worked == False)  # noqa: E712
            )
            failed = result.scalar() or 0

            total = sum(by_category.values())

            # Calculate learning rate
            outcomes_recorded = worked + failed
            learning_rate = outcomes_recorded / total if total > 0 else 0

            return {
                "total_memories": total,
                "by_category": by_category,
                "with_outcomes": {
                    "worked": worked,
                    "failed": failed,
                    "pending": total - worked - failed
                },
                "learning_insights": {
                    "outcome_tracking_rate": round(learning_rate, 2),
                    "failure_rate": round(failed / outcomes_recorded, 2) if outcomes_recorded > 0 else None,
                    "suggestion": (
                        "Record more outcomes to improve memory quality"
                        if learning_rate < 0.3 else
                        "Good outcome tracking!" if learning_rate > 0.5 else None
                    )
                }
            }

    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search across all memories using semantic similarity.
        """
        await self._check_index_freshness()
        index = await self._ensure_index()

        # Search using TF-IDF
        results = index.search(query, top_k=limit, threshold=0.05)

        if not results:
            # Fall back to text search for exact matches
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Memory)
                    .where(
                        _not_archived_condition(),
                        or_(
                            Memory.content.like(f"%{query}%"),
                            Memory.rationale.like(f"%{query}%")
                        )
                    )
                    .order_by(desc(Memory.created_at))
                    .limit(limit)
                )
                memories = result.scalars().all()

                return [
                    {
                        'id': m.id,
                        'category': m.category,
                        'content': m.content,
                        'rationale': m.rationale,
                        'tags': m.tags,
                        'relevance': 0.5,  # Exact match baseline
                        'created_at': m.created_at.isoformat()
                    }
                    for m in memories
                ]

        # Get full memory objects
        memory_ids = [doc_id for doc_id, _ in results]

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.id.in_(memory_ids),
                    _not_archived_condition()
                )
            )
            memories = {m.id: m for m in result.scalars().all()}

        return [
            {
                'id': mem_id,
                'category': memories[mem_id].category,
                'content': memories[mem_id].content,
                'rationale': memories[mem_id].rationale,
                'tags': memories[mem_id].tags,
                'relevance': round(score, 3),
                'created_at': memories[mem_id].created_at.isoformat()
            }
            for mem_id, score in results
            if mem_id in memories
        ]

    async def find_related(
        self,
        memory_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find memories related to a specific memory.

        Useful for exploring connected decisions/patterns.
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            source = result.scalar_one_or_none()

            if not source:
                return []

        # Search using the source memory's content
        text = source.content
        if source.rationale:
            text += " " + source.rationale

        results = await self.search(text, limit=limit + 1)

        # Filter out the source memory itself
        return [r for r in results if r['id'] != memory_id][:limit]

    async def recall_for_file(
        self,
        file_path: str,
        limit: int = 10,
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all memories associated with a specific file.

        Use this when opening a file to see all relevant context -
        warnings, patterns, and past decisions about this file.

        Args:
            file_path: The file path to look up
            limit: Max memories to return
            project_path: Optional project root path for normalizing file paths

        Returns:
            Dict with memories organized by category
        """
        # Normalize the input path if project_path is provided
        normalized_abs = None
        normalized_rel = None
        if project_path:
            normalized_abs, normalized_rel = _normalize_file_path(file_path, project_path)

        async with self.db.get_session() as session:
            # Query both file_path and file_path_relative columns
            if normalized_abs or normalized_rel:
                # Use normalized paths with OR condition
                conditions = []
                if normalized_abs:
                    conditions.append(Memory.file_path == normalized_abs)
                if normalized_rel:
                    conditions.append(Memory.file_path_relative == normalized_rel)

                result = await session.execute(
                    select(Memory)
                    .where(
                        _not_archived_condition(),
                        or_(*conditions)
                    )
                    .order_by(desc(Memory.created_at))
                    .limit(limit)
                )
            else:
                # Fallback to original behavior if no project_path
                result = await session.execute(
                    select(Memory)
                    .where(
                        _not_archived_condition(),
                        Memory.file_path == file_path
                    )
                    .order_by(desc(Memory.created_at))
                    .limit(limit)
                )
            direct_memories = result.scalars().all()

            # Also search for memories mentioning this file in content
            # Use os.path for cross-platform compatibility
            filename = os.path.basename(file_path) if file_path else file_path
            result = await session.execute(
                select(Memory)
                .where(
                    _not_archived_condition(),
                    or_(
                        Memory.content.like(f"%{filename}%"),
                        Memory.rationale.like(f"%{filename}%")
                    )
                )
                .order_by(desc(Memory.created_at))
                .limit(limit)
            )
            mentioned_memories = result.scalars().all()

        # Combine and deduplicate
        seen_ids = set()
        all_memories = []
        for mem in direct_memories:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                all_memories.append(mem)
        for mem in mentioned_memories:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                all_memories.append(mem)

        # Organize by category
        by_category = {
            'decisions': [],
            'patterns': [],
            'warnings': [],
            'learnings': []
        }

        for mem in all_memories[:limit]:
            cat_key = mem.category + 's'
            if cat_key in by_category:
                mem_dict = {
                    'id': mem.id,
                    'content': mem.content,
                    'rationale': mem.rationale,
                    'context': mem.context,
                    'tags': mem.tags,
                    'file_path': mem.file_path,
                    'outcome': mem.outcome,
                    'worked': mem.worked,
                    'created_at': mem.created_at.isoformat()
                }

                if mem.worked is False:
                    mem_dict['_warning'] = f"⚠️ This approach FAILED: {mem.outcome or 'no details recorded'}"

                by_category[cat_key].append(mem_dict)

        total = sum(len(v) for v in by_category.values())

        # Increment recall_count for accessed memories (saliency tracking)
        recalled_ids = [m['id'] for cat in by_category.values() for m in cat]
        await self._increment_recall_counts(recalled_ids)

        return {
            'file_path': file_path,
            'found': total,
            'has_warnings': len(by_category['warnings']) > 0 or any(
                m.get('worked') is False for cat in by_category.values() for m in cat
            ),
            **by_category
        }

    async def rebuild_index(self) -> Dict[str, Any]:
        """
        Force rebuild of TF-IDF index.

        Qdrant is persistent and doesn't need rebuilding.
        Returns statistics about the rebuild.
        """
        # Clear existing TF-IDF index
        self._index = TFIDFIndex()
        self._index_loaded = False

        # Rebuild TF-IDF from SQLite
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory).where(_not_archived_condition())
            )
            memories = result.scalars().all()

            for mem in memories:
                text = mem.content
                if mem.rationale:
                    text += " " + mem.rationale
                self._index.add_document(mem.id, text, mem.tags)
                # Qdrant is persistent and doesn't need rebuilding

        self._index_loaded = True
        self._index_built_at = datetime.now(timezone.utc)

        return {
            "memories_indexed": len(memories),
            "vectors_indexed": self._qdrant.get_count() if self._qdrant else 0,
            "built_at": self._index_built_at.isoformat()
        }

    async def compact_memories(
        self,
        summary: str,
        limit: int = 10,
        topic: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Compact recent episodic memories into a single summary.

        Creates a summary memory, links it to originals via 'supersedes' edges,
        and archives the originals. Preserves full history via graph edges.

        Args:
            summary: The summary text (must be >= 50 chars after trimming)
            limit: Max number of memories to compact (must be > 0)
            topic: Optional topic filter (content/rationale/tags substring match)
            dry_run: If True, preview candidates without changes (default: True)

        Returns:
            Result dict with status, summary_id, compacted_count, etc.
        """
        # Validate inputs
        summary = summary.strip() if summary else ""
        if len(summary) < 50:
            return {
                "error": "Summary must be at least 50 characters",
                "provided_length": len(summary)
            }
        if limit <= 0:
            return {"error": "Limit must be greater than 0"}

        async with self.db.get_session() as session:
            # Select candidate memories: episodic, not pinned, not permanent, not archived
            # For decisions, require outcome to be recorded (don't hide pending decisions)
            query = (
                select(Memory)
                .where(
                    Memory.category.in_(["decision", "learning"]),
                    or_(Memory.pinned == False, Memory.pinned.is_(None)),  # noqa: E712
                    or_(Memory.is_permanent == False, Memory.is_permanent.is_(None)),  # noqa: E712
                    _not_archived_condition(),
                )
                .order_by(Memory.created_at.asc())  # Oldest first
            )

            # For decisions, exclude those without outcomes (pending)
            # This is done via post-fetch filtering to keep query simple

            result = await session.execute(query)
            all_candidates = result.scalars().all()

            # Filter: decisions must have outcome recorded
            candidates = []
            for mem in all_candidates:
                if mem.category == "decision":
                    if mem.outcome is None and mem.worked is None:
                        continue  # Skip pending decisions
                candidates.append(mem)

            # Apply topic filter if provided
            if topic:
                topic_lower = topic.lower()
                filtered = []
                for mem in candidates:
                    content_match = topic_lower in (mem.content or "").lower()
                    rationale_match = topic_lower in (mem.rationale or "").lower()
                    tags_match = any(
                        topic_lower in str(tag).lower()
                        for tag in (mem.tags or [])
                    )
                    if content_match or rationale_match or tags_match:
                        filtered.append(mem)
                candidates = filtered

            # Apply limit
            candidates = candidates[:limit]

            if not candidates:
                reason = "topic_mismatch" if topic else "no_candidates"
                return {
                    "status": "skipped",
                    "reason": reason,
                    "topic": topic,
                    "message": "No matching memories to compact"
                }

            compacted_ids = [m.id for m in candidates]

            # Dry run - just return preview
            if dry_run:
                return {
                    "status": "dry_run",
                    "would_compact": len(candidates),
                    "candidate_ids": compacted_ids,
                    "candidates": [
                        {
                            "id": m.id,
                            "category": m.category,
                            "content": m.content[:100] + "..." if len(m.content) > 100 else m.content,
                            "created_at": m.created_at.isoformat()
                        }
                        for m in candidates
                    ],
                    "topic": topic,
                    "message": f"Would compact {len(candidates)} memories (dry_run=True)"
                }

            # Compute tags: ["compacted", "checkpoint"] + topic if provided
            summary_tags = ["compacted", "checkpoint"]
            if topic:
                summary_tags.append(topic)
            # Add union of common tags (appearing in > 50% of candidates)
            tag_counts: Dict[str, int] = {}
            for mem in candidates:
                for tag in (mem.tags or []):
                    if isinstance(tag, str) and tag not in summary_tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
            threshold = len(candidates) / 2
            for tag, count in tag_counts.items():
                if count >= threshold:
                    summary_tags.append(tag)
            summary_tags = sorted(set(summary_tags))

            # Create summary memory
            keywords = extract_keywords(summary, summary_tags)
            vector_embedding = vectors.encode(summary) if self._vectors_enabled else None

            summary_memory = Memory(
                category="learning",
                content=summary,
                rationale=f"Compacted summary of {len(candidates)} memories.",
                context={"compacted_ids": compacted_ids, "topic": topic},
                tags=summary_tags,
                keywords=keywords,
                is_permanent=False,
                vector_embedding=vector_embedding
            )
            session.add(summary_memory)
            await session.flush()  # Get the ID

            summary_id = summary_memory.id

            # Create supersedes relationships and archive originals
            for mem in candidates:
                rel = MemoryRelationship(
                    source_id=summary_id,
                    target_id=mem.id,
                    relationship="supersedes",
                    description="Session compaction"
                )
                session.add(rel)
                mem.archived = True
                # Delete from Qdrant since memory is archived
                if self._qdrant:
                    self._qdrant.delete_memory(mem.id)

        # Rebuild index to reflect archived items and new summary
        await self.rebuild_index()

        # Clear recall cache since memories have been modified
        get_recall_cache().clear()

        return {
            "status": "compacted",
            "summary_id": summary_id,
            "compacted_count": len(candidates),
            "compacted_ids": compacted_ids,
            "category": "learning",
            "tags": summary_tags,
            "topic": topic,
            "message": f"Compacted {len(candidates)} memories into summary {summary_id}"
        }

    # =========================================================================
    # Graph Memory Methods - Explicit relationship edges between memories
    # =========================================================================

    async def link_memories(
        self,
        source_id: int,
        target_id: int,
        relationship: str,
        description: Optional[str] = None,
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Create an explicit relationship edge between two memories.

        Args:
            source_id: The "from" memory ID
            target_id: The "to" memory ID
            relationship: Type of relationship (led_to, supersedes, depends_on, conflicts_with, related_to)
            description: Optional context explaining this relationship
            confidence: Strength of relationship (0.0-1.0, default 1.0)

        Returns:
            Status of the link operation
        """
        # Validate relationship type
        if relationship not in VALID_RELATIONSHIPS:
            return {
                "error": f"Invalid relationship type '{relationship}'. Valid types: {', '.join(sorted(VALID_RELATIONSHIPS))}"
            }

        # Prevent self-reference
        if source_id == target_id:
            return {"error": "Cannot link a memory to itself"}

        from sqlalchemy import and_

        async with self.db.get_session() as session:
            # Verify both memories exist
            source = await session.get(Memory, source_id)
            target = await session.get(Memory, target_id)

            if not source:
                return {"error": f"Source memory {source_id} not found"}
            if not target:
                return {"error": f"Target memory {target_id} not found"}

            # Check for existing relationship
            existing = await session.execute(
                select(MemoryRelationship).where(
                    and_(
                        MemoryRelationship.source_id == source_id,
                        MemoryRelationship.target_id == target_id,
                        MemoryRelationship.relationship == relationship
                    )
                )
            )
            if existing.scalar_one_or_none():
                return {
                    "status": "already_exists",
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship": relationship
                }

            # Create the relationship
            rel = MemoryRelationship(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                description=description,
                confidence=confidence
            )
            session.add(rel)
            await session.flush()  # Get the ID

            logger.info(f"Created relationship: {source_id} --{relationship}--> {target_id}")

            return {
                "status": "linked",
                "id": rel.id,
                "source_id": source_id,
                "target_id": target_id,
                "relationship": relationship,
                "description": description,
                "message": f"Linked memory {source_id} --{relationship}--> {target_id}"
            }

    async def unlink_memories(
        self,
        source_id: int,
        target_id: int,
        relationship: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Remove a relationship edge between two memories.

        Args:
            source_id: The "from" memory ID
            target_id: The "to" memory ID
            relationship: Specific relationship to remove (if None, removes all between the pair)

        Returns:
            Status of the unlink operation
        """
        from sqlalchemy import and_, delete

        async with self.db.get_session() as session:
            # Build conditions
            conditions = [
                MemoryRelationship.source_id == source_id,
                MemoryRelationship.target_id == target_id
            ]
            if relationship:
                conditions.append(MemoryRelationship.relationship == relationship)

            # Find existing relationships
            result = await session.execute(
                select(MemoryRelationship).where(and_(*conditions))
            )
            existing = result.scalars().all()

            if not existing:
                return {
                    "status": "not_found",
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship": relationship
                }

            # Delete the relationships
            await session.execute(
                delete(MemoryRelationship).where(and_(*conditions))
            )

            logger.info(f"Removed {len(existing)} relationship(s) between {source_id} and {target_id}")

            return {
                "status": "unlinked",
                "source_id": source_id,
                "target_id": target_id,
                "relationship": relationship,
                "removed_count": len(existing),
                "message": f"Removed {len(existing)} relationship(s)"
            }

    async def trace_chain(
        self,
        memory_id: int,
        direction: str = "both",
        relationship_types: Optional[List[str]] = None,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        Traverse the memory graph from a starting point using recursive CTE.

        Args:
            memory_id: Starting memory ID
            direction: "forward" (descendants), "backward" (ancestors), or "both"
            relationship_types: Filter to specific relationship types (default: all)
            max_depth: Maximum traversal depth (default: 10)

        Returns:
            Chain of connected memories with relationship info
        """
        if direction not in ("forward", "backward", "both"):
            return {"error": f"Invalid direction '{direction}'. Use: forward, backward, both"}

        from sqlalchemy import text

        async with self.db.get_session() as session:
            # Verify starting memory exists
            start_memory = await session.get(Memory, memory_id)
            if not start_memory:
                return {"error": f"Memory {memory_id} not found"}

            # Build recursive CTE based on direction
            if direction == "forward":
                cte_sql = """
                    WITH RECURSIVE chain AS (
                        SELECT r.target_id as id, r.relationship, r.source_id as from_id, 1 as depth
                        FROM memory_relationships r
                        WHERE r.source_id = :start_id

                        UNION ALL

                        SELECT r.target_id, r.relationship, r.source_id, c.depth + 1
                        FROM memory_relationships r
                        JOIN chain c ON r.source_id = c.id
                        WHERE c.depth < :max_depth
                    )
                    SELECT DISTINCT c.id, c.relationship, c.from_id, c.depth, m.content, m.category
                    FROM chain c
                    JOIN memories m ON c.id = m.id
                    ORDER BY c.depth
                """
            elif direction == "backward":
                cte_sql = """
                    WITH RECURSIVE chain AS (
                        SELECT r.source_id as id, r.relationship, r.target_id as from_id, 1 as depth
                        FROM memory_relationships r
                        WHERE r.target_id = :start_id

                        UNION ALL

                        SELECT r.source_id, r.relationship, r.target_id, c.depth + 1
                        FROM memory_relationships r
                        JOIN chain c ON r.target_id = c.id
                        WHERE c.depth < :max_depth
                    )
                    SELECT DISTINCT c.id, c.relationship, c.from_id, c.depth, m.content, m.category
                    FROM chain c
                    JOIN memories m ON c.id = m.id
                    ORDER BY c.depth
                """
            else:  # both
                cte_sql = """
                    WITH RECURSIVE chain AS (
                        -- Forward edges
                        SELECT r.target_id as id, r.relationship, r.source_id as from_id, 1 as depth
                        FROM memory_relationships r
                        WHERE r.source_id = :start_id

                        UNION

                        -- Backward edges
                        SELECT r.source_id as id, r.relationship, r.target_id as from_id, 1 as depth
                        FROM memory_relationships r
                        WHERE r.target_id = :start_id

                        UNION ALL

                        -- Recursive forward
                        SELECT r.target_id, r.relationship, r.source_id, c.depth + 1
                        FROM memory_relationships r
                        JOIN chain c ON r.source_id = c.id
                        WHERE c.depth < :max_depth

                        UNION ALL

                        -- Recursive backward
                        SELECT r.source_id, r.relationship, r.target_id, c.depth + 1
                        FROM memory_relationships r
                        JOIN chain c ON r.target_id = c.id
                        WHERE c.depth < :max_depth
                    )
                    SELECT DISTINCT c.id, c.relationship, c.from_id, c.depth, m.content, m.category
                    FROM chain c
                    JOIN memories m ON c.id = m.id
                    ORDER BY c.depth
                """

            result = await session.execute(
                text(cte_sql),
                {"start_id": memory_id, "max_depth": max_depth}
            )
            rows = result.fetchall()

            # Filter by relationship types if specified
            chain = []
            for row in rows:
                if relationship_types and row[1] not in relationship_types:
                    continue
                chain.append({
                    "id": row[0],
                    "relationship": row[1],
                    "from_id": row[2],
                    "depth": row[3],
                    "content": row[4],
                    "category": row[5]
                })

            return {
                "memory_id": memory_id,
                "direction": direction,
                "max_depth": max_depth,
                "chain": chain,
                "total_found": len(chain),
                "message": f"Found {len(chain)} connected memories"
            }

    async def get_graph(
        self,
        memory_ids: Optional[List[int]] = None,
        topic: Optional[str] = None,
        format: str = "json",
        include_orphans: bool = False
    ) -> Dict[str, Any]:
        """
        Get a subgraph of memories and their relationships.

        Args:
            memory_ids: Specific memory IDs to include (if None, uses topic search)
            topic: Topic to search for memories (alternative to memory_ids)
            format: Output format - "json" or "mermaid"
            include_orphans: Include memories with no relationships

        Returns:
            Graph structure with nodes and edges
        """
        async with self.db.get_session() as session:
            # Determine which memories to include
            if memory_ids:
                result = await session.execute(
                    select(Memory).where(Memory.id.in_(memory_ids))
                )
                memories = result.scalars().all()
            elif topic:
                # Use recall to find relevant memories
                recall_result = await self.recall(topic, limit=20)
                all_mems = []
                for cat in ["decisions", "patterns", "warnings", "learnings"]:
                    all_mems.extend(recall_result.get(cat, []))
                if not all_mems:
                    return {"nodes": [], "edges": [], "message": "No memories found for topic"}
                memory_ids = [m["id"] for m in all_mems]
                result = await session.execute(
                    select(Memory).where(Memory.id.in_(memory_ids))
                )
                memories = result.scalars().all()
            else:
                return {"error": "Must provide either memory_ids or topic"}

            if not memories:
                return {"nodes": [], "edges": [], "message": "No memories found"}

            mem_ids = [m.id for m in memories]

            # Get all edges between these memories
            result = await session.execute(
                select(MemoryRelationship).where(
                    or_(
                        MemoryRelationship.source_id.in_(mem_ids),
                        MemoryRelationship.target_id.in_(mem_ids)
                    )
                )
            )
            edges = result.scalars().all()

            # Filter orphans if requested
            if not include_orphans and edges:
                connected_ids = set()
                for edge in edges:
                    connected_ids.add(edge.source_id)
                    connected_ids.add(edge.target_id)
                memories = [m for m in memories if m.id in connected_ids]

            # Build output
            nodes = [
                {
                    "id": m.id,
                    "content": m.content[:100] if len(m.content) > 100 else m.content,
                    "category": m.category,
                    "tags": m.tags or []
                }
                for m in memories
            ]

            edge_list = [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "relationship": e.relationship,
                    "description": e.description,
                    "confidence": e.confidence
                }
                for e in edges
                if e.source_id in mem_ids and e.target_id in mem_ids
            ]

            result_dict = {
                "nodes": nodes,
                "edges": edge_list,
                "node_count": len(nodes),
                "edge_count": len(edge_list)
            }

            # Generate mermaid if requested
            if format == "mermaid":
                result_dict["mermaid"] = self._generate_mermaid(nodes, edge_list)

            return result_dict

    def _generate_mermaid(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """Generate a Mermaid flowchart from graph data."""
        lines = ["flowchart TD"]

        # Map category to node shape
        category_shapes = {
            "decision": ("[[", "]]"),      # Stadium shape
            "pattern": ("((", "))"),       # Circle
            "warning": (">", "]"),         # Flag
            "learning": ("(", ")")         # Rounded
        }

        # Add nodes
        for node in nodes:
            shape = category_shapes.get(node["category"], ("[", "]"))
            # Escape special chars and truncate
            label = node["content"][:30].replace('"', "'").replace("\n", " ")
            lines.append(f'    {node["id"]}{shape[0]}"{label}"{shape[1]}')

        # Arrow styles by relationship type
        arrow_styles = {
            "led_to": "-->",
            "supersedes": "-.->",
            "depends_on": "==>",
            "conflicts_with": "--x",
            "related_to": "---"
        }

        # Add edges
        for edge in edges:
            arrow = arrow_styles.get(edge["relationship"], "-->")
            lines.append(f'    {edge["source_id"]} {arrow}|{edge["relationship"]}| {edge["target_id"]}')

        return "\n".join(lines)

    # Maximum tags allowed in FTS search filter (prevent query explosion)
    _FTS_MAX_TAGS = 20

    def _build_fts_tag_filter(self, tags: List[str], params: Dict[str, Any]) -> str:
        """
        Build parameterized tag filter clause for FTS search.

        Args:
            tags: List of tags to filter by (max _FTS_MAX_TAGS)
            params: Parameter dict to update with tag values

        Returns:
            SQL clause string with parameterized placeholders
        """
        # Limit tags to prevent query explosion
        safe_tags = tags[:self._FTS_MAX_TAGS]

        # Build placeholder names and populate params
        placeholders = []
        for i, tag in enumerate(safe_tags):
            param_name = f"tag{i}"
            placeholders.append(f":{param_name}")
            params[param_name] = tag

        placeholder_list = ", ".join(placeholders)
        return f"""
            AND EXISTS (
                SELECT 1 FROM json_each(m.tags)
                WHERE json_each.value IN ({placeholder_list})
            )
        """

    async def fts_search(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        file_path: Optional[str] = None,
        limit: int = 20,
        highlight: bool = False,
        highlight_start: str = "<b>",
        highlight_end: str = "</b>",
        excerpt_tokens: int = 32
    ) -> List[Dict[str, Any]]:
        """
        Fast full-text search using SQLite FTS5 with optional highlighting.

        Falls back to LIKE search if FTS5 is not available.

        Args:
            query: Search query (supports FTS5 syntax)
            tags: Optional tag filter (max 20 tags)
            file_path: Optional file path filter
            limit: Maximum results
            highlight: If True, include highlighted excerpts in results
            highlight_start: Opening tag for matched terms (default: <b>)
            highlight_end: Closing tag for matched terms (default: </b>)
            excerpt_tokens: Max tokens in excerpt (default: 32)

        Returns:
            List of matching memories with relevance info.
            If highlight=True, includes 'excerpt' field with highlighted matches.
        """
        # Input validation
        if not query or not query.strip():
            return []

        limit = min(max(1, limit), 100)  # Clamp to reasonable range
        excerpt_tokens = min(max(8, excerpt_tokens), 64)  # Reasonable excerpt size

        async with self.db.get_session() as session:
            try:
                from sqlalchemy import text

                # Base FTS5 query with parameterized inputs
                # The snippet function uses column index:
                # - Column 0 = content (from FTS index)
                # - Column 1 = rationale (if indexed)
                if highlight:
                    sql_parts = [
                        f"""
                        SELECT m.*,
                               bm25(memories_fts) as rank,
                               snippet(memories_fts, 0, '{highlight_start}', '{highlight_end}', '...', {excerpt_tokens}) as content_excerpt
                        FROM memories m
                        JOIN memories_fts ON m.id = memories_fts.rowid
                        WHERE memories_fts MATCH :query
                        AND (m.archived = 0 OR m.archived IS NULL)
                        """
                    ]
                else:
                    sql_parts = [
                        """
                        SELECT m.*, bm25(memories_fts) as rank
                        FROM memories m
                        JOIN memories_fts ON m.id = memories_fts.rowid
                        WHERE memories_fts MATCH :query
                        AND (m.archived = 0 OR m.archived IS NULL)
                        """
                    ]
                params: Dict[str, Any] = {"query": query.strip()}

                # Add tag filter using helper
                if tags:
                    sql_parts.append(self._build_fts_tag_filter(tags, params))

                # Add file path filter
                if file_path:
                    sql_parts.append(" AND m.file_path = :file_path")
                    params["file_path"] = file_path

                sql_parts.append(" ORDER BY rank LIMIT :limit")
                params["limit"] = limit

                sql = "".join(sql_parts)
                result = await session.execute(text(sql), params)
                rows = result.fetchall()

                results = []
                for row in rows:
                    item = {
                        "id": row.id,
                        "category": row.category,
                        "content": row.content,
                        "rationale": row.rationale,
                        "tags": row.tags,
                        "file_path": row.file_path,
                        "relevance": abs(row.rank),  # bm25 returns negative scores
                        "created_at": row.created_at if isinstance(row.created_at, str) else (row.created_at.isoformat() if row.created_at else None)
                    }
                    if highlight and hasattr(row, 'content_excerpt'):
                        item["excerpt"] = row.content_excerpt
                    results.append(item)

                return results

            except Exception as e:
                # FTS5 not available, fall back to LIKE search
                logger.debug(f"FTS5 not available, using LIKE search: {e}")
                return await self.search(query, limit=limit)
