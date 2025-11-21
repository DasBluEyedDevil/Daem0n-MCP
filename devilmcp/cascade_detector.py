"""
Cascade Detector Module
Detects and analyzes potential cascading failures and dependency chains.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, desc, func

from .database import DatabaseManager
from .models import CascadeEvent

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

        # Dependency graph
        if nx:
            self.dep_graph = nx.DiGraph()
        else:
            self.dep_graph = None

    def build_dependency_graph(self, dependencies: Dict[str, Dict]) -> Dict:
        """
        Build a dependency graph from project dependencies.
        """
        if not self.dep_graph:
            return {"error": "networkx not available for graph analysis"}

        # Clear existing graph
        self.dep_graph.clear()

        # Build graph from dependencies
        for file_path, deps in dependencies.items():
            self.dep_graph.add_node(file_path, type='file')

            # Add edges for each dependency
            for dep in deps.get('internal_deps', []):
                self.dep_graph.add_node(dep, type='module')
                self.dep_graph.add_edge(file_path, dep, dep_type='internal')

            for dep in deps.get('external_deps', []):
                self.dep_graph.add_node(dep, type='external')
                self.dep_graph.add_edge(file_path, dep, dep_type='external')

        # Calculate graph statistics
        stats = {
            "total_nodes": self.dep_graph.number_of_nodes(),
            "total_edges": self.dep_graph.number_of_edges(),
            "density": nx.density(self.dep_graph),
            "strongly_connected_components": nx.number_strongly_connected_components(self.dep_graph),
            "weakly_connected_components": nx.number_weakly_connected_components(self.dep_graph),
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

        return stats

    def detect_dependencies(
        self,
        target: str,
        depth: int = 5,
        direction: str = "both"
    ) -> Dict:
        """
        Detect all dependencies for a target file or module.
        """
        if not self.dep_graph or target not in self.dep_graph:
            # Fallback to simple analysis without graph
            return {
                "target": target,
                "upstream": [],
                "downstream": [],
                "message": "Limited analysis - full graph not available"
            }

        result = {
            "target": target,
            "upstream": [],
            "downstream": [],
            "depth": depth
        }

        # Upstream dependencies (what depends on this)
        if direction in ["upstream", "both"]:
            try:
                visited = set()
                current_layer = {target}
                
                for level in range(1, depth + 1):
                    next_layer = set()
                    for node in current_layer:
                        preds = list(self.dep_graph.predecessors(node))
                        for p in preds:
                            if p not in visited and p not in current_layer:
                                next_layer.add(p)
                                visited.add(p)
                    
                    if next_layer:
                         result["upstream"].append({
                            "level": level,
                            "dependencies": list(next_layer)
                        })
                    current_layer = next_layer
                    if not current_layer:
                        break

            except Exception as e:
                logger.error(f"Error analyzing upstream dependencies: {e}")

        # Downstream dependencies (what this depends on)
        if direction in ["downstream", "both"]:
            try:
                visited = set()
                current_layer = {target}
                
                for level in range(1, depth + 1):
                    next_layer = set()
                    for node in current_layer:
                        succs = list(self.dep_graph.successors(node))
                        for s in succs:
                            if s not in visited and s not in current_layer:
                                next_layer.add(s)
                                visited.add(s)
                    
                    if next_layer:
                         result["downstream"].append({
                            "level": level,
                            "dependencies": list(next_layer)
                        })
                    current_layer = next_layer
                    if not current_layer:
                        break
            except Exception as e:
                logger.error(f"Error analyzing downstream dependencies: {e}")

        return result

    def generate_dependency_diagram(
        self,
        target: str,
        depth: int = 3
    ) -> str:
        """
        Generate a MermaidJS dependency diagram for visual impact analysis.
        """
        if not self.dep_graph or target not in self.dep_graph:
            return "graph TD;\nError[Target not found in graph];"

        mermaid = ["graph TD"]
        
        # Style definitions
        mermaid.append("classDef target fill:#ff9900,stroke:#333,stroke-width:2px;")
        mermaid.append("classDef upstream fill:#ffcccc,stroke:#333;")
        mermaid.append("classDef downstream fill:#ccffcc,stroke:#333;")
        
        # Add target node
        mermaid.append(f'Target("{target}"):::target')

        # Get dependencies
        deps = self.detect_dependencies(target, depth=depth, direction="both")
        
        added_nodes = {target}
        
        # Process Upstream (Who depends on Target)
        # A -> Target
        for level in deps.get("upstream", []):
            for node in level["dependencies"]:
                if node not in added_nodes:
                    mermaid.append(f'"{node}"("{node}"):::upstream')
                    added_nodes.add(node)
                
                # We need edges. Since detect_dependencies returns levels, we know 'node' eventually hits target.
                # But for the diagram, we want direct edges if possible.
                # Let's look at graph edges that connect 'node' towards 'target' or previously added nodes.
                # Simple approach: Just show immediate edges from the graph subset
                pass

        # Process Downstream (Target depends on Who)
        # Target -> B
        for level in deps.get("downstream", []):
            for node in level["dependencies"]:
                if node not in added_nodes:
                    mermaid.append(f'"{node}"("{node}"):::downstream')
                    added_nodes.add(node)

        # Add Edges
        # We iterate all added nodes and check if edges exist between them in the main graph
        subgraph = self.dep_graph.subgraph(added_nodes)
        for u, v in subgraph.edges():
            mermaid.append(f'"{u}" --> "{v}"')

        return "\n".join(mermaid)

    def analyze_cascade_risk(
        self,
        target: str,
        change_type: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze the risk of cascading failures from a change.
        """
        risk = {
            "target": target,
            "change_type": change_type,
            "cascade_probability": "unknown",
            "risk_level": "unknown",
            "affected_components": [],
            "critical_paths": [],
            "recommendations": []
        }

        # Analyze dependency depth
        deps = self.detect_dependencies(target, depth=5, direction="upstream")

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
        if self.dep_graph and target in self.dep_graph:
            risk["critical_paths"] = self._find_critical_paths(target)

        # Generate recommendations
        risk["recommendations"] = self._generate_cascade_recommendations(risk)

        return risk

    def _find_critical_paths(self, target: str, max_paths: int = 5) -> List[List[str]]:
        """Find critical dependency paths from target."""
        if not self.dep_graph:
            return []

        critical_paths = []

        try:
            # Find paths to highly connected nodes
            for node in self.dep_graph.nodes():
                if node == target:
                    continue

                # Check if there's a path
                if nx.has_path(self.dep_graph, target, node):
                    # Find all simple paths (limited to reasonable length)
                    paths = list(nx.all_simple_paths(
                        self.dep_graph, target, node, cutoff=5
                    ))

                    for path in paths[:max_paths]:
                        # Calculate path criticality based on node degrees
                        criticality = sum(self.dep_graph.out_degree(n) for n in path)

                        critical_paths.append({
                            "path": path,
                            "length": len(path),
                            "criticality": criticality
                        })

            # Sort by criticality and return top paths
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
                "⚠️  HIGH RISK: This change has high cascade potential",
                "Consider breaking this change into smaller, isolated changes",
                "Implement comprehensive integration tests before proceeding",
                "Set up canary deployment to catch issues early",
                "Have immediate rollback plan ready"
            ])

        if affected_count > 10:
            recommendations.append(
                f"This change affects {affected_count} components - "
                "review each for compatibility"
            )

        if cascade_prob in ["high", "very_high"]:
            recommendations.extend([
                "Create feature flag to control rollout",
                "Monitor error rates and performance metrics closely",
                "Notify affected team members of the change"
            ])

        if risk["change_type"] in ["breaking", "delete"]:
            recommendations.extend([
                "Provide migration guide for affected consumers",
                "Consider deprecation period before removal",
                "Update all documentation to reflect changes"
            ])

        # General best practices
        recommendations.extend([
            "Run full test suite including integration tests",
            "Review dependency chain manually",
            "Document the change and its impact"
        ])

        return recommendations

    async def log_cascade_event(
        self,
        trigger: str,
        affected_components: List[str],
        severity: str,
        description: str,
        resolution: Optional[str] = None
    ) -> Dict:
        """
        Log a cascade failure event for learning.
        """
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
        """
        Query historical cascade events.
        """
        async with self.db.get_session() as session:
            stmt = select(CascadeEvent).order_by(desc(CascadeEvent.timestamp))

            if trigger:
                stmt = stmt.where(CascadeEvent.trigger.contains(trigger))
            
            if severity:
                stmt = stmt.where(CascadeEvent.severity == severity)
            
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            
            return [self._event_to_dict(e) for e in result.scalars()]

    def suggest_safe_changes(
        self,
        target: str,
        proposed_change: str
    ) -> Dict:
        """
        Suggest safe approaches for making a change to minimize cascade risk.
        (Logic mostly sync, but reuses analyze_cascade_risk)
        """
        # Analyze current risk
        risk = self.analyze_cascade_risk(target, "modify")

        suggestions = {
            "target": target,
            "risk_level": risk["risk_level"],
            "approach": [],
            "testing_strategy": [],
            "rollout_plan": []
        }

        # Approach suggestions based on risk
        if risk["risk_level"] in ["critical", "high"]:
            suggestions["approach"].extend([
                "Use adapter pattern to maintain backward compatibility",
                "Implement changes behind feature flag",
                "Create parallel implementation before deprecating old one",
                "Add extensive logging and monitoring"
            ])

            suggestions["testing_strategy"].extend([
                "Comprehensive integration test suite",
                "Test with production-like data volume",
                "Stress testing of affected components",
                "Shadow deployment for comparison"
            ])

            suggestions["rollout_plan"].extend([
                "Stage 1: Deploy to development environment",
                "Stage 2: Limited rollout to 5% of traffic",
                "Stage 3: Monitor metrics for 24-48 hours",
                "Stage 4: Gradual increase if metrics are good",
                "Have automated rollback triggers ready"
            ])

        else:  # Medium or low risk
            suggestions["approach"].extend([
                "Make incremental changes",
                "Ensure backward compatibility where possible",
                "Add appropriate error handling"
            ])

            suggestions["testing_strategy"].extend([
                "Unit tests for changed functionality",
                "Integration tests for affected components",
                "Manual testing of key workflows"
            ])

            suggestions["rollout_plan"].extend([
                "Deploy to staging first",
                "Run smoke tests",
                "Deploy to production with monitoring",
                "Quick rollback available if needed"
            ])

        return suggestions

    async def get_cascade_statistics(self) -> Dict:
        """
        Get statistics about cascade analysis and events.
        """
        async with self.db.get_session() as session:
            total_events = await session.scalar(select(func.count(CascadeEvent.id)))
            
            if total_events == 0:
                return {"total_events": 0}
            
            stmt = select(CascadeEvent.severity, func.count(CascadeEvent.id)).group_by(CascadeEvent.severity)
            res = await session.execute(stmt)
            severity_dist = {row[0]: row[1] for row in res.all()}
            
            stmt_trig = select(CascadeEvent.trigger, func.count(CascadeEvent.id)).group_by(CascadeEvent.trigger).order_by(desc(func.count(CascadeEvent.id))).limit(5)
            res_trig = await session.execute(stmt_trig)
            common_triggers = [(row[0], row[1]) for row in res_trig.all()]
            
            last_event = await session.scalar(select(CascadeEvent.timestamp).order_by(desc(CascadeEvent.timestamp)).limit(1))

            return {
                "total_events": total_events,
                "severity_distribution": severity_dist,
                "most_common_triggers": common_triggers,
                "most_recent_event": last_event.isoformat() if last_event else None
            }

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