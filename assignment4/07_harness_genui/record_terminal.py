"""Record a real terminal run of the harness to SVG (for docs/).

    .\.venv\Scripts\python.exe record_terminal.py --mode declarative --prompt "Show me the study-room dashboard" --svg docs\terminal_declarative.svg

Swaps stage 13's ui.console for a recording console, then runs harness/main.py
for one turn exactly as `main.py --prompt` does.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness"))
from rich.console import Console  # noqa: E402

import ui  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--mode", required=True)
ap.add_argument("--prompt", required=True)
ap.add_argument("--svg", required=True)
a = ap.parse_args()
ui.console = Console(record=True, width=118)
import main  # noqa: E402

main.main(["--mode", a.mode, "--prompt", a.prompt])
ui.console.save_svg(a.svg, title=f"stage 15 harness + render_ui - {a.mode}")
