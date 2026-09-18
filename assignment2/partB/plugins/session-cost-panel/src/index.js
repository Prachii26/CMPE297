/**
 * session-cost-panel — tracks estimated tokens/cost per model call across a
 * session, with a per-tool-call breakdown, surfaced through a /cost
 * command and persisted to disk so the number survives a reload.
 *
 * ALL cost figures here are ESTIMATED, not measured: DSH has no dollar-cost
 * field on TokenUsage (packages/llm/llm), unlike OpenRouter's own
 * usage.include extension used directly in this assignment's Part A. This
 * plugin multiplies real token counts by an illustrative, hand-maintained
 * price table -- see README.md's honesty note. Every user-facing string
 * below says "estimated" for the same reason; that word is not decoration.
 *
 * Data flow, all real dsh session events (packages/core/session):
 *   request/header    -> which model/provider is about to answer
 *   assistant/message -> usage for one step (this is where cost is priced)
 *   tool/call         -> which tool(s) that SAME step's usage should also
 *                        count toward, for the per-tool breakdown
 * (see docs/subsystems/session.md's turn/step flow: assistant/message
 * always precedes any tool/call events within the same step, which is why
 * usage is priced first and only ATTRIBUTED to a tool afterward.)
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'session-cost-panel'
export const inject = ['sessions', 'commands']

const DATA_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'data')
const DATA_FILE = path.join(DATA_DIR, 'session-cost.json')

// Illustrative USD per MILLION tokens, [prompt, completion]. NOT fetched
// live from OpenRouter -- a display estimate, never a billing source of
// truth. Keys match Assignment2/partB/openrouter.patch.yml's models.
const PRICE_TABLE = {
  'deepseek/deepseek-v4-flash-0731:free': [0, 0],
  'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': [0, 0],
  'liquid/lfm-2.5-2.6b:free': [0, 0],
}
// Fallback guess for a model this table doesn't know, so the estimate
// degrades gracefully instead of silently reading zero.
const DEFAULT_PRICE = [0.5, 1.5]

function estimateCost(model, inputTokens, outputTokens) {
  const [promptPrice, completionPrice] = PRICE_TABLE[model] ?? DEFAULT_PRICE
  return (inputTokens * promptPrice + outputTokens * completionPrice) / 1_000_000
}

function emptySessionRecord() {
  return { totalCostEstimate: 0, totalTokens: 0, calls: 0, byTool: {}, updatedAt: null }
}

async function loadState() {
  try {
    const raw = await readFile(DATA_FILE, 'utf8')
    return JSON.parse(raw)
  } catch {
    return { sessions: {} } // first run, or file not there yet -- not an error
  }
}

async function saveState(state) {
  await mkdir(DATA_DIR, { recursive: true })
  await writeFile(DATA_FILE, JSON.stringify(state, null, 2), 'utf8')
}

function sessionIdOf(session) {
  return session?.id ?? session?.sessionId ?? String(session)
}

export function apply(ctx) {
  let state = { sessions: {} }
  let loaded = false
  // sessionId -> model string most recently seen in that session's
  // request/header. assistant/message carries usage but not the model,
  // so this is how we know which price row to charge it against.
  const modelBySession = new Map()
  // "<sessionId>:<turn>:<step>" -> the priced usage for that step, kept
  // just long enough for a same-step tool/call to attribute it.
  const pendingStepUsage = new Map()

  async function ensureLoaded() {
    if (!loaded) {
      state = await loadState()
      loaded = true
    }
  }

  function resolveSessionId(agent) {
    const direct = [agent?.session?.id, agent?.sessionId, agent?.id].find(
      (c) => typeof c === 'string' && state.sessions[c],
    )
    if (direct) return direct
    // Fall back to whichever tracked session updated most recently --
    // correct in the common case (one active session) even when the
    // exact Agent->sessionId accessor isn't the one we guessed.
    let latest = null
    for (const [id, rec] of Object.entries(state.sessions)) {
      if (!latest || (rec.updatedAt ?? '') > (state.sessions[latest].updatedAt ?? '')) latest = id
    }
    return latest ?? 'unknown'
  }

  function formatReport(sessionId) {
    const rec = state.sessions[sessionId]
    if (!rec || rec.calls === 0) {
      return 'session-cost-panel: no model calls recorded yet for this session.'
    }
    const lines = [
      'Session cost report -- ESTIMATED, not measured (DSH has no dollar-cost ' +
        'field; this uses an illustrative price table, see the plugin README):',
      '',
      `  total: ~$${rec.totalCostEstimate.toFixed(6)} across ${rec.calls} model call(s), ` +
        `${rec.totalTokens} tokens`,
      '',
      'per-tool breakdown:',
    ]
    const toolNames = Object.keys(rec.byTool)
    if (toolNames.length === 0) {
      lines.push('  (no tool calls yet -- only direct model replies so far)')
    } else {
      for (const toolName of toolNames) {
        const b = rec.byTool[toolName]
        lines.push(`  ${toolName}: ${b.calls} call(s), ~$${b.costEstimate.toFixed(6)}, ${b.tokens} tokens`)
      }
    }
    lines.push('', `(persisted to ${DATA_FILE} -- survives a reload/restart)`)
    return lines.join('\n')
  }

  ctx.on('session/event', async (session, event) => {
    await ensureLoaded()
    const sessionId = sessionIdOf(session)

    if (event.type === 'request/header') {
      const model = event.data?.header?.config?.model
      if (model) modelBySession.set(sessionId, model)
      return
    }

    if (event.type === 'assistant/message') {
      const { turn, step, usage } = event.data
      if (!usage) return
      const model = modelBySession.get(sessionId) ?? 'unknown'
      const inputTokens = usage.inputTokens ?? 0
      const outputTokens = usage.outputTokens ?? 0
      const costEstimate = estimateCost(model, inputTokens, outputTokens)

      pendingStepUsage.set(`${sessionId}:${turn}:${step}`, { inputTokens, outputTokens, costEstimate })

      const rec = state.sessions[sessionId] ?? emptySessionRecord()
      rec.totalCostEstimate += costEstimate
      rec.totalTokens += inputTokens + outputTokens
      rec.calls += 1
      rec.updatedAt = new Date().toISOString()
      state.sessions[sessionId] = rec
      await saveState(state)
      return
    }

    if (event.type === 'tool/call') {
      const { turn, step, name: toolName } = event.data
      const stepUsage = pendingStepUsage.get(`${sessionId}:${turn}:${step}`)
      if (!stepUsage) return // no priced usage recorded for this step yet
      const rec = state.sessions[sessionId] ?? emptySessionRecord()
      const bucket = rec.byTool[toolName] ?? { calls: 0, costEstimate: 0, tokens: 0 }
      bucket.calls += 1
      // A step's cost is attributed to EVERY tool it called, not split
      // between them -- see README's honesty note on double-counting
      // when one step makes several tool calls at once.
      bucket.costEstimate += stepUsage.costEstimate
      bucket.tokens += stepUsage.inputTokens + stepUsage.outputTokens
      rec.byTool[toolName] = bucket
      rec.updatedAt = new Date().toISOString()
      state.sessions[sessionId] = rec
      await saveState(state)
    }
  })

  ctx.commands.register({
    name: 'cost',
    description: 'Show the running token/cost estimate for this session (estimated, not measured).',
    handler: async ({ agent }) => {
      await ensureLoaded()
      const sessionId = resolveSessionId(agent)
      return { kind: 'success', text: formatReport(sessionId) }
    },
  })
}
