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
await page.waitForTimeout(1000)

// Screenshot 1: the command palette recognizing /autoresearch-status as a
// real, registered plugin command (proves the plugin is live and wired up
// in the running instance, not just present as source code).
const boxes = page.getByRole('textbox')
const composer = boxes.last()
await composer.click()
await page.waitForTimeout(200)
await page.keyboard.type('/autoresearch-status', { delay: 25 })
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/02-autoresearch-status-command.png' })
console.log('captured 02-autoresearch-status-command.png')

// Screenshot 2: the /autoresearch <n> command, same proof for the loop-driving command.
await page.keyboard.press('Escape')
await composer.click({ clickCount: 3 })
await page.keyboard.press('Backspace')
await page.waitForTimeout(200)
await page.keyboard.type('/autoresearch 10', { delay: 25 })
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/03-autoresearch-run-command.png' })
console.log('captured 03-autoresearch-run-command.png')

await browser.close()
