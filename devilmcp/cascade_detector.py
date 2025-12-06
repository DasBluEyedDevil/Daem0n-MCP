"""
Cascade Detector Module
Detects and analyzes potential cascading failures and dependency chains.

Auto-hydrates dependency graph from the database - no manual ETL required.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone
from sqlalchemy import select, desc, func

from .database import DatabaseManager
from .models import CascadeEvent, FileDependency, ProjectFile

try:
    import networkx as nx
except ImportError:
    nx = None
    logging.warning("networkx not available - graph analysis will be limited")

logger = logging.getLogger(__name__)


class CascadeDetector:
    """Detects cascading failures and analyzes dependency chains."""

    def __init__(self, db_manager: DatabaseManager, storage_path: str = "./storage"):
        self.db = db_manager
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self._graph_hydrated = False

        # Dependency graph
        if nx:
            self.dep_graph = nx.DiGraph()
        else:
            self.dep_graph = None

    async def _ensure_hydrated(self) -> bool:
        """
        Ensure the dependency graph is loaded from DB.
        Called automatically before any graph operation.
        """
        if self._graph_hydrated or not self.dep_graph:
            return self._graph_hydrated

        try:
            await self._hydrate_from_db()
            self._graph_hydrated = True
            return True
        except Exception as e:
            logger.error(f"Failed to hydrate dependency graph: {e}")
            return False

    async def _hydrate_from_db(self) -> None:
        """
        Load the dependency graph from FileDependency table.
        This replaces the manual build_dependency_graph() approach.
        """
        if not self.dep_graph:
            return

        self.dep_graph.clear()

        async with self.db.get_session() as session:
            # Get all files
            files_result = await session.execute(select(ProjectFile))
            files = {f.id: f.file_path for f in files_result.scalars().all()}

            # Add all files as nodes
            for file_id, file_path in files.items():
                self.dep_graph.add_node(file_path, type='file')

            # Get all dependencies
            deps_result = await session.execute(select(FileDependency))
            deps = deps_result.scalars().all()

            # Add edges
            for dep in deps:
                source_path = files.get(dep.source_file_id)
                target_path = files.get(dep.target_file_id)

                if source_path and target_path:
                    self.dep_graph.add_edge(
                        source_path,
                        target_path,
                        dep_type=dep.dependency_type or 'import'
                    )

        node_count = self.dep_graph.number_of_nodes()
        edge_count = self.dep_graph.number_of_edges()
        logger.info(f"Hydrated dependency graph: {node_count} nodes, {edge_count} edges")

    async def refresh_graph(self) -> Dict:
        """
        Force refresh the dependency graph from DB.
        Returns graph statistics.
        """
        self._graph_hydrated = False
        await self._ensure_hydrated()

        if not self.dep_graph:
            return {"error": "networkx not available"}

        return {
            "total_nodes": self.dep_graph.number_of_nodes(),
            "total_edges": self.dep_graph.number_of_edges(),
            "density": nx.density(self.dep_graph) if self.dep_graph.number_of_nodes() > 0 else 0,
            "refreshed_at": datetime.now(timezone.utc).isoformat()
        }

    async def detect_dependencies(
        self,
        target: str,
        depth: int = 5,
        direction: str = "both"
    ) -> Dict:
        """
        Detect all dependencies for a target file or module.
        Auto-hydrates from DB if needed.
        """
        await self._ensure_hydrated()

        if not self.dep_graph:
            return {
                "target": target,
                "upstream": [],
                "downstream": [],
                "message": "networkx not available - install with: pip install networkx"
            }

        # Try to find the target (support partial paths)
        actual_target = self._find_node(target)
        if not actual_target:
            return {
                "target": target,
                "upstream": [],
                "downstream": [],
                "message": f"Target '{target}' not found in dependency graph"
            }

        result = {
            "target": actual_target,
            "upstream": [],
            "downstream": [],
            "depth": depth
        }

        # Upstream dependencies (what depends on this)
        if direction in ["upstream", "both"]:
            result["upstream"] = self._trace_dependencies(actual_target, depth, "upstream")

        # Downstream dependencies (what this depends on)
        if direction in ["downstream", "both"]:
            result["downstream"] = self._trace_dependencies(actual_target, depth, "downstream")

        return result

    def _find_node(self, target: str) -> Optional[str]:
        """Find a node that matches the target (exact or suffix match)."""
        if not self.dep_graph:
            return None

        # Exact match
        if target in self.dep_graph:
            return target

        # Suffix match (e.g., 'server.py' matches 'devilmcp/server.py')
        for node in self.dep_graph.nodes():
            if node.endswith(target) or node.endswith('/' + target):
                return node

        return None

    def _trace_dependencies(self, target: str, depth: int, direction: str) -> List[Dict]:
        """Trace dependencies in a given direction."""
        layers = []
        visited = set()
        current_layer = {target}

        for level in range(1, depth + 1):
            next_layer = set()
            for node in current_layer:
                if direction == "upstream":
                    neighbors = list(self.dep_graph.predecessors(node))
                else:
                    neighbors = list(self.dep_graph.successors(node))

                for n in neighbors:
                    if n not in visited and n not in current_layer:
                        next_layer.add(n)
                        visited.add(n)

            if next_layer:
                layers.append({
                    "level": level,
                    "dependencies": list(next_layer)
                })
            current_layer = next_layer
            if not current_layer:
                break

        return layers

    async def analyze_cascade_risk(
        self,
        target: str,
        change_type: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze the risk of cascading failures from a change.
        Auto-hydrates from DB if needed.
        """
        await self._ensure_hydrated()

        risk = {
            "target": target,
            "change_type": change_type,
            "cascade_probability": "unknown",
            "risk_level": "unknown",
            "affected_components": [],
            "critical_paths": [],
            "recommendations": []
        }

        # Get dependencies
        deps = await self.detect_dependencies(target, depth=5, direction="upstream")
        upstream_count = sum(len(level["dependencies"]) for level in deps.get("upstream", []))

        # Assess risk based on dependency count and change type
        if change_type in ["breaking", "delete"]:
            if upstream_count > 10:
                risk["cascade_probability"] = "very_high"
                risk["risk_level"] = "critical"
            elif upstream_count > 5:
                risk["cascade_probability"] = "high"
                risk["risk_level"] = "high"
            elif upstream_count > 0:
                risk["cascade_probability"] = "medium"
                risk["risk_level"] = "medium"
            else:
                risk["cascade_probability"] = "low"
                risk["risk_level"] = "low"

        elif change_type in ["modify", "refactor"]:
            if upstream_count > 15:
                risk["cascade_probability"] = "high"
                risk["risk_level"] = "high"
            elif upstream_count > 8:
                risk["cascade_probability"] = "medium"
                risk["risk_level"] = "medium"
            else:
                risk["cascade_probability"] = "low"
                risk["risk_level"] = "low"

        else:  # add, non-breaking
            risk["cascade_probability"] = "very_low"
            risk["risk_level"] = "low"

        # List affected components
        risk["affected_components"] = [
            dep for level in deps.get("upstream", [])
            for dep in level["dependencies"]
        ]

        # Find critical paths
        actual_target = self._find_node(target)
        if self.dep_graph and actual_target:
            risk["critical_paths"] = self._find_critical_paths(actual_target)

        # Generate recommendations
        risk["recommendations"] = self._generate_cascade_recommendations(risk)

        return risk

    def _find_critical_paths(self, target: str, max_paths: int = 5) -> List[Dict]:
        """Find critical dependency paths from target."""
        if not self.dep_graph:
            return []

        critical_paths = []

        try:
            # Find paths to highly connected nodes
            for node in self.dep_graph.nodes():
                if node == target:
                    continue

                if nx.has_path(self.dep_graph, target, node):
                    paths = list(nx.all_simple_paths(
                        self.dep_graph, target, node, cutoff=5
                    ))

                    for path in paths[:max_paths]:
                        criticality = sum(self.dep_graph.out_degree(n) for n in path)

                        critical_paths.append({
                            "path": path,
                            "length": len(path),
                            "criticality": criticality
                        })

            critical_paths.sort(key=lambda x: x["criticality"], reverse=True)
            return critical_paths[:max_paths]

        except Exception as e:
            logger.error(f"Error finding critical paths: {e}")
            return []

    def _generate_cascade_recommendations(self, risk: Dict) -> List[str]:
        """Generate recommendations based on cascade risk."""
        recommendations = []

        risk_level = risk["risk_level"]
        cascade_prob = risk["cascade_probability"]
        affected_count = len(risk["affected_components"])

        if risk_level in ["critical", "high"]:
            recommendations.extend([
                "HIGH RISK: This change has high cascade potential",
                "Consider breaking this change into smaller, isolated changes",
                "Implement comprehensive integration tests before proceeding",
                "Have immediate rollback plan ready"
            ])

        if affected_count > 10:
            recommendations.append(
                f"This change affects {affected_count} components - "
                "review each for compatibility"
            )

        if cascade_prob in ["high", "very_high"]:
            recommendations.extend([
                "Monitor error rates and performance metrics closely",
                "Consider feature flag to control rollout"
            ])

        if risk["change_type"] in ["breaking", "delete"]:
            recommendations.extend([
                "Provide migration guide for affected consumers",
                "Consider deprecation period before removal"
            ])

        recommendations.append("Run full test suite including integration tests")

        return recommendations

    async def generate_dependency_diagram(
        self,
        target: str,
        depth: int = 3
    ) -> str:
        """
        Generate a MermaidJS dependency diagram for visual impact analysis.
        """
        await self._ensure_hydrated()

        actual_target = self._find_node(target)
        if not self.dep_graph or not actual_target:
            return "graph TD;\nError[Target not found in graph];"

        mermaid = ["graph TD"]
        mermaid.append("classDef target fill:#ff9900,stroke:#333,stroke-width:2px;")
        mermaid.append("classDef upstream fill:#ffcccc,stroke:#333;")
        mermaid.append("classDef downstream fill:#ccffcc,stroke:#333;")

        # Sanitize node names for mermaid
        def sanitize(name: str) -> str:
            return name.replace("/", "_").replace(".", "_").replace("-", "_")

        mermaid.append(f'{sanitize(actual_target)}["{actual_target}"]:::target')

        deps = await self.detect_dependencies(actual_target, depth=depth, direction="both")
        added_nodes = {actual_target}

        for level in deps.get("upstream", []):
            for node in level["dependencies"]:
                if node not in added_nodes:
                    mermaid.append(f'{sanitize(node)}["{node}"]:::upstream')
                    added_nodes.add(node)

        for level in deps.get("downstream", []):
            for node in level["dependencies"]:
                if node not in added_nodes:
                    mermaid.append(f'{sanitize(node)}["{node}"]:::downstream')
                    added_nodes.add(node)

        # Add edges from subgraph
        subgraph = self.dep_graph.subgraph(added_nodes)
        for u, v in subgraph.edges():
            mermaid.append(f'{sanitize(u)} --> {sanitize(v)}')

        return "\n".join(mermaid)

    async def log_cascade_event(
        self,
        trigger: str,
        affected_components: List[str],
        severity: str,
        description: str,
        resolution: Optional[str] = None
    ) -> Dict:
        """Log a cascade failure event for learning."""
        async with self.db.get_session() as session:
            new_event = CascadeEvent(
                trigger=trigger,
                affected_components=affected_components,
                severity=severity,
                description=description,
                resolution=resolution,
                timestamp=datetime.now(timezone.utc)
            )
            session.add(new_event)
            await session.commit()
            await session.refresh(new_event)

            logger.warning(f"Cascade event logged: {trigger} - {severity}")
            return self._event_to_dict(new_event)

    async def query_cascade_history(
        self,
        trigger: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Query historical cascade events."""
        async with self.db.get_session() as session:
            stmt = select(CascadeEvent).order_by(desc(CascadeEvent.timestamp))

            if trigger:
                stmt = stmt.where(CascadeEvent.trigger.contains(trigger))

            if severity:
                stmt = stmt.where(CascadeEvent.severity == severity)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)

            return [self._event_to_dict(e) for e in result.scalars()]

    async def get_cascade_statistics(self) -> Dict:
        """Get statistics about cascade analysis and events."""
        await self._ensure_hydrated()

        stats = {
            "graph_nodes": self.dep_graph.number_of_nodes() if self.dep_graph else 0,
            "graph_edges": self.dep_graph.number_of_edges() if self.dep_graph else 0
        }

        async with self.db.get_session() as session:
            total_events = await session.scalar(select(func.count(CascadeEvent.id)))

            if total_events == 0:
                stats["total_events"] = 0
                return stats

            stmt = select(CascadeEvent.severity, func.count(CascadeEvent.id)).group_by(CascadeEvent.severity)
            res = await session.execute(stmt)
            severity_dist = {row[0]: row[1] for row in res.all()}

            stmt_trig = select(CascadeEvent.trigger, func.count(CascadeEvent.id)).group_by(
                CascadeEvent.trigger
            ).order_by(desc(func.count(CascadeEvent.id))).limit(5)
            res_trig = await session.execute(stmt_trig)
            common_triggers = [(row[0], row[1]) for row in res_trig.all()]

            last_event = await session.scalar(
                select(CascadeEvent.timestamp).order_by(desc(CascadeEvent.timestamp)).limit(1)
            )

            stats.update({
                "total_events": total_events,
                "severity_distribution": severity_dist,
                "most_common_triggers": common_triggers,
                "most_recent_event": last_event.isoformat() if last_event else None
            })

        return stats

    def _event_to_dict(self, e: CascadeEvent) -> Dict:
        return {
            "id": e.id,
            "trigger": e.trigger,
            "affected_components": e.affected_components,
            "severity": e.severity,
            "description": e.description,
            "resolution": e.resolution,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None
        }
