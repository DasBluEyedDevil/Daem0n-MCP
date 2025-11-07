# DevilMCP Usage Guide

Complete guide to using DevilMCP's 30+ tools for better software development.

## Table of Contents

1. [Context Management Tools](#context-management-tools)
2. [Decision Tracking Tools](#decision-tracking-tools)
3. [Change Analysis Tools](#change-analysis-tools)
4. [Cascade Detection Tools](#cascade-detection-tools)
5. [Thought Process Tools](#thought-process-tools)
6. [Workflow Examples](#workflow-examples)

---

## Context Management Tools

### 1. `analyze_project_structure`

**Purpose:** Build a comprehensive understanding of your project's architecture.

**When to use:**
- Starting work on a new or unfamiliar project
- Onboarding to a codebase
- Understanding project organization

**Example:**
```python
# Via MCP tool call
result = analyze_project_structure(
    project_path="C:\\Users\\dasbl\\Projects\\MyApp"
)

# Returns:
{
    "root": "C:\\Users\\dasbl\\Projects\\MyApp",
    "total_files": 234,
    "languages": {
        "Python": 120,
        "JavaScript": 80,
        "CSS": 20,
        "HTML": 14
    },
    "directory_structure": {...},
    "file_types": {...}
}
```

**Use case:**
```
You: "Analyze the structure of my e-commerce project"
AI: [Uses analyze_project_structure]
AI: "Your project has 234 files across 4 languages.
     Main components: backend (Python), frontend (JavaScript),
     with 12 modules in src/"
```

---

### 2. `track_file_dependencies`

**Purpose:** Understand what a file depends on and what depends on it.

**When to use:**
- Before modifying a file
- Understanding code relationships
- Finding circular dependencies

**Example:**
```python
result = track_file_dependencies(
    file_path="src/auth/authentication.py",
    project_root="C:\\Users\\dasbl\\Projects\\MyApp"
)

# Returns:
{
    "file": "src/auth/authentication.py",
    "imports": [
        "jwt",
        "bcrypt",
        "src.database.models",
        "src.config"
    ],
    "imported_by": [
        "src/api/routes.py",
        "src/middleware/auth_middleware.py"
    ],
    "complexity": "medium"
}
```

**Use case:**
```
You: "What depends on authentication.py?"
AI: [Uses track_file_dependencies]
AI: "authentication.py is imported by 2 files: routes.py and
     auth_middleware.py. It imports jwt, bcrypt, and your
     database models."
```

---

### 3. `get_project_context`

**Purpose:** Retrieve comprehensive project information.

**When to use:**
- Resuming work on a project
- Getting full context before making decisions
- Understanding project state

**Example:**
```python
result = get_project_context(
    project_path="C:\\Users\\dasbl\\Projects\\MyApp",
    include_dependencies=True
)

# Returns:
{
    "project": "MyApp",
    "structure": {...},
    "dependencies": {...},
    "last_updated": "2025-11-04T20:00:00Z",
    "file_count": 234
}
```

---

### 4. `search_context`

**Purpose:** Find specific files, dependencies, or context information.

**When to use:**
- Looking for specific functionality
- Finding files related to a feature
- Searching dependency information

**Example:**
```python
result = search_context(
    query="authentication",
    context_type="files"  # "files", "dependencies", or "all"
)

# Returns:
[
    {
        "file": "src/auth/authentication.py",
        "type": "file",
        "relevance": 0.95
    },
    {
        "file": "src/middleware/auth_middleware.py",
        "type": "file",
        "relevance": 0.87
    }
]
```

---

## Decision Tracking Tools

### 5. `log_decision`

**Purpose:** Record important decisions with full context and rationale.

**When to use:**
- Making architectural decisions
- Choosing between implementation approaches
- Selecting libraries or frameworks
- Any significant technical choice

**Example:**
```python
decision = log_decision(
    decision="Use PostgreSQL for database instead of MongoDB",
    rationale="Need strong ACID guarantees for financial transactions, complex queries with JOINs, and mature ecosystem",
    context={
        "project": "FinanceApp",
        "component": "database",
        "team_size": 5,
        "budget": "moderate"
    },
    alternatives_considered=[
        "MongoDB - Good performance but weak consistency",
        "MySQL - Viable but less advanced features",
        "SQLite - Too limited for production"
    ],
    expected_impact="Better data consistency, more complex queries possible, established patterns",
    risk_level="medium",  # "low", "medium", "high", "critical"
    tags=["database", "architecture", "backend"]
)

# Returns:
{
    "id": 1,
    "decision": "Use PostgreSQL...",
    "timestamp": "2025-11-04T20:00:00Z",
    "rationale": "...",
    "expected_impact": "...",
    "risk_level": "medium"
}
```

**Use case:**
```
You: "Should we use REST or GraphQL for our API?"
AI: "Let me log this decision..."
AI: [Uses log_decision with full context]
AI: "I've logged decision #1 to use GraphQL because of your
     complex data requirements and mobile client needs."
```

---

### 6. `update_decision_outcome`

**Purpose:** Record what actually happened after implementing a decision.

**When to use:**
- After implementing a decision
- When outcomes become clear
- Learning from decisions

**Example:**
```python
result = update_decision_outcome(
    decision_id=1,
    outcome="Successfully implemented PostgreSQL. Migration completed in 3 days.",
    actual_impact="Significantly improved data consistency. Complex reports now 40% faster. Team adapted quickly.",
    lessons_learned="Schema migrations need more planning. Should have invested in better migration tools earlier."
)
```

**Use case:**
```
You: "We finished implementing PostgreSQL. It went great!"
AI: [Uses update_decision_outcome for decision #1]
AI: "Updated decision #1 with the successful outcome.
     Glad it worked well!"
```

---

### 7. `query_decisions`

**Purpose:** Search past decisions to learn from them.

**When to use:**
- Before making similar decisions
- Understanding why something was done
- Reviewing project history

**Example:**
```python
results = query_decisions(
    query="database",
    tags=["architecture"],
    risk_level="medium",
    limit=5
)

# Returns:
[
    {
        "id": 1,
        "decision": "Use PostgreSQL...",
        "timestamp": "2025-11-04T20:00:00Z",
        "outcome": "Successfully implemented...",
        "risk_level": "medium"
    }
]
```

**Use case:**
```
You: "What decisions have we made about the database?"
AI: [Uses query_decisions with query="database"]
AI: "Found 3 database-related decisions:
     1. PostgreSQL choice (successful)
     2. Connection pooling strategy (successful)
     3. Backup strategy (in progress)"
```

---

### 8. `analyze_decision_impact`

**Purpose:** Compare expected vs actual outcomes of decisions.

**Example:**
```python
analysis = analyze_decision_impact(decision_id=1)

# Returns:
{
    "decision_id": 1,
    "expected_impact": "Better data consistency...",
    "actual_impact": "Significantly improved...",
    "variance": "Positive - exceeded expectations",
    "lessons": [...]
}
```

---

### 9. `get_decision_statistics`

**Purpose:** Understand overall decision-making patterns.

**Example:**
```python
stats = get_decision_statistics()

# Returns:
{
    "total_decisions": 15,
    "by_risk_level": {
        "low": 5,
        "medium": 8,
        "high": 2,
        "critical": 0
    },
    "outcome_tracking_rate": 0.8,  # 80% have outcomes recorded
    "average_success_rate": 0.9
}
```

---

## Change Analysis Tools

### 10. `log_change`

**Purpose:** Record changes BEFORE making them to create a paper trail.

**When to use:**
- Before modifying code
- Refactoring
- Bug fixes
- Feature additions

**Example:**
```python
change = log_change(
    file_path="src/api/payment_handler.py",
    change_type="modify",  # "add", "modify", "delete", "refactor"
    description="Add retry logic for failed payment transactions",
    rationale="Users report payment failures due to temporary network issues. Need automatic retry.",
    affected_components=[
        "payment_handler",
        "transaction_logger",
        "notification_service"
    ],
    risk_assessment={
        "data_loss_risk": "low",
        "breaking_change": False,
        "performance_impact": "minimal"
    },
    rollback_plan="Revert commit, feature flag allows instant disable"
)

# Returns:
{
    "id": 1,
    "file_path": "src/api/payment_handler.py",
    "change_type": "modify",
    "timestamp": "2025-11-04T20:00:00Z",
    "status": "planned"
}
```

**Use case:**
```
You: "I need to add retry logic to payment processing"
AI: "Let me log this change first for tracking..."
AI: [Uses log_change]
AI: "Logged change #1. Now let's implement it..."
```

---

### 11. `analyze_change_impact`

**Purpose:** CRITICAL - Analyze potential impact BEFORE making changes.

**When to use:**
- Before ANY significant code change
- Understanding blast radius
- Risk assessment

**Example:**
```python
impact = analyze_change_impact(
    file_path="src/database/models.py",
    change_description="Rename User.email field to User.email_address",
    dependencies={
        "imported_by": [
            "src/api/user_routes.py",
            "src/auth/authentication.py",
            "src/email/sender.py",
            "tests/test_users.py"
        ]
    }
)

# Returns:
{
    "file": "src/database/models.py",
    "change": "Rename User.email...",
    "affected_files": [
        "src/api/user_routes.py",
        "src/auth/authentication.py",
        "src/email/sender.py",
        "tests/test_users.py"
    ],
    "impact_level": "high",
    "risk_factors": [
        "Field rename affects 4 files",
        "Database migration required",
        "Authentication system affected"
    ],
    "recommendations": [
        "Create database migration",
        "Update all 4 dependent files",
        "Run full test suite",
        "Consider adding alias for backward compatibility"
    ]
}
```

**Use case:**
```
You: "I want to rename the email field in User model"
AI: [Uses analyze_change_impact]
AI: "WARNING: This affects 4 files including authentication!
     You'll need a database migration and updates to
     user_routes.py, authentication.py, and sender.py."
```

---

### 12. `update_change_status`

**Purpose:** Track change implementation progress.

**Example:**
```python
result = update_change_status(
    change_id=1,
    status="implemented",  # "planned", "in_progress", "implemented", "tested", "rolled_back", "failed"
    actual_impact="Payment retry working well. Reduced failure rate from 5% to 0.3%.",
    issues=["Initial implementation had off-by-one error in retry count"]
)
```

---

### 13. `query_changes`

**Purpose:** Search change history.

**Example:**
```python
results = query_changes(
    file_path="src/api/",
    change_type="modify",
    status="implemented",
    limit=10
)
```

---

### 14. `detect_change_conflicts`

**Purpose:** Find potential conflicts with other recent changes.

**Example:**
```python
conflicts = detect_change_conflicts(
    proposed_change={
        "file_path": "src/api/payment_handler.py",
        "affected_components": ["payment_handler"]
    }
)

# Returns:
[
    {
        "change_id": 5,
        "file_path": "src/api/payment_handler.py",
        "status": "in_progress",
        "conflict_type": "same_file",
        "risk": "high"
    }
]
```

---

## Cascade Detection Tools

### 15. `build_dependency_graph`

**Purpose:** Create visual map of component dependencies.

**Example:**
```python
graph = build_dependency_graph(
    dependencies={
        "payment_handler": {
            "imports": ["database", "logger", "notification"],
            "imported_by": ["api_routes"]
        },
        "database": {
            "imports": ["config"],
            "imported_by": ["payment_handler", "user_handler"]
        }
    }
)
```

---

### 16. `detect_dependencies`

**Purpose:** Find all upstream and downstream dependencies.

**Example:**
```python
deps = detect_dependencies(
    target="payment_handler",
    depth=3,
    direction="both"  # "upstream", "downstream", "both"
)

# Returns:
{
    "target": "payment_handler",
    "upstream": {
        "level_1": ["database", "logger"],
        "level_2": ["config", "log_formatter"],
        "level_3": ["env_loader"]
    },
    "downstream": {
        "level_1": ["api_routes"],
        "level_2": ["web_server"],
        "level_3": ["main"]
    }
}
```

---

### 17. `analyze_cascade_risk`

**Purpose:** CRITICAL - Understand cascading failure potential.

**When to use:**
- Before breaking changes
- Major refactoring
- Removing deprecated code

**Example:**
```python
risk = analyze_cascade_risk(
    target="database.py",
    change_type="breaking",  # "breaking", "non-breaking", "refactor", "removal"
    context={
        "component": "database layer",
        "criticality": "high"
    }
)

# Returns:
{
    "target": "database.py",
    "cascade_probability": 0.85,  # 85% chance of cascade
    "risk_level": "high",
    "affected_components": [
        "payment_handler",
        "user_handler",
        "auth_system",
        "api_layer"
    ],
    "failure_chain": [
        "database.py -> payment_handler -> api_routes -> web_server"
    ],
    "recommendations": [
        "Implement feature flag for gradual rollout",
        "Add backward compatibility layer",
        "Test each dependent component",
        "Have rollback plan ready"
    ],
    "estimated_downtime": "Could affect all API endpoints if not careful"
}
```

**Use case:**
```
You: "I want to change the database connection pooling"
AI: [Uses analyze_cascade_risk]
AI: "CAUTION: High cascade risk (85%)! This affects
     payment_handler, user_handler, and the entire API layer.
     Recommendation: Use a feature flag and gradual rollout."
```

---

### 18. `log_cascade_event`

**Purpose:** Record when cascading failures occur (learn from them).

**Example:**
```python
event = log_cascade_event(
    trigger="database.py connection pool exhausted",
    affected_components=[
        "payment_handler",
        "user_handler",
        "api_layer",
        "web_server"
    ],
    severity="critical",  # "low", "medium", "high", "critical"
    description="Pool limit too low (10 connections). Under load, all connections used, causing 503 errors across all API endpoints.",
    resolution="Increased pool size to 50, added connection timeout, implemented connection health checks"
)
```

---

### 19. `suggest_safe_changes`

**Purpose:** Get recommendations for making changes safely.

**Example:**
```python
suggestions = suggest_safe_changes(
    target="authentication.py",
    proposed_change="Update JWT token expiration from 24h to 1h"
)

# Returns:
{
    "approach": [
        "Implement gradual rollout with feature flag",
        "Add refresh token mechanism first",
        "Monitor token refresh rates",
        "Have instant rollback capability"
    ],
    "testing_strategy": [
        "Test with subset of users first",
        "Monitor authentication errors",
        "Check mobile app compatibility"
    ],
    "rollback_plan": [
        "Toggle feature flag",
        "Keep old token validation for 48h",
        "Maintain backward compatibility"
    ]
}
```

---

## Thought Process Tools

### 20. `start_thought_session`

**Purpose:** Begin tracking your reasoning for a work session.

**When to use:**
- Starting work on complex features
- Debugging difficult issues
- Architectural planning

**Example:**
```python
session = start_thought_session(
    session_id="feature-payment-retry-2025-11-04",
    context={
        "task": "Implement payment retry logic",
        "project": "FinanceApp",
        "goal": "Reduce payment failure rate",
        "constraints": ["Must not double-charge", "Max 3 retries"]
    }
)
```

---

### 21. `log_thought_process`

**Purpose:** Record your thinking as you work.

**Example:**
```python
thought = log_thought_process(
    thought="Should retry only on network errors, not on insufficient funds",
    category="analysis",  # "analysis", "hypothesis", "concern", "question", "validation"
    reasoning="Retrying insufficient funds errors would be wasteful and annoy users. Network errors are transient and worth retrying.",
    related_to=["payment errors", "user experience"],
    confidence=0.9,
    session_id="feature-payment-retry-2025-11-04"
)
```

**Categories explained:**
- **analysis**: Understanding the problem
- **hypothesis**: Potential solutions
- **concern**: Risks or worries
- **question**: Things you need to figure out
- **validation**: Testing assumptions

---

### 22. `retrieve_thought_context`

**Purpose:** Recall previous thinking to maintain continuity.

**Example:**
```python
thoughts = retrieve_thought_context(
    category="concern",
    session_id="feature-payment-retry-2025-11-04",
    limit=5
)

# Returns previous concerns to address
```

---

### 23. `analyze_reasoning_gaps`

**Purpose:** IMPORTANT - Find blind spots in your thinking.

**When to use:**
- Before finalizing implementation
- During code review
- Periodically during complex work

**Example:**
```python
gaps = analyze_reasoning_gaps(
    session_id="feature-payment-retry-2025-11-04"
)

# Returns:
{
    "gaps": [
        "No thoughts about database transaction handling",
        "Haven't considered monitoring/alerting",
        "Missing thoughts about retry timing/backoff",
        "No validation thoughts logged"
    ],
    "suggestions": [
        "Consider how retries interact with transactions",
        "Think about how to monitor retry success rates",
        "Define retry timing strategy (exponential backoff?)",
        "Plan testing approach"
    ],
    "missing_categories": ["validation", "monitoring"]
}
```

**Use case:**
```
AI: [Uses analyze_reasoning_gaps periodically]
AI: "I notice I haven't considered monitoring yet. Let me
     think about how to track retry success rates..."
```

---

### 24. `record_insight`

**Purpose:** Capture learnings for future reference.

**Example:**
```python
insight = record_insight(
    insight="Payment retries need exponential backoff to avoid overwhelming payment provider during outages",
    source="Implementing payment retry feature",
    applicability="Any retry logic for external services",
    session_id="feature-payment-retry-2025-11-04"
)
```

---

### 25. `end_thought_session`

**Purpose:** Conclude session with summary.

**Example:**
```python
summary = end_thought_session(
    session_id="feature-payment-retry-2025-11-04",
    summary="Implemented payment retry with exponential backoff, max 3 retries, only for network errors. Added monitoring.",
    outcomes=[
        "Feature implemented and tested",
        "Reduced failure rate from 5% to 0.3%",
        "Added monitoring dashboard",
        "Documented retry strategy"
    ]
)
```

---

### 26. `get_session_summary`

**Purpose:** Review what happened in a session.

**Example:**
```python
summary = get_session_summary(
    session_id="feature-payment-retry-2025-11-04"
)

# Returns:
{
    "session_id": "feature-payment-retry-2025-11-04",
    "duration": "3 hours",
    "total_thoughts": 15,
    "by_category": {
        "analysis": 5,
        "hypothesis": 3,
        "concern": 4,
        "validation": 3
    },
    "insights": 2,
    "outcomes": [...]
}
```

---

## Workflow Examples

### Example 1: Adding a New Feature

```
1. Start session
   -> start_thought_session(session_id="feature-user-profile")

2. Understand context
   -> analyze_project_structure()
   -> search_context(query="user")

3. Log decision about approach
   -> log_decision(
        decision="Add user profile page with React component",
        rationale="Consistent with existing architecture"
      )

4. Log thoughts as you work
   -> log_thought_process(
        thought="Need to consider privacy settings",
        category="concern"
      )

5. Before making changes
   -> log_change(file_path="src/components/UserProfile.jsx")
   -> analyze_change_impact(...)

6. Check for gaps in thinking
   -> analyze_reasoning_gaps()

7. After implementation
   -> update_change_status(change_id=1, status="implemented")
   -> update_decision_outcome(decision_id=1, outcome="Success!")

8. End session
   -> record_insight(insight="Profile components need mobile optimization")
   -> end_thought_session(session_id="feature-user-profile")
```

---

### Example 2: Bug Fix with Cascade Risk

```
1. Start
   -> start_thought_session(session_id="bug-auth-timeout")

2. Understand the issue
   -> track_file_dependencies(file_path="src/auth/session.py")
   -> log_thought_process(
        thought="Auth timeout causing API failures",
        category="analysis"
      )

3. Analyze impact of fix
   -> analyze_cascade_risk(
        target="session.py",
        change_type="breaking"
      )

4. Get safe change recommendations
   -> suggest_safe_changes(
        target="session.py",
        proposed_change="Increase timeout from 5min to 15min"
      )

5. Log the change
   -> log_change(
        file_path="src/auth/session.py",
        change_type="modify",
        affected_components=[...]
      )

6. Make the change, then update
   -> update_change_status(change_id=1, status="tested")

7. Record what you learned
   -> record_insight(
        insight="Auth timeouts should be configurable per endpoint"
      )
```

---

### Example 3: Refactoring Decision

```
1. Query past decisions
   -> query_decisions(query="refactoring")

2. Log new decision
   -> log_decision(
        decision="Refactor authentication to use service pattern",
        alternatives_considered=[
           "Keep current approach",
           "Use third-party auth service"
        ]
      )

3. Build dependency graph
   -> build_dependency_graph(dependencies={...})

4. Check cascade risk
   -> analyze_cascade_risk(target="auth/", change_type="refactor")

5. Log all affected changes
   -> log_change(file_path="auth/service.py", change_type="add")
   -> log_change(file_path="auth/old_auth.py", change_type="refactor")

6. Track conflicts
   -> detect_change_conflicts(proposed_change={...})
```

---

## Best Practices

1. **Always use `analyze_change_impact` before significant changes**
2. **Log decisions for anything non-trivial**
3. **Use `analyze_cascade_risk` before breaking changes**
4. **Track your thought process during complex work**
5. **Update outcomes after implementation**
6. **Use `analyze_reasoning_gaps` to catch blind spots**
7. **Query past decisions before making new similar ones**

---

## Quick Reference

### Most Important Tools

| Tool | When | Why |
|------|------|-----|
| `analyze_change_impact` | Before ANY change | Understand blast radius |
| `analyze_cascade_risk` | Before breaking changes | Prevent cascade failures |
| `log_decision` | Making choices | Build decision history |
| `analyze_reasoning_gaps` | During complex work | Catch blind spots |
| `log_change` | Before modifying code | Create paper trail |

### Tool Categories

- **Context (5 tools)**: Understanding the codebase
- **Decisions (6 tools)**: Tracking choices and outcomes
- **Changes (5 tools)**: Managing code modifications
- **Cascades (6 tools)**: Preventing cascade failures
- **Thoughts (8 tools)**: Managing reasoning process

---

## Next Steps

Ready to try DevilMCP? The tools are available whenever Claude Code is running in your project. Just ask your AI assistant to use them!

Example: "Analyze the impact of changing the database schema" → AI will use the appropriate tools automatically.
