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
await page.waitForTimeout(1000)

const bodyText = await page.innerText('body')
const names = ['composer-expand', 'cool-theme', 'engineer-tools', 'init', 'instruction-memory', 'write-protect']
for (const name of names) {
  const idx = bodyText.indexOf(name)
  console.log(name, '->', idx === -1 ? 'NOT FOUND' : bodyText.slice(idx, idx + 60).replace(/\n/g, ' | '))
}

await page.screenshot({ path: '../screenshots/16-all-plugins-final.png', fullPage: true })
await browser.close()
