"""Open a mode, perform one user action, wait for the agent's reply, screenshot.

    python tools\\shoot_action.py --port 8002 --mode declarative --click "#act" --out 02_ag_ui\\docs\\state_patch.png
    python tools\\shoot_action.py --port 8002 --mode mixed --frame-click ".room" --out ...

Waits for <body data-done>, clicks (in the page, or inside the first
sandboxed iframe), waits for data-done to be set again by the follow-up run,
then saves a full-page screenshot. Prints any text matched by --report.
"""
import argparse
import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--mode", required=True)
    ap.add_argument("--click")
    ap.add_argument("--frame-click")
    ap.add_argument("--out", required=True)
    ap.add_argument("--query", default="&delay=0.01")
    ap.add_argument("--report", default="")
    ap.add_argument("--path", default="/")
    a = ap.parse_args()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{a.port}{a.path}?mode={a.mode}{a.query}")
        pg.wait_for_selector("body[data-done]", timeout=30000)
        pg.wait_for_timeout(600)
        if a.frame_click:
            pg.frame_locator("iframe").first.locator(a.frame_click).first.click()
        else:
            pg.click(a.click)
        pg.wait_for_timeout(300)
        pg.wait_for_selector("body[data-done]", timeout=30000)
        pg.wait_for_timeout(800)
        if a.report:
            for t in pg.locator(a.report).all_inner_texts():
                print("report:", t.replace("\n", " ")[:200])
        pg.screenshot(path=a.out, full_page=True)
        print("saved", a.out)
        b.close()
    if errors:
        print("PAGE ERRORS:", *errors, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
