/**
 * Calls the real Cordis ctx.llm service to propose one edit to train.py.
 * One request, one response, no tool loop, no subagent -- the loop's own
 * driver (loop.js) owns applying, guarding, running, and deciding, so
 * the model is only ever asked for text and never given write access to
 * anything.
 *
 * ctx.llm.stream({provider, model, messages}) yields raw StreamChunks
 * (packages/llm/llm): { type: 'text-delta', text } chunks carry the
 * content; the stream always ends with one terminal 'finish' chunk
 * (packages/llm/llm/README.md). This accumulates the text deltas itself
 * rather than pulling in BlockAssembler, since a plain string is all a
 * one-shot internal call like this needs.
 *
 * Deliberately does NOT `import ... from '@deepseek-ai/dsh-llm'` for the
 * createUserMessage helper: this plugin is loaded locally by absolute
 * path (custom-plugins.patch.yml), not installed through pnpm into the
 * profile, so it sits outside the profile's own dependency graph and
 * that import fails at boot with ERR_MODULE_NOT_FOUND -- confirmed
 * against the real running instance, not assumed. A plain object with
 * the same shape works fine, since ctx itself (passed into apply(ctx))
 * needs no import at all.
 */
import { readFile, appendFile } from 'node:fs/promises'
import path from 'node:path'

async function debugLog(rootDir, line) {
  try {
    await appendFile(
      path.join(rootDir, 'runs', 'debug.log'),
      `[${new Date().toISOString()}] ${line}\n`,
      'utf8',
    )
  } catch {
    // best-effort only -- never let logging itself break the loop
  }
}

async function buildPrompt(rootDir, { currentCode, bestMetric, recentHistory }) {
  const programText = await readFile(path.join(rootDir, 'program.md'), 'utf8')

  const historyLines = recentHistory.length
    ? recentHistory
        .map((h) => {
          const outcome =
            h.decision === 'kept'
              ? `KEPT (accuracy ${h.metricBefore?.toFixed(4)} -> ${h.metricAfter?.toFixed(4)})`
              : `REVERTED -- ${h.reason}`
          return `- iteration ${h.iteration}: ${h.proposedChangeSummary ?? '(no summary)'} => ${outcome}`
        })
        .join('\n')
    : '(no iterations yet -- this is the first edit)'

  return `${programText}

---

CURRENT target/train.py (the version currently kept, because it produced the best held-out accuracy seen so far: ${bestMetric.toFixed(4)}):

\`\`\`python
${currentCode}
\`\`\`

RECENT ITERATION HISTORY:
${historyLines}
`
}

/** Extracts the first fenced code block's content, preferring a
 * \`\`\`python block if more than one fence is present. */
function extractCodeBlock(text) {
  const pythonFence = text.match(/```python\s*\n([\s\S]*?)```/)
  if (pythonFence) return pythonFence[1].trim()
  const anyFence = text.match(/```[a-zA-Z]*\s*\n([\s\S]*?)```/)
  if (anyFence) return anyFence[1].trim()
  return null
}

const PROPOSE_TIMEOUT_MS = 120_000

/** The actual streaming call, with no timeout of its own -- wrapped by
 * proposeEdit() below, so a stall here can never hang the whole loop. */
async function streamOnce(ctx, rootDir, { provider, model, promptText }) {
  let fullText = ''
  let finishInfo = null
  let chunkCount = 0

  await debugLog(rootDir, `stream starting: provider=${provider} model=${model}`)
  for await (const chunk of ctx.llm.stream({
    provider,
    model,
    messages: [{ role: 'user', content: [{ type: 'text', text: promptText }] }],
  })) {
    chunkCount += 1
    if (chunk.type === 'text-delta') {
      fullText += chunk.text
    } else if (chunk.type === 'finish') {
      finishInfo = chunk
    }
    if (chunkCount === 1) await debugLog(rootDir, `first chunk received: ${JSON.stringify(chunk).slice(0, 200)}`)
  }
  await debugLog(rootDir, `stream done: ${chunkCount} chunks, finish=${JSON.stringify(finishInfo)}`)
  return { fullText, finishInfo }
}

async function proposeEditOnce(ctx, rootDir, { provider, model, promptText }) {
  let timeoutHandle
  const timeoutPromise = new Promise((resolve) => {
    timeoutHandle = setTimeout(() => resolve({ timedOut: true }), PROPOSE_TIMEOUT_MS)
  })

  const streamPromise = streamOnce(ctx, rootDir, { provider, model, promptText }).then((r) => ({ ...r, timedOut: false }))

  let result
  try {
    result = await Promise.race([streamPromise, timeoutPromise])
  } finally {
    clearTimeout(timeoutHandle)
  }

  if (result.timedOut) {
    await debugLog(rootDir, `propose TIMED OUT after ${PROPOSE_TIMEOUT_MS}ms`)
    return { code: null, rawText: '', error: `ctx.llm.stream did not finish within ${PROPOSE_TIMEOUT_MS}ms` }
  }

  const { fullText, finishInfo } = result
  if (finishInfo && finishInfo.kind && finishInfo.kind !== 'stop' && finishInfo.kind !== 'ok') {
    return { code: null, rawText: fullText, error: `llm stream finished as ${JSON.stringify(finishInfo)}` }
  }

  const code = extractCodeBlock(fullText)
  return { code, rawText: fullText, error: code ? null : 'no fenced code block found in the model response' }
}

const MAX_ATTEMPTS = 3

/** OpenRouter's free tier has real, observed latency variance -- a
 * timeout here is infrastructure flakiness, not a guard-relevant event,
 * so it gets retried before the iteration gives up on it. Confirmed
 * against the live instance: one iteration's stream stalled completely
 * (no chunks at all within 45s) while a later, identical call to the
 * same model completed in under 20s. */
export async function proposeEdit(ctx, { rootDir, provider, model, currentCode, bestMetric, recentHistory }) {
  const promptText = await buildPrompt(rootDir, { currentCode, bestMetric, recentHistory })

  let lastResult = null
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    await debugLog(rootDir, `propose attempt ${attempt}/${MAX_ATTEMPTS}`)
    lastResult = await proposeEditOnce(ctx, rootDir, { provider, model, promptText })
    if (lastResult.code) {
      return { ...lastResult, promptText, attempts: attempt }
    }
    await debugLog(rootDir, `attempt ${attempt} failed: ${lastResult.error}`)
  }
  return { ...lastResult, promptText, attempts: MAX_ATTEMPTS, error: `${lastResult.error} (after ${MAX_ATTEMPTS} attempts)` }
}
