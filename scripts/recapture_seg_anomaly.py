#!/usr/bin/env python3
"""Recapture segmentation (4 shots) and anomaly (4 shots) screenshots."""
import subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "docs" / "screenshots"
PORT = 8515
BASE_URL = f"http://localhost:{PORT}"
CHART = ".js-plotly-plot"
TAB   = '[data-testid="stTab"]'


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


def snap(page, name):
    dest = SCREENSHOTS / name
    page.screenshot(path=str(dest), full_page=True)
    kb = dest.stat().st_size // 1024
    flag = "  ← BLANK?" if kb < 50 else ""
    print(f"  {name}  ({kb} KB){flag}")


def wait(page, has_chart=True, has_tabs=True, extra=3.0):
    page.wait_for_load_state("networkidle", timeout=30_000)
    if has_tabs:
        try:
            page.wait_for_selector(TAB, timeout=20_000)
        except Exception:
            pass
    if has_chart:
        try:
            page.wait_for_selector(CHART, state="attached", timeout=20_000)
        except Exception:
            pass
    time.sleep(extra)


def click_tab(page, label, has_chart=True, extra=2.5):
    page.wait_for_selector(TAB, timeout=10_000)
    page.get_by_role("tab", name=label).click()
    page.wait_for_load_state("networkidle", timeout=15_000)
    if has_chart:
        try:
            page.wait_for_selector(CHART, state="attached", timeout=15_000)
        except Exception:
            pass
    time.sleep(extra)


def main():
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
         "--server.port", str(PORT), "--server.headless", "true",
         "--browser.gatherUsageStats", "false", "--server.fileWatcherType", "none"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        print(f"Polling {BASE_URL} ...")
        if not poll(BASE_URL, 35):
            raise RuntimeError("Streamlit did not start")
        print("Ready.\n")

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
            page = ctx.new_page()

            # ── Customer Segmentation ──────────────────────────────────
            print("[Customer Segmentation]")
            page.goto(f"{BASE_URL}/Customer_Segmentation", wait_until="domcontentloaded")
            wait(page, has_chart=False, extra=8)
            snap(page, "03_segmentation.png")

            click_tab(page, "Modeling", has_chart=True, extra=5)
            snap(page, "03_segmentation_modeling.png")

            click_tab(page, "Evaluation", has_chart=True, extra=5)
            snap(page, "03_segmentation_evaluation.png")

            click_tab(page, "Live Inference", has_chart=False, extra=3)
            snap(page, "03_segmentation_live.png")

            # ── Anomaly Detection ──────────────────────────────────────
            print("\n[Anomaly Detection]")
            page.goto(f"{BASE_URL}/Anomaly_Detection", wait_until="domcontentloaded")
            wait(page, has_chart=False, extra=10)
            snap(page, "05_anomaly.png")

            click_tab(page, "Modeling", has_chart=True, extra=5)
            snap(page, "05_anomaly_modeling.png")

            click_tab(page, "Evaluation", has_chart=True, extra=5)
            snap(page, "05_anomaly_evaluation.png")

            click_tab(page, "Live Inference", has_chart=True, extra=4)
            snap(page, "05_anomaly_live.png")

            browser.close()

        # Verify
        print("\n=== Summary ===")
        targets = [
            "03_segmentation.png", "03_segmentation_modeling.png",
            "03_segmentation_evaluation.png", "03_segmentation_live.png",
            "05_anomaly.png", "05_anomaly_modeling.png",
            "05_anomaly_evaluation.png", "05_anomaly_live.png",
        ]
        bad = []
        for name in targets:
            f = SCREENSHOTS / name
            kb = f.stat().st_size // 1024
            flag = "  BLANK?" if kb < 50 else ""
            print(f"  {name}: {kb} KB{flag}")
            if kb < 50:
                bad.append(name)
        if bad:
            print(f"\nFAILED: {bad}")
            sys.exit(1)
        else:
            print("\nAll 8 screenshots OK.")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
