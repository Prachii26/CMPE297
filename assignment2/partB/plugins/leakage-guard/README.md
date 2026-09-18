# leakage-guard

A DeepSeek Harness (dsh) plugin that inspects Python code the agent is
about to write or run, flags common ML data-leakage patterns, and warns
without blocking — the warning is delivered as part of the tool's own
result, so the agent reads it and can self-correct on its next turn.

Built for CMPE 297 Assignment 2 Part B, connecting to earlier
leakage-auditing work from this course (Assignment 1's CRISP-DM audit).
See [`PROMPT.md`](PROMPT.md) for the exact prompt this was built from.

## What it flags

Four heuristic checks, run over any Python code the agent is about to
introduce:

1. **`fit_transform` on the full dataset before a split** — a transformer
   fit on something that doesn't look like a training-only slice, in code
   that also calls `train_test_split(...)`.
2. **A scaler fit outside a `Pipeline`** — `StandardScaler`/`MinMaxScaler`/
   `RobustScaler`/`MaxAbsScaler`/`Normalizer` fit directly, with no
   `Pipeline(...)` wrapping it.
3. **`shuffle=True` on what looks like a time series** — shuffling
   alongside `TimeSeriesSplit` or a date/timestamp column lets future rows
   leak into training.
4. **Test data touched during a `.fit(...)` call** — any `.fit(` or
   `.fit_transform(` call whose arguments contain something named `test`.

**Honesty note:** these are regex heuristics over source text, not a real
Python AST analysis. They will miss cleverly-restructured leaky code and
can false-positive on code that merely *mentions* the word "test" near a
`.fit(` call. That's a deliberate, disclosed tradeoff — the same one
Part A's `stage_12_permissions` made for shell commands — not a hidden
limitation.

## How it hooks into the harness

The assignment's own wording calls this "a pre-execute hook." The real
dsh API doesn't quite allow that alone. `packages/core/tools/src/index.ts`
defines the pre-execute decision as:

```ts
export type PreToolDecision =
  | { kind: 'allow' } | { kind: 'deny'; reason; info? } | { kind: 'cancel' } | { kind: 'ask'; reason? }
```

There is no non-blocking "warn" verdict there — only allow, deny, ask, or
cancel. So this plugin uses **two** real, documented extension points
together:

```js
ctx.on('tools/pre-execute', async (exec, next) => {
  const code = extractCode(exec.name, exec.arguments)
  if (code) {
    const findings = runChecks(code)
    if (findings.length > 0) pendingFindings.set(exec.token, findings)
  }
  return next()   // never deny, never ask — the call always proceeds
})

ctx.on('tools/post-execute', async (exec, result, next) => {
  const decision = await next()
  const findings = pendingFindings.get(exec.token)
  if (!findings) return decision
  pendingFindings.delete(exec.token)
  if (decision.kind === 'block') return decision   // respect a stricter policy
  const baseContent = decision.kind === 'accept' && decision.content ? decision.content : result.content
  return { kind: 'accept', content: [...baseContent, { type: 'text', text: formatWarning(findings) }] }
})
```

- **`tools/pre-execute`** does the actual inspection — matching the
  assignment's framing that this looks at code *before* it runs — and
  stashes any finding keyed by the call's opaque `exec.token` (unique per
  call, shared between both hooks for the same call). It always calls
  `next()`, so the call is never denied or paused for approval.
- **`tools/post-execute`** is what makes "the warning goes back to the
  agent as the tool result" literally true: it takes the tool's real
  result content and appends the warning text to it, returning
  `{ kind: 'accept', ... }` — never `{ kind: 'block' }`. A `block` from
  a stricter policy plugin registered elsewhere is left untouched.

Both are documented, real extension points
(`docs/cookbook/extension-cookbook.md`'s permission-gate example shows the
exact `ctx.on('tools/pre-execute', async (exec, next) => {...})` shape
used here), not an improvisation.

`extractCode()` only looks at the tools that can actually introduce
Python: `write`/`edit` (checked when `file_path` ends in `.py`/`.ipynb`,
using `content` for `write` and `new_string` for `edit` — the exact field
names `packages/fs/tool-fs/README.md` documents) and `bash`/`pwsh`
(checked when the command looks like an inline `python -c "..."` call).

## Install

Not published to npm — loaded locally, exactly the way the "Your first
plugin" tutorial in the real docs describes for an unpublished plugin: an
absolute-path insert in a `cordis.yml` overlay.

```yaml
# Assignment2/partB/custom-plugins.patch.yml
- insert:
    - id: leakage-guard
      name: 'C:\Users\sarth\Desktop\297\CMPE297\assignment2\partB\plugins\leakage-guard\src\index.js'
```

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml
```

Confirmed **Enabled** with zero load errors in Settings → Plugins →
Plugin list (search "leakage-guard").

## Demo

Ask the agent to write a file with an intentionally leaky pattern, e.g.:

> Write a file called leaky_example.py with EXACTLY this code, do not fix
> or improve it: `scaler = StandardScaler(); X_scaled =
> scaler.fit_transform(X); X_train, X_test, y_train, y_test =
> train_test_split(X_scaled, y, test_size=0.2)`

The agent writes the file (not blocked), then its own reply quotes the
warning directly:

> "For the record, the leakage-guard heuristic flagged two things
> (fit_transform on the full X before the split, and a scaler fit outside
> a Pipeline)."

Screenshots:
[`../../screenshots/24-leakage-guard-full-turn.png`](../../screenshots/24-leakage-guard-full-turn.png)
(the full turn) and
[`../../screenshots/25-toolcall-expanded.png`](../../screenshots/25-toolcall-expanded.png)
(the expanded tool call trajectory, showing the model's own `Think` step
reacting to "a heuristic leak guard message").
