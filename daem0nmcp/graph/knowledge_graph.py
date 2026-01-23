"""
KnowledgeGraph - In-memory graph synchronized with SQLite.

This module implements the dual-storage pattern for GraphRAG:
- NetworkX DiGraph for fast in-memory traversal
- SQLite as the source of truth via existing models

Node naming convention:
- "entity:{id}" - ExtractedEntity nodes
- "memory:{id}" - Memory nodes (via MemoryEntityRef)

Edge types:
- Memory -> Entity: "references" (from MemoryEntityRef)
- Memory -> Memory: relationship type (from MemoryRelationship)
"""

import logging
from typing import TYPE_CHECKING, List, Optional, Set

import networkx as nx

if TYPE_CHECKING:
    from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    In-memory knowledge graph synchronized with SQLite database.

    Uses NetworkX DiGraph for efficient traversal while SQLite remains
    the source of truth. Supports lazy loading and forced reloads.

    Node types:
    - entity:{id}: Extracted entities from memory content
    - memory:{id}: Memory nodes connected via relationships

    Usage:
        db = DatabaseManager(storage_path="./storage")
        await db.init_db()

        kg = KnowledgeGraph(db)
        await kg.ensure_loaded()

        print(f"Nodes: {kg.get_node_count()}")
        neighbors = kg.get_neighbors("entity:42")
    """

    def __init__(self, db: "DatabaseManager") -> None:
        """
        Initialize the knowledge graph.

        Args:
            db: DatabaseManager instance for SQLite access
        """
        self._db = db
        self._graph: nx.DiGraph = nx.DiGraph()
        self._loaded: bool = False

    async def ensure_loaded(self) -> None:
        """
        Load graph from SQLite if not already loaded.

        Uses lazy loading pattern - first call loads from DB,
        subsequent calls are no-ops until reload_from_db() is called.
        """
        if self._loaded:
            return

        await self._load_from_db()
        self._loaded = True

    async def reload_from_db(self) -> None:
        """
        Force reload of the graph from SQLite.

        Clears current graph and reloads all data.
        Use when database has been modified externally.
        """
        self._loaded = False
        self._graph.clear()
        await self.ensure_loaded()

    async def _load_from_db(self) -> None:
        """
        Load entities and relationships from SQLite into NetworkX graph.

        Loading order:
        1. ExtractedEntity -> entity:{id} nodes
        2. MemoryEntityRef -> memory:{id} nodes + edges to entities
        3. MemoryRelationship -> edges between memory nodes
        """
        from sqlalchemy import select

        from ..models import ExtractedEntity, MemoryEntityRef, MemoryRelationship

        async with self._db.get_session() as session:
            # 1. Load extracted entities as nodes
            entity_result = await session.execute(select(ExtractedEntity))
            entities = entity_result.scalars().all()

            for entity in entities:
                node_id = f"entity:{entity.id}"
                self._graph.add_node(
                    node_id,
                    node_type="entity",
                    entity_type=entity.entity_type,
                    name=entity.name,
                    qualified_name=entity.qualified_name,
                    project_path=entity.project_path,
                    mention_count=entity.mention_count,
                )

            logger.debug(f"Loaded {len(entities)} entity nodes")

            # 2. Load memory-entity references
            # This creates memory nodes and edges to entities
            ref_result = await session.execute(select(MemoryEntityRef))
            refs = ref_result.scalars().all()

            memory_ids_seen: Set[int] = set()

            for ref in refs:
                memory_node_id = f"memory:{ref.memory_id}"
                entity_node_id = f"entity:{ref.entity_id}"

                # Add memory node if not seen
                if ref.memory_id not in memory_ids_seen:
                    self._graph.add_node(
                        memory_node_id,
                        node_type="memory",
                    )
                    memory_ids_seen.add(ref.memory_id)

                # Add edge from memory to entity
                if self._graph.has_node(entity_node_id):
                    self._graph.add_edge(
                        memory_node_id,
                        entity_node_id,
                        edge_type="references",
                        relationship=ref.relationship,
                        context_snippet=ref.context_snippet,
                    )

            logger.debug(f"Loaded {len(refs)} memory-entity references")

            # 3. Load memory-memory relationships
            rel_result = await session.execute(select(MemoryRelationship))
            relationships = rel_result.scalars().all()

            for rel in relationships:
                source_node = f"memory:{rel.source_id}"
                target_node = f"memory:{rel.target_id}"

                # Ensure both memory nodes exist
                if rel.source_id not in memory_ids_seen:
                    self._graph.add_node(source_node, node_type="memory")
                    memory_ids_seen.add(rel.source_id)

                if rel.target_id not in memory_ids_seen:
                    self._graph.add_node(target_node, node_type="memory")
                    memory_ids_seen.add(rel.target_id)

                # Add edge between memories
                self._graph.add_edge(
                    source_node,
                    target_node,
                    edge_type="relationship",
                    relationship=rel.relationship,
                    description=rel.description,
                    confidence=rel.confidence,
                )

            logger.debug(f"Loaded {len(relationships)} memory-memory relationships")

        logger.info(
            f"KnowledgeGraph loaded: {self.get_node_count()} nodes, "
            f"{self.get_edge_count()} edges"
        )

    def get_node_count(self) -> int:
        """
        Return the total number of nodes in the graph.

        Returns:
            Number of nodes (entities + memories)
        """
        return self._graph.number_of_nodes()

    def get_edge_count(self) -> int:
        """
        Return the total number of edges in the graph.

        Returns:
            Number of edges (references + relationships)
        """
        return self._graph.number_of_edges()

    def has_node(self, node_id: str) -> bool:
        """
        Check if a node exists in the graph.

        Args:
            node_id: Node identifier (e.g., "entity:42" or "memory:17")

        Returns:
            True if node exists, False otherwise
        """
        return self._graph.has_node(node_id)

    def get_neighbors(
        self, node_id: str, direction: str = "both"
    ) -> List[str]:
        """
        Get connected nodes for a given node.

        Args:
            node_id: Node identifier (e.g., "entity:42")
            direction: "in" (predecessors), "out" (successors), or "both"

        Returns:
            List of connected node IDs
        """
        if not self._graph.has_node(node_id):
            return []

        if direction == "in":
            return list(self._graph.predecessors(node_id))
        elif direction == "out":
            return list(self._graph.successors(node_id))
        else:  # both
            predecessors = set(self._graph.predecessors(node_id))
            successors = set(self._graph.successors(node_id))
            return list(predecessors | successors)

    def get_node_attributes(self, node_id: str) -> Optional[dict]:
        """
        Get attributes for a node.

        Args:
            node_id: Node identifier

        Returns:
            Dictionary of node attributes or None if node doesn't exist
        """
        if not self._graph.has_node(node_id):
            return None
        return dict(self._graph.nodes[node_id])

    def get_edge_attributes(
        self, source_id: str, target_id: str
    ) -> Optional[dict]:
        """
        Get attributes for an edge.

        Args:
            source_id: Source node identifier
            target_id: Target node identifier

        Returns:
            Dictionary of edge attributes or None if edge doesn't exist
        """
        if not self._graph.has_edge(source_id, target_id):
            return None
        return dict(self._graph.edges[source_id, target_id])
