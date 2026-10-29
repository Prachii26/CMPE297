"""Web search for the researchers, backed by DuckDuckGo via `ddgs`.

Why not the built-in `google_search`: Gemini's Search grounding is metered on a
quota dimension separate from (and far tighter than) the model's own, and it is
exhausted on this key. Proved by a controlled test — same model, same minute, a
plain request returns 200 while the identical request carrying
`tools: [{google_search: {}}]` returns 429. Three researchers all grounded on
Google therefore could never get past the parallel stage, whichever models they
used.

DDG needs no API key and no quota, so the pipeline can actually run. What the
pipeline is demonstrating — Sequential/Parallel/Loop composition, `output_key`
state passing, and a critic that rejects unsourced leads — does not depend on
which search engine is behind the tool.

This is a plain `FunctionTool`, so unlike `google_search` it can sit on an
agent alongside other tools without tripping ADK's built-in-tool restriction.
"""

from __future__ import annotations

import os
import random
import threading
import time
from typing import Any

MAX_RESULTS_CAP = 8
SNIPPET_CHARS = 400

# DDG throttles bursts. Three researchers fire at once, so calls are spaced
# out by reserving a time slot under a lock.
#
# The lock is held only long enough to claim a slot — never across the network
# call. An earlier version wrapped the whole request, and a single slow search
# then blocked every other researcher: a live run sat for 1500 seconds with
# zero API errors and never left the parallel stage.
_LOCK = threading.Lock()
# DDG answers a burst with HTTP 202 and no results rather than an error, so the
# gap has to be generous. Measured: three researchers at 1.5s produced 4 usable
# responses against 15 rate-limited ones.
_MIN_GAP_SECONDS = float(os.environ.get("LEAD_RESEARCH_SEARCH_GAP", "6.0"))
_next_slot = [0.0]

RETRY_ATTEMPTS = 4

# Hard ceiling on one DDG request, so a hung connection cannot stall a
# researcher indefinitely.
SEARCH_TIMEOUT = float(os.environ.get("LEAD_RESEARCH_SEARCH_TIMEOUT", "20"))


def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the web and return titles, URLs and snippets.

    Use this to find real companies and real evidence. Every URL you report in
    your findings must come from a result this tool returned; never construct
    or guess one.

    Args:
        query: The search query. Be specific — include the industry, the
            region and the size band rather than searching a bare company name.
        max_results: How many results to return, 1 to 8. Default 5.

    Returns:
        A dict with the query, the result count, and `results`: a list of
        {title, url, snippet}. On failure, `ok` is False and `error` explains
        why; this tool never raises.
    """
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "query must not be empty", "results": []}

    try:
        n = max(1, min(int(max_results), MAX_RESULTS_CAP))
    except (TypeError, ValueError):
        n = 5

    try:
        from ddgs import DDGS
    except ImportError:
        return {
            "ok": False,
            "error": "ddgs is not installed; run: pip install ddgs",
            "results": [],
        }

    last_error = ""
    for attempt in range(RETRY_ATTEMPTS):
        try:
            # Claim a slot (fast, under the lock), then wait and search
            # outside it so no caller can block the others.
            with _LOCK:
                now = time.time()
                slot = max(now, _next_slot[0])
                _next_slot[0] = slot + _MIN_GAP_SECONDS
            delay = slot - time.time()
            if delay > 0:
                time.sleep(delay)

            with DDGS(timeout=SEARCH_TIMEOUT) as ddgs:
                rows = list(ddgs.text(query, max_results=n))

            # An empty result set from DDG usually means throttling (it
            # answers a burst with 202 and an empty body, not an error), so
            # treat it as retryable rather than as a genuine "nothing found".
            if not rows and attempt < RETRY_ATTEMPTS - 1:
                raise RuntimeError("empty result set, likely rate limited (HTTP 202)")

            results = []
            for r in rows:
                url = (r.get("href") or r.get("url") or "").strip()
                if not url:
                    continue
                results.append({
                    "title": (r.get("title") or "").strip(),
                    "url": url,
                    "snippet": (r.get("body") or "").strip()[:SNIPPET_CHARS],
                })

            return {
                "ok": True,
                "query": query,
                "result_count": len(results),
                "results": results,
                "note": (
                    "No results. Try a broader query."
                    if not results
                    else "Cite the `url` values exactly; do not invent URLs."
                ),
            }
        except Exception as e:  # ddgs raises a variety of transport errors
            last_error = f"{type(e).__name__}: {e}"
            if attempt < RETRY_ATTEMPTS - 1:
                # Backoff with jitter; DDG rate-limits bursts rather than quotas.
                time.sleep((2 ** attempt) * 2 + random.uniform(0, 1.5))

    return {
        "ok": False,
        "error": f"search failed after {RETRY_ATTEMPTS} attempts: {last_error}",
        "query": query,
        "results": [],
    }
