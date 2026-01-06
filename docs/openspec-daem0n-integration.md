# OpenSpec + Daem0n-MCP Integration

This guide explains how to integrate OpenSpec (spec-driven development) with Daem0n-MCP (AI memory system) for a complete development feedback loop.

## The Value

```
OpenSpec defines WHAT to build  ─────►  Daem0n remembers HOW IT WENT
         ▲                                         │
         │         ◄──── feedback loop ────►       │
         │                                         │
    Future specs are informed by past outcomes
```

**Benefits:**
- Past failures inform new proposals ("we tried X before, it failed")
- Spec requirements become enforced rules
- Archived changes become queryable learnings
- Decision history persists across sessions

## Setup

### 1. Install Daem0n-MCP

See [Daem0n-MCP README](https://github.com/DasBluEyedDevil/Daem0n-MCP) for installation.

### 2. Enable Auto-Detection

The integration auto-activates when both are present:
- Daem0n-MCP tools available
- `openspec/` directory exists in project

No additional configuration needed.

## AGENTS.md Snippet

Add this to your project's `AGENTS.md` or `CLAUDE.md` to enable the integration:

```markdown
## Daem0n-MCP Integration

This project uses Daem0n-MCP for AI memory. When Daem0n tools are available:

### On Session Start
After `get_briefing()`, OpenSpec specs are automatically imported as:
- **Patterns**: Spec overviews and SHOULD requirements
- **Rules**: MUST/MUST NOT requirements become semantic rules
- **Warnings**: Known limitations and constraints

### Before Creating Proposals
Before drafting an OpenSpec change proposal:
1. Query memory: `recall("[feature topic]")`
2. Check rules: `check_rules("proposing [feature]")`
3. Review past decisions for similar features

This surfaces:
- Previous failed approaches to avoid
- Patterns that worked
- Relevant rules from existing specs

### After Archiving Changes
When a change is archived via `openspec archive [id]`:
1. Record the outcome: `record_outcome(decision_id, outcome, worked)`
2. Create learnings from the implementation
3. Link proposal to learnings for traceability

### Workflow Summary
```
SESSION START
    └─> get_briefing()
    └─> [auto] Import OpenSpec specs if not already done

BEFORE PROPOSAL
    └─> recall("[feature]")
    └─> check_rules("proposing [feature]")
    └─> remember(decision about proposal intent)

AFTER ARCHIVE
    └─> record_outcome(proposal_id, outcome, worked)
    └─> remember_batch(learnings)
    └─> link_memories(proposal → learnings)
```
```

## Trigger Phrases

The `openspec-daem0n-bridge` skill responds to:

| Phrase | Action |
|--------|--------|
| "sync specs to memory" | Force re-import all specs |
| "import openspec" | Same as above |
| "prepare proposal for X" | Query memory before proposing |
| "check before proposing X" | Same as above |
| "record outcome for [id]" | Convert archived change to learnings |

## How Data Flows

### OpenSpec → Daem0n

| OpenSpec Source | Daem0n Destination |
|-----------------|-------------------|
| `specs/*/spec.md` overview | Pattern memory |
| MUST requirements | Rule with must_do |
| MUST NOT constraints | Rule with must_not |
| SHOULD patterns | Pattern memory |
| SHOULD NOT anti-patterns | Warning memory |
| Known limitations | Warning memory |

### Daem0n → OpenSpec

| Daem0n Source | OpenSpec Usage |
|---------------|----------------|
| Past failed decisions | Avoid in new proposals |
| Successful patterns | Include in new proposals |
| Existing spec rules | Validate proposal consistency |
| Linked learnings | Inform implementation approach |

## Tags Convention

All integration memories use these tags:

| Tag | Meaning |
|-----|---------|
| `openspec` | From OpenSpec integration |
| `spec` | From spec.md file |
| `proposal` | From change proposal |
| `pending` | Proposal not yet archived |
| `completed` | From archived change |

Query with: `recall(topic="X", tags=["openspec"])`

## Example Workflow

```
User: I want to add rate limiting to the API

Claude: [Queries Daem0n memory]

        # Memory Context for Proposal: rate limiting

        ## Relevant Specs
        - api-endpoints: "All endpoints MUST include rate limiting headers"
        - security: "Rate limits SHOULD be configurable per client"

        ## Past Decisions
        - Token bucket vs sliding window: chose sliding window (worked=true)
        - Redis-based rate limiting rejected due to latency (worked=false)

        ## Rules
        MUST: Include X-RateLimit-* headers
        MUST NOT: Use in-memory rate limiting in production

        Ready to create the proposal?

User: Yes, let's proceed

Claude: [Records decision]
        Creating openspec/changes/add-rate-limiting/proposal.md...

[After implementation and archiving]

User: Archive is complete

Claude: [Records outcome, creates learnings, links memories]
        Recorded outcome: Rate limiting implemented with sliding window
        Created 2 learnings about the implementation
        Linked to proposal decision for future reference
```

## Troubleshooting

### Specs not importing
- Verify `openspec/specs/` directory exists
- Check that spec.md files are valid markdown
- Run "sync specs to memory" to force import

### Past decisions not surfacing
- Ensure `record_outcome()` was called on previous decisions
- Check tags: `recall(tags=["openspec"])`
- Try broader search: `search_memories("feature name")`

### Rules not matching
- List rules: `list_rules()`
- Check trigger wording matches your action description
- Rules use semantic matching, not exact keywords

## Related Documentation

- [Daem0n-MCP README](https://github.com/DasBluEyedDevil/Daem0n-MCP)
- [OpenSpec Documentation](https://github.com/Fission-AI/OpenSpec)
- [Sacred Covenant Protocol](.claude/skills/daem0nmcp-protocol/SKILL.md)
