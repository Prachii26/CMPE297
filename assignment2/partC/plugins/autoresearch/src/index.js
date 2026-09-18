/**
 * autoresearch -- a DSH plugin implementing Karpathy's autoresearch loop
 * end to end: propose an edit to target/train.py, run it, measure it on
 * a held-out split the edit can never see, keep it if the held-out
 * metric improved, revert it if it did not, and log every iteration
 * (accepted or rejected, and why) to an append-only ledger.
 *
 * Two commands, following the same ctx.commands pattern Part B's
 * session-cost-panel used (packages/interaction/commands):
 *   /autoresearch <n>  -- run n more iterations
 *   /autoresearch-status -- the results view: trajectory, accept/reject
 *                            counts, best-so-far, most recent entries
 */
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { runLoop } from './loop.js'
import { readLedger, readState } from './ledger.js'

export const name = 'autoresearch'
export const inject = ['commands', 'llm']

const ROOT_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const PROVIDER = 'openrouter'
const MODEL = 'deepseek/deepseek-v4-flash-0731:free'

function formatStatus(state, ledger) {
  if (!state) {
    return 'autoresearch: no run yet. Use /autoresearch <n> to start (e.g. /autoresearch 10).'
  }
  const editEntries = ledger.filter((e) => e.kind !== 'baseline')
  const baseline = ledger.find((e) => e.kind === 'baseline')

  const lines = [
    'autoresearch results',
    '',
    `baseline held-out accuracy: ${baseline ? baseline.metricAfter.toFixed(4) : 'n/a'} ` +
      `(measured in ${baseline ? baseline.elapsedSeconds.toFixed(3) : '?'}s)`,
    `best-so-far held-out accuracy: ${state.bestMetric.toFixed(4)}`,
    `iterations run: ${editEntries.length}  |  kept: ${state.acceptedCount}  |  reverted: ${state.revertedCount}` +
      `  (of which guard-rejected: ${state.guardRejectedCount})`,
    '',
    'metric trajectory (best-so-far after each iteration):',
    ...editEntries.map(
      (e) => `  ${e.iteration}. ${e.decision.padEnd(9)} best=${e.bestSoFarAfter?.toFixed(4)}  ${e.reason ?? ''}`,
    ),
    '',
    'most recent rejections and their reasons:',
    ...editEntries
      .filter((e) => e.decision === 'reverted')
      .slice(-5)
      .map((e) => `  iteration ${e.iteration}: ${e.reason}`),
  ]
  if (!editEntries.some((e) => e.decision === 'reverted')) {
    lines.push('  (none yet)')
  }
  return lines.join('\n')
}

export function apply(ctx) {
  ctx.commands.register({
    name: 'autoresearch',
    description: 'Run N autoresearch iterations on target/train.py (propose, run, measure, keep/revert).',
    input: { hint: '<iterations>' },
    handler: async ({ rawInput }) => {
      const iterations = Math.max(1, Math.min(50, parseInt((rawInput || '1').trim(), 10) || 1))
      try {
        const { state, results } = await runLoop(ctx, {
          rootDir: ROOT_DIR,
          provider: PROVIDER,
          model: MODEL,
          iterations,
        })
        const kept = results.filter((r) => r.decision === 'kept').length
        const reverted = results.filter((r) => r.decision === 'reverted').length
        const summary =
          `autoresearch: ran ${results.length} iteration(s) -- ${kept} kept, ${reverted} reverted. ` +
          `Best held-out accuracy so far: ${state.bestMetric.toFixed(4)}. Run /autoresearch-status for the full trajectory.`
        return { kind: 'success', text: summary }
      } catch (err) {
        return { kind: 'error', text: `autoresearch failed: ${err.stack || err}` }
      }
    },
  })

  ctx.commands.register({
    name: 'autoresearch-status',
    description: 'Show the autoresearch results view: trajectory, accept/reject counts, best-so-far.',
    handler: async () => {
      const state = await readState(ROOT_DIR)
      const ledger = await readLedger(ROOT_DIR)
      return { kind: 'success', text: formatStatus(state, ledger) }
    },
  })
}
