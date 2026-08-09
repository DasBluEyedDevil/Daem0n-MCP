# Multi-Repository Setup Guide (v7)

Daem0n v7 identifies every registered repository with an opaque
`workspace_id`. Tool inputs and resource URIs use that ID, never a filesystem
root. Register roots in server configuration before starting either stdio or
Streamable HTTP at `/mcp`.

## Choose an ownership model

### Consolidated parent workspace

Use one registered parent workspace when the repositories share lifecycle and
access policy:

```text
/workspace/                 -> ws_parent
├── backend/
└── client/
```

Start the session and query the shared record stream with the parent ID:

```text
session_brief(workspace_id="ws_000000000000000000000001")
memory_recall(
    workspace_id="ws_000000000000000000000001",
    query="authentication across backend and client",
    limit=10
)
```

### Linked workspaces

Register each repository separately when it needs independent ownership,
authorization, export, or archival:

```text
/workspace/backend/         -> ws_000000000000000000000002
/workspace/client/          -> ws_000000000000000000000003
```

`workspace_link` is protected. Preflight its exact arguments first:

```text
memory_preflight(
    workspace_id="ws_000000000000000000000002",
    target_tool="workspace_link",
    target_arguments={
        "linked_workspace_id": "ws_000000000000000000000003",
        "relationship": "same-project"
    }
)
workspace_link(
    workspace_id="ws_000000000000000000000002",
    linked_workspace_id="ws_000000000000000000000003",
    relationship="same-project",
    preflight_token="<token-from-memory_preflight>"
)
```

Linked recall remains explicit: provide authorized `linked_workspace_ids` to
`memory_recall`. The server resolves every ID before reading and does not infer
workspace scope from paths.

## Consolidating registered workspaces

Consolidation appends canonical v7 events to the target workspace. It is a
protected replay-safe write, so use the same exact arguments for preflight and
reuse the idempotency key on retry:

```text
memory_preflight(
    workspace_id="ws_000000000000000000000001",
    target_tool="workspace_consolidate",
    target_arguments={
        "source_workspace_ids": [
            "ws_000000000000000000000002",
            "ws_000000000000000000000003"
        ],
        "idempotency_key": "consolidate-product-2026-0001"
    }
)
workspace_consolidate(
    workspace_id="ws_000000000000000000000001",
    source_workspace_ids=[
        "ws_000000000000000000000002",
        "ws_000000000000000000000003"
    ],
    idempotency_key="consolidate-product-2026-0001",
    preflight_token="<token-from-memory_preflight>"
)
```

Use `workspace_consolidate_and_archive_sources` only when source archival is
intentional and separately authorized. Verify the target with `system_health`
and bounded recall before archiving anything.

## Read-only workspace context

Replace `{workspace_id}` with the exact registered ID:

- `memory://workspaces/{workspace_id}/warnings`
- `memory://workspaces/{workspace_id}/failures`
- `memory://workspaces/{workspace_id}/rules`
- `memory://workspaces/{workspace_id}/active-context`

For a v6 installation, migrate/register the repositories before using these
examples. The generated mapping at
[`docs/v6-to-v7-tools.json`](v6-to-v7-tools.json) documents every v6 split or
rename.
