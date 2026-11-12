"""Token counts for the same study-room interface in three formats.

    .\.venv\Scripts\python.exe measure_tokens.py

Method
  * Content: identical in all three (see formats.py) -- 1 heading, 3 metrics,
    7 chart points, 6 rooms x 6 fields, a form with 3 rooms and 4 slots, a button.
  * Tokenizers: tiktoken cl100k_base and o200k_base, loaded from the BPE files
    vendored in tokenizer/ (TIKTOKEN_CACHE_DIR), so no network is used.
  * JSON is counted twice: compact (no whitespace) and pretty (indent=2), because
    a model's output can be either and the gap is large.
  * OpenUI Lang is counted as written: one statement per line.
Writes docs/token_measurement.json and prints a markdown table.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).parent
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(HERE / "tokenizer"))

import tiktoken  # noqa: E402

import formats  # noqa: E402

ENCODINGS = ("cl100k_base", "o200k_base")


def count(text):
    return {e: len(tiktoken.get_encoding(e).encode(text)) for e in ENCODINGS}


def main():
    rows = {
        "OpenUI Lang": formats.openui_lang(),
        "A2UI JSONL (compact)": formats.a2ui_jsonl(),
        "A2UI JSONL (pretty)": formats.pretty(formats.a2ui_jsonl()),
        "json-render JSON (compact)": formats.json_render(),
        "json-render JSON (pretty)": formats.pretty(formats.json_render()),
    }
    base = count(rows["OpenUI Lang"])
    out = []
    for name, text in rows.items():
        c = count(text)
        out.append({"format": name, "chars": len(text), **c,
                    "vs_lang_cl100k": round(c["cl100k_base"] / base["cl100k_base"], 2)})
    (HERE / "docs").mkdir(exist_ok=True)
    (HERE / "docs" / "token_measurement.json").write_text(json.dumps(out, indent=2))
    print("| format | chars | cl100k_base tokens | o200k_base tokens | x OpenUI Lang (cl100k) |")
    print("|---|---|---|---|---|")
    for r in out:
        print(f"| {r['format']} | {r['chars']} | {r['cl100k_base']} | {r['o200k_base']} | {r['vs_lang_cl100k']}x |")


if __name__ == "__main__":
    main()
