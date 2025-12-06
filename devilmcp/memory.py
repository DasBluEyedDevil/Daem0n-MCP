"""
Memory Manager - The core of DevilMCP's AI memory system.

This module handles:
- Storing memories (decisions, patterns, warnings, learnings)
- Semantic-ish retrieval based on keywords and tags
- Outcome tracking for learning
"""

import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select, or_, func, desc

from .database import DatabaseManager
from .models import Memory

logger = logging.getLogger(__name__)

# Common stop words to filter out from keyword extraction
STOP_WORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
    'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
    'because', 'until', 'while', 'this', 'that', 'these', 'those', 'it',
    'its', 'we', 'they', 'them', 'what', 'which', 'who', 'whom', 'i', 'you',
    'he', 'she', 'use', 'using', 'used'
}


def extract_keywords(text: str, tags: Optional[List[str]] = None) -> str:
    """
    Extract meaningful keywords from text for search indexing.

    Simple but effective: lowercase, split on non-alphanumeric, filter stop words.
    Returns space-separated keywords.
    """
    if not text:
        return ""

    # Normalize and split
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())

    # Filter stop words and short words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    # Add tags (already meaningful)
    if tags:
        keywords.extend([t.lower() for t in tags])

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return " ".join(unique)


def calculate_relevance(query_keywords: set, memory_keywords: str, memory_tags: list) -> float:
    """
    Calculate relevance score between query and memory.

    Returns a score from 0.0 to 1.0.
    """
    if not query_keywords:
        return 0.0

    memory_kw_set = set(memory_keywords.lower().split()) if memory_keywords else set()
    tag_set = set(t.lower() for t in memory_tags) if memory_tags else set()

    all_memory_terms = memory_kw_set | tag_set

    if not all_memory_terms:
        return 0.0

    # Count matches
    matches = len(query_keywords & all_memory_terms)

    # Jaccard-ish similarity with boost for matches
    score = matches / len(query_keywords)

    # Boost exact tag matches
    tag_matches = len(query_keywords & tag_set)
    if tag_matches > 0:
        score += 0.2 * tag_matches

    return min(score, 1.0)


class MemoryManager:
    """
    Manages AI memories - storing, retrieving, and learning from them.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def remember(
        self,
        category: str,
        content: str,
        rationale: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Store a new memory.

        Args:
            category: One of 'decision', 'pattern', 'warning', 'learning'
            content: The actual content to remember
            rationale: Why this is important / the reasoning
            context: Structured context (files, alternatives, etc.)
            tags: Tags for retrieval

        Returns:
            The created memory as a dict
        """
        valid_categories = {'decision', 'pattern', 'warning', 'learning'}
        if category not in valid_categories:
            return {"error": f"Invalid category. Must be one of: {valid_categories}"}

        # Extract keywords for search
        keywords = extract_keywords(content, tags)
        if rationale:
            keywords = keywords + " " + extract_keywords(rationale)

        memory = Memory(
            category=category,
            content=content,
            rationale=rationale,
            context=context or {},
            tags=tags or [],
            keywords=keywords.strip()
        )

        async with self.db.get_session() as session:
            session.add(memory)
            await session.flush()
            memory_id = memory.id

            logger.info(f"Stored {category}: {content[:50]}...")

            return {
                "id": memory_id,
                "category": category,
                "content": content,
                "rationale": rationale,
                "tags": tags or [],
                "created_at": memory.created_at.isoformat()
            }

    async def recall(
        self,
        topic: str,
        categories: Optional[List[str]] = None,
        limit: int = 10,
        include_warnings: bool = True
    ) -> Dict[str, Any]:
        """
        Recall memories relevant to a topic.

        This is the core "active memory" function - it finds relevant memories
        and returns them organized by category.

        Args:
            topic: What you're looking for (will be keyword-matched)
            categories: Limit to specific categories (default: all)
            limit: Max memories per category
            include_warnings: Always include warnings even if not in categories

        Returns:
            Dict with categorized memories and relevance scores
        """
        # Extract query keywords
        query_keywords = set(extract_keywords(topic).split())

        if not query_keywords:
            return {"memories": [], "message": "No searchable terms in topic"}

        async with self.db.get_session() as session:
            # Build base query
            query = select(Memory)

            # Category filter
            if categories:
                if include_warnings and 'warning' not in categories:
                    categories = list(categories) + ['warning']
                query = query.where(Memory.category.in_(categories))

            # Keyword search - find memories that have any of our keywords
            # SQLite LIKE is case-insensitive by default
            keyword_conditions = []
            for kw in query_keywords:
                keyword_conditions.append(Memory.keywords.like(f"%{kw}%"))
                keyword_conditions.append(Memory.content.like(f"%{kw}%"))

            query = query.where(or_(*keyword_conditions))
            query = query.order_by(desc(Memory.created_at))
            query = query.limit(limit * 3)  # Fetch more to re-rank

            result = await session.execute(query)
            memories = result.scalars().all()

            # Score and sort by relevance
            scored = []
            for mem in memories:
                score = calculate_relevance(query_keywords, mem.keywords, mem.tags)
                if score > 0.1:  # Minimum relevance threshold
                    scored.append((mem, score))

            scored.sort(key=lambda x: x[1], reverse=True)

            # Organize by category
            by_category = {
                'decisions': [],
                'patterns': [],
                'warnings': [],
                'learnings': []
            }

            for mem, score in scored[:limit * 2]:
                cat_key = mem.category + 's'  # decision -> decisions
                if cat_key in by_category and len(by_category[cat_key]) < limit:
                    by_category[cat_key].append({
                        'id': mem.id,
                        'content': mem.content,
                        'rationale': mem.rationale,
                        'context': mem.context,
                        'tags': mem.tags,
                        'relevance': round(score, 2),
                        'outcome': mem.outcome,
                        'worked': mem.worked,
                        'created_at': mem.created_at.isoformat()
                    })

            # Count total found
            total = sum(len(v) for v in by_category.values())

            return {
                'topic': topic,
                'found': total,
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

        Args:
            memory_id: The memory to update
            outcome: What actually happened
            worked: Did it work out?

        Returns:
            Updated memory or error
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

            # If it didn't work, consider creating a warning from this
            if not worked:
                logger.info(f"Memory {memory_id} marked as failed - consider adding a warning")

            return {
                "id": memory_id,
                "content": memory.content,
                "outcome": outcome,
                "worked": worked,
                "message": "Outcome recorded" + (
                    " - this failure will inform future recalls" if not worked else ""
                )
            }

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
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

            return {
                "total_memories": total,
                "by_category": by_category,
                "with_outcomes": {
                    "worked": worked,
                    "failed": failed,
                    "pending": total - worked - failed
                }
            }

    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Simple full-text search across all memories.
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Memory)
                .where(
                    or_(
                        Memory.content.like(f"%{query}%"),
                        Memory.rationale.like(f"%{query}%"),
                        Memory.keywords.like(f"%{query}%")
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
                    'created_at': m.created_at.isoformat()
                }
                for m in memories
            ]
