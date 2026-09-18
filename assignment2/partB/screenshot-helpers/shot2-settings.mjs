import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

// Dismiss the internal testing notice modal.
const continueBtn = page.getByRole('button', { name: 'Continue' })
if (await continueBtn.isVisible().catch(() => false)) {
  await continueBtn.click()
  await page.waitForTimeout(500)
}

await page.screenshot({ path: '../screenshots/02-chat-empty.png' })
console.log('screenshot saved: 02-chat-empty.png')

// Open Settings.
await page.getByText('Settings', { exact: true }).click()
await page.waitForTimeout(1000)
await page.screenshot({ path: '../screenshots/03-settings-opened.png' })
console.log('screenshot saved: 03-settings-opened.png')

// Try to find a Models link/tab within settings.
const modelsLink = page.getByText('Models', { exact: true }).first()
if (await modelsLink.isVisible().catch(() => false)) {
  await modelsLink.click()
  await page.waitForTimeout(1000)
  await page.screenshot({ path: '../screenshots/04-settings-models.png' })
  console.log('screenshot saved: 04-settings-models.png')
} else {
  console.log('no "Models" link found in settings view')
}

// Dump visible text for debugging selector choices.
console.log('--- visible body text (first 2000 chars) ---')
console.log((await page.innerText('body')).slice(0, 2000))

await browser.close()
