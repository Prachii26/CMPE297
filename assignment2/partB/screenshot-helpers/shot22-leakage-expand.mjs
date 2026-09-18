import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

// Wait until the "Deep diving..." / running indicator is gone, up to 60s.
for (let i = 0; i < 20; i++) {
  const text = await page.innerText('body')
  if (!text.includes('Deep diving') && !text.includes('Running')) break
  await page.waitForTimeout(3000)
}

await page.screenshot({ path: '../screenshots/22-leakage-settled.png', fullPage: true })

// Expand the Write tool call card to see its full result content.
const writeRow = page.getByText('leaky_example.py', { exact: false }).first()
await writeRow.click().catch(() => {})
await page.waitForTimeout(1000)
await page.screenshot({ path: '../screenshots/23-leakage-write-expanded.png', fullPage: true })

console.log('--- body text ---')
console.log((await page.innerText('body')).slice(0, 4000))

await browser.close()
