"""Screenshot each mode of a running theme server, from a real browser run.

Needs Playwright with Chromium (not a theme dependency; any venv that has it):

    python tools\\shoot.py --port 8001 --out 01_foundations\\docs --modes static declarative open_ended mixed

For each mode it opens http://127.0.0.1:<port>/?mode=<mode>, waits until the
page sets <body data-done>, gives sandboxed iframes a moment to paint, and
saves <out>/mode_<mode>.png. Extra query parameters can be appended with
--query (e.g. "&delay=0.02").
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modes", nargs="+", default=["static", "declarative", "open_ended", "mixed"])
    ap.add_argument("--query", default="")
    ap.add_argument("--path", default="/")
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--prefix", default="mode_")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": args.height})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for mode in args.modes:
            url = f"http://127.0.0.1:{args.port}{args.path}?mode={mode}{args.query}"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("body[data-done]", timeout=30000)
            page.wait_for_timeout(900)
            path = out / f"{args.prefix}{mode}.png"
            page.screenshot(path=str(path), full_page=True)
            print("saved", path)
        browser.close()
    if errors:
        print("PAGE ERRORS:", *errors, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
