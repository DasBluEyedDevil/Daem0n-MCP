# Summon Daem0n v7 in Claude Code

This is the maintained Claude Code ritual for Daem0n v7. It uses opaque
workspace selectors, replay-safe writes, and the authenticated MCP invocation
scope. Do not substitute a filesystem path for `workspace_id`, and do not
invent transport identity fields.

## 1. Detect the v7 tools

The core ritual tools are:

- `session_brief`
- `memory_preflight`
- `memory_recall`
- `memory_store`
- `memory_record_outcome`
- `system_health`

Claude Code normally exposes them as `mcp__daem0nmcp__<tool>`. Hosts may also
show the bare name or the `daem0nmcp_<tool>` form. Detect only those exact
forms. If none is present, install or reconnect the MCP server; do not guess a
retired tool name.

## 2. Connect the server

Daem0n v7 supports stdio and Streamable HTTP.

For a user-scoped stdio connection:

```bash
python -m pip install -e "/path/to/Daem0n-MCP"
claude mcp add daem0nmcp --scope user -- python -m daem0nmcp.server
claude mcp list
```

For Streamable HTTP, start the launcher and point the Claude MCP configuration
at its single MCP endpoint:

```bash
python start_server.py --port 9876
```

```json
{
  "mcpServers": {
    "daem0nmcp": {
      "type": "http",
      "url": "http://127.0.0.1:9876/mcp"
    }
  }
}
```

Restart Claude Code after changing MCP configuration. Use `system_health` for
diagnostics once the tools are visible:

```text
mcp__daem0nmcp__system_health(
    workspace_id="<opaque-workspace-id>"
)
```

## 3. Begin every scoped session

Use the configured, opaque workspace selector exactly as issued. The first
scoped call is:

```text
mcp__daem0nmcp__session_brief(
    workspace_id="<opaque-workspace-id>"
)
```

The server-issued session and authenticated transport establish scope. Request
headers, addresses, client descriptions, and arbitrary caller-supplied metadata
are not identity inputs.

## 4. Recall relevant history

Use bounded recall when prior decisions, warnings, or failures may affect the
task:

```text
mcp__daem0nmcp__memory_recall(
    workspace_id="<opaque-workspace-id>",
    query="authentication",
    limit=10
)
```

Treat returned evidence as counsel. Respect `must_not`, warnings, and failed
approaches before protected work.

## 5. Preflight the exact protected request

Before `memory_store`, call `memory_preflight` for that exact tool and its exact
arguments. Exclude only `workspace_id` and `preflight_token` from
`target_arguments`:

```text
mcp__daem0nmcp__memory_preflight(
    workspace_id="<opaque-workspace-id>",
    target_tool="memory_store",
    target_arguments={
        "record_type": "decision",
        "content": "Use signed session cookies",
        "rationale": "Avoid shared server-side session state",
        "idempotency_key": "decision-auth-cookie-0001"
    },
    description="Record the authentication decision"
)
```

Use the returned `preflight_token` only once with the exact request it
authorizes. If the arguments change, request a new preflight.

## 6. Store durable knowledge replay-safely

Every write needs a stable idempotency key. Retries of the same logical write
must reuse the same key and exact payload:

```text
mcp__daem0nmcp__memory_store(
    workspace_id="<opaque-workspace-id>",
    record_type="decision",
    content="Use signed session cookies",
    rationale="Avoid shared server-side session state",
    idempotency_key="decision-auth-cookie-0001",
    preflight_token="<token-from-memory_preflight>"
)
```

Keep the returned opaque `record_id`. Never replace it with a legacy numeric
identifier.

## 7. Record the verified outcome

When the result is known, record success or failure with a separate stable
idempotency key:

```text
mcp__daem0nmcp__memory_record_outcome(
    workspace_id="<opaque-workspace-id>",
    record_id="<record-id-from-memory_store>",
    outcome_text="Focused and integration tests passed",
    worked=true,
    idempotency_key="outcome-auth-cookie-0001"
)
```

Failures are durable evidence. Use `worked=false` and state precisely what
failed.

## 8. Read bounded workspace resources

The maintained v7 resources are:

```text
memory://workspaces/{workspace_id}/warnings
memory://workspaces/{workspace_id}/failures
memory://workspaces/{workspace_id}/rules
memory://workspaces/{workspace_id}/active-context
```

These resources are read-only views. Domain writes go through admitted v7 MCP
tools, never through a direct database, script, or memory-writing CLI command.

## 9. Hook behavior

The root hook templates are advisory and read-only. The pre-edit hook fails
closed because a standalone process cannot validate a scoped capability. It
directs Claude Code to the exact `memory_recall` and `memory_preflight` calls.
Post-edit and Stop hooks print replay-safe `memory_store` and
`memory_record_outcome` suggestions; they do not mutate Daem0n storage.

Install the packaged hook configuration with:

```bash
python -m daem0nmcp.cli install-claude-hooks
```

## 10. Migration reference

The generated source of truth for renamed or split v6 capabilities is
[`docs/v6-to-v7-tools.json`](docs/v6-to-v7-tools.json). Consult that mapping
instead of copying an older invocation into a prompt, hook, or skill.

The complete ritual is therefore: `session_brief`, bounded `memory_recall`,
exact `memory_preflight`, replay-safe `memory_store`, and verified
`memory_record_outcome`, with `system_health` available for diagnostics.
