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
## The Daem0n's Covenant (Sacred Protocol)

This project is bound to Daem0n for persistent AI memory. When daem0nmcp tools
are available, follow this protocol. Memory without discipline is noise.

### 1. SESSION START (Non-Negotiable)
IMMEDIATELY call: daem0nmcp_commune(action="briefing")
Do NOT skip. Do NOT ask the user first. The briefing loads past decisions,
warnings, failed approaches, patterns, and git changes.

### 2. BEFORE ANY CODE CHANGES
Call: daem0nmcp_consult(action="preflight", description="what you plan to do")
For specific files: daem0nmcp_consult(action="recall_file", file_path="...")
Respect warnings, failed approaches, and must_not constraints.

### 3. AFTER MAKING DECISIONS
Call: daem0nmcp_inscribe(action="remember", category="decision|pattern|warning|learning", content="...", rationale="...", file_path="...", tags=[...])
Save the memory ID for the outcome step.

### 4. AFTER IMPLEMENTATION
Call: daem0nmcp_reflect(action="outcome", memory_id=<id>, outcome_text="...", worked=true|false)
Failures are valuable -- record worked=false with explanation.

### Enforcement
- Skip briefing: ALL tools return COMMUNION_REQUIRED with remedy
- Skip preflight: Mutating tools return COUNSEL_REQUIRED with remedy
- Each block includes the exact tool call to fix it
</daem0n-covenant>`;

const COVENANT_RULES_SIMPLIFIED = `<daem0n-covenant mode="simplified">
## Memory Protocol (Required Steps)

This project uses Daem0n for persistent AI memory. Follow these 4 steps:

1. START: Call daem0nmcp_commune(action="briefing") first
2. BEFORE CHANGES: Call daem0nmcp_consult(action="preflight", description="<plan>")
3. SAVE DECISIONS: Call daem0nmcp_inscribe(action="remember", category="decision", content="<what>", rationale="<why>", tags=["tag1","tag2"])
4. RECORD RESULT: Call daem0nmcp_reflect(action="outcome", memory_id=<id>, outcome_text="<result>", worked=true|false)

Rules:
- Step 1 is required before any other steps
- Step 2 is required before editing files
- Step 3 requires: content (what happened), rationale (why it matters), tags (at least one)
- Step 4 requires the memory_id returned from step 3
</daem0n-covenant>`;

// Module-level state tracking current LLM model (safe: one model per plugin session)
let currentModel: { providerID: string; modelID: string } | null = null;

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

      // Track model for _client_meta injection in tool calls
      currentModel = { providerID: provider, modelID: modelId };
    },

    // -----------------------------------------------------------------------
    // HOOK 2: Pre-tool enforcement (pre-edit + pre-bash)
    // Blocks edits without preflight token (exit 2 from Python).
    // Blocks bash commands matching must_not rules (exit 2 from Python).
    // -----------------------------------------------------------------------
    "tool.execute.before": async (input, output) => {
      // Inject client metadata for daem0nmcp tools (server-side provenance tracking)
      const toolLower = input.tool?.toLowerCase() ?? "";
      if (toolLower.startsWith("daem0nmcp_") || toolLower.includes("mcp__daem0nmcp__")) {
        if (currentModel && output.args) {
          output.args._client_meta = JSON.stringify({
            client: "opencode",
            providerID: currentModel.providerID,
            modelID: currentModel.modelID,
          });
        }
      }

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
    // Suggests remembering significant changes via inscribe().
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
    // session.idle     -> stop hook (auto-capture decisions)
    // -----------------------------------------------------------------------
    event: async ({ event }) => {
      try {
        if (event.type === "session.created") {
          currentModel = null;
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
