"""Rasterise rich's SVG terminal export to PNG with Playwright: python tools\svg_to_png.py in.svg out.png"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

src, dst = Path(sys.argv[1]).resolve(), sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1100, "height": 900})
    pg.goto(src.as_uri()); pg.wait_for_timeout(300)
    pg.locator("svg").first.screenshot(path=dst); b.close()
print("saved", dst)
