"""
Test script for DevilMCP Server
Validates that all modules and tools work correctly.
"""

import os
import json
import tempfile
from pathlib import Path

from context_manager import ContextManager
from decision_tracker import DecisionTracker
from change_analyzer import ChangeAnalyzer
from cascade_detector import CascadeDetector
from thought_processor import ThoughtProcessor


def test_context_manager():
    """Test context manager functionality."""
    print("\n" + "=" * 70)
    print("Testing Context Manager")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = ContextManager(tmpdir)

        # Test project structure analysis
        print("\n[OK] Testing project structure analysis...")
        current_dir = Path(__file__).parent
        structure = ctx.analyze_project_structure(str(current_dir))

        assert "root" in structure
        assert "total_files" in structure
        assert structure["total_files"] > 0
        print(f"  Found {structure['total_files']} files")

        # Test dependency tracking
        print("\n✓ Testing dependency tracking...")
        test_file = Path(__file__)
        deps = ctx.track_file_dependencies(str(test_file))

        assert "file" in deps
        assert "imports" in deps
        print(f"  Tracked {len(deps.get('imports', []))} imports")

        # Test context retrieval
        print("\n✓ Testing context retrieval...")
        context = ctx.get_project_context(str(current_dir))

        assert "project" in context
        assert "last_updated" in context
        print("  Context retrieved successfully")

        # Test context search
        print("\n✓ Testing context search...")
        results = ctx.search_context("test", context_type="all")
        print(f"  Found {len(results)} matches for 'test'")

    print("\n✅ Context Manager: ALL TESTS PASSED")


def test_decision_tracker():
    """Test decision tracker functionality."""
    print("\n" + "=" * 70)
    print("Testing Decision Tracker")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        dt = DecisionTracker(tmpdir)

        # Test decision logging
        print("\n✓ Testing decision logging...")
        decision = dt.log_decision(
            decision="Use JWT for authentication",
            rationale="Stateless and scalable",
            context={"project": "test"},
            alternatives_considered=["Sessions", "OAuth2"],
            expected_impact="Improved scalability",
            risk_level="medium",
            tags=["auth", "security"]
        )

        assert decision["id"] == 1
        assert decision["decision"] == "Use JWT for authentication"
        print(f"  Logged decision #{decision['id']}")

        # Test decision query
        print("\n✓ Testing decision query...")
        results = dt.query_decisions(query="JWT", limit=10)

        assert len(results) > 0
        assert results[0]["id"] == 1
        print(f"  Found {len(results)} decisions")

        # Test decision update
        print("\n✓ Testing decision outcome update...")
        updated = dt.update_decision_outcome(
            decision_id=1,
            outcome="Successfully implemented",
            actual_impact="Better than expected",
            lessons_learned="JWT works great"
        )

        assert updated["outcome"] == "Successfully implemented"
        print("  Decision outcome updated")

        # Test decision analysis
        print("\n✓ Testing decision impact analysis...")
        analysis = dt.analyze_decision_impact(1)

        assert "decision_id" in analysis
        assert analysis["decision_id"] == 1
        print("  Decision impact analyzed")

        # Test statistics
        print("\n✓ Testing decision statistics...")
        stats = dt.get_decision_statistics()

        assert stats["total_decisions"] == 1
        assert stats["outcome_tracking_rate"] == 1.0
        print(f"  Statistics: {stats['total_decisions']} decisions tracked")

    print("\n✅ Decision Tracker: ALL TESTS PASSED")


def test_change_analyzer():
    """Test change analyzer functionality."""
    print("\n" + "=" * 70)
    print("Testing Change Analyzer")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        ca = ChangeAnalyzer(tmpdir)

        # Test change logging
        print("\n✓ Testing change logging...")
        change = ca.log_change(
            file_path="/test/file.py",
            change_type="modify",
            description="Update authentication logic",
            rationale="Security improvement",
            affected_components=["auth", "api"],
            rollback_plan="Revert commit"
        )

        assert change["id"] == 1
        assert change["change_type"] == "modify"
        print(f"  Logged change #{change['id']}")

        # Test change impact analysis
        print("\n✓ Testing change impact analysis...")
        impact = ca.analyze_change_impact(
            file_path="/test/config.py",
            change_description="Update configuration"
        )

        assert "file" in impact
        assert "risk_factors" in impact
        print(f"  Risk factors identified: {len(impact['risk_factors'])}")

        # Test change query
        print("\n✓ Testing change query...")
        results = ca.query_changes(change_type="modify", limit=10)

        assert len(results) > 0
        print(f"  Found {len(results)} changes")

        # Test status update
        print("\n✓ Testing change status update...")
        updated = ca.update_change_status(
            change_id=1,
            status="implemented",
            actual_impact="Positive impact"
        )

        assert updated["status"] == "implemented"
        print("  Change status updated")

        # Test conflict detection
        print("\n✓ Testing conflict detection...")
        conflicts = ca.detect_change_conflicts({
            "file_path": "/test/file.py",
            "affected_components": ["auth"]
        })

        print(f"  Detected {len(conflicts)} potential conflicts")

        # Test statistics
        print("\n✓ Testing change statistics...")
        stats = ca.get_change_statistics()

        assert stats["total_changes"] == 1
        print(f"  Statistics: {stats['total_changes']} changes tracked")

    print("\n✅ Change Analyzer: ALL TESTS PASSED")


def test_cascade_detector():
    """Test cascade detector functionality."""
    print("\n" + "=" * 70)
    print("Testing Cascade Detector")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        cd = CascadeDetector(tmpdir)

        # Test cascade risk analysis
        print("\n✓ Testing cascade risk analysis...")
        risk = cd.analyze_cascade_risk(
            target="/test/file.py",
            change_type="breaking"
        )

        assert "cascade_probability" in risk
        assert "risk_level" in risk
        print(f"  Risk level: {risk['risk_level']}")

        # Test cascade event logging
        print("\n✓ Testing cascade event logging...")
        event = cd.log_cascade_event(
            trigger="/test/file.py",
            affected_components=["component1", "component2"],
            severity="medium",
            description="Test cascade",
            resolution="Fixed by rollback"
        )

        assert event["id"] == 1
        print(f"  Logged cascade event #{event['id']}")

        # Test cascade history
        print("\n✓ Testing cascade history query...")
        history = cd.query_cascade_history(severity="medium", limit=10)

        assert len(history) > 0
        print(f"  Found {len(history)} cascade events")

        # Test safe change suggestions
        print("\n✓ Testing safe change suggestions...")
        suggestions = cd.suggest_safe_changes(
            target="/test/file.py",
            proposed_change="Refactor function"
        )

        assert "approach" in suggestions
        assert "testing_strategy" in suggestions
        print(f"  Generated {len(suggestions['approach'])} approach suggestions")

        # Test statistics
        print("\n✓ Testing cascade statistics...")
        stats = cd.get_cascade_statistics()

        assert stats["total_events"] == 1
        print(f"  Statistics: {stats['total_events']} events logged")

    print("\n✅ Cascade Detector: ALL TESTS PASSED")


def test_thought_processor():
    """Test thought processor functionality."""
    print("\n" + "=" * 70)
    print("Testing Thought Processor")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tp = ThoughtProcessor(tmpdir)

        # Test session start
        print("\n✓ Testing session start...")
        session = tp.start_session(
            session_id="test-session-1",
            context={"task": "Test task"}
        )

        assert session["id"] == "test-session-1"
        assert session["status"] == "active"
        print(f"  Started session: {session['id']}")

        # Test thought logging
        print("\n✓ Testing thought logging...")
        thought = tp.log_thought_process(
            thought="This is a test thought",
            category="analysis",
            reasoning="Testing the system",
            confidence=0.8,
            session_id="test-session-1"
        )

        assert thought["id"] == 1
        assert thought["category"] == "analysis"
        print(f"  Logged thought #{thought['id']}")

        # Test thought retrieval
        print("\n✓ Testing thought retrieval...")
        thoughts = tp.retrieve_thought_context(
            category="analysis",
            session_id="test-session-1"
        )

        assert len(thoughts) > 0
        print(f"  Retrieved {len(thoughts)} thoughts")

        # Test reasoning gaps
        print("\n✓ Testing reasoning gap analysis...")
        gaps = tp.analyze_reasoning_gaps(session_id="test-session-1")

        assert "gaps" in gaps
        assert "suggestions" in gaps
        print(f"  Identified {len(gaps['gaps'])} gaps")

        # Test insight recording
        print("\n✓ Testing insight recording...")
        insight = tp.record_insight(
            insight="Test insight",
            source="Test",
            applicability="Testing",
            session_id="test-session-1"
        )

        assert insight["id"] == 1
        print(f"  Recorded insight #{insight['id']}")

        # Test session end
        print("\n✓ Testing session end...")
        ended = tp.end_session(
            session_id="test-session-1",
            summary="Test completed",
            outcomes=["All tests passed"]
        )

        assert ended["status"] == "completed"
        print(f"  Ended session: {ended['id']}")

        # Test session summary
        print("\n✓ Testing session summary...")
        summary = tp.get_session_summary("test-session-1")

        assert summary["session_id"] == "test-session-1"
        assert summary["total_thoughts"] == 1
        print(f"  Summary: {summary['total_thoughts']} thoughts in session")

        # Test statistics
        print("\n✓ Testing thought statistics...")
        stats = tp.get_thought_statistics()

        assert stats["total_thoughts"] == 1
        assert stats["total_sessions"] == 1
        print(f"  Statistics: {stats['total_thoughts']} thoughts, "
              f"{stats['total_sessions']} sessions")

    print("\n✅ Thought Processor: ALL TESTS PASSED")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("DevilMCP Server Test Suite")
    print("=" * 70)
    print("\nRunning comprehensive tests on all modules...\n")

    try:
        test_context_manager()
        test_decision_tracker()
        test_change_analyzer()
        test_cascade_detector()
        test_thought_processor()

        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("=" * 70)
        print("""
DevilMCP Server is fully functional and ready to use!

All modules tested:
  ✓ Context Manager
  ✓ Decision Tracker
  ✓ Change Analyzer
  ✓ Cascade Detector
  ✓ Thought Processor

You can now start the server with: python server.py
        """)

        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
