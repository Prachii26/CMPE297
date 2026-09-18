import { chromium } from 'playwright'

const token = process.argv[2]
const url = `http://127.0.0.1:3080/?token=${token}`

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto(url, { waitUntil: 'networkidle' })
await page.waitForTimeout(2000)
await page.screenshot({ path: '../screenshots/01-web-ui-loaded.png', fullPage: false })
console.log('title:', await page.title())
console.log('screenshot saved: 01-web-ui-loaded.png')
await browser.close()
