import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3081/?token=${token}`
const workspacePath = 'C:\\Users\\sarth\\Desktop\\297\\CMPE297\\assignment2\\partC'

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1000)

const result = await page.evaluate(async ({ path }) => {
  const res = await fetch('/api/workspace/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: 'client-request',
      rpcId: crypto.randomUUID(),
      method: 'workspace/create',
      payload: { args: { request: { path, title: 'partC' } } },
    }),
  })
  return { status: res.status, text: await res.text() }
}, { path: workspacePath })

console.log('workspace/create ->', result.status, result.text)

await browser.close()
