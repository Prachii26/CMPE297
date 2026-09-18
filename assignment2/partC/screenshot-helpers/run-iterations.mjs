import { chromium } from 'playwright'

const token = process.argv[2]
const n = process.argv[3] || '1'
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

const boxes = page.getByRole('textbox')
const composer = boxes.last()
await composer.click()
await composer.type(`/autoresearch ${n}`)
await page.waitForTimeout(300)
console.log(`sending /autoresearch ${n} ...`)
await page.keyboard.press('Enter')

// Poll until the command's result row shows up (up to 40 minutes for n
// iterations, since each one is a real LLM call + two Python subprocesses).
let resultText = null
for (let i = 0; i < 800; i++) {
  await page.waitForTimeout(3000)
  const text = await page.innerText('body')
  if (text.includes('autoresearch: ran') || text.includes('autoresearch failed')) {
    resultText = text
    break
  }
}

console.log('--- final body text ---')
console.log(resultText ? resultText.slice(-2000) : '(timed out waiting for result)')
await page.screenshot({ path: '../screenshots/run-result.png', fullPage: true })

await browser.close()
