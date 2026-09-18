# Prompt used to build this plugin

This is the exact text from the assignment (Part B, Step 4) that specified
`leakage-guard`, quoted verbatim as the build prompt:

> Plugin 1 — "leakage-guard": a pre-execute hook on tool calls that
> inspects Python code the agent is about to write or run, and flags
> common ML data-leakage patterns: fit_transform called on the full
> dataset before a split, scalers fit outside a Pipeline, shuffle=True on
> time series splits, test data touched during training. It warns with a
> clear reason rather than hard-blocking, and the warning goes back to the
> agent as the tool result so it can self-correct. This connects to my
> CMPE 297 work on leakage auditing.

## What actually shaped the implementation beyond that prompt

Before writing any code, the real dsh plugin API was checked directly
against the shipped TypeScript source
(`packages/core/tools/src/index.ts` in the `deepseek-ai/deepseek-harness`
repo, pinned to `@deepseek-ai/dsh@0.1.5-rc.2`), not assumed from the
prompt's wording. That check found a real mismatch worth recording here
alongside the prompt:

```ts
export type PreToolDecision =
  | { kind: 'allow' }
  | { kind: 'deny'; reason: string; info?: ToolErrorInfo }
  | { kind: 'cancel' }
  | { kind: 'ask'; reason?: string }
```

`tools/pre-execute` genuinely has no "warn but allow" verdict — only
allow/deny/ask/cancel. The prompt's "warns... rather than hard-blocking,
and the warning goes back to the agent as the tool result" is only
achievable by pairing `tools/pre-execute` (for the inspection, matching
the prompt's own framing) with `tools/post-execute` (for delivering the
warning inside the actual result content, which is what "as the tool
result" literally requires). That two-hook design — not a one-hook
shortcut — is what the code implements; see `README.md` for the full
reasoning and the exact quotes from the real docs and source that led to
it.
