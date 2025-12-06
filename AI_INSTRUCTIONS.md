# DevilMCP: AI Memory System - Protocol & Instructions

**CRITICAL: Read and follow this protocol for every session.**

---

## MANDATORY PROTOCOL

### 1. INITIALIZATION (Every Session Start)
```
IMMEDIATELY call: get_briefing()
```
- This loads your context: recent decisions, warnings, rules, git changes
- Do NOT ask the user for context that is already in the briefing
- Review any `failed_approaches` - these are mistakes to avoid

### 2. BEFORE ANY CODING/CHANGES
```
Call: context_check("description of what you're about to do")
```
Or for detailed info:
```
Call: recall(topic)
Call: check_rules(action)
```

**CRITICAL**: If `context_check` returns a WARNING or FAILED APPROACH:
- You MUST acknowledge it explicitly
- Explain how your new approach differs
- Do NOT repeat past failures

### 3. FILE-LEVEL AWARENESS
```
When opening/modifying a file: recall_for_file("path/to/file.py")
```
This shows all memories (warnings, patterns, decisions) linked to that file.

### 4. MEMORY MANAGEMENT
After completing significant work:
```
remember(
    category="decision",  # or "pattern", "warning", "learning"
    content="What you decided/learned",
    rationale="Why",
    tags=["relevant", "tags"],
    file_path="optional/file.py"  # Link to specific file
)
```

**Category Guide:**
- `decision`: Architectural/design choices (decays over time)
- `pattern`: Recurring approaches to follow (PERMANENT - never decays)
- `warning`: Things to avoid (PERMANENT - never decays)
- `learning`: Lessons from experience (decays over time)

### 5. OUTCOME TRACKING (NON-NEGOTIABLE)
```
record_outcome(
    memory_id=<id>,
    outcome="What actually happened",
    worked=true/false
)
```

**CRITICAL**: If something fails, you MUST call `record_outcome` with `worked=false`.
This prevents future loops - failures get boosted in future recalls.

---

## RULES ENFORCEMENT

When `check_rules` returns guidance:
- `must_do`: These are REQUIRED actions - do them
- `must_not`: These are HARD CONSTRAINTS - never violate
- `ask_first`: Consider these questions before proceeding
- `warnings`: Past experiences to keep in mind

---

## AVAILABLE TOOLS (13 Total)

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `get_briefing()` | Session start | FIRST thing every session |
| `context_check(description)` | Quick pre-flight | Before any changes |
| `recall(topic)` | Get topic memories | Deep dive on a topic |
| `recall_for_file(path)` | File-specific memories | When touching a file |
| `remember(...)` | Store memory | After decisions/learnings |
| `record_outcome(...)` | Track result | After implementation |
| `check_rules(action)` | Get rule guidance | Before significant action |
| `add_rule(trigger, ...)` | Create rule | Establishing team patterns |
| `update_rule(id, ...)` | Modify rule | Refining guidance |
| `list_rules()` | Show all rules | Reviewing configuration |
| `search_memories(query)` | Search memories | Finding specific content |
| `find_related(id)` | Related memories | Exploring connections |
| `scan_todos(path)` | Find tech debt | Discovering TODO/FIXME/HACK comments |

---

## EXAMPLE SESSION

```
[Session starts]
AI: get_briefing()
→ "DevilMCP ready. 15 memories. ⚠️ 2 failed approaches to avoid!"
→ git_changes: {"uncommitted_changes": ["api/auth.py"]}

User: "Fix the authentication bug in auth.py"

AI: recall_for_file("api/auth.py")
→ Warning: "Session tokens caused race conditions" (Memory #12)
→ Pattern: "Always use JWT validation middleware" (Memory #8)

AI: context_check("fixing authentication in auth.py")
→ WARNING: "Similar fix attempted on 2024-01-15, failed due to cache"
→ must_do: ["Add rate limiting", "Test with concurrent requests"]

AI: [Acknowledges the warning]
"I see there was a failed attempt before due to caching. I'll ensure
this fix doesn't rely on cached tokens and will test concurrency."

[After fixing]
AI: remember(
    category="decision",
    content="Fixed auth by invalidating token cache on logout",
    rationale="Previous attempt failed because stale tokens persisted",
    file_path="api/auth.py",
    tags=["auth", "cache", "bugfix"]
)
→ id: 42

[After testing]
AI: record_outcome(42, "Fix works, concurrent tests pass", worked=true)
```

---

## KEY FEATURES

### Permanent vs. Episodic Memory
- **Patterns** and **Warnings** are PERMANENT - they never decay
- **Decisions** and **Learnings** decay over time (30-day half-life)
- Recent memories score higher than old ones

### Conflict Detection
When you `remember()` something:
- System checks for similar failed decisions
- Warns about potential duplicates
- Surfaces related warnings

### Git Awareness
`get_briefing()` shows:
- Recent commits since last memory
- Uncommitted changes
- Current branch

### Failed Decision Boosting
Failures get 1.5x relevance boost in future searches.
You WILL see past mistakes - learn from them.

---

## DATA STORAGE

Per-project storage at:
```
<project_root>/.devilmcp/storage/devilmcp.db
```

---

## SUMMARY

```
Session Start:  get_briefing()
Before Changes: context_check(description) or recall_for_file(path)
Making Decision: remember(category, content, rationale, file_path)
After Result:   record_outcome(id, outcome, worked)
```

**The system learns from YOUR outcomes. Record them.**

---

*DevilMCP v2.1.2: Persistent memory with semantic understanding, code symbol extraction, and tech debt scanning.*
