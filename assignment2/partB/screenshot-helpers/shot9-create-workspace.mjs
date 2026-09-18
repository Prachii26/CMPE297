import { chromium } from 'playwright'
import { randomUUID } from 'crypto'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`
const workspacePath = 'C:\\Users\\sarth\\Desktop\\297\\CMPE297\\assignment2\\partB'

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1000)

async function tryRpc(method, args) {
  return page.evaluate(async ({ method, args }) => {
    const res = await fetch('/api/' + method, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'client-request',
        rpcId: crypto.randomUUID(),
        method,
        payload: { args },
      }),
    })
    const text = await res.text()
    return { status: res.status, text }
  }, { method, args })
}

for (const method of ['workspace/create', 'workspaceRegistry/create', 'workspaces/create']) {
  const result = await tryRpc(method, { path: workspacePath, title: 'partB' })
  console.log(method, '->', result.status, result.text.slice(0, 300))
}

await browser.close()
