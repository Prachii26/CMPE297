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

await page.locator('.workspaces, [class*=sidebar]').first().locator('text=Write a file called leaky_exam').first().click().catch(async () => {
  await page.locator('text=Write a file called leaky_exam').first().click()
})
await page.waitForTimeout(1500)

// The "1 tool call" summary row has a chevron; click it to expand.
const toolCallRow = page.getByText('1 tool call')
await toolCallRow.click()
await page.waitForTimeout(1000)
await page.screenshot({ path: '../screenshots/25-toolcall-expanded.png', fullPage: true })
console.log((await page.innerText('body')).slice(0, 3500))

await browser.close()
