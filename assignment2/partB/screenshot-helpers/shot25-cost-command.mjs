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

const boxes = page.getByRole('textbox')
const composer = boxes.last()
await composer.click()
await composer.type('/cost')
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/26-cost-command-typed.png' })
await page.keyboard.press('Enter')
await page.waitForTimeout(3000)
await page.screenshot({ path: '../screenshots/27-cost-command-result.png', fullPage: true })

console.log('--- body text ---')
console.log((await page.innerText('body')).slice(-2500))

await browser.close()
