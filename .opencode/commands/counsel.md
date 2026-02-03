---
description: Consult Daem0n before making changes (preflight check)
---

Call `daem0nmcp_consult(action="preflight", description="$ARGUMENTS")` immediately.

After receiving the preflight results:
1. Report any WARNINGS the user must know about
2. Report any FAILED APPROACHES that are relevant
3. Report any must_not constraints that apply
4. If no issues found, confirm it is safe to proceed

Do NOT skip this step. Do NOT ask for confirmation before calling the tool.
