#!/usr/bin/env python3
"""
Automated full-page screenshot capture for the data science portfolio.

Usage (from the project root):
    python scripts/capture_screenshots.py

Prerequisites:
    pip install playwright
    playwright install chromium
"""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "docs" / "screenshots"
PORT = 8501
BASE_URL = f"http://localhost:{PORT}"

# Streamlit renders Plotly in iframes that embed this class once paint is done.
CHART_SEL = ".js-plotly-plot"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def poll_until_ready(url: str, timeout: float = 30.0) -> bool:
    """Poll url until HTTP 200 or timeout. No fixed sleep — tight 0.5 s loop."""
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


def wait_render(pw_page, has_chart: bool = True, has_tabs: bool = True,
                extra: float = 2.0) -> None:
    """
    Three-phase wait so screenshots are never taken on a blank/spinner frame:
      1. networkidle  — no pending XHR/WebSocket messages
      2. Content DOM  — stTab or stPlotlyChart exist in DOM (signals full render)
      3. Paint sleep  — give Plotly's requestAnimationFrame time to draw pixels

    In Streamlit 1.63, tabs are <div role="tab" data-testid="stTab">,
    not <button role="tab"> — we wait on the testid.
    """
    pw_page.wait_for_load_state("networkidle", timeout=30_000)
    if has_tabs:
        try:
            pw_page.wait_for_selector('[data-testid="stTab"]', timeout=20_000)
        except Exception:
            pass
    if has_chart:
        try:
            pw_page.wait_for_selector(CHART_SEL, state="attached", timeout=20_000)
        except Exception:
            pass
    time.sleep(extra)


def click_tab(pw_page, label: str, has_chart: bool = True, extra: float = 2.5) -> None:
    """
    Click a Streamlit tab and wait for its content to render.

    Streamlit 1.63 renders tabs as <div role="tab" data-testid="stTab">.
    Playwright's get_by_role("tab") searches by ARIA role regardless of tag,
    which works correctly here.
    """
    # Ensure tabs are present before clicking
    pw_page.wait_for_selector('[data-testid="stTab"]', timeout=20_000)
    pw_page.get_by_role("tab", name=label).click()
    pw_page.wait_for_load_state("networkidle", timeout=15_000)
    if has_chart:
        try:
            pw_page.wait_for_selector(CHART_SEL, state="attached", timeout=15_000)
        except Exception:
            pass
    time.sleep(extra)


def goto(pw_page, url: str, has_chart: bool = True, has_tabs: bool = True,
         extra: float = 3.0) -> None:
    """Navigate to a URL and wait for full render."""
    pw_page.goto(url, wait_until="domcontentloaded")
    wait_render(pw_page, has_chart=has_chart, has_tabs=has_tabs, extra=extra)


def snap(pw_page, filename: str) -> int:
    """Full-page PNG to docs/screenshots/. Returns file size in bytes."""
    dest = SCREENSHOTS / filename
    pw_page.screenshot(path=str(dest), full_page=True)
    kb = dest.stat().st_size // 1024
    print(f"  {filename}  ({kb} KB)")
    return dest.stat().st_size


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print(f"Polling {BASE_URL} (max 30 s) ...")
        if not poll_until_ready(BASE_URL, timeout=30):
            raise RuntimeError("Streamlit did not start within 30 seconds.")
        print("App ready.\n")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1600, "height": 1000},
                device_scale_factor=1,
            )
            page = ctx.new_page()

            # Streamlit multipage URL routing (1.32+):
            # pages/N_Name.py → /{Name}  (leading "N_" stripped by Streamlit)
            # We navigate there then fall back to sidebar click if the title
            # doesn't match, handling any future routing changes automatically.

            def nav(url_suffix: str, expected_title_fragment: str,
                    has_chart: bool = True, has_tabs: bool = True,
                    extra: float = 6.0) -> None:
                """Navigate to a page and verify we landed on it."""
                target = BASE_URL + url_suffix
                goto(page, target, has_chart=has_chart, has_tabs=has_tabs, extra=extra)
                # If Streamlit redirected back to home (wrong URL format),
                # fall back to clicking the sidebar nav link.
                content = page.content()
                if expected_title_fragment.lower() not in content.lower():
                    sidebar_link = page.locator(
                        f'[data-testid="stSidebarNavLink"]:has-text("{expected_title_fragment}")'
                    ).first
                    if sidebar_link.count() > 0:
                        sidebar_link.click()
                        wait_render(page, has_chart=has_chart, has_tabs=has_tabs,
                                    extra=extra)

            # ── 01 Home ──────────────────────────────────────────────────
            print("[01] Home")
            goto(page, BASE_URL, has_chart=False, has_tabs=False, extra=4)
            snap(page, "01_home.png")

            # ── 02 Trip Duration ─────────────────────────────────────────
            print("[02] Trip Duration")
            # First page visited trains models — allow extra time
            nav("/Trip_Duration", "Trip Duration", extra=12)
            snap(page, "02_trip_duration.png")
            click_tab(page, "Modeling")
            snap(page, "02_trip_duration_modeling.png")
            click_tab(page, "Evaluation")
            snap(page, "02_trip_duration_evaluation.png")
            click_tab(page, "Live Inference")
            snap(page, "02_trip_duration_live.png")

            # ── 03 Customer Segmentation ─────────────────────────────────
            print("[03] Customer Segmentation")
            nav("/Customer_Segmentation", "Customer Segmentation")
            snap(page, "03_segmentation.png")
            click_tab(page, "Modeling")
            snap(page, "03_segmentation_modeling.png")
            click_tab(page, "Evaluation")
            snap(page, "03_segmentation_evaluation.png")
            click_tab(page, "Live Inference", has_chart=False)
            snap(page, "03_segmentation_live.png")

            # ── 04 Market Basket ─────────────────────────────────────────
            print("[04] Market Basket")
            nav("/Market_Basket", "Market Basket", has_chart=False)
            snap(page, "04_basket.png")
            # Modeling tab runs Apriori — give it extra time
            click_tab(page, "Modeling", has_chart=False, extra=6)
            snap(page, "04_basket_modeling.png")
            click_tab(page, "Evaluation", has_chart=True, extra=5)
            snap(page, "04_basket_evaluation.png")
            click_tab(page, "Live Inference", has_chart=False, extra=5)
            snap(page, "04_basket_live.png")

            # ── 05 Anomaly Detection ─────────────────────────────────────
            print("[05] Anomaly Detection")
            nav("/Anomaly_Detection", "Anomaly Detection")
            snap(page, "05_anomaly.png")
            click_tab(page, "Modeling")
            snap(page, "05_anomaly_modeling.png")
            click_tab(page, "Evaluation")
            snap(page, "05_anomaly_evaluation.png")
            click_tab(page, "Live Inference", has_chart=True, extra=3)
            snap(page, "05_anomaly_live.png")

            # ── 06 Time Series ───────────────────────────────────────────
            print("[06] Time Series")
            nav("/Time_Series", "Time Series")
            snap(page, "06_timeseries.png")
            click_tab(page, "Modeling")
            snap(page, "06_timeseries_modeling.png")
            click_tab(page, "Evaluation")
            snap(page, "06_timeseries_evaluation.png")
            click_tab(page, "Live Inference")
            snap(page, "06_timeseries_live.png")

            # ── 07 CRISP-DM Audit ────────────────────────────────────────
            print("[07] CRISP-DM Audit")
            nav("/CRISPDM_Audit", "CRISP-DM", has_chart=False, extra=5)
            snap(page, "07_audit.png")
            # Leakage audit table is in the second tab
            click_tab(page, "Leakage Audit Table", has_chart=False, extra=1.5)
            snap(page, "07_audit_leakage_table.png")

            browser.close()

        # ── Size check ───────────────────────────────────────────────────
        print("\n=== Screenshot summary ===")
        small: list[str] = []
        for f in sorted(SCREENSHOTS.glob("*.png")):
            kb = f.stat().st_size // 1024
            flag = "  ← BLANK?" if kb < 50 else ""
            print(f"  {f.name:45s}  {kb:5d} KB{flag}")
            if kb < 50:
                small.append(f.name)

        if small:
            print(f"\nFAILED: {len(small)} screenshots under 50 KB — likely blank:")
            for n in small:
                print(f"  {n}")
            sys.exit(1)
        else:
            print(f"\nAll {len(list(SCREENSHOTS.glob('*.png')))} screenshots OK (>= 50 KB).")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
