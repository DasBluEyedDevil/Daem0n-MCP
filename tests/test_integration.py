import pytest
import pytest_asyncio
import tempfile
import os
import asyncio
import toml
import base64
from pathlib import Path
from database import DatabaseManager
from decision_tracker import DecisionTracker
from thought_processor import ThoughtProcessor
from change_analyzer import ChangeAnalyzer
from cascade_detector import CascadeDetector
from process_manager import ProcessManager, ProcessState
from tool_registry import ToolRegistry, ToolCapability
# Removed TaskRouter, Orchestrator imports

# Fixture for DatabaseManager
@pytest_asyncio.fixture
async def db_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = DatabaseManager(tmpdir, db_name="test_db.db")
        await db.init_db()
        yield db
        await db.close()

# Fixture for storage path (some modules need it for other files, though mostly unused now)
@pytest.fixture
def storage_path(db_manager):
    return str(db_manager.storage_path)

# Fixture for a dummy tools.toml
@pytest.fixture(scope="session", autouse=True)
def create_dummy_tools_toml():
    """Create a dummy tools.toml for testing."""
    import sys
    
    # Simple one-liner script
    # Print prompt, flush, then sleep to keep process alive.
    # We don't need to read stdin for the mock to "accept" commands, buffering handles small writes.
    # This avoids potential stdin EOF issues on Windows subprocesses in test environment.
    simple_script = "import sys, time; sys.stdout.write('{prompt}\n'); sys.stdout.flush(); time.sleep(30)"
    
    # Use python from PATH as it worked in other tests
    python_exe = "python"

    data = {
        "tools": {
            "test-cli": {
                "display_name": "Test CLI",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Ready")],
                "capabilities": ["testing", "dev_ops"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Ready"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            },
            "test-cli-2": {
                "display_name": "Test CLI 2",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Ready2")],
                "capabilities": ["implementation"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Ready2"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            },
            "gemini-cli": {
                "display_name": "Gemini CLI",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Gemini ready")],
                "capabilities": ["architect", "ui_designer", "codebase_analysis"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Gemini ready"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            },
            "copilot-cli": {
                "display_name": "Copilot CLI",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Copilot ready")],
                "capabilities": ["backend_developer", "api_implementation"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Copilot ready"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            },
            "codex-cli": {
                "display_name": "Codex CLI",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Codex ready")],
                "capabilities": ["secondary_developer", "technical_task_performer"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Codex ready"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            },
            "claude-code": {
                "display_name": "Claude Code",
                "command": python_exe,
                "args": ["-c", simple_script.format(prompt="Claude ready")],
                "capabilities": ["orchestrator"],
                "enabled": True,
                "config": {
                    "prompt_patterns": ["Claude ready"],
                    "init_timeout": 500,
                    "command_timeout": 2000
                }
            }
        }
    }
    
    with open("tools.toml", "w") as f:
        toml.dump(data, f)
    
    yield
    
    if os.path.exists("tools.toml"):
        os.remove("tools.toml")

# Tests
@pytest.mark.asyncio
async def test_decision_tracker(db_manager):
    dt = DecisionTracker(db_manager)
    
    decision = await dt.log_decision(
        decision="Use Pytest",
        rationale="Standard testing framework",
        context={"project": "DevilMCP"}
    )
    assert decision["id"] is not None
    assert decision["decision"] == "Use Pytest"
    
    stats = await dt.get_decision_statistics()
    assert stats["total_decisions"] == 1

@pytest.mark.asyncio
async def test_change_analyzer_integration(db_manager, storage_path):
    # Init CascadeDetector first
    cd = CascadeDetector(db_manager, storage_path)
    ca = ChangeAnalyzer(db_manager, cd)
    
    # Log a change
    change = await ca.log_change(
        file_path="server.py",
        change_type="modify",
        description="Test change",
        rationale="Testing",
        affected_components=["core"]
    )
    assert change["id"] is not None
    
    # Analyze impact (should run without error even if graph is empty)
    impact = await ca.analyze_change_impact("server.py", "Test change")
    # Estimated blast radius might be "unknown" if no graph or limited context
    # We just ensure it doesn't crash
    assert "estimated_blast_radius" in impact

@pytest.mark.asyncio
async def test_thought_processor(db_manager):
    tp = ThoughtProcessor(db_manager)
    
    session = await tp.start_session("sess-1", {})
    assert session["status"] == "active"
    
    thought = await tp.log_thought_process("Thinking...", "analysis", "reasoning")
    assert thought["id"] is not None
    
    summary = await tp.get_session_summary("sess-1")
    assert summary["total_thoughts"] == 1

@pytest.mark.asyncio
async def test_cascade_detector(db_manager, storage_path):
    cd = CascadeDetector(db_manager, storage_path)
    
    event = await cd.log_cascade_event("trigger", [], "high", "desc")
    assert event["id"] is not None
    
    history = await cd.query_cascade_history()
    assert len(history) == 1

    # Test Mermaid Generation
    # Mock graph
    import networkx as nx
    cd.dep_graph = nx.DiGraph()
    cd.dep_graph.add_edge("A", "B")
    cd.dep_graph.add_edge("B", "C")
    
    diagram = cd.generate_dependency_diagram("B")
    assert "graph TD" in diagram
    assert '"A" --> "B"' in diagram
    assert '"B" --> "C"' in diagram

@pytest.mark.asyncio
async def test_git_features(db_manager, storage_path):
    # Test ContextManager Git awareness (safe even if no git)
    from context_manager import ContextManager
    cm = ContextManager(storage_path)
    structure = cm.analyze_project_structure(os.getcwd()) # Use current dir for test
    assert structure["total_files"] >= 0

    # Test ChangeAnalyzer Git scanning
    # Note: It's hard to mock git in integration tests without a real repo state, 
    # but we can ensure it runs without crashing.
    cd = CascadeDetector(db_manager, storage_path)
    ca = ChangeAnalyzer(db_manager, cd)
    changes = await ca.scan_uncommitted_changes(os.getcwd())
    # It returns list (empty or changes) or error dict
    assert isinstance(changes, list)

# --- Robustness Tests (Process/Tool) ---
@pytest.mark.asyncio
async def test_tool_registry(db_manager, create_dummy_tools_toml):
    tr = ToolRegistry(db_manager)
    await tr.load_tools()
    
    tool = tr.get_tool("test-cli")
    assert tool is not None
    assert tool.display_name == "Test CLI"
    assert ToolCapability.TESTING in tool.capabilities
    
    all_tools = tr.get_all_tools()
    assert len(all_tools) >= 6 # At least our test tools

    await tr.register_tool("new-cli", "New CLI", "newcmd", ["dev_ops"])
    new_tool = tr.get_tool("new-cli")
    assert new_tool is not None
    assert ToolCapability.DEV_OPS in new_tool.capabilities
    
    await tr.disable_tool("new-cli")
    disabled_tool = tr.get_tool("new-cli")
    assert disabled_tool is None # Disabled tools are removed from cache

@pytest.mark.asyncio
async def test_process_manager(db_manager): # Add db_manager fixture
    pm = ProcessManager(db_manager) # Pass db_manager
    
    # Register "echo-cli" in the database for ProcessManager to find it
    tr = ToolRegistry(db_manager) # Instantiate ToolRegistry
    # Ensure ToolRegistry's cache is loaded
    await tr.load_tools() 
    
    # Define command and register
    cmd_echo = "import sys; line = sys.stdin.readline(); sys.stdout.write(line); sys.stdout.flush();"
    import sys
    await tr.register_tool(
        name="echo-cli",
        display_name="Echo CLI Test Tool",
        command=sys.executable,
        capabilities=["testing"],
        args=["-c", cmd_echo],
        config={}
    )
    
    proc_info = await pm.spawn_process("echo-cli", sys.executable, ["-c", cmd_echo])
    
    
    assert proc_info.pid is not None
    assert proc_info.state == ProcessState.INITIALIZING

    # Give it a moment to start
    await asyncio.sleep(0.1)
    
    status = pm.get_process_status("echo-cli")
    # It should be running
    assert status is not None
    assert status["state"] != ProcessState.TERMINATED.value

    # Send command and read response
    # send_command writes "hello\n", mock reads it, echoes it back
    response = await pm.send_command("echo-cli", "hello")
    assert "hello" in response

    # Terminate process
    await pm.terminate_process("echo-cli")
    
    status = pm.get_process_status("echo-cli")
    assert status is None or status["state"] == ProcessState.TERMINATED.value