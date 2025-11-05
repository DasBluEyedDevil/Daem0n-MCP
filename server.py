"""
DevilMCP Server
An extremely powerful MCP server for AI agents to maintain context,
track decisions, and understand cascading impacts.
"""

import os
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install -r requirements.txt")
    exit(1)

from context_manager import ContextManager
from decision_tracker import DecisionTracker
from change_analyzer import ChangeAnalyzer
from cascade_detector import CascadeDetector
from thought_processor import ThoughtProcessor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Determine project-specific storage path
def get_storage_path():
    """
    Determine storage path with project isolation.

    Priority:
    1. STORAGE_PATH environment variable (explicit override)
    2. PROJECT_ROOT/.devilmcp/storage (if PROJECT_ROOT is set)
    3. <cwd>/.devilmcp/storage (current working directory)
    4. ./storage (fallback for centralized storage)
    """
    from pathlib import Path

    # Check for explicit storage path override
    if os.getenv('STORAGE_PATH'):
        return os.getenv('STORAGE_PATH')

    # Get project root
    project_root = os.getenv('PROJECT_ROOT', os.getcwd())
    project_path = Path(project_root).resolve()
    server_path = Path(__file__).parent.resolve()

    # If we're running from the DevilMCP server directory itself, use centralized storage
    if project_path == server_path:
        storage = server_path / "storage" / "centralized"
        logger.info("Using centralized storage (running from DevilMCP directory)")
    else:
        # Use project-specific storage
        storage = project_path / ".devilmcp" / "storage"
        logger.info(f"Project detected: {project_path.name}")
        logger.info(f"Using project-specific storage: {storage}")

    # Create directory if it doesn't exist
    storage.mkdir(parents=True, exist_ok=True)

    return str(storage)

# Initialize FastMCP server
port = int(os.getenv('PORT', 8080))
storage_path = get_storage_path()

mcp = FastMCP("DevilMCP")

# Initialize modules
context_mgr = ContextManager(storage_path)
decision_tracker = DecisionTracker(storage_path)
change_analyzer = ChangeAnalyzer(storage_path)
cascade_detector = CascadeDetector(storage_path)
thought_processor = ThoughtProcessor(storage_path)

logger.info("DevilMCP Server initialized")


# ============================================================================
# CONTEXT MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def analyze_project_structure(project_path: str) -> Dict:
    """
    Analyze entire project structure to build comprehensive context.

    Use this tool when starting work on a project to understand its
    architecture, file organization, and composition.

    Args:
        project_path: Absolute path to the project root directory

    Returns:
        Complete project structure analysis including files, languages, and organization
    """
    logger.info(f"Analyzing project structure: {project_path}")
    return context_mgr.analyze_project_structure(project_path)


@mcp.tool()
def track_file_dependencies(
    file_path: str,
    project_root: Optional[str] = None
) -> Dict:
    """
    Analyze file dependencies including imports and relationships.

    Use this tool to understand what a file depends on and what depends on it.

    Args:
        file_path: Path to the file to analyze
        project_root: Optional project root for relative path resolution

    Returns:
        Dependency information including imports and relationships
    """
    logger.info(f"Tracking dependencies: {file_path}")
    return context_mgr.track_file_dependencies(file_path, project_root)


@mcp.tool()
def get_project_context(
    project_path: Optional[str] = None,
    include_dependencies: bool = True
) -> Dict:
    """
    Retrieve comprehensive project context.

    Use this tool to get full context about a project including structure
    and dependencies. Essential for maintaining context during work.

    Args:
        project_path: Optional specific project path
        include_dependencies: Whether to include dependency information

    Returns:
        Complete project context
    """
    logger.info(f"Getting project context: {project_path or 'all'}")
    return context_mgr.get_project_context(project_path, include_dependencies)


@mcp.tool()
def search_context(query: str, context_type: str = "all") -> List[Dict]:
    """
    Search context data for specific information.

    Use this tool to find files, dependencies, or other context information.

    Args:
        query: Search query string
        context_type: Type to search ('files', 'dependencies', 'all')

    Returns:
        List of matching context entries
    """
    logger.info(f"Searching context: {query}")
    return context_mgr.search_context(query, context_type)


# ============================================================================
# DECISION TRACKING TOOLS
# ============================================================================

@mcp.tool()
def log_decision(
    decision: str,
    rationale: str,
    context: Dict,
    alternatives_considered: Optional[List[str]] = None,
    expected_impact: Optional[str] = None,
    risk_level: str = "medium",
    tags: Optional[List[str]] = None
) -> Dict:
    """
    Log a decision with full context and rationale.

    CRITICAL: Use this tool for EVERY significant decision you make.
    This builds decision history and helps avoid repeating mistakes.

    Args:
        decision: The decision made
        rationale: Why this decision was made
        context: Contextual information about the decision
        alternatives_considered: Alternative approaches considered
        expected_impact: Expected impact of the decision
        risk_level: Risk level (low, medium, high, critical)
        tags: Tags for categorization

    Returns:
        The logged decision record with ID
    """
    logger.info(f"Logging decision: {decision}")
    return decision_tracker.log_decision(
        decision, rationale, context, alternatives_considered,
        expected_impact, risk_level, tags
    )


@mcp.tool()
def update_decision_outcome(
    decision_id: int,
    outcome: str,
    actual_impact: str,
    lessons_learned: Optional[str] = None
) -> Optional[Dict]:
    """
    Update a decision with its actual outcome.

    Use this after implementing a decision to record what actually happened.
    This builds institutional knowledge.

    Args:
        decision_id: ID of the decision to update
        outcome: The actual outcome
        actual_impact: The actual impact observed
        lessons_learned: Lessons learned

    Returns:
        Updated decision record
    """
    logger.info(f"Updating decision outcome: {decision_id}")
    return decision_tracker.update_decision_outcome(
        decision_id, outcome, actual_impact, lessons_learned
    )


@mcp.tool()
def query_decisions(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    risk_level: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Query past decisions.

    Use this to learn from past decisions before making new ones.

    Args:
        query: Text to search for
        tags: Filter by tags
        risk_level: Filter by risk level
        limit: Maximum results

    Returns:
        List of matching decisions
    """
    logger.info(f"Querying decisions: {query}")
    return decision_tracker.query_decisions(query, tags, risk_level, limit)


@mcp.tool()
def analyze_decision_impact(decision_id: int) -> Dict:
    """
    Analyze the impact of a specific decision.

    Use this to understand how a decision played out and learn from it.

    Args:
        decision_id: Decision ID to analyze

    Returns:
        Impact analysis including expected vs actual
    """
    logger.info(f"Analyzing decision impact: {decision_id}")
    return decision_tracker.analyze_decision_impact(decision_id)


@mcp.tool()
def get_decision_statistics() -> Dict:
    """
    Get statistics about decisions made.

    Use this to understand decision patterns and quality.

    Returns:
        Statistics including risk distribution and tracking rate
    """
    return decision_tracker.get_decision_statistics()


# ============================================================================
# CHANGE ANALYSIS TOOLS
# ============================================================================

@mcp.tool()
def log_change(
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

    Use this BEFORE making changes to create a paper trail.

    Args:
        file_path: Path to file being changed
        change_type: Type (add, modify, delete, refactor)
        description: Description of the change
        rationale: Why this change is needed
        affected_components: List of affected components
        risk_assessment: Risk assessment
        rollback_plan: How to rollback if needed

    Returns:
        The logged change record
    """
    logger.info(f"Logging change: {file_path}")
    return change_analyzer.log_change(
        file_path, change_type, description, rationale,
        affected_components, risk_assessment, rollback_plan
    )


@mcp.tool()
def update_change_status(
    change_id: int,
    status: str,
    actual_impact: Optional[str] = None,
    issues: Optional[List[str]] = None
) -> Optional[Dict]:
    """
    Update the status of a logged change.

    Use this after implementing changes to track results.

    Args:
        change_id: Change ID to update
        status: New status (implemented, tested, rolled_back, failed)
        actual_impact: Actual impact observed
        issues: Issues encountered

    Returns:
        Updated change record
    """
    logger.info(f"Updating change status: {change_id}")
    return change_analyzer.update_change_status(
        change_id, status, actual_impact, issues
    )


@mcp.tool()
def analyze_change_impact(
    file_path: str,
    change_description: str,
    dependencies: Optional[Dict] = None
) -> Dict:
    """
    Analyze the potential impact of a proposed change.

    CRITICAL: Use this BEFORE making changes to understand the blast radius.

    Args:
        file_path: Path to file to be changed
        change_description: Description of proposed change
        dependencies: Dependency information (from track_file_dependencies)

    Returns:
        Impact analysis including affected areas and risk factors
    """
    logger.info(f"Analyzing change impact: {file_path}")
    return change_analyzer.analyze_change_impact(
        file_path, change_description, dependencies
    )


@mcp.tool()
def query_changes(
    file_path: Optional[str] = None,
    change_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Query change history.

    Use this to understand what changes have been made.

    Args:
        file_path: Filter by file path
        change_type: Filter by change type
        status: Filter by status
        limit: Maximum results

    Returns:
        List of matching changes
    """
    logger.info(f"Querying changes: {file_path}")
    return change_analyzer.query_changes(file_path, change_type, status, limit)


@mcp.tool()
def detect_change_conflicts(proposed_change: Dict) -> List[Dict]:
    """
    Detect potential conflicts with other changes.

    Use this before implementing changes to avoid conflicts.

    Args:
        proposed_change: The proposed change to check

    Returns:
        List of potential conflicts
    """
    logger.info("Detecting change conflicts")
    return change_analyzer.detect_change_conflicts(proposed_change)


# ============================================================================
# CASCADE FAILURE DETECTION TOOLS
# ============================================================================

@mcp.tool()
def build_dependency_graph(dependencies: Dict[str, Dict]) -> Dict:
    """
    Build a dependency graph from project dependencies.

    Use this to create a visual map of how components depend on each other.

    Args:
        dependencies: Dictionary mapping files to their dependencies

    Returns:
        Graph statistics and structure
    """
    logger.info("Building dependency graph")
    return cascade_detector.build_dependency_graph(dependencies)


@mcp.tool()
def detect_dependencies(
    target: str,
    depth: int = 5,
    direction: str = "both"
) -> Dict:
    """
    Detect all dependencies for a target.

    Use this to understand what depends on something and what it depends on.

    Args:
        target: Target file or module
        depth: How many levels deep to traverse
        direction: 'upstream' (depends on target), 'downstream' (target depends on), 'both'

    Returns:
        Dependencies at each level
    """
    logger.info(f"Detecting dependencies: {target}")
    return cascade_detector.detect_dependencies(target, depth, direction)


@mcp.tool()
def analyze_cascade_risk(
    target: str,
    change_type: str,
    context: Optional[Dict] = None
) -> Dict:
    """
    Analyze the risk of cascading failures from a change.

    CRITICAL: Use this before making changes to understand cascade potential.
    This is your early warning system for short-sighted decisions.

    Args:
        target: Target file or component being changed
        change_type: Type of change (breaking, non-breaking, refactor, etc.)
        context: Additional context

    Returns:
        Risk assessment including cascade probability and affected components
    """
    logger.info(f"Analyzing cascade risk: {target}")
    return cascade_detector.analyze_cascade_risk(target, change_type, context)


@mcp.tool()
def log_cascade_event(
    trigger: str,
    affected_components: List[str],
    severity: str,
    description: str,
    resolution: Optional[str] = None
) -> Dict:
    """
    Log a cascade failure event for learning.

    Use this when cascade failures occur to build institutional knowledge.

    Args:
        trigger: What triggered the cascade
        affected_components: List of affected components
        severity: Severity (low, medium, high, critical)
        description: What happened
        resolution: How it was resolved

    Returns:
        The logged cascade event
    """
    logger.info(f"Logging cascade event: {trigger}")
    return cascade_detector.log_cascade_event(
        trigger, affected_components, severity, description, resolution
    )


@mcp.tool()
def suggest_safe_changes(target: str, proposed_change: str) -> Dict:
    """
    Suggest safe approaches for making a change.

    Use this to get recommendations on how to safely implement changes.

    Args:
        target: Target component to change
        proposed_change: Description of proposed change

    Returns:
        Suggestions for safe implementation
    """
    logger.info(f"Suggesting safe changes: {target}")
    return cascade_detector.suggest_safe_changes(target, proposed_change)


# ============================================================================
# THOUGHT PROCESS MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def start_thought_session(session_id: str, context: Dict) -> Dict:
    """
    Start a new thought processing session.

    Use this at the beginning of a work session to track your reasoning.

    Args:
        session_id: Unique identifier for the session
        context: Initial context

    Returns:
        Session information
    """
    logger.info(f"Starting thought session: {session_id}")
    return thought_processor.start_session(session_id, context)


@mcp.tool()
def end_thought_session(
    session_id: str,
    summary: Optional[str] = None,
    outcomes: Optional[List[str]] = None
) -> Dict:
    """
    End a thought processing session.

    Use this at the end of a work session to summarize.

    Args:
        session_id: Session to end
        summary: Summary of the session
        outcomes: Outcomes achieved

    Returns:
        Final session state
    """
    logger.info(f"Ending thought session: {session_id}")
    return thought_processor.end_session(session_id, summary, outcomes)


@mcp.tool()
def log_thought_process(
    thought: str,
    category: str,
    reasoning: str,
    related_to: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    session_id: Optional[str] = None
) -> Dict:
    """
    Log a thought process with reasoning.

    Use this to record your thinking as you work. This helps maintain
    coherent reasoning and allows review of thought processes.

    Args:
        thought: The thought or consideration
        category: Category (analysis, hypothesis, concern, question, validation, etc.)
        reasoning: The reasoning behind this thought
        related_to: Related thought IDs or concepts
        confidence: Confidence level (0.0 to 1.0)
        session_id: Session this belongs to

    Returns:
        The logged thought record
    """
    logger.info(f"Logging thought: {category}")
    return thought_processor.log_thought_process(
        thought, category, reasoning, related_to, confidence, session_id
    )


@mcp.tool()
def retrieve_thought_context(
    thought_id: Optional[int] = None,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Retrieve related thought context.

    Use this to recall previous thinking and maintain continuity.

    Args:
        thought_id: Specific thought ID
        category: Filter by category
        session_id: Filter by session
        limit: Maximum results

    Returns:
        List of related thoughts
    """
    logger.info(f"Retrieving thought context: {thought_id}")
    return thought_processor.retrieve_thought_context(
        thought_id, category, session_id, limit
    )


@mcp.tool()
def analyze_reasoning_gaps(session_id: Optional[str] = None) -> Dict:
    """
    Analyze gaps in reasoning or considerations.

    IMPORTANT: Use this periodically to ensure you're not missing critical
    considerations. This helps catch blind spots.

    Args:
        session_id: Session to analyze (defaults to active)

    Returns:
        Analysis of reasoning gaps and suggestions
    """
    logger.info(f"Analyzing reasoning gaps: {session_id}")
    return thought_processor.analyze_reasoning_gaps(session_id)


@mcp.tool()
def record_insight(
    insight: str,
    source: str,
    applicability: str,
    session_id: Optional[str] = None
) -> Dict:
    """
    Record an insight gained during processing.

    Use this to capture learnings for future reference.

    Args:
        insight: The insight discovered
        source: Where this came from
        applicability: Where/how this can be applied
        session_id: Session this came from

    Returns:
        The recorded insight
    """
    logger.info(f"Recording insight: {insight[:50]}...")
    return thought_processor.record_insight(
        insight, source, applicability, session_id
    )


@mcp.tool()
def get_session_summary(session_id: str) -> Dict:
    """
    Get comprehensive summary of a session.

    Use this to review what happened in a session.

    Args:
        session_id: Session to summarize

    Returns:
        Session summary with statistics and key points
    """
    logger.info(f"Getting session summary: {session_id}")
    return thought_processor.get_session_summary(session_id)


# ============================================================================
# UTILITY TOOLS
# ============================================================================

@mcp.tool()
def get_mcp_statistics() -> Dict:
    """
    Get comprehensive statistics about MCP usage.

    Use this to understand how the MCP server is being used and
    the health of your decision/change tracking.

    Returns:
        Statistics from all modules
    """
    logger.info("Getting MCP statistics")

    return {
        "decisions": decision_tracker.get_decision_statistics(),
        "changes": change_analyzer.get_change_statistics(),
        "cascades": cascade_detector.get_cascade_statistics(),
        "thoughts": thought_processor.get_thought_statistics(),
        "server_info": {
            "name": "DevilMCP",
            "version": "1.0.0",
            "storage_path": storage_path
        }
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting DevilMCP server on port {port}")
    logger.info(f"Storage path: {storage_path}")

    print("""
    =================================================================
                             DevilMCP Server
    =================================================================
      An extremely powerful MCP server for AI agents that:
      * Maintains full project context
      * Tracks decisions and their outcomes
      * Analyzes change impacts and cascade risks
      * Manages thought processes and reasoning
      * Prevents short-sighted development decisions
    =================================================================
    """)

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
