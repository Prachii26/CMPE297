"""Build article/article-medium.md from article/article.md.

The repo version uses relative links. The Medium version rewrites every repo
link to an absolute GitHub URL, points images at raw.githubusercontent.com so
the markdown previews, and starts with an upload checklist of the figures in
the order they appear. Run from the short_story folder:

    .\.venv\Scripts\python.exe scripts\make_medium.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = "https://github.com/Prachii26/CMPE297"
RAW = "https://raw.githubusercontent.com/Prachii26/CMPE297/main"
ROOT = Path(__file__).resolve().parent.parent          # short_story/
REPO_ROOT = ROOT.parent
SRC = ROOT / "article" / "article.md"
DST = ROOT / "article" / "article-medium.md"


def absolute(target: str) -> str:
    """Resolve a link relative to short_story/article/ into a GitHub URL."""
    path = (SRC.parent / target).resolve()
    rel = path.relative_to(REPO_ROOT).as_posix()
    kind = "tree" if path.is_dir() or target.endswith("/") else "blob"
    return f"{REPO}/{kind}/main/{rel}"


def main() -> None:
    text = SRC.read_text(encoding="utf-8")

    figures = re.findall(r"!\[[^\]]*\]\(figures/([^)]+)\)", text)
    text = re.sub(r"!\[([^\]]*)\]\(figures/([^)]+)\)",
                  lambda m: f"![{m.group(1)}]({RAW}/short_story/article/figures/{m.group(2)})", text)
    text = re.sub(r"(?<!!)\[([^\]]+)\]\((\.\./[^)]+)\)",
                  lambda m: f"[{m.group(1)}]({absolute(m.group(2))})", text)

    leftovers = re.findall(r"\]\((?!https?://)[^)]+\)", text)
    if leftovers:
        raise SystemExit(f"relative links left in Medium version: {leftovers}")

    lines = ["> **Medium upload order** (delete this block before publishing). Upload these images "
             "from `short_story/article/figures/` in this order; each caption is the italic line "
             "under the image.", ">"]
    lines += [f"> {i}. `{name}`" for i, name in enumerate(figures, 1)]
    lines += ["", "---", ""]
    DST.write_text("\n".join(lines) + "\n" + text, encoding="utf-8")
    print(f"wrote {DST.name}: {len(figures)} figures")
    for i, name in enumerate(figures, 1):
        print(f"  {i}. {name}")


if __name__ == "__main__":
    main()
