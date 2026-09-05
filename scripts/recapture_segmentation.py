#!/usr/bin/env python3
"""Recapture the 4 Customer Segmentation screenshots after the Plotly 7 fix."""
import subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "docs" / "screenshots"
PORT = 8506
BASE_URL = f"http://localhost:{PORT}"
CHART_SEL = ".js-plotly-plot"


def poll(url, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
         "--server.port", str(PORT), "--server.headless", "true",
         "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        print(f"Polling {BASE_URL} ...")
        if not poll(BASE_URL, 30):
            raise RuntimeError("Streamlit did not start")
        print("Ready.")

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = ctx.new_page()

            print("[Customer Segmentation]")
            page.goto(f"{BASE_URL}/Customer_Segmentation", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=30_000)
            page.wait_for_selector('[data-testid="stTab"]', timeout=20_000)
            page.wait_for_selector(CHART_SEL, state="attached", timeout=20_000)
            time.sleep(5)

            def snap(name):
                dest = SCREENSHOTS / name
                page.screenshot(path=str(dest), full_page=True)
                kb = dest.stat().st_size // 1024
                print(f"  {name}  ({kb} KB)")

            snap("03_segmentation.png")

            for label, fname, chart, extra in [
                ("Modeling",      "03_segmentation_modeling.png",    True,  4),
                ("Evaluation",    "03_segmentation_evaluation.png",  True,  4),
                ("Live Inference","03_segmentation_live.png",        False, 2),
            ]:
                page.wait_for_selector('[data-testid="stTab"]', timeout=10_000)
                page.get_by_role("tab", name=label).click()
                page.wait_for_load_state("networkidle", timeout=15_000)
                if chart:
                    try:
                        page.wait_for_selector(CHART_SEL, state="attached", timeout=15_000)
                    except Exception:
                        pass
                time.sleep(extra)
                snap(fname)

            browser.close()

        print("\n=== Segmentation screenshots ===")
        for f in sorted(SCREENSHOTS.glob("03_seg*.png")):
            kb = f.stat().st_size // 1024
            flag = "  ← BLANK?" if kb < 50 else ""
            print(f"  {f.name}: {kb} KB{flag}")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
