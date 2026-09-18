import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

const continueBtn = page.getByRole('button', { name: 'Continue' })
if (await continueBtn.isVisible().catch(() => false)) {
  await continueBtn.click()
  await page.waitForTimeout(500)
}

await page.getByText('Settings', { exact: true }).click()
await page.waitForTimeout(800)
await page.getByText('Plugins', { exact: true }).click()
await page.waitForTimeout(800)
await page.getByText('Plugin list', { exact: true }).click()
await page.waitForTimeout(800)

const search = page.getByPlaceholder('Search plugins')
for (const name of ['leakage-guard', 'session-cost-panel']) {
  await search.fill(name)
  await page.waitForTimeout(600)
  const text = await page.innerText('body')
  const idx = text.indexOf(name)
  console.log(name, '=>', idx === -1 ? 'NOT FOUND' : text.slice(Math.max(0, idx - 5), idx + 60).replace(/\n/g, ' | '))
}

await search.fill('leakage')
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/18-leakage-guard-in-list.png' })
await search.fill('cost-panel')
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/19-cost-panel-in-list.png' })

await browser.close()
