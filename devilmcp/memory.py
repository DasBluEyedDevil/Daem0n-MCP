"""
Memory Manager - The core of DevilMCP's AI memory system.

This module handles:
- Storing memories (decisions, patterns, warnings, learnings)
- Semantic retrieval using TF-IDF similarity
- Time-based memory decay
- Conflict detection
- Outcome tracking for learning
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, or_, func, desc

from .database import DatabaseManager
from .models import Memory
from .similarity import (
    TFIDFIndex,
    tokenize,
    calculate_memory_decay,
    detect_conflict,
    get_global_index,
    STOP_WORDS
)
from . import vectors

logger = logging.getLogger(__name__)


def extract_keywords(text: str, tags: Optional[List[str]] = None) -> str:
    """
    Extract keywords from text for backward compatibility.
    Uses the new tokenizer under the hood.
    """
    tokens = tokenize(text)
    if tags:
        for tag in tags:
            tokens.extend(tokenize(tag))
    return " ".join(sorted(set(tokens)))


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
        self._vector_index: Optional[vectors.VectorIndex] = None
        self._index_loaded = False
        self._vectors_enabled = vectors.is_available()

    async def _ensure_index(self) -> TFIDFIndex:
        """Ensure the TF-IDF index is loaded with all memories."""
        if self._index is None:
            self._index = TFIDFIndex()

        if self._vector_index is None:
            self._vector_index = vectors.VectorIndex()

        if not self._index_loaded:
            async with self.db.get_session() as session:
                result = await session.execute(select(Memory))
                memories = result.scalars().all()

                for mem in memories:
                    text = mem.content
                    if mem.rationale:
                        text += " " + mem.rationale
                    self._index.add_document(mem.id, text, mem.tags)

                    # Load vectors if available
                    if self._vectors_enabled and mem.vector_embedding:
                        self._vector_index.add_from_bytes(mem.id, mem.vector_embedding)

                self._index_loaded = True
                vector_count = len(self._vector_index) if self._vector_index else 0
                logger.info(f"Loaded {len(memories)} memories into TF-IDF index ({vector_count} with vectors)")

        return self._index

    async def remember(
        self,
        category: str,
        content: str,
        rationale: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        file_path: Optional[str] = None
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

        memory = Memory(
            category=category,
            content=content,
            rationale=rationale,
            context=context or {},
            tags=tags or [],
            keywords=keywords.strip(),
            file_path=file_path,
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

            # Add to vector index if available
            if self._vectors_enabled and vector_embedding and self._vector_index:
                self._vector_index.add_from_bytes(memory_id, vector_embedding)

            logger.info(f"Stored {category}: {content[:50]}..." + (" [+vector]" if vector_embedding else ""))

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

            return result

    async def _check_conflicts(
        self,
        content: str,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Check for conflicts with existing memories."""
        async with self.db.get_session() as session:
            # Get recent memories that might conflict
            result = await session.execute(
                select(Memory)
                .order_by(desc(Memory.created_at))
                .limit(100)  # Check against recent memories
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

    async def recall(
        self,
        topic: str,
        categories: Optional[List[str]] = None,
        limit: int = 10,
        include_warnings: bool = True,
        decay_half_life_days: float = 30.0
    ) -> Dict[str, Any]:
        """
        Recall memories relevant to a topic using semantic similarity.

        This is the core "active memory" function. It:
        1. Uses TF-IDF to find semantically similar memories
        2. Applies time decay to favor recent memories
        3. Boosts failed decisions (they're important warnings)
        4. Organizes by category

        Args:
            topic: What you're looking for
            categories: Limit to specific categories (default: all)
            limit: Max memories per category
            include_warnings: Always include warnings even if not in categories
            decay_half_life_days: How quickly old memories lose relevance

        Returns:
            Dict with categorized memories and relevance scores
        """
        index = await self._ensure_index()

        # Use hybrid search if vectors available, otherwise TF-IDF only
        if self._vectors_enabled and self._vector_index and len(self._vector_index) > 0:
            hybrid = vectors.HybridSearch(index, self._vector_index)
            search_results = hybrid.search(topic, top_k=limit * 4)
        else:
            search_results = index.search(topic, top_k=limit * 4, threshold=0.05)

        if not search_results:
            return {"memories": [], "message": "No relevant memories found", "topic": topic}

        # Get full memory objects
        memory_ids = [doc_id for doc_id, _ in search_results]
        score_map = {doc_id: score for doc_id, score in search_results}

        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory).where(Memory.id.in_(memory_ids))
            )
            memories = {m.id: m for m in result.scalars().all()}

        # Score with decay and organize
        scored_memories = []
        for mem_id, base_score in search_results:
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
                final_score *= 1.5

            # Boost warnings
            if mem.category == 'warning':
                final_score *= 1.2

            scored_memories.append((mem, final_score, base_score, decay))

        # Sort by final score
        scored_memories.sort(key=lambda x: x[1], reverse=True)

        # Organize by category
        by_category = {
            'decisions': [],
            'patterns': [],
            'warnings': [],
            'learnings': []
        }

        for mem, final_score, base_score, decay in scored_memories:
            cat_key = mem.category + 's'  # decision -> decisions
            if cat_key in by_category and len(by_category[cat_key]) < limit:
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

        return {
            'topic': topic,
            'found': total,
            'summary': " | ".join(summary_parts) if summary_parts else None,
            **by_category
        }

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
        index = await self._ensure_index()

        # Search using TF-IDF
        results = index.search(query, top_k=limit, threshold=0.05)

        if not results:
            # Fall back to text search for exact matches
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(Memory)
                    .where(
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
                select(Memory).where(Memory.id.in_(memory_ids))
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
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get all memories associated with a specific file.

        Use this when opening a file to see all relevant context -
        warnings, patterns, and past decisions about this file.

        Args:
            file_path: The file path to look up
            limit: Max memories to return

        Returns:
            Dict with memories organized by category
        """
        async with self.db.get_session() as session:
            # Get memories directly linked to this file
            result = await session.execute(
                select(Memory)
                .where(Memory.file_path == file_path)
                .order_by(desc(Memory.created_at))
                .limit(limit)
            )
            direct_memories = result.scalars().all()

            # Also search for memories mentioning this file in content
            filename = file_path.split('/')[-1] if '/' in file_path else file_path
            result = await session.execute(
                select(Memory)
                .where(
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

        return {
            'file_path': file_path,
            'found': total,
            'has_warnings': len(by_category['warnings']) > 0 or any(
                m.get('worked') is False for cat in by_category.values() for m in cat
            ),
            **by_category
        }
