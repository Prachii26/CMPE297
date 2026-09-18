"""Stage 14: compaction.

Four mechanisms, cheapest first. `cap_fresh_result` runs unconditionally,
the instant a tool result is created in run_loop, regardless of how full
the context window is -- a single huge result shouldn't sit in memory at
full size even when the rest of the transcript is nowhere near the
limit. The other three only run inside `compact()`, called once before
every outgoing request, and only do anything once the transcript has
crossed HIGH_WATER (85%) of the window:

  1. cap_fresh_result       -- one oversized result -> a temp file + stub.
  2. shrink_finished_results -- old tool results -> a 300-char stub.
  3. drop_old_results       -- old tool results -> a one-line marker.
  4. summarize (no tools)   -- ask the model for a handoff note, and
                                replace the bulk of the transcript with it.

Each is more destructive (and, for #4, more expensive -- it's a whole
extra API call) than the one before it, so `compact()` only reaches for
a costlier mechanism once the cheaper ones have nothing left to give.

Size is measured in characters, not tokens. That's an approximation, not
real tokenization -- see the README for why that's an honest tradeoff for
a project with no tokenizer dependency, not a claim of precision.
"""
import os
import tempfile
import time

CONTEXT_WINDOW_CHARS = 400_000
FRESH_RESULT_CAP = 10_000
FINISHED_STUB_LEN = 300
HIGH_WATER = 0.85
LOW_WATER = 0.35

_TEMP_DIR = None


def _temp_dir():
    global _TEMP_DIR
    if _TEMP_DIR is None:
        _TEMP_DIR = tempfile.mkdtemp(prefix="agent_compaction_")
    return _TEMP_DIR


def estimate_chars(messages) -> int:
    """A char count, not a token count -- the cheap proxy this project
    uses instead of a tokenizer dependency."""
    total = 0
    for m in messages:
        total += len(m.get("content") or "")
        for call in m.get("tool_calls") or []:
            total += len(call["function"]["arguments"])
    return total


def cap_fresh_result(content: str) -> str:
    """Mechanism 1, cheapest: a single length check, no scan of the rest
    of the transcript. Applied the moment a tool result is created."""
    if len(content) <= FRESH_RESULT_CAP:
        return content
    path = os.path.join(_temp_dir(), f"result_{time.time_ns()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return (
        f"(output was {len(content)} chars, over the {FRESH_RESULT_CAP} cap; "
        f"full output written to {path}. read_file that path if more is needed.)"
    )


def _last_user_index(messages):
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "user":
            return i
    return -1


def shrink_finished_results(messages) -> bool:
    """Mechanism 2. A tool result belongs to a FINISHED turn if it sits
    before the most recent user message -- a new user turn only starts
    once the model has already answered the previous one. Shrinks the
    first untouched one found; returns whether it found one, so
    compact() can re-check size and decide whether to shrink another."""
    boundary = _last_user_index(messages)
    for m in messages[:boundary] if boundary >= 0 else []:
        if m["role"] != "tool":
            continue
        if m["content"].startswith("(shrunk:") or m["content"].startswith("(dropped:"):
            continue
        if len(m["content"]) > FINISHED_STUB_LEN:
            original_len = len(m["content"])
            m["content"] = f"(shrunk: was {original_len} chars) " + m["content"][:FINISHED_STUB_LEN]
            return True
    return False


def drop_old_results(messages) -> bool:
    """Mechanism 3, more aggressive than shrinking: replace one finished
    tool result with a one-line marker, oldest first. One at a time, so
    compact() only drops as many as it actually needs to."""
    boundary = _last_user_index(messages)
    for m in messages[:boundary] if boundary >= 0 else []:
        if m["role"] == "tool" and m["content"] != "(dropped: old tool result, no longer available)":
            m["content"] = "(dropped: old tool result, no longer available)"
            return True
    return False


def _summarize(messages, client, model):
    """Mechanism 4: a call with NO tools= at all -- it cannot act, it can
    only write a handoff note."""
    response = client.chat.completions.create(
        model=model,
        messages=messages
        + [
            {
                "role": "user",
                "content": (
                    "Write a short handoff note (under 500 words) covering what "
                    "the user wants, what has already been done, and what is "
                    "still left to do. This note will REPLACE the conversation "
                    "history, so include everything still needed to continue."
                ),
            }
        ],
    )
    return response.choices[0].message.content


def compact(messages, client, model, summarize_fn=None):
    """Called once before every outgoing request. Mutates `messages` in
    place. Does nothing at all if the transcript is under HIGH_WATER."""
    if estimate_chars(messages) <= CONTEXT_WINDOW_CHARS * HIGH_WATER:
        return

    while estimate_chars(messages) > CONTEXT_WINDOW_CHARS * LOW_WATER:
        if shrink_finished_results(messages):
            continue
        if drop_old_results(messages):
            continue
        break  # nothing cheap left to try -- fall through to mechanism 4

    if estimate_chars(messages) > CONTEXT_WINDOW_CHARS * HIGH_WATER:
        note = (summarize_fn or _summarize)(messages, client, model)
        system_msgs = [m for m in messages if m["role"] == "system"]
        messages[:] = system_msgs + [{"role": "user", "content": f"<handoff-note>\n{note}\n</handoff-note>"}]
