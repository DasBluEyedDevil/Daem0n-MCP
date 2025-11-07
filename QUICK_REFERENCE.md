# DevilMCP Quick Reference Card

## Critical "Always Use" Tools

These tools prevent major issues. Use them religiously:

```
🚨 BEFORE ANY CODE CHANGE:
   → analyze_change_impact()      - Understand blast radius
   → analyze_cascade_risk()       - Check for cascade potential

📝 FOR ALL DECISIONS:
   → log_decision()               - Record why you chose this

🧠 DURING COMPLEX WORK:
   → analyze_reasoning_gaps()     - Find your blind spots
```

---

## Tool Categories (30+ tools)

### 🗂️ Context Management (5 tools)

| Tool | Purpose | Use When |
|------|---------|----------|
| `analyze_project_structure` | Map the codebase | Starting new project |
| `track_file_dependencies` | Find what depends on what | Before changing file |
| `get_project_context` | Get full project info | Resuming work |
| `search_context` | Find files/dependencies | Looking for something |
| `get_mcp_statistics` | Get usage stats | Reviewing progress |

### 📋 Decision Tracking (6 tools)

| Tool | Purpose | Use When |
|------|---------|----------|
| `log_decision` | Record decision + rationale | Making ANY choice |
| `update_decision_outcome` | Record what happened | After implementing |
| `query_decisions` | Search past decisions | Before similar decision |
| `analyze_decision_impact` | Compare expected vs actual | Learning from decision |
| `get_decision_statistics` | Overall decision stats | Reviewing quality |

### 🔄 Change Analysis (5 tools)

| Tool | Purpose | Use When |
|------|---------|----------|
| `log_change` | Record planned change | BEFORE modifying code |
| `analyze_change_impact` | Assess impact | BEFORE making change |
| `update_change_status` | Track progress | After implementing |
| `query_changes` | Search change history | Understanding past |
| `detect_change_conflicts` | Find conflicts | Before concurrent changes |

### ⚠️ Cascade Detection (6 tools)

| Tool | Purpose | Use When |
|------|---------|----------|
| `build_dependency_graph` | Map dependencies | Understanding system |
| `detect_dependencies` | Find upstream/downstream | Assessing change scope |
| `analyze_cascade_risk` | Cascade failure risk | BEFORE breaking changes |
| `log_cascade_event` | Record cascade failure | When cascade occurs |
| `suggest_safe_changes` | Get safety recommendations | Planning changes |

### 🧠 Thought Process (8 tools)

| Tool | Purpose | Use When |
|------|---------|----------|
| `start_thought_session` | Begin tracking thoughts | Starting complex work |
| `log_thought_process` | Record thinking | Throughout work |
| `retrieve_thought_context` | Recall previous thoughts | Maintaining continuity |
| `analyze_reasoning_gaps` | Find blind spots | Periodically/before done |
| `record_insight` | Capture learning | Discovery moment |
| `end_thought_session` | Finish + summarize | Completing work |
| `get_session_summary` | Review session | Understanding work done |

---

## Common Workflows

### 🆕 Adding New Feature

```bash
1. start_thought_session()
2. analyze_project_structure()      # Understand codebase
3. log_decision()                   # Document approach
4. log_change()                     # Before writing code
5. analyze_change_impact()          # Check blast radius
6. [Write code]
7. analyze_reasoning_gaps()         # Check for blind spots
8. update_change_status()           # Mark complete
9. update_decision_outcome()        # Record results
10. end_thought_session()
```

### 🐛 Fixing Bug

```bash
1. start_thought_session()
2. track_file_dependencies()        # Understand relationships
3. analyze_cascade_risk()           # Check if fix could break things
4. log_change()                     # Record planned fix
5. [Fix bug]
6. update_change_status()
```

### 🏗️ Major Refactoring

```bash
1. query_decisions()                # Learn from past refactorings
2. log_decision()                   # Document refactoring choice
3. build_dependency_graph()         # Map all dependencies
4. analyze_cascade_risk()           # HIGH IMPORTANCE for refactoring
5. suggest_safe_changes()           # Get recommendations
6. [Multiple log_change() calls]    # Track each file
7. detect_change_conflicts()        # Check for conflicts
8. [Perform refactoring]
9. [Multiple update_change_status()]
10. log_cascade_event()             # If any issues occurred
```

### 🤔 Making Architecture Decision

```bash
1. query_decisions()                # Check past similar decisions
2. analyze_project_structure()      # Understand current state
3. log_decision()                   # Record choice with alternatives
4. analyze_change_impact()          # If implementing now
5. [Later] update_decision_outcome() # Record how it went
```

---

## Risk Levels Guide

### Decision Risk Levels

- **low**: Minor change, easily reversible, low impact
- **medium**: Moderate change, some effort to reverse, noticeable impact
- **high**: Major change, difficult to reverse, significant impact
- **critical**: System-critical, very hard to reverse, business-critical

### Change Types

- **add**: New file/feature (usually lower risk)
- **modify**: Existing code change (risk depends on scope)
- **delete**: Removing code (high risk - check dependencies!)
- **refactor**: Restructuring (medium-high risk)

### Cascade Risk Indicators

- **Low (< 30%)**: Change is isolated, few dependencies
- **Medium (30-60%)**: Some dependencies, manageable impact
- **High (60-85%)**: Many dependencies, significant cascade potential
- **Critical (> 85%)**: Core component, likely cascade failure

---

## How Claude Code Uses These Tools

When you're working with Claude Code in your project, you can simply ask:

```
You: "Should I use Redux or Context API?"
Claude: [Automatically uses log_decision()]

You: "Analyze the impact of changing the auth system"
Claude: [Uses analyze_change_impact() + analyze_cascade_risk()]

You: "What did we decide about the database?"
Claude: [Uses query_decisions(query="database")]

You: "I want to refactor the API layer"
Claude: [Uses multiple tools: analyze_project_structure,
         build_dependency_graph, analyze_cascade_risk,
         suggest_safe_changes, then logs everything]
```

**The AI assistant knows when to use these tools automatically!**

---

## Thought Categories Explained

When using `log_thought_process()`, choose the right category:

| Category | When to Use | Example |
|----------|-------------|---------|
| `analysis` | Understanding the problem | "The bug occurs when user has no email" |
| `hypothesis` | Potential solutions | "Maybe we can cache the results" |
| `concern` | Risks or worries | "This might cause race conditions" |
| `question` | Need to figure out | "How does the payment gateway handle retries?" |
| `validation` | Testing assumptions | "Confirmed: timeout is 30 seconds" |

---

## Storage Location

All data stored per-project in:
```
YourProject/.devilmcp/storage/
├── decisions.db      # Decision history
├── changes.db        # Change tracking
├── context.db        # Project structure
├── cascades.db       # Cascade events
└── thoughts.db       # Thought processes
```

---

## Tips for Maximum Benefit

1. ✅ **Use `analyze_change_impact` religiously** - It's your safety net
2. ✅ **Log decisions as you make them** - Not after
3. ✅ **Check cascade risk for ANY breaking change** - Prevents disasters
4. ✅ **Use reasoning gap analysis** - Catches what you missed
5. ✅ **Query past decisions** - Learn from history
6. ✅ **Update outcomes** - Build institutional knowledge
7. ✅ **Track thoughts on complex work** - Maintains clarity

---

## Common Mistakes to Avoid

❌ Making changes without `analyze_change_impact`
❌ Not logging important decisions
❌ Ignoring cascade risk warnings
❌ Forgetting to update decision outcomes
❌ Not using reasoning gap analysis on complex work

---

## Getting Help

- **Full Guide**: See `USAGE_GUIDE.md` for detailed examples
- **Project Isolation**: See `PROJECT_ISOLATION.md` for multi-project setup
- **Testing**: Run `python test_server.py` to verify everything works

---

## Example Session

```
You: "I need to add a caching layer to our API"

Claude:
1. [Uses analyze_project_structure()]
   "Your API has 15 endpoints across 3 routers"

2. [Uses log_decision()]
   "Logged decision #5: Use Redis for caching"

3. [Uses track_file_dependencies()]
   "api_routes.py is imported by 5 modules"

4. [Uses analyze_change_impact()]
   "Adding caching affects 3 components, medium risk"

5. [Uses analyze_cascade_risk()]
   "Low cascade risk (20%) - caching is additive"

6. [Uses log_change()]
   "Logged change #8 for cache_layer.py"

7. [Helps you implement]

8. [Uses update_change_status()]
   "Updated change #8 as implemented"

9. [Uses update_decision_outcome()]
   "Updated decision #5 with successful outcome"
```

All tracked, all documented, all searchable for future reference!

---

## Remember

🎯 **DevilMCP's purpose**: Help you make better decisions by:
- Understanding impact before making changes
- Learning from past decisions
- Preventing cascade failures
- Maintaining context
- Catching blind spots in reasoning

**Use it, and avoid short-sighted development!**
