# Repository Guidelines

## Project Structure & Module Organization
- `daem0nmcp/` contains the core Python package (server, memory, rules, indexing).
- `daem0nmcp/migrations/` holds database schema migrations.
- `daem0nmcp/channels/` provides notification channel implementations.
- `tests/` is the pytest suite (`test_*.py`, `test_*` functions).
- `docs/`, `scripts/`, and `hooks/` contain documentation, utilities, and git hook templates.
- Runtime data lives under `.daem0nmcp/` (e.g., `.daem0nmcp/storage/daem0nmcp.db`); do not commit it.

## Build, Test, and Development Commands
- `pip install -e ".[dev]"` installs the package in editable mode with test deps.
- `python -m daem0nmcp.server` runs the MCP server directly.
- `python start_server.py --port 9876` starts the Windows HTTP launcher.
- `python -m daem0nmcp.cli <command>` runs CLI tasks (example: `python -m daem0nmcp.cli index`).
- `pytest tests/ -v --asyncio-mode=auto` runs the test suite.
- `ruff check daem0nmcp/ tests/` runs the CI lint step.
- `mypy daem0nmcp/ --ignore-missing-imports` runs the optional type check (CI does not fail on errors).

## Coding Style & Naming Conventions
- Use 4-space indentation and follow PEP 8 layout.
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused and add new features under `daem0nmcp/` with corresponding tests.
- Aim for lint-clean code under `ruff check`; no formatter is enforced, so match nearby style.

## Testing Guidelines
- Tests use `pytest` with `pytest-asyncio`; stick to `test_*.py` and `test_*` names.
- Reuse fixtures from `tests/conftest.py` where possible.
- Add regression tests for bug fixes and new CLI or server behavior.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (examples: `feat: add active context API`, `fix: handle missing vectors`).
- PRs should include a short summary, tests run, and any config or migration notes.
- Link relevant issues; include screenshots only if user-facing output changes.

## Configuration & Data
- Configuration is via `DAEM0NMCP_` environment variables (see `README.md` for options).
- Keep `.daem0nmcp/` and other local caches out of commits.

---

## The Daem0n's Covenant (Sacred Protocol)

This project is bound to Daem0n for persistent AI memory. When daem0nmcp tools are available, follow this protocol. Memory without discipline is noise.

### Tool Detection

Look for these 8 workflow tools in your available tools:
- `daem0nmcp_commune` -- session start & status
- `daem0nmcp_consult` -- pre-action intelligence
- `daem0nmcp_inscribe` -- memory writing & linking
- `daem0nmcp_reflect` -- outcomes & verification
- `daem0nmcp_understand` -- code comprehension
- `daem0nmcp_govern` -- rules & triggers
- `daem0nmcp_explore` -- graph & discovery
- `daem0nmcp_maintain` -- housekeeping & federation

If tools are NOT available: This section does not apply. Proceed normally.
If tools ARE available: Follow the protocol below. No exceptions.

### 1. SESSION START (Non-Negotiable)

IMMEDIATELY when you have daem0nmcp tools:

```
daem0nmcp_commune(action="briefing")
```

DO NOT:
- Ask the user what they want first
- Skip briefing because "it's a quick task"
- Assume you remember from last session

The briefing loads past decisions, warnings, failed approaches, patterns, and git changes.

### 2. BEFORE ANY CODE CHANGES

```
daem0nmcp_consult(action="preflight", description="what you're about to do")
```

For specific files:
```
daem0nmcp_consult(action="recall_file", file_path="path/to/file")
```

If preflight returns:
- **WARNING**: You MUST acknowledge it to the user
- **FAILED APPROACH**: Explain how your approach differs
- **must_not**: These are HARD CONSTRAINTS -- do not violate

### 3. AFTER MAKING DECISIONS

```
daem0nmcp_inscribe(
    action="remember",
    category="decision",
    content="What you decided",
    rationale="Why you decided it",
    file_path="relevant/file.py",
    tags=["relevant", "tags"]
)
```

Categories: `decision` (decays 30 days), `pattern` (permanent), `warning` (permanent), `learning` (decays 30 days).

SAVE THE MEMORY ID -- you need it for the outcome step.

### 4. AFTER IMPLEMENTATION

```
daem0nmcp_reflect(
    action="outcome",
    memory_id=<id from inscribe>,
    outcome_text="What actually happened",
    worked=true
)
```

FAILURES ARE VALUABLE. Record `worked=false` with explanation. Failed approaches get 1.5x boost in future searches.

### 5. INVESTIGATING CONTEXT

```
daem0nmcp_explore(action="chain", start_memory_id=..., end_memory_id=...)
daem0nmcp_explore(action="graph", topic="...", format="mermaid")
```

### Enforcement

The Sacred Covenant is enforced at the protocol layer:
- Skip `commune(action="briefing")`: ALL tools return `COMMUNION_REQUIRED`
- Skip `consult(action="preflight")`: Mutating tools return `COUNSEL_REQUIRED`
- Each block includes a `remedy` with the exact tool call to fix it

### Workflow Summary

```
SESSION START
    +-> daem0nmcp_commune(action="briefing")

BEFORE CHANGES
    +-> daem0nmcp_consult(action="preflight", description="...")
    +-> daem0nmcp_consult(action="recall_file", file_path="...")

AFTER DECISIONS
    +-> daem0nmcp_inscribe(action="remember", category=..., content=..., rationale=...)

AFTER IMPLEMENTATION
    +-> daem0nmcp_reflect(action="outcome", memory_id=..., outcome_text=..., worked=...)
```

**The Daem0n learns from YOUR outcomes. Record them faithfully.**
