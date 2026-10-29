"""Tests for the deterministic 1-5 fit score. This is our change from the
reference, which had no numeric score at all."""

from __future__ import annotations

import pytest

from lead_research.scoring import score_lead_fit

URL = ["https://example.com/profile"]


def test_perfect_match_with_signals_scores_five():
    r = score_lead_fit(
        company="Northwind Logistics",
        industry_match="exact",
        region_match="exact",
        size_match="exact",
        buying_signals=2,
        evidence_urls=URL,
    )
    # 2.0 + 1.5 + 1.5 + 1.0 = 6.0, clamped to 5.
    assert r["fit_score"] == 5
    assert r["raw_total"] == 6.0
    assert r["evidence_capped"] is False


def test_score_decreases_monotonically_as_match_weakens():
    def s(level):
        return score_lead_fit(
            company="C",
            industry_match=level,
            region_match=level,
            size_match=level,
            buying_signals=0,
            evidence_urls=URL,
        )["fit_score"]

    assert s("exact") > s("adjacent") > s("none") or (
        s("exact") >= s("adjacent") >= s("none")
    )
    assert s("exact") == 5
    assert s("none") == 1  # clamped up from a raw 0.0


def test_industry_outweighs_region_and_size_individually():
    industry_only = score_lead_fit(
        company="C", industry_match="exact", region_match="none",
        size_match="none", buying_signals=0, evidence_urls=URL,
    )
    region_only = score_lead_fit(
        company="C", industry_match="none", region_match="exact",
        size_match="none", buying_signals=0, evidence_urls=URL,
    )
    assert industry_only["raw_total"] > region_only["raw_total"]
    assert industry_only["contributions"]["industry"] == 2.0
    assert region_only["contributions"]["region"] == 1.5


def test_buying_signal_bonus_is_capped_at_two_signals():
    def raw(n):
        return score_lead_fit(
            company="C", industry_match="exact", region_match="none",
            size_match="none", buying_signals=n, evidence_urls=URL,
        )["contributions"]["buying_signals"]

    assert raw(0) == 0.0
    assert raw(1) == 0.5
    assert raw(2) == 1.0
    assert raw(9) == 1.0  # a company does not get to farm signals for score


def test_unevidenced_lead_is_capped_at_two_however_good_the_match():
    r = score_lead_fit(
        company="Ghost Corp",
        industry_match="exact",
        region_match="exact",
        size_match="exact",
        buying_signals=3,
        evidence_urls=[],
    )
    assert r["fit_score"] == 2
    assert r["evidence_capped"] is True
    assert r["raw_total"] == 6.0  # the raw score is preserved for the critic
    assert "no source URL" in r["rationale"]


def test_blank_and_whitespace_urls_do_not_count_as_evidence():
    r = score_lead_fit(
        company="Ghost Corp", industry_match="exact", region_match="exact",
        size_match="exact", buying_signals=0, evidence_urls=["", "   ", None],
    )
    assert r["evidence_count"] == 0
    assert r["evidence_capped"] is True
    assert r["fit_score"] == 2


@pytest.mark.parametrize("bad", ["partial", "EXACT-ish", "yes", ""])
def test_invalid_match_level_is_rejected_rather_than_coerced(bad):
    r = score_lead_fit(
        company="C", industry_match=bad, region_match="exact",
        size_match="exact", buying_signals=0, evidence_urls=URL,
    )
    assert "error" in r
    assert "industry_match" in r["error"]


def test_match_levels_are_case_and_space_insensitive():
    r = score_lead_fit(
        company="C", industry_match="  Exact ", region_match="ADJACENT",
        size_match="none", buying_signals=0, evidence_urls=URL,
    )
    assert "error" not in r
    assert r["contributions"]["industry"] == 2.0
    assert r["contributions"]["region"] == 0.75


def test_score_is_always_in_range_one_to_five():
    levels = ("exact", "adjacent", "none")
    for i in levels:
        for rg in levels:
            for sz in levels:
                for sig in (0, 1, 5):
                    r = score_lead_fit(
                        company="C", industry_match=i, region_match=rg,
                        size_match=sz, buying_signals=sig, evidence_urls=URL,
                    )
                    assert 1 <= r["fit_score"] <= 5, r


def test_scoring_is_deterministic():
    args = dict(
        company="Repeat Co", industry_match="adjacent", region_match="exact",
        size_match="adjacent", buying_signals=1, evidence_urls=URL,
    )
    assert score_lead_fit(**args) == score_lead_fit(**args)
