# session-cost-panel

A DeepSeek Harness (dsh) plugin that tracks estimated tokens and cost per
model call across a session, with a per-tool-call breakdown, surfaced via
a `/cost` command and persisted to disk so the number survives a reload.

Built for CMPE 297 Assignment 2 Part B. See [`PROMPT.md`](PROMPT.md) for
the exact prompt this was built from.

## Every cost figure here is an ESTIMATE, not a measurement

DSH's `TokenUsage` type (`packages/llm/llm`) has `inputTokens`,
`outputTokens`, `cacheReadTokens`, `cacheWriteTokens` — real, measured
token counts — but **no dollar-cost field at all**. Unlike this
assignment's Part A, where OpenRouter's `usage.include` extension returns
a real billed dollar amount per call, DSH has nothing equivalent to
return. This plugin multiplies real token counts by a small,
hand-maintained, illustrative price table (`PRICE_TABLE` in
`src/index.js`) — never fetched live, never a billing source of truth.
Every user-facing string says **"ESTIMATED, not measured"** for exactly
this reason; it is not decorative wording.

## How it hooks into the harness

Three real, documented dsh session events, listened to via one `ctx.on`
registration (`packages/core/session`):

```js
ctx.on('session/event', async (session, event) => {
  if (event.type === 'request/header') {
    // event.data.header.config.model -- which model is about to answer
  }
  if (event.type === 'assistant/message') {
    // event.data.usage -- real token counts for one step; priced here
  }
  if (event.type === 'tool/call') {
    // event.data.name -- which tool this SAME step's already-priced
    // usage should also count toward, for the per-tool breakdown
  }
})
```

The ordering matters and comes straight from `docs/subsystems/session.md`'s
turn/step flow: within one step, `assistant/message` (carrying `usage`)
is always logged *before* any `tool/call*` events for the tools that
message requested. So this plugin prices the step's cost the moment
`assistant/message` arrives, stashes it keyed by `"<sessionId>:<turn>:<step>"`,
and only *attributes* that already-priced cost to a tool name when the
matching `tool/call` shows up afterward. A step with several parallel
tool calls has its cost added to every one of those tools' buckets — a
deliberate simplification (documented here, not hidden) that means the
per-tool breakdown can sum to more than the grand total when a step calls
more than one tool at once.

### Surfacing it in the UI: `/cost`, not a custom Chat node

The "textbook" way to add a real chat-visible business card is a
`ConversationNodeDefinition` + keyed renderer
(`docs/cookbook/extension-cookbook.md`). That needs a client-side
JavaScript bundle built with dsh's own `tsdown` preset, which the docs
say plainly has "no published preset... outside this repository"
(`docs/cookbook/adding-a-settings-card.md`). Rather than fake that or
leave it half-working, this plugin uses a different, equally real,
host-side-only extension point:

```js
ctx.commands.register({
  name: 'cost',
  description: 'Show the running token/cost estimate for this session (estimated, not measured).',
  handler: async ({ agent }) => {
    const sessionId = resolveSessionId(agent)
    return { kind: 'success', text: formatReport(sessionId) }
  },
})
```

Typing `/cost` in the Web UI runs this handler directly against the agent
— per `packages/interaction/commands/README.md`, "without turning the
command or its result into a model message" — and the returned `text`
renders as its own row in the transcript, visibly outside the model's own
reply (confirmed in the demo screenshot below: the `cost` row sits below
the assistant turn's own usage/footer line, not inside it).

### Persistence

```js
const DATA_FILE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'data', 'session-cost.json')
```

A plain JSON file next to the plugin, read on first use and rewritten on
every tracked event. This is a simpler choice than the harness-native
`ctx.storageDomain` seam (`packages/storage/storage-domain`) — schema-
validated KV domains over a configured backend — made deliberately for
this assignment to avoid pulling in a schema-validation dependency
(`zod`) into an unpublished local plugin. It satisfies the actual
requirement ("survives a reload") the same way: verified below by
**actually restarting the dsh process** and re-running `/cost`, not just
by reasoning that a JSON file on disk should work.

## Install

Not published to npm — loaded locally by absolute path, same pattern as
`leakage-guard`:

```yaml
# Assignment2/partB/custom-plugins.patch.yml
- insert:
    - id: session-cost-panel
      name: 'C:\Users\sarth\Desktop\297\CMPE297\assignment2\partB\plugins\session-cost-panel\src\index.js'
```

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml
```

Confirmed **Enabled** with zero load errors in Settings → Plugins →
Plugin list (search "session-cost-panel").

## Demo

Run a few turns (any turns — this plugin doesn't care what they do), then
type `/cost`:

```
Session cost report -- ESTIMATED, not measured (DSH has no dollar-cost field;
this uses an illustrative price table, see the plugin README):

  total: ~$0.000000 across 2 model call(s), 6799 tokens

per-tool breakdown:
  write: 1 call(s), ~$0.000000, 4756 tokens

(persisted to ...\session-cost-panel\data\session-cost.json -- survives a reload/restart)
```

($0.000000 here is correct, not a bug — every model in this deployment's
`openrouter.patch.yml` is a free-tier route with a $0/$0 price row.)

**Persistence, actually proven, not just claimed:** the dsh process was
killed and restarted (new auth token, new browser session — see
`INSTALL.md`'s restart log), and `/cost` was run again against the fresh
process. It returned the exact same numbers, read back from
`session-cost.json` rather than recomputed.

Screenshots:
[`../../screenshots/28-cost-report-expanded.png`](../../screenshots/28-cost-report-expanded.png)
(the expanded report, first run) and
[`../../screenshots/29-cost-after-restart.png`](../../screenshots/29-cost-after-restart.png)
(same numbers, after killing and restarting the server).
