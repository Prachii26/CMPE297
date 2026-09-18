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

await page.screenshot({ path: '../screenshots/09-after-workspace-created.png' })
console.log('--- body text ---')
console.log((await page.innerText('body')).slice(0, 1000))

await browser.close()
