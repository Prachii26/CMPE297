# Prompt used to build this plugin

This is the exact text from the assignment (Part B, Step 4) that specified
`session-cost-panel`, quoted verbatim as the build prompt:

> Plugin 2 — "session-cost-panel": tracks tokens and cost per model call
> across a session, and surfaces a running total plus a per-tool-call
> breakdown in the UI. Persist it so the number survives a reload.

The follow-up instruction from Step 2 of the same conversation also
shaped this plugin directly and is recorded here because it changed the
actual code, not just the README:

> For session-cost-panel, label the cost figures as estimated, not
> measured, since DSH has no dollar-cost field and the price table is
> illustrative.

## What actually shaped the implementation beyond that prompt

Checked against the real session event types
(`docs/subsystems/session.md`) before writing anything: `TokenUsage`
(`packages/llm/llm`) has `inputTokens`/`outputTokens`/etc. but **no dollar
field at all** — unlike OpenRouter's own `usage.include` extension used
directly in this assignment's Part A. That is the direct cause of the
"estimated, not measured" instruction above, and it is why every
user-facing string in this plugin says "ESTIMATED" rather than just
computing and printing a number that looks authoritative.

The UI surface itself was also a real decision, not the obvious one:
building a true custom Web Client "Chat node" (`ConversationNodeDefinition`
+ keyed renderer, per `docs/cookbook/extension-cookbook.md`'s feature map)
needs a client-side bundle build step the docs themselves say has "no
published preset... outside this repository"
(`docs/cookbook/adding-a-settings-card.md`). Given that real constraint,
this plugin instead uses `ctx.commands.register()` (`/cost`) — a
documented, host-side-only extension point
(`packages/interaction/commands/README.md`) whose result the Web UI
renders directly in the transcript, outside model history. That is a
deliberate scope decision, recorded here rather than silently swapped in
for the harder client-bundle path.
