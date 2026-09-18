import { chromium } from 'playwright'

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

const result = await tryRpc('workspace/create', { request: { path: workspacePath, title: 'partB' } })
console.log('workspace/create ->', result.status, result.text)

await browser.close()
