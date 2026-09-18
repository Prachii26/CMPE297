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

await page.locator('text=Write a file called leaky_exam').first().click()
await page.waitForTimeout(1500)

await page.locator('text=Session cost report').first().click()
await page.waitForTimeout(800)
await page.screenshot({ path: '../screenshots/28-cost-report-expanded.png', fullPage: true })

await browser.close()
