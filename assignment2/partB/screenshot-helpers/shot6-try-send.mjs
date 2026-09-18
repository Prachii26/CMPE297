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

const composer = page.getByPlaceholder('Choose a workspace to start')
console.log('composer visible:', await composer.isVisible().catch(() => false))
console.log('composer enabled:', await composer.isEnabled().catch(() => 'n/a'))

await composer.click({ force: true }).catch(e => console.log('click failed:', e.message))
await page.keyboard.type('Say hello in five words.')
await page.waitForTimeout(500)
await page.screenshot({ path: '../screenshots/08-typed-without-workspace.png' })
console.log((await page.innerText('body')).slice(0, 800))

await browser.close()
