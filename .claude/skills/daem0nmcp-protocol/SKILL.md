---
name: daem0nmcp-protocol
description: Enforce the Daem0n v7 scoped session, exact preflight, replay-safe memory, and outcome protocol
---

# Daem0n v7 Protocol

Apply this skill whenever the Daem0n v7 tools are available.

## Detection

Recognize each canonical tool in bare form and with either host prefix:

| Canonical | OpenCode | Claude Code |
|---|---|---|
| `session_brief` | `daem0nmcp_session_brief` | `mcp__daem0nmcp__session_brief` |
| `memory_preflight` | `daem0nmcp_memory_preflight` | `mcp__daem0nmcp__memory_preflight` |
| `memory_recall` | `daem0nmcp_memory_recall` | `mcp__daem0nmcp__memory_recall` |
| `memory_store` | `daem0nmcp_memory_store` | `mcp__daem0nmcp__memory_store` |
| `memory_record_outcome` | `daem0nmcp_memory_record_outcome` | `mcp__daem0nmcp__memory_record_outcome` |
| `system_health` | `daem0nmcp_system_health` | `mcp__daem0nmcp__system_health` |

Do not treat a substring or an older workflow name as a match.

## Required sequence

1. Establish the authenticated workspace session:

   ```text
   mcp__daem0nmcp__session_brief(workspace_id="<workspace_id>")
   ```

2. Recall relevant context when needed:

   ```text
   mcp__daem0nmcp__memory_recall(
       workspace_id="<workspace_id>",
       query="the planned change",
       limit=10
   )
   ```

3. Before a protected call, request a token bound to its exact arguments:

   ```text
   mcp__daem0nmcp__memory_preflight(
       workspace_id="<workspace_id>",
       target_tool="memory_store",
       target_arguments={
           "record_type": "decision",
           "content": "Use append-only events",
           "idempotency_key": "decision-events-0001"
       }
   )
   ```

4. Execute that exact request with the returned token:

   ```text
   mcp__daem0nmcp__memory_store(
       workspace_id="<workspace_id>",
       record_type="decision",
       content="Use append-only events",
       idempotency_key="decision-events-0001",
       preflight_token="<token-from-memory_preflight>"
   )
   ```

5. After verification, record the outcome:

   ```text
   mcp__daem0nmcp__memory_record_outcome(
       workspace_id="<workspace_id>",
       record_id="<mem_id>",
       outcome_text="The event replay tests passed",
       worked=true,
       idempotency_key="outcome-events-0001"
   )
   ```

Use `worked=false` for failed approaches and explain the failure. Retry a write
with the same idempotency key; never mint a new key merely because a response
was lost.

## Boundaries

- A `preflight_token` authorizes only the exact workspace, tool, arguments,
  principal, and session for which it was issued.
- Never infer identity from headers, network address, client information, or
  `_client_meta`.
- Treat `must_not` guidance as a hard constraint.
- Use `system_health(workspace_id="<workspace_id>")` for diagnostics.
- Use stdio or Streamable HTTP at `/mcp`.

Read-only context is also available at:

- `memory://workspaces/{workspace_id}/warnings`
- `memory://workspaces/{workspace_id}/failures`
- `memory://workspaces/{workspace_id}/rules`
- `memory://workspaces/{workspace_id}/active-context`

For a v6 migration, consult the generated
[`docs/v6-to-v7-tools.json`](../../../docs/v6-to-v7-tools.json) mapping. It is
the authoritative reference for renamed and split operations.
