/**
 * Append-only JSON run ledger. One line per iteration -- JSONL, not a
 * single JSON array -- so an interrupted run never corrupts every entry
 * that came before it, and appending is a single fs.appendFile call with
 * no read-modify-write race.
 */
import { mkdir, appendFile, readFile } from 'node:fs/promises'
import path from 'node:path'

export function ledgerPath(rootDir) {
  return path.join(rootDir, 'runs', 'ledger.jsonl')
}

export async function appendEntry(rootDir, entry) {
  const file = ledgerPath(rootDir)
  await mkdir(path.dirname(file), { recursive: true })
  await appendFile(file, JSON.stringify(entry) + '\n', 'utf8')
}

export async function readLedger(rootDir) {
  try {
    const raw = await readFile(ledgerPath(rootDir), 'utf8')
    return raw
      .split('\n')
      .filter((line) => line.trim().length > 0)
      .map((line) => JSON.parse(line))
  } catch {
    return []
  }
}

/** One line of standing state the loop reads back after a restart:
 * which iteration to resume at, and the best-kept content + metric. */
export function statePath(rootDir) {
  return path.join(rootDir, 'runs', 'state.json')
}

export async function readState(rootDir) {
  try {
    const raw = await readFile(statePath(rootDir), 'utf8')
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export async function writeState(rootDir, state) {
  const file = statePath(rootDir)
  await mkdir(path.dirname(file), { recursive: true })
  const { writeFile } = await import('node:fs/promises')
  await writeFile(file, JSON.stringify(state, null, 2), 'utf8')
}
