import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3081/?token=${token}`

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
await search.fill('autoresearch')
await page.waitForTimeout(600)
const text = await page.innerText('body')
const idx = text.indexOf('autoresearch')
console.log('autoresearch =>', idx === -1 ? 'NOT FOUND' : text.slice(Math.max(0, idx - 5), idx + 80).replace(/\n/g, ' | '))
await page.screenshot({ path: '../screenshots/01-autoresearch-in-plugin-list.png' })

await browser.close()
