/**
 * Daem0n Covenant Enforcement Plugin for OpenCode
 *
 * Mirrors the 5-hook discipline from Claude Code's hooks system:
 *   1. System prompt injection (covenant rules in every LLM call)
 *   2. Pre-edit enforcement (preflight token required)
 *   3. Pre-bash enforcement (must_not rule checking)
 *   4. Post-edit suggestions (informational, never blocks)
 *   5. Session lifecycle events (best-effort, never blocks)
 *
 * All enforcement logic lives in Python hook modules.
 * This TypeScript file is ONLY a shell-out wrapper -- zero duplication.
 */

import type { Plugin } from "@opencode-ai/plugin";

// ---------------------------------------------------------------------------
// Covenant rules injected into every system prompt
// ---------------------------------------------------------------------------

const COVENANT_RULES_FULL = `<daem0n-covenant>
## The Daem0n v7 Covenant

This project is bound to Daem0n for persistent AI memory. When daem0nmcp tools
are available, use the exact workspace-scoped v7 tools. The core names are
session_brief, memory_preflight, memory_recall, memory_store,
memory_record_outcome, and system_health.

### 1. SESSION START (Non-Negotiable)
IMMEDIATELY call:
daem0nmcp_session_brief(workspace_id="<workspace_id>")

Use daem0nmcp_memory_recall(workspace_id="<workspace_id>", query="...", limit=10)
for relevant history. Before a protected operation call:
daem0nmcp_memory_preflight(workspace_id="<workspace_id>", target_tool="<exact-tool>", target_arguments={<exact arguments>})
Respect warnings, failed approaches, and must_not constraints. A preflight token
is valid only for the exact workspace, principal, session, tool, and arguments.

### 3. AFTER MAKING DECISIONS
Call daem0nmcp_memory_store with the same target arguments, a stable
idempotency_key, and the returned preflight_token. Save its record_id.

### 4. AFTER IMPLEMENTATION
Call: daem0nmcp_memory_record_outcome(workspace_id="<workspace_id>", record_id="<mem_id>", outcome_text="...", worked=true|false, idempotency_key="<stable-key>")
Failures are valuable. Record worked=false with an explanation.

Use daem0nmcp_system_health(workspace_id="<workspace_id>") for diagnostics.
Read-only resources use memory://workspaces/{workspace_id}/warnings, /failures,
/rules, and /active-context. Supported transports are stdio and Streamable HTTP
at /mcp. Migration mapping: docs/v6-to-v7-tools.json.
</daem0n-covenant>`;

const COVENANT_RULES_SIMPLIFIED = `<daem0n-covenant mode="simplified">
## Memory Protocol (Required Steps)

This project uses Daem0n for persistent AI memory. Follow these 4 steps:

1. START: daem0nmcp_session_brief(workspace_id="<workspace_id>")
2. RECALL: daem0nmcp_memory_recall(workspace_id="<workspace_id>", query="...", limit=10)
3. PREFLIGHT: daem0nmcp_memory_preflight(workspace_id="<workspace_id>", target_tool="memory_store", target_arguments={<exact arguments>})
4. STORE: daem0nmcp_memory_store(workspace_id="<workspace_id>", record_type="decision", content="...", idempotency_key="<stable-key>", preflight_token="<token>")
5. OUTCOME: daem0nmcp_memory_record_outcome(workspace_id="<workspace_id>", record_id="<mem_id>", outcome_text="...", worked=true|false, idempotency_key="<stable-key>")

Rules:
- Never use paths as workspace selectors.
- Reuse an idempotency key when retrying the same write.
- Use daem0nmcp_system_health for diagnostics.
- Exact host-prefixed names are accepted; lookalike substrings are not.
- Migration mapping: docs/v6-to-v7-tools.json.
</daem0n-covenant>`;

// ---------------------------------------------------------------------------
// Shell-out helper
// ---------------------------------------------------------------------------

type HookResult = { exitCode: number; stdout: string; stderr: string };

/**
 * Run a Python hook module via BunShell. Returns a normalized result.
 * On ANY failure (Python missing, timeout, crash), returns exitCode 0
 * so the host IDE is never broken by hook infrastructure.
 */
async function runHook(
  $: Parameters<Plugin>[0]["$"],
  directory: string,
  module: string,
  env: Record<string, string>,
  _timeoutMs?: number,
): Promise<HookResult> {
  try {
    const hookEnv: Record<string, string> = {
      CLAUDE_PROJECT_DIR: directory,
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
      ...env,
    };
    const shell = $.nothrow().env(hookEnv);
    // BunShell template literals require static strings for the command.
    // Build the full module path as a variable and interpolate it.
    const mod = `daem0nmcp.claude_hooks.${module}`;
    const result = await shell`python -m ${mod}`.quiet();
    return {
      exitCode: result.exitCode,
      stdout: result.stdout.toString().trim(),
      stderr: result.stderr.toString().trim(),
    };
  } catch {
    // Graceful degradation: Python not found, timeout, or any other error.
    // Never crash the host IDE.
    return { exitCode: 0, stdout: "", stderr: "" };
  }
}

// ---------------------------------------------------------------------------
// Tool name classification helpers
// ---------------------------------------------------------------------------

function isEditTool(tool: string): boolean {
  const t = tool.toLowerCase();
  return t.includes("edit") || t.includes("write") || t.includes("notebookedit");
}

function isBashTool(tool: string): boolean {
  const t = tool.toLowerCase();
  return t.includes("bash") || t.includes("shell");
}

// ---------------------------------------------------------------------------
// Plugin export
// ---------------------------------------------------------------------------

export const Daem0nPlugin: Plugin = async ({ $, directory }) => {
  return {
    // -----------------------------------------------------------------------
    // HOOK 1: System prompt injection
    // Every LLM call sees the covenant rules.
    // -----------------------------------------------------------------------
    "experimental.chat.system.transform": async (input, output) => {
      const provider = input.model?.providerID ?? "unknown";
      const modelId = input.model?.id ?? "unknown";
      const isClaude = provider === "anthropic" || modelId.toLowerCase().includes("claude");

      output.system.push(isClaude ? COVENANT_RULES_FULL : COVENANT_RULES_SIMPLIFIED);

    },

    // -----------------------------------------------------------------------
    // HOOK 2: Pre-tool enforcement (pre-edit + pre-bash)
    // Blocks edits without preflight token (exit 2 from Python).
    // Blocks bash commands matching must_not rules (exit 2 from Python).
    // -----------------------------------------------------------------------
    "tool.execute.before": async (input, output) => {
      if (isEditTool(input.tool)) {
        const result = await runHook($, directory, "pre_edit", {
          TOOL_INPUT: JSON.stringify(output.args ?? {}),
        });
        if (result.exitCode === 2) {
          throw new Error(
            result.stderr || result.stdout || "[Daem0n blocks] Preflight required",
          );
        }
      }

      if (isBashTool(input.tool)) {
        const result = await runHook($, directory, "pre_bash", {
          TOOL_INPUT: JSON.stringify(output.args ?? {}),
        });
        if (result.exitCode === 2) {
          throw new Error(
            result.stderr || result.stdout || "[Daem0n blocks] Rule violation",
          );
        }
      }
    },

    // -----------------------------------------------------------------------
    // HOOK 3: Post-edit suggestions (informational, never blocks)
    // Suggests replay-safe v7 memory calls for significant changes.
    // -----------------------------------------------------------------------
    "tool.execute.after": async (input, output) => {
      try {
        if (isEditTool(input.tool)) {
          const result = await runHook(
            $,
            directory,
            "post_edit",
            { TOOL_INPUT: JSON.stringify({}) },
            5000,
          );
          if (result.stdout) {
            output.output = (output.output || "") + "\n" + result.stdout;
          }
        }
      } catch {
        // Never throw from post-edit. Informational only.
      }
    },

    // -----------------------------------------------------------------------
    // HOOK 4: Session lifecycle events (best-effort, never blocks)
    // session.created  -> session_start hook (auto-briefing)
    // session.idle     -> stop hook (fail-closed memory suggestions)
    // -----------------------------------------------------------------------
    event: async ({ event }) => {
      try {
        if (event.type === "session.created") {
          await runHook($, directory, "session_start", {}, 5000);
        } else if (event.type === "session.idle") {
          await runHook(
            $,
            directory,
            "stop",
            { CLAUDE_TRANSCRIPT_PATH: "" },
            15000,
          );
        }
      } catch {
        // Never throw from event hooks. Best-effort only.
      }
    },
  };
};
