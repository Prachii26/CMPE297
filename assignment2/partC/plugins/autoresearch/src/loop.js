/**
 * The Karpathy loop: propose an edit, run it, measure it against the
 * held-out set, keep it if the metric improved, revert it if it did not
 * -- with a reward-hacking guard checked at every stage that could be
 * gamed (before running, right after running, and after evaluating).
 */
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

import { staticGuard, checkTiming, checkMetricPlausibility } from './guard.js'
import { runTrainPy, runEvaluatePy } from './runner.js'
import { appendEntry, readLedger, readState, writeState } from './ledger.js'
import { proposeEdit } from './propose.js'

const TRAIN_PY_REL = path.join('target', 'train.py')

function modelClassOf(code) {
  const match = code.match(/\b([A-Za-z_]*(?:Classifier|Regressor))\s*\(/)
  return match ? match[1] : null
}

function summarizeChange(oldCode, newCode) {
  if (oldCode === newCode) return '(no textual change)'
  const oldModel = modelClassOf(oldCode)
  const newModel = modelClassOf(newCode)
  const oldLines = oldCode.split('\n').length
  const newLines = newCode.split('\n').length
  const modelNote = oldModel && newModel && oldModel !== newModel
    ? `model changed ${oldModel} -> ${newModel}`
    : newModel
      ? `model stayed ${newModel} (hyperparameters/features likely changed)`
      : 'model class unclear from a simple scan'
  return `${modelNote}; ${oldLines} -> ${newLines} lines`
}

async function initState(rootDir, baselineCode) {
  await writeFile(path.join(rootDir, TRAIN_PY_REL), baselineCode, 'utf8')
  const trainResult = await runTrainPy(rootDir)
  if (trainResult.exitCode !== 0) {
    throw new Error(`baseline train.py failed to run: ${trainResult.stderr}`)
  }
  const evalResult = await runEvaluatePy(rootDir)
  if (evalResult.accuracy == null) {
    throw new Error(`baseline evaluate.py failed to run: ${evalResult.stderr || evalResult.parseError}`)
  }
  const state = {
    bestCode: baselineCode,
    bestMetric: evalResult.accuracy,
    baselineElapsedSeconds: trainResult.elapsedSeconds,
    acceptedCount: 0,
    revertedCount: 0,
    guardRejectedCount: 0,
    nextIteration: 1,
  }
  await writeState(rootDir, state)
  await appendEntry(rootDir, {
    iteration: 0,
    timestamp: new Date().toISOString(),
    kind: 'baseline',
    proposedChangeSummary: 'baseline (DecisionTreeClassifier(max_depth=2)), measured fresh at loop start',
    guardVerdict: 'n/a',
    guardReason: null,
    metricBefore: null,
    metricAfter: evalResult.accuracy,
    elapsedSeconds: trainResult.elapsedSeconds,
    baselineElapsedSeconds: trainResult.elapsedSeconds,
    decision: 'baseline',
    reason: 'initial measurement, not an edit',
    bestSoFarAfter: evalResult.accuracy,
  })
  return state
}

async function revertTo(rootDir, code) {
  await writeFile(path.join(rootDir, TRAIN_PY_REL), code, 'utf8')
}

/** Runs exactly one iteration against already-initialized state and
 * returns the ledger entry it wrote. Exported separately from
 * runLoop() so a caller can drive iterations one at a time if it wants
 * to (e.g. from a slower, resumable command). */
export async function runOneIteration(ctx, { rootDir, provider, model }, state) {
  const iteration = state.nextIteration
  const ledgerSoFar = await readLedger(rootDir)
  const recentHistory = ledgerSoFar.filter((e) => e.kind !== 'baseline').slice(-5)

  const entry = {
    iteration,
    timestamp: new Date().toISOString(),
    kind: 'edit',
    proposedChangeSummary: null,
    guardVerdict: null,
    guardReason: null,
    metricBefore: state.bestMetric,
    metricAfter: null,
    elapsedSeconds: null,
    baselineElapsedSeconds: state.baselineElapsedSeconds,
    decision: null,
    reason: null,
    bestSoFarAfter: state.bestMetric,
  }

  const proposal = await proposeEdit(ctx, {
    rootDir,
    provider,
    model,
    currentCode: state.bestCode,
    bestMetric: state.bestMetric,
    recentHistory,
  })

  if (!proposal.code) {
    entry.guardVerdict = 'rejected'
    entry.guardReason = `propose step failed: ${proposal.error}`
    entry.decision = 'reverted'
    entry.reason = entry.guardReason
    state.revertedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  entry.proposedChangeSummary = summarizeChange(state.bestCode, proposal.code)

  // STAGE 1 -- static guard, before the proposed code ever touches disk.
  const staticResult = staticGuard(proposal.code)
  if (!staticResult.ok) {
    entry.guardVerdict = 'rejected'
    entry.guardReason = staticResult.reason
    entry.decision = 'reverted'
    entry.reason = `rejected before running: ${staticResult.reason}`
    state.revertedCount += 1
    state.guardRejectedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  // Only now does the proposed code become the file on disk.
  await writeFile(path.join(rootDir, TRAIN_PY_REL), proposal.code, 'utf8')
  const trainResult = await runTrainPy(rootDir)
  entry.elapsedSeconds = trainResult.elapsedSeconds

  if (trainResult.exitCode !== 0) {
    entry.decision = 'reverted'
    entry.reason = trainResult.timedOut
      ? `train.py timed out after ${trainResult.elapsedSeconds.toFixed(1)}s (60s budget)`
      : `train.py crashed (exit ${trainResult.exitCode}): ${trainResult.stderr.trim().slice(-400)}`
    await revertTo(rootDir, state.bestCode)
    state.revertedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  // STAGE 2 -- timing guard, right after running, before evaluation even.
  const timingResult = checkTiming(trainResult.elapsedSeconds, state.baselineElapsedSeconds)
  if (!timingResult.ok) {
    entry.guardVerdict = 'rejected'
    entry.guardReason = timingResult.reason
    entry.decision = 'reverted'
    entry.reason = `rejected after running: ${timingResult.reason}`
    await revertTo(rootDir, state.bestCode)
    state.revertedCount += 1
    state.guardRejectedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  const evalResult = await runEvaluatePy(rootDir)
  if (evalResult.accuracy == null) {
    entry.decision = 'reverted'
    entry.reason = `evaluate.py failed to produce a metric (exit ${evalResult.exitCode}): ` +
      (evalResult.stderr.trim().slice(-400) || evalResult.parseError)
    await revertTo(rootDir, state.bestCode)
    state.revertedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  entry.metricAfter = evalResult.accuracy

  // STAGE 3 -- plausibility guard, after seeing the actual metric.
  const plausibilityResult = checkMetricPlausibility(evalResult.accuracy)
  if (!plausibilityResult.ok) {
    entry.guardVerdict = 'rejected'
    entry.guardReason = plausibilityResult.reason
    entry.decision = 'reverted'
    entry.reason = `rejected after evaluation: ${plausibilityResult.reason}`
    await revertTo(rootDir, state.bestCode)
    state.revertedCount += 1
    state.guardRejectedCount += 1
    state.nextIteration += 1
    await writeState(rootDir, state)
    await appendEntry(rootDir, entry)
    return entry
  }

  entry.guardVerdict = 'passed'

  if (evalResult.accuracy > state.bestMetric) {
    entry.decision = 'kept'
    entry.reason = `held-out accuracy improved from ${state.bestMetric.toFixed(4)} to ${evalResult.accuracy.toFixed(4)}`
    state.bestCode = proposal.code
    state.bestMetric = evalResult.accuracy
    state.acceptedCount += 1
  } else {
    entry.decision = 'reverted'
    entry.reason = `held-out accuracy did not improve (${evalResult.accuracy.toFixed(4)} did not exceed best ${state.bestMetric.toFixed(4)})`
    await revertTo(rootDir, state.bestCode)
    state.revertedCount += 1
  }

  entry.bestSoFarAfter = state.bestMetric
  state.nextIteration += 1
  await writeState(rootDir, state)
  await appendEntry(rootDir, entry)
  return entry
}

/** Runs N iterations back to back, initializing state (and measuring a
 * fresh baseline) on the very first call. */
export async function runLoop(ctx, { rootDir, provider, model, iterations }) {
  let state = await readState(rootDir)
  if (!state) {
    const baselineCode = await readFile(path.join(rootDir, TRAIN_PY_REL), 'utf8')
    state = await initState(rootDir, baselineCode)
  }

  const results = []
  for (let i = 0; i < iterations; i++) {
    const entry = await runOneIteration(ctx, { rootDir, provider, model }, state)
    results.push(entry)
  }
  return { state, results }
}
