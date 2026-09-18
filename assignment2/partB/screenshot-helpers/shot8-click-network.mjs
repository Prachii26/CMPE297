import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()

const apiCalls = []
page.on('request', req => {
  if (req.url().includes('/api')) {
    apiCalls.push(`${req.method()} ${req.url()} BODY=${req.postData() ?? ''}`)
  }
})

await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(1000)
const continueBtn = page.getByRole('button', { name: 'Continue' })
if (await continueBtn.isVisible().catch(() => false)) {
  await continueBtn.click()
  await page.waitForTimeout(500)
}

apiCalls.length = 0 // reset, only care about what the click itself triggers
await page.getByText('Choose workspace').click()
await page.waitForTimeout(1500)

console.log('--- /api calls triggered by the click ---')
console.log(apiCalls.join('\n') || '(none)')

await browser.close()
