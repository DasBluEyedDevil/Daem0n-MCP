"""
Change Analyzer Module
Analyzes code changes and their potential cascading impacts across the project.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ChangeAnalyzer:
    """Analyzes and tracks code changes with impact assessment."""

    def __init__(self, storage_path: str = "./storage"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.changes_file = self.storage_path / "changes.json"
        self.changes = self._load_changes()

    def _load_changes(self) -> List[Dict]:
        """Load existing changes or create new list."""
        if self.changes_file.exists():
            try:
                with open(self.changes_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading changes: {e}")
        return []

    def _save_changes(self):
        """Persist changes to storage."""
        try:
            with open(self.changes_file, 'w') as f:
                json.dump(self.changes, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving changes: {e}")

    def log_change(
        self,
        file_path: str,
        change_type: str,
        description: str,
        rationale: str,
        affected_components: List[str],
        risk_assessment: Optional[Dict] = None,
        rollback_plan: Optional[str] = None
    ) -> Dict:
        """
        Log a code change with comprehensive context.

        Args:
            file_path: Path to the file being changed
            change_type: Type of change (add, modify, delete, refactor, etc.)
            description: Description of the change
            rationale: Why this change is being made
            affected_components: List of components/modules affected
            risk_assessment: Assessment of risks introduced by this change
            rollback_plan: Plan for rolling back if issues arise

        Returns:
            The logged change record
        """
        change_id = len(self.changes) + 1

        # Generate a hash of the change for tracking
        change_hash = hashlib.md5(
            f"{file_path}{change_type}{description}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]

        change_record = {
            "id": change_id,
            "hash": change_hash,
            "file_path": file_path,
            "change_type": change_type,
            "description": description,
            "rationale": rationale,
            "affected_components": affected_components,
            "risk_assessment": risk_assessment or {
                "level": "unknown",
                "factors": []
            },
            "rollback_plan": rollback_plan,
            "timestamp": datetime.now().isoformat(),
            "status": "planned",  # planned, implemented, tested, rolled_back
            "actual_impact": None,
            "issues_encountered": []
        }

        self.changes.append(change_record)
        self._save_changes()

        logger.info(f"Change logged: {change_id} - {file_path}")
        return change_record

    def update_change_status(
        self,
        change_id: int,
        status: str,
        actual_impact: Optional[str] = None,
        issues: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Update the status of a logged change.

        Args:
            change_id: ID of the change to update
            status: New status (implemented, tested, rolled_back, failed)
            actual_impact: The actual impact observed
            issues: List of issues encountered

        Returns:
            Updated change record or None if not found
        """
        for change in self.changes:
            if change["id"] == change_id:
                change["status"] = status
                if actual_impact:
                    change["actual_impact"] = actual_impact
                if issues:
                    change["issues_encountered"].extend(issues)
                change["updated_at"] = datetime.now().isoformat()

                self._save_changes()
                logger.info(f"Change {change_id} status updated to {status}")
                return change

        logger.warning(f"Change {change_id} not found")
        return None

    def analyze_change_impact(
        self,
        file_path: str,
        change_description: str,
        dependencies: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze the potential impact of a proposed change.

        Args:
            file_path: Path to the file to be changed
            change_description: Description of the proposed change
            dependencies: Dependency information for impact analysis

        Returns:
            Impact analysis including affected areas and risk factors
        """
        impact = {
            "file": file_path,
            "change": change_description,
            "direct_impact": [],
            "indirect_impact": [],
            "risk_factors": [],
            "recommendations": [],
            "estimated_blast_radius": "unknown"
        }

        # Analyze file extension and type
        file_ext = Path(file_path).suffix

        # Direct impact assessment
        if dependencies:
            # Files that import this file will be directly affected
            internal_deps = dependencies.get("internal_deps", [])
            external_deps = dependencies.get("external_deps", [])

            if internal_deps:
                impact["direct_impact"].extend(internal_deps)
                impact["risk_factors"].append(
                    f"Change affects {len(internal_deps)} internal dependencies"
                )

        # Assess based on file type and common patterns
        if file_ext in ['.py', '.js', '.ts']:
            # Check if it's a configuration or core file
            if 'config' in file_path.lower():
                impact["risk_factors"].append("Configuration file - changes may affect entire application")
                impact["estimated_blast_radius"] = "high"
                impact["recommendations"].append("Test all configuration-dependent features")

            elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                impact["risk_factors"].append("Utility file - changes may affect multiple features")
                impact["estimated_blast_radius"] = "medium-high"
                impact["recommendations"].append("Identify and test all callers of modified utilities")

            elif 'model' in file_path.lower() or 'schema' in file_path.lower():
                impact["risk_factors"].append("Data model change - may require migrations")
                impact["estimated_blast_radius"] = "high"
                impact["recommendations"].extend([
                    "Check for database migration requirements",
                    "Verify backward compatibility",
                    "Test data validation logic"
                ])

            elif 'api' in file_path.lower() or 'endpoint' in file_path.lower():
                impact["risk_factors"].append("API change - may affect external consumers")
                impact["estimated_blast_radius"] = "high"
                impact["recommendations"].extend([
                    "Check API versioning",
                    "Verify backward compatibility",
                    "Update API documentation"
                ])

        # Check historical change patterns
        historical_issues = self._check_historical_issues(file_path)
        if historical_issues:
            impact["risk_factors"].append(
                f"File has {len(historical_issues)} historical issues"
            )
            impact["historical_issues"] = historical_issues

        # General recommendations
        impact["recommendations"].extend([
            "Run full test suite before deployment",
            "Monitor error rates after deployment",
            "Have rollback plan ready"
        ])

        return impact

    def _check_historical_issues(self, file_path: str) -> List[Dict]:
        """Check for historical issues with this file."""
        issues = []

        for change in self.changes:
            if change["file_path"] == file_path and change["issues_encountered"]:
                issues.append({
                    "change_id": change["id"],
                    "timestamp": change["timestamp"],
                    "issues": change["issues_encountered"]
                })

        return issues

    def query_changes(
        self,
        file_path: Optional[str] = None,
        change_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query changes by various criteria.

        Args:
            file_path: Filter by file path
            change_type: Filter by change type
            status: Filter by status
            limit: Maximum number of results

        Returns:
            List of matching changes
        """
        results = []

        for change in reversed(self.changes):
            if file_path and file_path not in change["file_path"]:
                continue

            if change_type and change["change_type"] != change_type:
                continue

            if status and change["status"] != status:
                continue

            results.append(change)

            if len(results) >= limit:
                break

        return results

    def detect_change_conflicts(self, proposed_change: Dict) -> List[Dict]:
        """
        Detect potential conflicts with other recent or planned changes.

        Args:
            proposed_change: The proposed change to check for conflicts

        Returns:
            List of potential conflicts
        """
        conflicts = []
        file_path = proposed_change.get("file_path")
        affected_components = set(proposed_change.get("affected_components", []))

        # Check recent changes to the same file
        for change in reversed(self.changes[-20:]):  # Check last 20 changes
            if change["file_path"] == file_path and change["status"] in ["planned", "implemented"]:
                conflicts.append({
                    "type": "same_file",
                    "change_id": change["id"],
                    "description": f"Concurrent change to same file: {change['description']}",
                    "severity": "high"
                })

            # Check for overlapping affected components
            other_components = set(change.get("affected_components", []))
            overlap = affected_components & other_components

            if overlap and change["status"] in ["planned", "implemented"]:
                conflicts.append({
                    "type": "shared_components",
                    "change_id": change["id"],
                    "description": f"Changes affect shared components: {', '.join(overlap)}",
                    "severity": "medium"
                })

        return conflicts

    def get_change_statistics(self) -> Dict:
        """
        Get statistics about changes tracked.

        Returns:
            Statistics including change types, success rates, etc.
        """
        if not self.changes:
            return {"total_changes": 0}

        type_distribution = {}
        status_distribution = {}
        files_changed = set()
        changes_with_issues = 0

        for change in self.changes:
            # Type distribution
            change_type = change["change_type"]
            type_distribution[change_type] = type_distribution.get(change_type, 0) + 1

            # Status distribution
            status = change["status"]
            status_distribution[status] = status_distribution.get(status, 0) + 1

            # Files changed
            files_changed.add(change["file_path"])

            # Issues tracking
            if change["issues_encountered"]:
                changes_with_issues += 1

        return {
            "total_changes": len(self.changes),
            "type_distribution": type_distribution,
            "status_distribution": status_distribution,
            "unique_files_changed": len(files_changed),
            "changes_with_issues": changes_with_issues,
            "issue_rate": changes_with_issues / len(self.changes) if self.changes else 0,
            "most_recent": self.changes[-1]["timestamp"] if self.changes else None
        }

    def suggest_safe_changes(self, context: Dict) -> List[str]:
        """
        Suggest safe approaches for making changes based on historical data.

        Args:
            context: Context about the proposed change area

        Returns:
            List of safety recommendations
        """
        suggestions = [
            "Start with the smallest possible change that achieves the goal",
            "Implement changes incrementally with testing between steps",
            "Create feature flags to enable gradual rollout",
            "Ensure comprehensive test coverage before proceeding",
            "Document the change rationale and expected behavior",
            "Set up monitoring for key metrics affected by the change",
            "Prepare rollback procedures before implementing",
            "Review similar past changes for lessons learned"
        ]

        # Add context-specific suggestions
        file_path = context.get("file_path", "")

        if "test" in file_path.lower():
            suggestions.append("Consider adding both positive and negative test cases")

        if context.get("affects_api"):
            suggestions.extend([
                "Maintain API backward compatibility",
                "Version the API if breaking changes are necessary",
                "Update API documentation and client examples"
            ])

        if context.get("affects_database"):
            suggestions.extend([
                "Create reversible database migrations",
                "Test migration on a copy of production data",
                "Plan for data migration rollback"
            ])

        return suggestions
