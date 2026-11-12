"""Inquiry memory (SO-RSI, signal 3): causal findings that persist across
rounds.

Every probe result is written here -- confirmed and refuted -- with the
round it came from and its evidence, and appended to a JSONL file so the
memory is inspectable after the run. The loop reads it back to decide:

  pending()          confirmed mechanisms not yet applied -> next systematic edit
  blocked_by(cause)  failed fixes this cause explains -> re-apply them with it
  cause_of(edit)     why an edit failed, if known -> veto a blind retry
"""
from __future__ import annotations

import json
from pathlib import Path

from so_probes import Finding


class InquiryMemory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.findings: list[dict] = []
        self.applied: set[str] = set()          # mechanisms applied and kept
        self.exhausted: set[str] = set()        # mechanisms applied and not kept
        self.edit_cause: dict[str, str] = {}    # edit_key -> mechanism that blocked it

    def record(self, finding: Finding, round_: int) -> dict:
        row = {"round": round_, **finding.as_dict()}
        self.findings.append(row)
        if finding.confirmed and finding.mechanism and finding.blocked_edit:
            self.edit_cause[finding.blocked_edit] = finding.mechanism
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        return row

    def confirmed(self) -> list[dict]:
        return [f for f in self.findings if f["confirmed"] and f["mechanism"]]

    def pending(self) -> list[str]:
        seen, out = set(), []
        for f in self.confirmed():
            m = f["mechanism"]
            if m not in self.applied and m not in self.exhausted and m not in seen:
                seen.add(m)
                out.append(m)
        return out

    def evidence_for(self, mechanism: str) -> tuple[str, ...]:
        qids: list[str] = []
        for f in self.confirmed():
            if f["mechanism"] == mechanism:
                for key in ("fixed_by_priority_dispatch", "fixed_by_entity_linking",
                            "fixed_by_distinct"):
                    qids += f["evidence"].get(key, [])
        return tuple(dict.fromkeys(qids))

    def blocked_by(self, mechanism: str) -> list[str]:
        return [e for e, m in self.edit_cause.items() if m == mechanism]

    def cause_of(self, edit_key: str) -> str | None:
        m = self.edit_cause.get(edit_key)
        return m if m and m not in self.applied else None

    def mark(self, mechanism: str, kept: bool) -> None:
        (self.applied if kept else self.exhausted).add(mechanism)
        if kept:
            for e in [e for e, m in self.edit_cause.items() if m == mechanism]:
                del self.edit_cause[e]
