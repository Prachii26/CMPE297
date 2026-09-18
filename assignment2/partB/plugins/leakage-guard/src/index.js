/**
 * leakage-guard — flags common ML data-leakage patterns in Python code the
 * agent is about to write or run, and warns instead of blocking.
 *
 * Hooks two real dsh extension points, not one, because the real
 * PreToolDecision type (packages/core/tools/src/index.ts) only supports
 * { kind: 'allow' | 'deny' | 'cancel' | 'ask' } -- there is no non-blocking
 * "warn" verdict from tools/pre-execute alone. So:
 *
 *   tools/pre-execute  -- inspects the code the agent is ABOUT to run
 *                          (matching the assignment's own framing) and
 *                          stashes any finding, keyed by the call's opaque
 *                          exec.token. Always delegates via next() -- it
 *                          never denies or asks, so the call is never
 *                          hard-blocked.
 *   tools/post-execute -- looks up that stash and, if a finding exists,
 *                          returns { kind: 'accept', content: [...] } with
 *                          the warning appended to the tool's own result
 *                          content -- literally "the warning goes back to
 *                          the agent as the tool result."
 *
 * See README.md for why this two-hook design is the faithful reading of
 * the real API, not a shortcut around it.
 */

export const name = 'leakage-guard'
export const inject = ['tools']

// exec.token (opaque, unique per call) -> array of finding strings.
// Cleared the moment post-execute consumes it, so this never grows
// unbounded across a long session.
const pendingFindings = new Map()

const PY_FILE_RE = /\.(py|ipynb)$/i
const INLINE_PY_RE = /\bpython3?\b\s+(-c\b|["'][^"']*\.py["'])/i

/**
 * Which tool call actually carries Python code, and what that code is.
 * Returns null for anything else -- a tool we don't recognize, or one
 * whose arguments don't look like Python at all.
 */
function extractCode(execName, args) {
  if (!args) return null
  switch (execName) {
    case 'write':
      if (typeof args.file_path === 'string' && PY_FILE_RE.test(args.file_path)) {
        return typeof args.content === 'string' ? args.content : null
      }
      return null
    case 'edit':
      // old_string is what the file USED to say; new_string is the code
      // the agent is actually introducing, which is what we can judge.
      if (typeof args.file_path === 'string' && PY_FILE_RE.test(args.file_path)) {
        return typeof args.new_string === 'string' ? args.new_string : null
      }
      return null
    case 'bash':
    case 'pwsh':
      if (typeof args.command === 'string' && INLINE_PY_RE.test(args.command)) {
        return args.command
      }
      return null
    default:
      return null
  }
}

/**
 * Four checks, each independent, each returning a finding string (with a
 * concrete reason) or null. These are regex heuristics over source text,
 * not a real Python AST analysis -- see the honesty note in README.md.
 */
const CHECKS = [
  // 1. fit_transform on the whole dataset, not a training split.
  function fitTransformBeforeSplit(code) {
    const fitMatch = code.match(/\bfit_transform\s*\(\s*([A-Za-z_]\w*)/)
    if (!fitMatch) return null
    const arg = fitMatch[1]
    const looksLikeTrainSlice = /train/i.test(arg)
    const hasSplit = /\btrain_test_split\s*\(/.test(code)
    if (!looksLikeTrainSlice && hasSplit) {
      return (
        `fit_transform(${arg}, ...) is called on '${arg}', which doesn't look like a ` +
        "training-only slice, in code that also calls train_test_split(). Fit the " +
        "transformer (scaler/encoder/vectorizer/imputer) on the TRAINING split only, " +
        "then .transform() (not .fit_transform()) the test split with that same fitted " +
        "object -- fitting on the full dataset leaks test-set statistics into training."
      )
    }
    return null
  },

  // 2. A scaler fit outside a sklearn Pipeline.
  function scalerFitOutsidePipeline(code) {
    const scalerRe = /\b(StandardScaler|MinMaxScaler|RobustScaler|MaxAbsScaler|Normalizer)\s*\(/
    const scalerMatch = code.match(scalerRe)
    if (!scalerMatch) return null
    const fitsSomething = /\.(fit|fit_transform)\s*\(/.test(code)
    const insidePipeline = /\bPipeline\s*\(/.test(code)
    if (fitsSomething && !insidePipeline) {
      return (
        `${scalerMatch[1]} is fit directly, outside a sklearn Pipeline. A scaler fit ` +
        "standalone is easy to accidentally fit on data that includes the test split " +
        "(or to forget to re-apply consistently at inference time). Wrap it in a " +
        "Pipeline([('scaler', ...), ('model', ...)]) so fit/transform only ever see " +
        "whatever split the Pipeline itself was called with."
      )
    }
    return null
  },

  // 3. shuffle=True on what looks like a time series split.
  function shuffleOnTimeSeries(code) {
    const hasShuffleTrue = /\bshuffle\s*=\s*True\b/.test(code)
    if (!hasShuffleTrue) return null
    const looksTimeSeries =
      /\bTimeSeriesSplit\s*\(/.test(code) ||
      /\b(date|datetime|timestamp|time_series)\b/i.test(code)
    if (looksTimeSeries) {
      return (
        "shuffle=True appears alongside what looks like time-series data " +
        "(TimeSeriesSplit or a date/timestamp column). Shuffling before splitting a " +
        "time series lets future rows leak into the training set. Use a " +
        "chronological split (TimeSeriesSplit, or an explicit date cutoff) with " +
        "shuffle=False."
      )
    }
    return null
  },

  // 4. Test data touched during a .fit(...) call.
  function testDataTouchedDuringFit(code) {
    const fitCallRe = /\.(fit|fit_transform)\s*\(([^)]*)\)/g
    let match
    while ((match = fitCallRe.exec(code)) !== null) {
      const [, method, args] = match
      if (/\btest\b/i.test(args)) {
        return (
          `.${method}(${args.trim()}) passes an argument containing 'test' into a ` +
          "fit call. Fitting on test data (even alongside training data) is the " +
          "clearest form of leakage: the model or transformer directly learns from " +
          "data it will later be scored on. Fit only on the training split; use the " +
          "test split only for .transform() / .predict() / .score()."
        )
      }
    }
    return null
  },
]

function runChecks(code) {
  const findings = []
  for (const check of CHECKS) {
    const finding = check(code)
    if (finding) findings.push(finding)
  }
  return findings
}

function formatWarning(findings) {
  const lines = [
    '',
    '⚠️ leakage-guard found ' + findings.length + ' possible data-leakage issue(s) in this code:',
    ...findings.map((f, i) => `  ${i + 1}. ${f}`),
    '',
    '(Heuristic pattern match, not a guarantee -- review each one and fix if it ' +
      'applies, or proceed if it is a false positive. The code above already ran; ' +
      'this is feedback for your NEXT edit, not a block.)',
  ]
  return lines.join('\n')
}

export function apply(ctx) {
  ctx.on('tools/pre-execute', async (exec, next) => {
    const code = extractCode(exec.name, exec.arguments)
    if (code) {
      const findings = runChecks(code)
      if (findings.length > 0) {
        pendingFindings.set(exec.token, findings)
      }
    }
    // Never deny, never ask -- inspection only. The call always proceeds.
    return next()
  })

  ctx.on('tools/post-execute', async (exec, result, next) => {
    const decision = await next()
    const findings = pendingFindings.get(exec.token)
    if (!findings) return decision
    pendingFindings.delete(exec.token)

    // Respect a stricter policy that already blocked this call -- our job
    // is to warn on top of a successful result, not override a real deny.
    if (decision.kind === 'block') return decision

    const baseContent =
      decision.kind === 'accept' && decision.content ? decision.content : result.content
    return {
      kind: 'accept',
      content: [...baseContent, { type: 'text', text: formatWarning(findings) }],
    }
  })
}
