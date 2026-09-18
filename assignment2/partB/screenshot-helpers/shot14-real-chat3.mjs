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
await page.waitForTimeout(1000)

const boxes = page.getByRole('textbox')
const count = await boxes.count()
for (let i = 0; i < count; i++) {
  const el = boxes.nth(i)
  console.log(i, await el.getAttribute('placeholder'), await el.getAttribute('class'))
}

const composer = boxes.last()
await composer.click()
await composer.fill('Use your shell tool to print 2+2, then tell me the result in one sentence.')
await page.screenshot({ path: '../screenshots/10-message-typed.png' })

await page.keyboard.press('Enter')
await page.waitForTimeout(5000)
await page.screenshot({ path: '../screenshots/11-mid-response.png' })

await page.waitForTimeout(15000)
await page.screenshot({ path: '../screenshots/12-final-response.png', fullPage: true })

console.log('--- final body text (first 2500 chars) ---')
console.log((await page.innerText('body')).slice(0, 2500))

await browser.close()
