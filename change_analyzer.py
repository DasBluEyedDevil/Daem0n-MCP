"""
Change Analyzer Module
Analyzes code changes and their potential cascading impacts across the project.
"""

import hashlib
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, desc, func, or_

from database import DatabaseManager
from models import Change

# Try importing gitpython
try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChangeAnalyzer:
    """Analyzes and tracks code changes with impact assessment."""

    def __init__(self, db_manager: DatabaseManager, cascade_detector=None):
        self.db = db_manager
        self.cascade_detector = cascade_detector

    async def scan_uncommitted_changes(self, repo_path: str) -> List[Dict]:
        """
        Scan the repository for uncommitted changes (staged and unstaged).
        """
        if not GIT_AVAILABLE:
            return [{"error": "GitPython not installed"}]

        changes = []
        try:
            repo = git.Repo(repo_path, search_parent_directories=True)
            
            # Helper to process diffs
            def process_diff(diff_list, status_label):
                for diff in diff_list:
                    path = diff.b_path if diff.b_path else diff.a_path
                    change_type = "modify"
                    if diff.new_file: change_type = "add"
                    elif diff.deleted_file: change_type = "delete"
                    elif diff.renamed_file: change_type = "rename"
                    
                    changes.append({
                        "file_path": path,
                        "change_type": change_type,
                        "status": status_label,
                        "diff_size": diff.diff.len if diff.diff else 0
                    })

            # Staged changes
            process_diff(repo.index.diff("HEAD"), "staged")
            
            # Unstaged changes
            process_diff(repo.index.diff(None), "unstaged")
            
            # Untracked files
            for untracked in repo.untracked_files:
                changes.append({
                    "file_path": untracked,
                    "change_type": "add",
                    "status": "untracked",
                    "diff_size": 0
                })

        except Exception as e:
            logger.error(f"Error scanning git changes: {e}")
            return [{"error": str(e)}]

        return changes

    async def log_change(
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
        """
        # Generate a hash of the change for tracking
        change_hash = hashlib.md5(
            f"{file_path}{change_type}{description}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:8]

        async with self.db.get_session() as session:
            new_change = Change(
                hash=change_hash,
                file_path=file_path,
                change_type=change_type,
                description=description,
                rationale=rationale,
                affected_components=affected_components,
                risk_assessment=risk_assessment or {
                    "level": "unknown",
                    "factors": []
                },
                rollback_plan=rollback_plan,
                timestamp=datetime.now(timezone.utc),
                status="planned",
                actual_impact=None,
                issues_encountered=[]
            )
            session.add(new_change)
            await session.commit()
            await session.refresh(new_change)

            logger.info(f"Change logged: {new_change.id} - {file_path}")
            return self._to_dict(new_change)

    async def update_change_status(
        self,
        change_id: int,
        status: str,
        actual_impact: Optional[str] = None,
        issues: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Update the status of a logged change.
        """
        async with self.db.get_session() as session:
            stmt = select(Change).where(Change.id == change_id)
            result = await session.execute(stmt)
            change = result.scalar_one_or_none()

            if change:
                change.status = status
                if actual_impact:
                    change.actual_impact = actual_impact
                if issues:
                    # Ensure issues_encountered is a list before extending
                    current_issues = change.issues_encountered or []
                    change.issues_encountered = current_issues + issues
                
                change.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(change)
                logger.info(f"Change {change_id} status updated to {status}")
                return self._to_dict(change)

        logger.warning(f"Change {change_id} not found")
        return None

    async def analyze_change_impact(
        self,
        file_path: str,
        change_description: str,
        dependencies: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze the potential impact of a proposed change.
        """
        impact = {
            "file": file_path,
            "change": change_description,
            "direct_impact": [],
            "indirect_impact": [],
            "risk_factors": [],
            "recommendations": [],
            "estimated_blast_radius": "unknown",
            "cascade_risk": None
        }

        # 1. Cascade Detector Integration (Graph Analysis)
        if self.cascade_detector:
            # Get upstream dependencies (who depends on me?)
            # Note: detect_dependencies is synchronous in CascadeDetector
            graph_deps = self.cascade_detector.detect_dependencies(file_path, depth=5, direction="upstream")
            
            upstream_levels = graph_deps.get("upstream", [])
            total_affected = sum(len(level["dependencies"]) for level in upstream_levels)
            
            if total_affected > 0:
                impact["risk_factors"].append(f"Graph Analysis: Change affects {total_affected} upstream components")
                for level in upstream_levels:
                    for dep in level["dependencies"]:
                        if dep not in impact["indirect_impact"]:
                            impact["indirect_impact"].append(dep)

            # Get Cascade Risk Assessment
            # Note: analyze_cascade_risk is synchronous in CascadeDetector
            risk_analysis = self.cascade_detector.analyze_cascade_risk(file_path, "modify")
            impact["cascade_risk"] = risk_analysis.get("risk_level")
            impact["estimated_blast_radius"] = risk_analysis.get("cascade_probability", "unknown")
            
            if risk_analysis.get("recommendations"):
                impact["recommendations"].extend(risk_analysis["recommendations"])

        # 2. Direct Dependency Analysis (Fallback/Complementary)
        # Analyze file extension and type
        file_ext = Path(file_path).suffix

        if dependencies:
            internal_deps = dependencies.get("internal_deps", [])
            if internal_deps:
                impact["direct_impact"].extend(internal_deps)
                if not self.cascade_detector: # Avoid duplicate reporting if graph covered it
                    impact["risk_factors"].append(
                        f"Change affects {len(internal_deps)} internal dependencies"
                    )

        # Assess based on file type and common patterns
        if file_ext in ['.py', '.js', '.ts']:
            if 'config' in file_path.lower():
                impact["risk_factors"].append("Configuration file - changes may affect entire application")
                if impact["estimated_blast_radius"] == "unknown":
                    impact["estimated_blast_radius"] = "high"
                impact["recommendations"].append("Test all configuration-dependent features")

            elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                impact["risk_factors"].append("Utility file - changes may affect multiple features")
                if impact["estimated_blast_radius"] == "unknown":
                    impact["estimated_blast_radius"] = "medium-high"
                impact["recommendations"].append("Identify and test all callers of modified utilities")

            elif 'model' in file_path.lower() or 'schema' in file_path.lower():
                impact["risk_factors"].append("Data model change - may require migrations")
                if impact["estimated_blast_radius"] == "unknown":
                    impact["estimated_blast_radius"] = "high"
                impact["recommendations"].extend([
                    "Check for database migration requirements",
                    "Verify backward compatibility",
                    "Test data validation logic"
                ])

            elif 'api' in file_path.lower() or 'endpoint' in file_path.lower():
                impact["risk_factors"].append("API change - may affect external consumers")
                if impact["estimated_blast_radius"] == "unknown":
                    impact["estimated_blast_radius"] = "high"
                impact["recommendations"].extend([
                    "Check API versioning",
                    "Verify backward compatibility",
                    "Update API documentation"
                ])

        # Check historical change patterns
        historical_issues = await self._check_historical_issues(file_path)
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
        
        # Deduplicate recommendations
        impact["recommendations"] = list(set(impact["recommendations"]))

        return impact

    async def _check_historical_issues(self, file_path: str) -> List[Dict]:
        """Check for historical issues with this file."""
        async with self.db.get_session() as session:
            # Find changes to this file that had issues
            stmt = select(Change).where(
                Change.file_path == file_path,
            )
            result = await session.execute(stmt)
            changes = result.scalars().all()
            
            issues = []
            for change in changes:
                if change.issues_encountered:
                     issues.append({
                        "change_id": change.id,
                        "timestamp": change.timestamp.isoformat(),
                        "issues": change.issues_encountered
                    })
            return issues

    async def query_changes(
        self,
        file_path: Optional[str] = None,
        change_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query changes by various criteria.
        """
        async with self.db.get_session() as session:
            stmt = select(Change).order_by(desc(Change.timestamp))

            if file_path:
                stmt = stmt.where(Change.file_path.contains(file_path))
            
            if change_type:
                stmt = stmt.where(Change.change_type == change_type)
                
            if status:
                stmt = stmt.where(Change.status == status)

            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            
            return [self._to_dict(c) for c in result.scalars()]

    async def detect_change_conflicts(self, proposed_change: Dict) -> List[Dict]:
        """
        Detect potential conflicts with other recent or planned changes.
        """
        conflicts = []
        file_path = proposed_change.get("file_path")
        affected_components = set(proposed_change.get("affected_components", []))

        async with self.db.get_session() as session:
            # Get recent planned/implemented changes (last 20)
            stmt = select(Change).order_by(desc(Change.timestamp)).limit(20)
            result = await session.execute(stmt)
            recent_changes = result.scalars().all()

            for change in recent_changes:
                # Check same file
                if change.file_path == file_path and change.status in ["planned", "implemented"]:
                    conflicts.append({
                        "type": "same_file",
                        "change_id": change.id,
                        "description": f"Concurrent change to same file: {change.description}",
                        "severity": "high"
                    })

                # Check overlapping components
                other_components = set(change.affected_components or [])
                overlap = affected_components & other_components

                if overlap and change.status in ["planned", "implemented"]:
                    conflicts.append({
                        "type": "shared_components",
                        "change_id": change.id,
                        "description": f"Changes affect shared components: {', '.join(overlap)}",
                        "severity": "medium"
                    })

        return conflicts

    async def get_change_statistics(self) -> Dict:
        """
        Get statistics about changes tracked.
        """
        async with self.db.get_session() as session:
            total_changes = await session.scalar(select(func.count(Change.id)))
            
            if total_changes == 0:
                return {"total_changes": 0}
            
            # Type distribution
            stmt_type = select(Change.change_type, func.count(Change.id)).group_by(Change.change_type)
            res_type = await session.execute(stmt_type)
            type_dist = {row[0]: row[1] for row in res_type.all()}
            
            # Status distribution
            stmt_status = select(Change.status, func.count(Change.id)).group_by(Change.status)
            res_status = await session.execute(stmt_status)
            status_dist = {row[0]: row[1] for row in res_status.all()}
            
            # Changes with issues (needs manual check or complex SQL for JSON array length)
            # We will fetch all changes that have issues_encountered not null/empty
            # Since SQLite JSON filtering is limited in standard SQL, we fetch simple count if possible
            # Or just iterate all if dataset is small. Let's do iterate for now or simple check.
            # Actually, we can check if issues_encountered != '[]' roughly.
            
            changes_with_issues = 0
            # A robust way is to fetch all and count in python for stats tool, assuming not millions of records
            all_changes_stmt = select(Change.issues_encountered)
            all_changes_res = await session.execute(all_changes_stmt)
            for issues in all_changes_res.scalars():
                if issues:
                    changes_with_issues += 1

            last_change = await session.scalar(select(Change.timestamp).order_by(desc(Change.timestamp)).limit(1))

            return {
                "total_changes": total_changes,
                "type_distribution": type_dist,
                "status_distribution": status_dist,
                "changes_with_issues": changes_with_issues,
                "issue_rate": changes_with_issues / total_changes,
                "most_recent": last_change.isoformat() if last_change else None
            }

    def suggest_safe_changes(self, context: Dict) -> List[str]:
        """
        Suggest safe approaches for making changes based on historical data.
        (Pure logic, no async needed, but good to keep signature consistent if we expanded it later)
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

    def _to_dict(self, c: Change) -> Dict:
        return {
            "id": c.id,
            "hash": c.hash,
            "file_path": c.file_path,
            "change_type": c.change_type,
            "description": c.description,
            "rationale": c.rationale,
            "affected_components": c.affected_components,
            "risk_assessment": c.risk_assessment,
            "rollback_plan": c.rollback_plan,
            "timestamp": c.timestamp.isoformat() if c.timestamp else None,
            "status": c.status,
            "actual_impact": c.actual_impact,
            "issues_encountered": c.issues_encountered,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
