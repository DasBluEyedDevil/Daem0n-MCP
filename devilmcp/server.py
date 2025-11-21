"""
DevilMCP Server
An extremely powerful MCP server for AI agents to maintain context,
track decisions, and understand cascading impacts.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional
from dotenv import load_dotenv

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: fastmcp not installed. Run: pip install -r requirements.txt", file=sys.stderr)
    exit(1)

from devilmcp.context_manager import ContextManager
from devilmcp.decision_tracker import DecisionTracker
from devilmcp.change_analyzer import ChangeAnalyzer
from devilmcp.cascade_detector import CascadeDetector
from devilmcp.thought_processor import ThoughtProcessor
from devilmcp.database import DatabaseManager
from devilmcp.process_manager import ProcessManager
from devilmcp.tool_registry import ToolRegistry
from devilmcp.task_manager import TaskManager
# Removed Orchestrator and TaskRouter imports

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

# Initialize core modules
db_manager = DatabaseManager(storage_path)
process_manager = ProcessManager(db_manager)
tool_registry = ToolRegistry(db_manager)
task_manager = TaskManager(db_manager)
context_mgr = ContextManager(db_manager)
decision_tracker = DecisionTracker(db_manager)
cascade_detector = CascadeDetector(db_manager, storage_path)
change_analyzer = ChangeAnalyzer(db_manager, cascade_detector)
thought_processor = ThoughtProcessor(db_manager)

logger.info("DevilMCP Server initialized")

# Context management tools
@mcp.tool()
async def analyze_project_structure(project_path: str) -> Dict:
    """
    Analyze entire project structure to build comprehensive context.
    """
    logger.info(f"Analyzing project structure: {project_path}")
    return await context_mgr.analyze_project_structure(project_path)

@mcp.tool()
async def track_file_dependencies(
    file_path: str,
    project_root: Optional[str] = None
) -> Dict:
    """
    Analyze file dependencies including imports and relationships.
    """
    logger.info(f"Tracking dependencies: {file_path}")
    return await context_mgr.track_file_dependencies(file_path, project_root)

@mcp.tool()
async def get_project_context(
    project_path: Optional[str] = None,
    include_dependencies: bool = True
) -> Dict:
    """
    Retrieve comprehensive project context.
    """
    logger.info(f"Getting project context: {project_path or 'all'}")
    return await context_mgr.get_project_context(project_path, include_dependencies)

@mcp.tool()
async def search_context(query: str, context_type: str = "all") -> List[Dict]:
    """
    Search context data for specific information.
    """
    logger.info(f"Searching context: {query}")
    return await context_mgr.search_context(query, context_type)

# Decision tracking tools
@mcp.tool()
async def log_decision(
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
    """
    logger.info(f"Logging decision: {decision}")
    return await decision_tracker.log_decision(
        decision, rationale, context, alternatives_considered,
        expected_impact, risk_level, tags
    )

@mcp.tool()
async def update_decision_outcome(
    decision_id: int,
    outcome: str,
    actual_impact: str,
    lessons_learned: Optional[str] = None
) -> Optional[Dict]:
    """
    Update a decision with its actual outcome.
    """
    logger.info(f"Updating decision outcome: {decision_id}")
    return await decision_tracker.update_decision_outcome(
        decision_id, outcome, actual_impact, lessons_learned
    )

@mcp.tool()
async def query_decisions(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    risk_level: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Query past decisions.
    """
    logger.info(f"Querying decisions: {query}")
    return await decision_tracker.query_decisions(query, tags, risk_level, limit)

@mcp.tool()
async def analyze_decision_impact(decision_id: int) -> Dict:
    """
    Analyze the impact of a specific decision.
    """
    logger.info(f"Analyzing decision impact: {decision_id}")
    return await decision_tracker.analyze_decision_impact(decision_id)

@mcp.tool()
async def get_decision_statistics() -> Dict:
    """
    Get statistics about decisions made.
    """
    return await decision_tracker.get_decision_statistics()

# Change analysis tools
@mcp.tool()
async def log_change(
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
    logger.info(f"Logging change: {file_path}")
    return await change_analyzer.log_change(
        file_path, change_type, description, rationale,
        affected_components, risk_assessment, rollback_plan
    )

@mcp.tool()
async def update_change_status(
    change_id: int,
    status: str,
    actual_impact: Optional[str] = None,
    issues: Optional[List[str]] = None
) -> Optional[Dict]:
    """
    Update the status of a logged change.
    """
    logger.info(f"Updating change status: {change_id}")
    return await change_analyzer.update_change_status(
        change_id, status, actual_impact, issues
    )

@mcp.tool()
async def analyze_change_impact(
    file_path: str,
    change_description: str,
    dependencies: Optional[Dict] = None
) -> Dict:
    """
    Analyze the potential impact of a proposed change.
    """
    logger.info(f"Analyzing change impact: {file_path}")
    return await change_analyzer.analyze_change_impact(
        file_path, change_description, dependencies
    )

@mcp.tool()
async def query_changes(
    file_path: Optional[str] = None,
    change_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Query change history.
    """
    logger.info(f"Querying changes: {file_path}")
    return await change_analyzer.query_changes(file_path, change_type, status, limit)

@mcp.tool()
async def scan_uncommitted_changes(repo_path: str) -> List[Dict]:
    """
    Scan the git repository for uncommitted (staged and unstaged) changes.
    """
    logger.info(f"Scanning uncommitted changes in: {repo_path}")
    return await change_analyzer.scan_uncommitted_changes(repo_path)

@mcp.tool()
async def detect_change_conflicts(proposed_change: Dict) -> List[Dict]:
    """
    Detect potential conflicts with other changes.
    """
    logger.info("Detecting change conflicts")
    return await change_analyzer.detect_change_conflicts(proposed_change)

# Cascade failure detection tools
@mcp.tool()
def build_dependency_graph(dependencies: Dict[str, Dict]) -> Dict:
    """
    Build a dependency graph from project dependencies.
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
    """
    logger.info(f"Detecting dependencies: {target}")
    return cascade_detector.detect_dependencies(target, depth, direction)

@mcp.tool()
def generate_dependency_diagram(target: str, depth: int = 3) -> str:
    """
    Generate a MermaidJS diagram of dependencies.
    """
    logger.info(f"Generating dependency diagram for: {target}")
    return cascade_detector.generate_dependency_diagram(target, depth)

@mcp.tool()
def analyze_cascade_risk(
    target: str,
    change_type: str,
    context: Optional[Dict] = None
) -> Dict:
    """
    Analyze the risk of cascading failures from a change.
    """
    logger.info(f"Analyzing cascade risk: {target}")
    return cascade_detector.analyze_cascade_risk(target, change_type, context)

@mcp.tool()
async def log_cascade_event(
    trigger: str,
    affected_components: List[str],
    severity: str,
    description: str,
    resolution: Optional[str] = None
) -> Dict:
    """
    Log a cascade failure event for learning.
    """
    logger.info(f"Logging cascade event: {trigger}")
    return await cascade_detector.log_cascade_event(
        trigger, affected_components, severity, description, resolution
    )

@mcp.tool()
async def query_cascade_history(
    trigger: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Query historical cascade events.
    """
    logger.info(f"Querying cascade history: {trigger}")
    return await cascade_detector.query_cascade_history(trigger, severity, limit)

@mcp.tool()
def suggest_safe_changes(target: str, proposed_change: str) -> Dict:
    """
    Suggest safe approaches for making a change.
    """
    logger.info(f"Suggesting safe changes: {target}")
    return cascade_detector.suggest_safe_changes(target, proposed_change)

# Thought process management tools
@mcp.tool()
async def start_thought_session(session_id: str, context: Dict) -> Dict:
    """
    Start a new thought processing session.
    """
    logger.info(f"Starting thought session: {session_id}")
    return await thought_processor.start_session(session_id, context)

@mcp.tool()
async def end_thought_session(
    session_id: str,
    summary: Optional[str] = None,
    outcomes: Optional[List[str]] = None
) -> Dict:
    """
    End a thought processing session.
    """
    logger.info(f"Ending thought session: {session_id}")
    return await thought_processor.end_session(session_id, summary, outcomes)

@mcp.tool()
async def log_thought_process(
    thought: str,
    category: str,
    reasoning: str,
    related_to: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    session_id: Optional[str] = None
) -> Dict:
    """
    Log a thought process with reasoning.
    """
    logger.info(f"Logging thought: {category}")
    return await thought_processor.log_thought_process(
        thought, category, reasoning, related_to, confidence, session_id
    )

@mcp.tool()
async def retrieve_thought_context(
    thought_id: Optional[int] = None,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Retrieve related thought context.
    """
    logger.info(f"Retrieving thought context: {thought_id}")
    return await thought_processor.retrieve_thought_context(
        thought_id, category, session_id, limit
    )

@mcp.tool()
async def analyze_reasoning_gaps(session_id: Optional[str] = None) -> Dict:
    """
    Analyze gaps in reasoning or considerations.
    """
    logger.info(f"Analyzing reasoning gaps: {session_id}")
    return await thought_processor.analyze_reasoning_gaps(session_id)

@mcp.tool()
async def record_insight(
    insight: str,
    source: str,
    applicability: str,
    session_id: Optional[str] = None
) -> Dict:
    """
    Record an insight gained during processing.
    """
    logger.info(f"Recording insight: {insight[:50]}...")
    return await thought_processor.record_insight(
        insight, source, applicability, session_id
    )

@mcp.tool()
async def get_session_summary(session_id: str) -> Dict:
    """
    Get comprehensive summary of a session.
    """
    logger.info(f"Getting session summary: {session_id}")
    return await thought_processor.get_session_summary(session_id)

# Task Management Tools
@mcp.tool()
async def create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    assigned_to: Optional[str] = None,
    tags: Optional[List[str]] = None,
    parent_id: Optional[int] = None
) -> Dict:
    """
    Create a new task.
    """
    logger.info(f"Creating task: {title}")
    return await task_manager.create_task(
        title, description, priority, assigned_to, tags, parent_id
    )

@mcp.tool()
async def update_task(
    task_id: int,
    status: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Dict:
    """
    Update a task.
    """
    logger.info(f"Updating task: {task_id}")
    updated = await task_manager.update_task(
        task_id, status, title, description, priority, assigned_to, tags
    )
    if updated:
        return updated
    return {"error": f"Task {task_id} not found"}

@mcp.tool()
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """
    List tasks with optional filters.
    """
    logger.info(f"Listing tasks (status={status})")
    return await task_manager.list_tasks(status, priority, assigned_to, limit)

@mcp.tool()
async def get_task(task_id: int) -> Dict:
    """
    Get details of a specific task.
    """
    logger.info(f"Getting task: {task_id}")
    task = await task_manager.get_task(task_id)
    if task:
        return task
    return {"error": f"Task {task_id} not found"}

# Utility tools
@mcp.tool()
async def get_mcp_statistics() -> Dict:
    """
    Get comprehensive statistics about MCP usage.
    """
    logger.info("Getting MCP statistics")
    decision_stats = await decision_tracker.get_decision_statistics()
    change_stats = await change_analyzer.get_change_statistics()
    cascade_stats = await cascade_detector.get_cascade_statistics()
    thought_stats = await thought_processor.get_thought_statistics()
    return {
        "decisions": decision_stats,
        "changes": change_stats,
        "cascades": cascade_stats,
        "thoughts": thought_stats,
        "server_info": {
            "name": "DevilMCP",
            "version": "1.0.0",
            "storage_path": storage_path
        }
    }

# === TOOL MANAGEMENT TOOLS (Robustness) ===

@mcp.tool()
async def start_tool_session(
    tool_name: str,
    context: Optional[Dict] = None
) -> Dict:
    """
    Start a CLI tool session.
    """
    logger.info(f"Starting tool session: {tool_name}")
    tool_config = tool_registry.get_tool(tool_name)
    if not tool_config:
        return {"error": f"Tool not found: {tool_name}"}

    proc_info = await process_manager.spawn_process(
        tool_name=tool_name,
        command=tool_config.command,
        args=tool_config.args
    )
    return {
        "tool_name": tool_name,
        "pid": proc_info.pid,
        "state": proc_info.state.value,
        "started_at": proc_info.started_at.isoformat(),
        "session_id": proc_info.session_id
    }

@mcp.tool()
def get_tool_status(tool_name: str) -> Dict:
    """
    Get status of a CLI tool process.
    """
    status = process_manager.get_process_status(tool_name)
    if status:
        return status
    else:
        return {"error": f"Tool '{tool_name}' not running."}

@mcp.tool()
async def terminate_tool_session(tool_name: str) -> Dict:
    """
    Terminate a CLI tool session.
    """
    logger.info(f"Terminating tool session: {tool_name}")
    await process_manager.terminate_process(tool_name)
    return {"status": "terminated", "tool_name": tool_name}

@mcp.tool()
async def register_custom_tool(
    name: str,
    display_name: str,
    command: str,
    capabilities: List[str],
    args: Optional[List[str]] = None,
    config: Optional[Dict] = None
) -> Dict:
    """
    Register a new custom CLI tool.
    """
    logger.info(f"Registering custom tool: {name}")
    success = await tool_registry.register_tool(
        name=name,
        display_name=display_name,
        command=command,
        capabilities=capabilities,
        args=args or [],
        config=config or {}
    )
    return {
        "status": "success" if success else "failed",
        "tool_name": name
    }

@mcp.tool()
async def update_tool_config(
    name: str,
    display_name: Optional[str] = None,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    capabilities: Optional[List[str]] = None,
    enabled: Optional[bool] = None,
    config: Optional[Dict] = None
) -> Dict:
    """
    Update an existing tool's configuration.
    """
    tool_config = await tool_registry.update_tool(
        name=name,
        display_name=display_name,
        command=command,
        args=args,
        capabilities=capabilities,
        enabled=enabled,
        config=config
    )
    if tool_config:
        return {"status": "success", "tool_name": name, "config": tool_config.config}
    else:
        return {"status": "failed", "tool_name": name, "error": "Tool not found or update failed."}

@mcp.tool()
async def disable_tool(tool_name: str) -> Dict:
    """Disable a tool."""
    success = await tool_registry.disable_tool(tool_name)
    return {"status": "success" if success else "failed", "tool_name": tool_name}

@mcp.tool()
async def enable_tool(tool_name: str) -> Dict:
    """Enable a tool."""
    success = await tool_registry.enable_tool(tool_name)
    return {"status": "success" if success else "failed", "tool_name": tool_name}

@mcp.tool()
async def list_available_tools() -> List[Dict]:
    """
    List all available CLI tools and their capabilities.
    """
    tools = tool_registry.get_all_tools()
    return [
        {
            "name": tool.name,
            "display_name": tool.display_name,
            "command": tool.command,
            "args": [arg for arg in tool.args],
            "capabilities": [c.value for c in tool.capabilities],
            "enabled": tool.enabled,
            "config_summary": {
                "prompt_patterns": tool.prompt_patterns,
                "init_timeout": tool.init_timeout,
                "command_timeout": tool.command_timeout
            }
        }
        for tool in tools
    ]

# Main entry point

async def init_tools():
    """Initialize tool registry."""
    await tool_registry.load_tools()
    logger.info("Tool registry initialized")

def main():
    """Main entry point for the DevilMCP server."""
    logger.info(f"Starting DevilMCP server on port {port}")
    logger.info(f"Storage path: {storage_path}")

    # Initialize database and tools
    try:
        asyncio.run(db_manager.init_db())
        asyncio.run(init_tools())
        logger.info("Database and Tools initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database or tools: {e}", exc_info=True)
        raise

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()