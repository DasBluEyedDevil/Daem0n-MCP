---
description: Store a memory in Daem0n (decision, pattern, warning, or learning)
---

Store the following as a memory using `daem0nmcp_inscribe`:

$ARGUMENTS

Determine the appropriate category from the content:
- "decision" for architectural or design choices
- "pattern" for recurring approaches to follow
- "warning" for things to avoid
- "learning" for lessons from experience

Call `daem0nmcp_inscribe(action="remember", category=<chosen>, content=<the memory>, rationale=<why this matters>)`.

Report the memory ID after storage. The user will need this for outcome tracking.
