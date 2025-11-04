# DevilMCP - Extremely Powerful Context Management for AI Agents

DevilMCP is an advanced Model Context Protocol (MCP) server designed to provide AI agents with comprehensive project context, decision tracking, change impact analysis, and cascade failure detection capabilities. It helps AI agents avoid short-sighted development decisions by maintaining full context awareness and understanding the ripple effects of changes.

## Features

### 🧠 Context Management
- **Project Structure Analysis**: Deep analysis of project architecture, file organization, and composition
- **Dependency Tracking**: Comprehensive tracking of file dependencies and relationships
- **Context Search**: Fast search across project context and dependencies
- **Full Context Retrieval**: Complete project context for maintaining awareness

### 📋 Decision Tracking
- **Decision Logging**: Record every decision with full rationale and context
- **Outcome Tracking**: Update decisions with actual outcomes and impacts
- **Decision Analysis**: Analyze decision impacts and compare expected vs actual results
- **Decision History**: Query past decisions to learn from history

### 🔄 Change Impact Analysis
- **Change Logging**: Track all code changes with comprehensive context
- **Impact Assessment**: Predict the blast radius of proposed changes
- **Conflict Detection**: Identify potential conflicts with other changes
- **Historical Analysis**: Learn from past changes and their outcomes
- **Safety Recommendations**: Get suggestions for safe change implementation

### ⚠️ Cascade Failure Detection
- **Dependency Graphs**: Build visual maps of component dependencies
- **Cascade Risk Analysis**: Evaluate the risk of cascading failures
- **Critical Path Detection**: Identify critical dependency chains
- **Safe Change Suggestions**: Get recommendations for minimizing cascade risk
- **Cascade Event Logging**: Learn from past cascade failures

### 💭 Thought Process Management
- **Thought Sessions**: Track reasoning processes throughout work sessions
- **Reasoning Chains**: Build and maintain coherent chains of thought
- **Gap Analysis**: Identify blind spots and missing considerations
- **Insight Recording**: Capture learnings for future reference
- **Session Summaries**: Review and learn from past thinking

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone or download this repository**

```bash
cd /path/to/DevilMCP
```

2. **Create a virtual environment (recommended)**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment (optional)**

```bash
cp .env.example .env
# Edit .env to customize settings
```

Environment variables:
- `PORT`: Server port (default: 8080)
- `LOG_LEVEL`: Logging level (default: INFO)
- `STORAGE_PATH`: Path for data storage (default: ./storage)
- `MAX_CONTEXT_DEPTH`: Maximum depth for context traversal (default: 10)

5. **Run the server**

```bash
python server.py
```

The server will start and listen on the configured port (default: 8080) using Server-Sent Events (SSE) transport.

## Usage

### Connecting AI Agents

Configure your AI agent to connect to the MCP server:

```json
{
  "mcpServers": {
    "devilmcp": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Available Tools

DevilMCP provides 30+ tools organized into categories:

#### Context Management Tools

1. **analyze_project_structure** - Analyze entire project architecture
2. **track_file_dependencies** - Track file imports and relationships
3. **get_project_context** - Retrieve comprehensive project context
4. **search_context** - Search for specific context information

#### Decision Tracking Tools

5. **log_decision** - Record a decision with full context
6. **update_decision_outcome** - Update with actual outcomes
7. **query_decisions** - Search past decisions
8. **analyze_decision_impact** - Analyze decision consequences
9. **get_decision_statistics** - Get decision-making statistics

#### Change Analysis Tools

10. **log_change** - Record a code change before making it
11. **update_change_status** - Update change status after implementation
12. **analyze_change_impact** - Predict change blast radius
13. **query_changes** - Search change history
14. **detect_change_conflicts** - Find conflicts with other changes

#### Cascade Detection Tools

15. **build_dependency_graph** - Create dependency graph
16. **detect_dependencies** - Find upstream/downstream dependencies
17. **analyze_cascade_risk** - Evaluate cascade failure risk
18. **log_cascade_event** - Record cascade failures
19. **suggest_safe_changes** - Get safe implementation suggestions

#### Thought Process Tools

20. **start_thought_session** - Begin a reasoning session
21. **end_thought_session** - Complete a reasoning session
22. **log_thought_process** - Record individual thoughts
23. **retrieve_thought_context** - Recall previous thinking
24. **analyze_reasoning_gaps** - Identify blind spots
25. **record_insight** - Capture learnings
26. **get_session_summary** - Review session results

#### Utility Tools

27. **get_mcp_statistics** - Get comprehensive usage statistics

## Example Workflows

### Starting a New Task

```python
# 1. Start a thought session
start_thought_session(
    session_id="feature-auth-2024-01",
    context={"task": "Implement user authentication", "project": "MyApp"}
)

# 2. Analyze project structure
project_context = analyze_project_structure("/path/to/project")

# 3. Log your thinking
log_thought_process(
    thought="Need to implement JWT-based authentication",
    category="analysis",
    reasoning="Current system has no auth; JWT is stateless and scalable",
    confidence=0.8
)

# 4. Check for reasoning gaps
gaps = analyze_reasoning_gaps()
# Review suggestions and address gaps
```

### Making a Code Change

```python
# 1. Analyze file dependencies
deps = track_file_dependencies("/path/to/file.py", "/path/to/project")

# 2. Analyze change impact
impact = analyze_change_impact(
    file_path="/path/to/file.py",
    change_description="Refactor authentication logic",
    dependencies=deps
)

# 3. Analyze cascade risk
risk = analyze_cascade_risk(
    target="/path/to/file.py",
    change_type="refactor",
    context={"affects": "authentication"}
)

# 4. Get safe change suggestions
suggestions = suggest_safe_changes(
    target="/path/to/file.py",
    proposed_change="Refactor to use JWT tokens"
)

# 5. Log the decision
decision = log_decision(
    decision="Refactor auth to use JWT tokens",
    rationale="Improves scalability and security",
    context={"risk": risk, "impact": impact},
    alternatives_considered=["Session-based auth", "OAuth2"],
    expected_impact="Improved performance, easier horizontal scaling",
    risk_level="medium",
    tags=["authentication", "refactor"]
)

# 6. Log the change
change = log_change(
    file_path="/path/to/file.py",
    change_type="refactor",
    description="Refactor to JWT-based authentication",
    rationale="Improve scalability and security",
    affected_components=["auth", "api", "middleware"],
    risk_assessment=risk,
    rollback_plan="Keep old auth code as fallback for 2 weeks"
)

# 7. After implementation, update status
update_change_status(
    change_id=change["id"],
    status="implemented",
    actual_impact="Performance improved by 15%, no issues detected"
)

update_decision_outcome(
    decision_id=decision["id"],
    outcome="Successfully implemented",
    actual_impact="Better than expected - 15% perf improvement",
    lessons_learned="JWT implementation was smoother with proper testing"
)
```

### Learning from History

```python
# Query similar past decisions
past_decisions = query_decisions(
    query="authentication",
    tags=["refactor"],
    limit=5
)

# Review cascade failures
cascade_history = query_cascade_history(
    severity="high",
    limit=10
)

# Get comprehensive statistics
stats = get_mcp_statistics()
print(f"Decision tracking rate: {stats['decisions']['outcome_tracking_rate']}")
print(f"Changes with issues: {stats['changes']['issue_rate']}")
```

## Best Practices for AI Agents

### 1. Always Start with Context
Before making any changes, use `analyze_project_structure` and `get_project_context` to understand the full picture.

### 2. Log All Decisions
Use `log_decision` for EVERY significant decision. This builds institutional knowledge and helps avoid repeating mistakes.

### 3. Analyze Before Changing
Always use `analyze_change_impact` and `analyze_cascade_risk` BEFORE making changes. This is your early warning system for short-sighted decisions.

### 4. Track Your Thinking
Use thought process tools throughout your work. `analyze_reasoning_gaps` helps catch blind spots.

### 5. Update Outcomes
After implementing changes, always use `update_change_status` and `update_decision_outcome` to close the feedback loop.

### 6. Learn from History
Regularly query past decisions and changes to learn from experience.

### 7. Check for Conflicts
Use `detect_change_conflicts` before implementing changes to avoid stepping on other work.

## Data Storage

DevilMCP stores all data in the configured `STORAGE_PATH` (default: `./storage`) as JSON files:

- `project_context.json` - Project structure and file information
- `decisions.json` - Decision log with outcomes
- `changes.json` - Change log with impacts
- `cascade_analysis.json` - Cascade risk data and events
- `thoughts.json` - Thought processes and reasoning chains

All data is persisted to disk and loaded on server start.

## Architecture

DevilMCP is built with a modular architecture:

```
server.py           # FastMCP server with tool registration
├── context_manager.py     # Project context and structure analysis
├── decision_tracker.py    # Decision logging and analysis
├── change_analyzer.py     # Change impact assessment
├── cascade_detector.py    # Cascade failure detection
└── thought_processor.py   # Thought process management
```

Each module is independent and can be extended or customized as needed.

## Advanced Features

### Dependency Graphs

With NetworkX installed, DevilMCP can build and analyze complex dependency graphs:

```python
# Build graph from all tracked dependencies
deps_dict = {
    "/path/to/file1.py": track_file_dependencies("/path/to/file1.py"),
    "/path/to/file2.py": track_file_dependencies("/path/to/file2.py"),
    # ... more files
}

graph_stats = build_dependency_graph(deps_dict)

# Analyze specific component
deps = detect_dependencies(
    target="/path/to/critical/file.py",
    depth=5,
    direction="both"
)
```

### Risk-Based Decision Making

DevilMCP tracks risk levels across decisions and changes:

```python
# Get all high-risk decisions
high_risk = query_decisions(risk_level="high", limit=20)

# Analyze patterns
stats = get_decision_statistics()
print(f"Risk distribution: {stats['risk_distribution']}")
```

### Session-Based Reasoning

Track entire work sessions with full reasoning chains:

```python
# Start session
start_thought_session("bug-fix-123", {"issue": "#123"})

# Log thoughts throughout work
log_thought_process("Found root cause in parser", "analysis", "...")
log_thought_process("Considering two fix approaches", "hypothesis", "...")
log_thought_process("Approach A might break edge cases", "concern", "...")

# Check for gaps
gaps = analyze_reasoning_gaps()

# End with summary
end_thought_session(
    "bug-fix-123",
    summary="Fixed parser bug with minimal impact",
    outcomes=["Bug fixed", "Tests passing", "No regressions"]
)

# Review later
summary = get_session_summary("bug-fix-123")
```

## Troubleshooting

### Server won't start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.8 or higher: `python --version`
- Check that the port is not in use: `netstat -an | grep 8080`

### Storage errors
- Ensure the storage directory is writable
- Check disk space
- Verify file permissions on the storage directory

### Import errors
- Activate the virtual environment
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

## Contributing

This MCP server is designed to be extended. To add new capabilities:

1. Create a new module in the project directory
2. Add tools to `server.py` using the `@mcp.tool()` decorator
3. Update this README with the new functionality

## License

This project is open source. Use it, extend it, make it your own.

## Credits

Built following the FastMCP architecture pattern from the FreeCodeCamp guide.
Designed specifically to prevent short-sighted AI development decisions through comprehensive context management and impact analysis.

---

**DevilMCP**: Because AI agents should know what they're doing, why they're doing it, and what might break when they do it.
