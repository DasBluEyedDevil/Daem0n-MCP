# Daem0nMCP: AI Memory System - Complete Protocol & Reference

**CRITICAL: Read and follow this protocol for every session.**

Daem0nMCP gives you persistent memory across sessions. You can remember decisions, learn from failures, and follow established patterns - all stored in a local database that persists between conversations.

---

## MANDATORY PROTOCOL

### 1. INITIALIZATION (Every Session Start)
```
IMMEDIATELY call: get_briefing()
```
- This loads your context: recent decisions, warnings, rules, git changes
- Do NOT ask the user for context that is already in the briefing
- Review any `failed_approaches` - these are mistakes to avoid
- Check `git_changes` to see what happened since your last session

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

## COMPLETE TOOL REFERENCE (15 Tools)

### Core Tools

#### `get_briefing(project_path?, focus_areas?)`
**When**: FIRST thing every session
**Returns**: Statistics, recent decisions, warnings, failed approaches, git changes
```
get_briefing()
get_briefing(focus_areas=["authentication", "database"])
```

#### `context_check(description)`
**When**: Before any changes - quick pre-flight check
**Returns**: Relevant memories + matching rules + warnings combined
```
context_check("adding user authentication to the API")
```

#### `recall(topic, categories?, limit?)`
**When**: Deep dive on a specific topic
**Returns**: Categorized memories ranked by relevance
```
recall("authentication")
recall("database", categories=["warning", "pattern"], limit=5)
```

#### `recall_for_file(file_path, limit?)`
**When**: Before modifying any file
**Returns**: All memories linked to that file
```
recall_for_file("src/auth/handlers.py")
```

#### `remember(category, content, rationale?, context?, tags?, file_path?)`
**When**: After making decisions or learning something
**Returns**: Created memory with ID (save this for record_outcome)
```
remember(
    category="decision",
    content="Using JWT instead of sessions for auth",
    rationale="Need stateless auth for horizontal scaling",
    tags=["auth", "architecture"],
    file_path="src/auth/jwt.py"
)
```

#### `record_outcome(memory_id, outcome, worked)`
**When**: After implementing and testing a decision
**Returns**: Updated memory
```
record_outcome(42, "JWT auth working, load tests pass", worked=true)
record_outcome(43, "Caching caused stale data", worked=false)
```

#### `check_rules(action, context?)`
**When**: Before significant actions
**Returns**: Matching rules with must_do/must_not/warnings
```
check_rules("adding a new API endpoint")
check_rules("modifying database schema")
```

### Rule Management

#### `add_rule(trigger, must_do?, must_not?, ask_first?, warnings?, priority?)`
**When**: Establishing team patterns or constraints
```
add_rule(
    trigger="adding new API endpoint",
    must_do=["Add rate limiting", "Add to OpenAPI spec"],
    must_not=["Use synchronous database calls"],
    ask_first=["Is this a breaking change?"],
    priority=10
)
```

#### `update_rule(rule_id, must_do?, must_not?, ask_first?, warnings?, priority?, enabled?)`
**When**: Refining existing rules
```
update_rule(5, must_do=["Add rate limiting", "Add authentication"])
update_rule(5, enabled=false)  # Disable a rule
```

#### `list_rules(enabled_only?, limit?)`
**When**: Reviewing all configured rules
```
list_rules()
list_rules(enabled_only=false)  # Include disabled rules
```

### Search & Discovery

#### `search_memories(query, limit?)`
**When**: Finding specific content across all memories
```
search_memories("rate limiting")
search_memories("JWT token", limit=10)
```

#### `find_related(memory_id, limit?)`
**When**: Exploring connections from a specific memory
```
find_related(42)  # Find memories related to memory #42
```

### Tech Debt & Refactoring

#### `scan_todos(path?, auto_remember?, types?)`
**When**: Finding TODO/FIXME/HACK comments in code
**Returns**: Grouped tech debt items with file locations
```
scan_todos()  # Scan current directory
scan_todos(path="src/", types=["FIXME", "HACK"])  # Only critical
scan_todos(auto_remember=true)  # Auto-create warning memories
```

#### `propose_refactor(file_path)`
**When**: Before refactoring a file - gets combined context
**Returns**: File memories + TODOs + rules + constraints + opportunities
```
propose_refactor("src/auth/handlers.py")
```
Use the returned `constraints` (failed approaches, warnings) and `opportunities` (TODOs) to plan your refactor.

#### `ingest_doc(url, topic, chunk_size?)`
**When**: Importing external documentation for reference
**Returns**: Chunks stored as permanent learnings
```
ingest_doc("https://stripe.com/docs/api/charges", "stripe")
ingest_doc("https://react.dev/reference/hooks", "react-hooks")
```
After ingesting, use `recall("stripe")` to retrieve the documentation.

---

## EXAMPLE SESSION

```
[Session starts]
AI: get_briefing()
→ "Daem0nMCP ready. 15 memories. ⚠️ 2 failed approaches to avoid!"
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

### Semantic Search
- Uses TF-IDF for keyword matching (always available)
- Optional vector embeddings for better semantic understanding
- "blocking database calls" can match "synchronous queries" with vectors

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

### Tech Debt Tracking
`scan_todos()` finds TODO/FIXME/HACK comments and can auto-create warnings.
Use before starting work to see what needs attention.

### External Knowledge
`ingest_doc()` imports documentation from URLs.
Use when working with external APIs or libraries to have their docs in memory.

---

## DATA STORAGE

Per-project storage at:
```
<project_root>/.daem0nmcp/storage/daem0nmcp.db
```

### Legacy Migration (from DevilMCP)
If upgrading from DevilMCP, your data is automatically migrated:
- Old location: `.devilmcp/storage/devilmcp.db`
- New location: `.daem0nmcp/storage/daem0nmcp.db`

Migration happens automatically on first startup. After migration completes, you can safely delete:
- `.devilmcp/` directory
- `devilmcp.egg-info/` directory (will regenerate as `daem0nmcp.egg-info`)
- `devilmcp/` source directory (replaced by `daem0nmcp/`)

---

## WORKFLOW CHEAT SHEET

```
┌─────────────────────────────────────────────────────────────┐
│  SESSION START                                              │
│  └─> get_briefing()                                         │
├─────────────────────────────────────────────────────────────┤
│  BEFORE CHANGES                                             │
│  └─> context_check("what you're doing")                     │
│  └─> recall_for_file("path/to/file.py")                     │
├─────────────────────────────────────────────────────────────┤
│  BEFORE REFACTORING                                         │
│  └─> propose_refactor("path/to/file.py")                    │
│  └─> scan_todos("path/to/dir")                              │
├─────────────────────────────────────────────────────────────┤
│  AFTER MAKING DECISIONS                                     │
│  └─> remember(category, content, rationale, file_path)      │
├─────────────────────────────────────────────────────────────┤
│  AFTER IMPLEMENTATION                                       │
│  └─> record_outcome(memory_id, outcome, worked)             │
├─────────────────────────────────────────────────────────────┤
│  IMPORTING EXTERNAL DOCS                                    │
│  └─> ingest_doc(url, topic)                                 │
│  └─> recall(topic)  # to retrieve later                     │
└─────────────────────────────────────────────────────────────┘
```

**The system learns from YOUR outcomes. Record them.**

---

*Daem0nMCP v2.2.0: Persistent memory with semantic understanding, optional vector embeddings, doc ingestion, and refactor proposals.*
