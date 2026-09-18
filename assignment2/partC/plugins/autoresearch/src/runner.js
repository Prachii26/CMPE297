/**
 * Runs target/train.py and harness/evaluate.py as real subprocesses and
 * times them with the harness's OWN clock (process.hrtime.bigint()), not
 * anything train.py self-reports. That is what makes the timing guard in
 * guard.js tamper-proof: the elapsed time it checks is measured from
 * outside the process the edit controls.
 */
import { spawn } from 'node:child_process'
import path from 'node:path'

function pythonExe(rootDir) {
  return process.platform === 'win32'
    ? path.join(rootDir, '.venv', 'Scripts', 'python.exe')
    : path.join(rootDir, '.venv', 'bin', 'python')
}

function runSubprocess(exe, args, { timeoutMs }) {
  return new Promise((resolve) => {
    const start = process.hrtime.bigint()
    const child = spawn(exe, args, { windowsHide: true })
    let stdout = ''
    let stderr = ''
    let timedOut = false

    const timer = setTimeout(() => {
      timedOut = true
      child.kill()
    }, timeoutMs)

    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })

    child.on('close', (exitCode) => {
      clearTimeout(timer)
      const elapsedSeconds = Number(process.hrtime.bigint() - start) / 1e9
      resolve({ exitCode, stdout, stderr, elapsedSeconds, timedOut })
    })

    child.on('error', (err) => {
      clearTimeout(timer)
      const elapsedSeconds = Number(process.hrtime.bigint() - start) / 1e9
      resolve({ exitCode: -1, stdout, stderr: String(err), elapsedSeconds, timedOut: false })
    })
  })
}

/** Runs target/train.py. 60s timeout matches the assignment's own budget
 * for the target script; a run that hits it is treated as a failure, not
 * silently given more time. */
export async function runTrainPy(rootDir, timeoutMs = 60_000) {
  const result = await runSubprocess(pythonExe(rootDir), ['target/train.py'], { timeoutMs })
  return result
}

/** Runs harness/evaluate.py and parses its one line of JSON stdout.
 * Never receives anything from train.py directly -- a fresh process,
 * reading the model artifact train.py left behind and the held-out data
 * train.py never saw. */
export async function runEvaluatePy(rootDir, timeoutMs = 30_000) {
  const result = await runSubprocess(pythonExe(rootDir), ['harness/evaluate.py'], { timeoutMs })
  if (result.exitCode !== 0) {
    return { ...result, accuracy: null, nHeldout: null, parseError: null }
  }
  try {
    const lastLine = result.stdout.trim().split('\n').pop()
    const parsed = JSON.parse(lastLine)
    return { ...result, accuracy: parsed.accuracy, nHeldout: parsed.n_heldout, parseError: null }
  } catch (err) {
    return { ...result, accuracy: null, nHeldout: null, parseError: String(err) }
  }
}
