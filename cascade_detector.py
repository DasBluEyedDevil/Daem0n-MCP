"""
Cascade Detector Module
Detects and analyzes potential cascading failures and dependency chains.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import logging

try:
    import networkx as nx
except ImportError:
    nx = None
    logging.warning("networkx not available - graph analysis will be limited")

logger = logging.getLogger(__name__)


class CascadeDetector:
    """Detects cascading failures and analyzes dependency chains."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.cascade_file = self.storage_path / "cascade_analysis.json"
        self.cascade_data = self._load_cascade_data()

        # Dependency graph
        if nx:
            self.dep_graph = nx.DiGraph()
        else:
            self.dep_graph = None

    def _load_cascade_data(self) -> Dict:
        """Load existing cascade analysis data."""
        if self.cascade_file.exists():
            try:
                with open(self.cascade_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cascade data: {e}")

        return {
            "dependency_chains": {},
            "cascade_events": [],
            "risk_scores": {}
        }

    def _save_cascade_data(self):
        """Persist cascade analysis data."""
        try:
            with open(self.cascade_file, 'w') as f:
                json.dump(self.cascade_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cascade data: {e}")

    def build_dependency_graph(self, dependencies: Dict[str, Dict]) -> Dict:
        """
        Build a dependency graph from project dependencies.

        Args:
            dependencies: Dictionary mapping files to their dependencies

        Returns:
            Graph statistics and structure information
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
            "analyzed_at": datetime.now().isoformat()
        }

        # Store graph structure
        self.cascade_data["dependency_chains"] = {
            "nodes": list(self.dep_graph.nodes()),
            "edges": [(u, v) for u, v in self.dep_graph.edges()],
            "stats": stats
        }
        self._save_cascade_data()

        return stats

    def detect_dependencies(
        self,
        target: str,
        depth: int = 5,
        direction: str = "both"
    ) -> Dict:
        """
        Detect all dependencies for a target file or module.

        Args:
            target: Target file or module to analyze
            depth: How many levels deep to traverse
            direction: 'upstream' (what depends on target), 'downstream' (what target depends on), or 'both'

        Returns:
            Dictionary of dependencies at each level
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
                upstream = set()
                for level in range(1, depth + 1):
                    level_deps = set()
                    for node in self.dep_graph.predecessors(target):
                        if node not in upstream:
                            level_deps.add(node)
                            upstream.add(node)

                    if level_deps:
                        result["upstream"].append({
                            "level": level,
                            "dependencies": list(level_deps)
                        })
            except Exception as e:
                logger.error(f"Error analyzing upstream dependencies: {e}")

        # Downstream dependencies (what this depends on)
        if direction in ["downstream", "both"]:
            try:
                downstream = set()
                for level in range(1, depth + 1):
                    level_deps = set()
                    for node in self.dep_graph.successors(target):
                        if node not in downstream:
                            level_deps.add(node)
                            downstream.add(node)

                    if level_deps:
                        result["downstream"].append({
                            "level": level,
                            "dependencies": list(level_deps)
                        })
            except Exception as e:
                logger.error(f"Error analyzing downstream dependencies: {e}")

        return result

    def analyze_cascade_risk(
        self,
        target: str,
        change_type: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze the risk of cascading failures from a change.

        Args:
            target: Target file or component being changed
            change_type: Type of change (breaking, non-breaking, refactor, etc.)
            context: Additional context about the change

        Returns:
            Risk assessment including cascade probability and affected components
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

        # Store cascade risk assessment
        self.cascade_data["risk_scores"][target] = {
            "score": risk["risk_level"],
            "timestamp": datetime.now().isoformat(),
            "change_type": change_type
        }
        self._save_cascade_data()

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

    def log_cascade_event(
        self,
        trigger: str,
        affected_components: List[str],
        severity: str,
        description: str,
        resolution: Optional[str] = None
    ) -> Dict:
        """
        Log a cascade failure event for learning.

        Args:
            trigger: What triggered the cascade
            affected_components: List of affected components
            severity: Severity level (low, medium, high, critical)
            description: Description of what happened
            resolution: How it was resolved

        Returns:
            The logged cascade event
        """
        event = {
            "id": len(self.cascade_data["cascade_events"]) + 1,
            "trigger": trigger,
            "affected_components": affected_components,
            "severity": severity,
            "description": description,
            "resolution": resolution,
            "timestamp": datetime.now().isoformat()
        }

        self.cascade_data["cascade_events"].append(event)
        self._save_cascade_data()

        logger.warning(f"Cascade event logged: {trigger} - {severity}")
        return event

    def query_cascade_history(
        self,
        trigger: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query historical cascade events.

        Args:
            trigger: Filter by trigger component
            severity: Filter by severity level
            limit: Maximum number of results

        Returns:
            List of matching cascade events
        """
        results = []

        for event in reversed(self.cascade_data["cascade_events"]):
            if trigger and trigger not in event["trigger"]:
                continue

            if severity and event["severity"] != severity:
                continue

            results.append(event)

            if len(results) >= limit:
                break

        return results

    def suggest_safe_changes(
        self,
        target: str,
        proposed_change: str
    ) -> Dict:
        """
        Suggest safe approaches for making a change to minimize cascade risk.

        Args:
            target: Target component to change
            proposed_change: Description of proposed change

        Returns:
            Suggestions for safe implementation
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

    def get_cascade_statistics(self) -> Dict:
        """
        Get statistics about cascade analysis and events.

        Returns:
            Statistics including event frequency, severity distribution, etc.
        """
        events = self.cascade_data.get("cascade_events", [])

        if not events:
            return {"total_events": 0}

        severity_distribution = {}
        triggers = {}

        for event in events:
            severity = event["severity"]
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1

            trigger = event["trigger"]
            triggers[trigger] = triggers.get(trigger, 0) + 1

        return {
            "total_events": len(events),
            "severity_distribution": severity_distribution,
            "most_common_triggers": sorted(
                triggers.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "most_recent_event": events[-1]["timestamp"] if events else None,
            "risk_scores_tracked": len(self.cascade_data.get("risk_scores", {}))
        }
