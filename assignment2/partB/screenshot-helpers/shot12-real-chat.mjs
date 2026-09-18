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

const composer = page.getByPlaceholder('Describe what you want to build, / commands, @ files or sessions')
await composer.click()
await composer.fill('Use your shell tool to print 2+2, then tell me the result in one sentence.')
await page.screenshot({ path: '../screenshots/10-message-typed.png' })

// Send: try Enter first.
await page.keyboard.press('Enter')

// Wait for an assistant reply to actually stream in.
await page.waitForTimeout(4000)
await page.screenshot({ path: '../screenshots/11-mid-response.png' })

// Give it real time to finish the tool call + final answer.
await page.waitForTimeout(15000)
await page.screenshot({ path: '../screenshots/12-final-response.png', fullPage: true })

console.log('--- final body text (first 2500 chars) ---')
console.log((await page.innerText('body')).slice(0, 2500))

await browser.close()
