"""Deterministic 1-5 fit scoring for a lead.

The split of labour here is deliberate: the model *observes* (how well does this
company match the industry, the region, the size band; what buying signals did I
find; what URLs back that up), and this code *decides* the number. That keeps
the score reproducible, testable without the API, and immune to a model that
feels generous on one run and stingy on the next.
"""

from __future__ import annotations

from typing import Any

MATCH_LEVELS = ("exact", "adjacent", "none")

# Industry is the strongest signal of fit, then region and size equally.
WEIGHTS: dict[str, dict[str, float]] = {
    "industry": {"exact": 2.0, "adjacent": 1.0, "none": 0.0},
    "region": {"exact": 1.5, "adjacent": 0.75, "none": 0.0},
    "size": {"exact": 1.5, "adjacent": 0.75, "none": 0.0},
}

SIGNAL_BONUS = 0.5
MAX_SIGNAL_BONUS = 1.0

# A lead nobody can cite is a guess. Without a source URL the score is capped,
# however good the match looks, so the critic loop has something to push on.
UNEVIDENCED_CAP = 2


def score_lead_fit(
    company: str,
    industry_match: str,
    region_match: str,
    size_match: str,
    buying_signals: int,
    evidence_urls: list[str],
) -> dict[str, Any]:
    """Score how well one company fits the ideal customer profile, 1 to 5.

    Call this once per candidate company. Supply what you actually found; do not
    guess a score yourself, this function computes it.

    Args:
        company: The company name.
        industry_match: How well the company's industry matches the ICP.
            One of "exact", "adjacent", "none".
        region_match: How well its headquarters or main market matches the ICP
            region. One of "exact", "adjacent", "none".
        size_match: How well its headcount or revenue matches the ICP size band.
            One of "exact", "adjacent", "none".
        buying_signals: How many distinct buying signals you found, such as a
            relevant job posting, a funding round, a public migration, or a
            leadership hire. 0 or more; only the first two affect the score.
        evidence_urls: Source URLs backing the claims above. A lead with no
            evidence URL is capped at 2 regardless of how well it matches.

    Returns:
        A dict with the integer fit_score (1-5), the raw weighted total, the
        per-dimension contributions, whether the evidence cap was applied, and
        a one-line rationale.
    """
    norm = {}
    for field, value in (
        ("industry", industry_match),
        ("region", region_match),
        ("size", size_match),
    ):
        v = (value or "").strip().lower()
        if v not in MATCH_LEVELS:
            return {
                "error": (
                    f"{field}_match must be one of {list(MATCH_LEVELS)}, "
                    f"got {value!r}"
                )
            }
        norm[field] = v

    try:
        signals = max(0, int(buying_signals))
    except (TypeError, ValueError):
        return {"error": f"buying_signals must be an integer, got {buying_signals!r}"}

    urls = [u.strip() for u in (evidence_urls or []) if isinstance(u, str) and u.strip()]

    contributions = {f: WEIGHTS[f][norm[f]] for f in norm}
    signal_bonus = min(signals * SIGNAL_BONUS, MAX_SIGNAL_BONUS)
    raw = sum(contributions.values()) + signal_bonus

    # raw is 0.0-6.0; map onto 1-5 and clamp.
    score = int(round(raw))
    score = max(1, min(score, 5))

    capped = False
    if not urls and score > UNEVIDENCED_CAP:
        score = UNEVIDENCED_CAP
        capped = True

    bits = [
        f"industry {norm['industry']}",
        f"region {norm['region']}",
        f"size {norm['size']}",
        f"{signals} buying signal{'s' if signals != 1 else ''}",
    ]
    rationale = f"{company}: " + ", ".join(bits)
    if capped:
        rationale += "; capped at 2 because no source URL was supplied"

    return {
        "company": company,
        "fit_score": score,
        "raw_total": round(raw, 2),
        "contributions": {
            **{k: round(v, 2) for k, v in contributions.items()},
            "buying_signals": round(signal_bonus, 2),
        },
        "evidence_count": len(urls),
        "evidence_capped": capped,
        "rationale": rationale,
    }
