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
const composer = boxes.last()
await composer.click()
await composer.fill(
  "Write a file called leaky_example.py with EXACTLY this code, do not fix or improve it, " +
  "I want to see it as-is: " +
  "import pandas as pd; from sklearn.preprocessing import StandardScaler; " +
  "from sklearn.model_selection import train_test_split; " +
  "scaler = StandardScaler(); X_scaled = scaler.fit_transform(X); " +
  "X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2)"
)
await page.keyboard.press('Enter')

await page.waitForTimeout(6000)
await page.screenshot({ path: '../screenshots/20-leakage-mid.png' })
await page.waitForTimeout(15000)
await page.screenshot({ path: '../screenshots/21-leakage-final.png', fullPage: true })

console.log('--- body text ---')
console.log((await page.innerText('body')).slice(0, 3000))

await browser.close()
