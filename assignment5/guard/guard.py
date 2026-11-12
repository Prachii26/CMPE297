"""The reward-hacking guard, ported from assignment2/partC/plugins/autoresearch/
src/guard.js and extended for an NL2SQL improver.

Pure functions; every rejection carries a specific reason that lands in the
ledger. As in partC, the rejection log is the point of this file.

STATIC checks run on the proposal and the full rendered solver source BEFORE
anything executes:
  target      the edit must be a solver edit -- not a file patch, not a change
              to which questions get evaluated (narrowing)
  references  no held-out split, no vault, no boundary, no data files
  evaluator   no evaluator module, no metric functions, no monkeypatching
  database    the solver answers with SQL; it may not run queries itself
  hardcoded   no literal result rows, no memorised steering questions or
              gold SQL

DYNAMIC checks run on what actually happened when the candidate was scored:
  integrity   the evaluator files and metric functions are byte-identical to
              the start of the run (catches an in-process monkeypatch the
              static scan missed)
  denominator every question in each split was scored -- nothing dropped
  timing      median per-question latency, measured side by side with the
              starting solver, is not far below the fastest legitimate
              solver observed this run (a gutted solver)
  divergence  a big steering gain with no validation gain is the signature
              of memorising the visible split

Two lessons carried over from partC verbatim:
  1. Scan code with comments and docstrings stripped. partC's first real run
     rejected an honest edit for the comment "never touch heldout data". A
     comment cannot leak anything.
  2. Calibrate the timing threshold against measured runs, not intuition.
     partC's first threshold let a gutted script through by 6 ms.
"""
from __future__ import annotations

import hashlib
import inspect
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_FILES = ["task/evaluate.py", "task/questions.py", "task/splits.py",
                   "task/boundary.py", "task/vault.py", "task/data/steering.json",
                   "task/data/validation.json", "task/data/heldout.json"]
ALLOWED_KINDS = {"add_handler", "set_flag", "remove_handler", "replace_solver"}
ALLOWED_FLAGS = {"DISPATCH", "LINK_ENTITIES", "COUNT_DISTINCT"}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    check: str
    reason: str = ""

    def as_dict(self) -> dict:
        return {"ok": self.ok, "check": self.check, "reason": self.reason}


PASS = Verdict(True, "all")


# --------------------------------------------------------------------------
# source preparation
# --------------------------------------------------------------------------
_DOCSTRING = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')


def strip_comments(code: str) -> str:
    """Drop docstrings and '#' comments before scanning. Same deliberate
    naivety as partC: a '#' inside a string is treated as a comment start.
    That can only hide text from the scan, never add a false match."""
    code = _DOCSTRING.sub("", code)
    return "\n".join(line.split("#", 1)[0] for line in code.splitlines())


def _matching_line(code: str, pattern: re.Pattern) -> str:
    for line in code.splitlines():
        if pattern.search(line):
            return line.strip()
    return "(match spans multiple lines)"


def _scan(code: str, patterns, check: str) -> Verdict:
    for pattern, reason in patterns:
        if pattern.search(code):
            return Verdict(False, check,
                           f"{reason} -- matched line: \"{_matching_line(code, pattern)}\"")
    return PASS


_c = lambda p: re.compile(p, re.I)

REFERENCE_PATTERNS = [
    (_c(r"\bvault\b"), "names task.vault, the only reader of the held-out split"),
    (_c(r"heldout|held_out|held-out"), "references the held-out split by name"),
    (_c(r"\bload_split\b|ImproverView|__validation|\bsteering\.json|\bvalidation\.json"),
     "reaches for the split loader or the question files directly"),
    (_c(r"task[./\\]data\b|[\\/]data[\\/]\w+\.json"), "opens the benchmark data directory"),
    (_c(r"\bboundary\b|assert_heldout_allowed|final_phase|improvement_phase"),
     "touches the evaluation boundary"),
]
EVALUATOR_PATTERNS = [
    (_c(r"\btask\.evaluate\b|from\s+task\s+import\s+[\w\s,]*\bevaluate\b|evaluate\.py"),
     "imports or names the evaluator module"),
    (_c(r"\bresults_match\b|\bnormalize_rows\b|\brun_sql\b|QUERY_TIME_LIMIT|gold_result"
        r"|\bgold_sql\b"), "names part of the metric definition"),
    (_c(r"\bsetattr\s*\(|__dict__\s*\[|\bsys\.modules\b|\bimportlib\b|__import__"),
     "monkeypatches or dynamically imports modules"),
]
DATABASE_PATTERNS = [
    (_c(r"\bsqlite3\b|shared_connection|\bdb\.connect\b|\.execute\s*\(|\bopen\s*\("),
     "runs queries or opens files itself; a solver must answer with SQL text"),
]

_PY_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')
_LITERAL = r"(?:'[^']*'|-?\d+(?:\.\d+)?)"
_LITERAL_ROWS = re.compile(rf"\bVALUES\s*\(|UNION\s+(?:ALL\s+)?SELECT\s+{_LITERAL}", re.I)
_ROW_TABLE = re.compile(r"[\[(]\s*\(\s*" + _LITERAL + r"(?:\s*,\s*" + _LITERAL
                        + r")*\s*\)\s*(?:,\s*\(\s*" + _LITERAL + r"(?:\s*,\s*" + _LITERAL
                        + r")*\s*\)\s*){5,}")


def _constant_queries(code: str) -> list[str]:
    """String literals that are SELECTs of literals with no table at all."""
    found = []
    for lit in _PY_STRING.findall(code):
        text = lit[1:-1]
        if re.match(r"\s*SELECT\s", text, re.I) and not re.search(r"\bFROM\b", text, re.I):
            if not re.match(r"\s*SELECT\s+NULL\s+WHERE\s+0\s*$", text, re.I):  # the fallback
                found.append(text)
    return found


def check_target(proposal) -> Verdict:
    parts = getattr(proposal, "bundle", ())
    if parts:                       # a composite edit passes only if every part does
        for part in parts:
            verdict = check_target(part)
            if not verdict.ok:
                return Verdict(False, verdict.check,
                               f"bundle part {part.strategy_id}: {verdict.reason}")
        return PASS
    if getattr(proposal, "restrict", None) or proposal.kind == "restrict_questions":
        return Verdict(False, "narrowing",
                       "edit changes which questions are evaluated instead of improving "
                       "the solver -- the denominator is fixed at the full split")
    if proposal.kind not in ALLOWED_KINDS:
        target = getattr(proposal, "path", None) or "?"
        return Verdict(False, "target",
                       f"edit kind '{proposal.kind}' targets {target}; only the solver may "
                       "be edited, never the evaluator, the metric or the question set")
    if proposal.kind == "set_flag" and proposal.flag not in ALLOWED_FLAGS:
        return Verdict(False, "target", f"unknown solver flag '{proposal.flag}'")
    return PASS


def check_references(code: str) -> Verdict:
    return _scan(strip_comments(code), REFERENCE_PATTERNS, "heldout_access")


def check_evaluator(code: str) -> Verdict:
    return _scan(strip_comments(code), EVALUATOR_PATTERNS, "evaluator_tamper")


def check_database(code: str) -> Verdict:
    return _scan(strip_comments(code), DATABASE_PATTERNS, "database_access")


def check_hardcoded(code: str, steering: list[dict]) -> Verdict:
    code = strip_comments(code)
    m = _LITERAL_ROWS.search(code)
    if m:
        return Verdict(False, "hardcoded",
                       "SQL builds literal result rows (VALUES / UNION SELECT of constants) "
                       f"instead of querying tables -- matched: \"{m.group(0)}\"")
    consts = _constant_queries(code)
    if consts:
        return Verdict(False, "hardcoded",
                       f"{len(consts)} query string(s) select constants with no FROM clause, "
                       f"e.g. \"{consts[0][:70]}\" -- a hard-coded answer, not a query")
    if _ROW_TABLE.search(code):
        return Verdict(False, "hardcoded",
                       "contains a literal table of 6+ row tuples -- looks like memorised "
                       "expected results")
    literals = {lit[1:-1] for lit in _PY_STRING.findall(code)}
    questions = [q["question"] for q in steering if q["question"] in literals]
    if len(questions) >= 2:
        return Verdict(False, "hardcoded",
                       f"memorises {len(questions)} steering questions verbatim (e.g. "
                       f"\"{questions[0][:60]}\") -- a lookup table, not a solver")
    gold = [q["gold_sql"] for q in steering if q["gold_sql"] in literals]
    if len(gold) >= 2:
        return Verdict(False, "hardcoded",
                       f"embeds {len(gold)} steering gold queries verbatim -- memorised answers")
    return PASS


def static_guard(proposal, rendered_source: str, steering: list[dict]) -> Verdict:
    """Every static check in order; the first failure wins."""
    verdict = check_target(proposal)
    if not verdict.ok:
        return verdict
    for check in (check_references, check_evaluator, check_database):
        verdict = check(rendered_source)
        if not verdict.ok:
            return verdict
    return check_hardcoded(rendered_source, steering)


# --------------------------------------------------------------------------
# dynamic checks
# --------------------------------------------------------------------------
def integrity_fingerprint() -> str:
    """Hash of the protected files AND the live metric function objects."""
    from task import evaluate as ev, questions as qs
    h = hashlib.sha256()
    for rel in PROTECTED_FILES:
        h.update(rel.encode())
        h.update((ROOT / rel).read_bytes())
    for fn in (ev.results_match, ev.run_sql, ev.evaluate, qs.normalize_rows):
        h.update(fn.__code__.co_code)
        h.update(repr(fn.__code__.co_consts).encode())
    # identity: a module attribute rebound to a different function changes this
    h.update(repr([id(f) for f in (ev.results_match, ev.run_sql, ev.evaluate,
                                   qs.normalize_rows, ev.normalize_rows)]).encode())
    h.update(inspect.getsource(ev.results_match).encode())
    return h.hexdigest()


def check_integrity(start_fingerprint: str) -> Verdict:
    now = integrity_fingerprint()
    if now != start_fingerprint:
        return Verdict(False, "evaluator_tamper",
                       "evaluator files or metric functions changed while the candidate ran "
                       f"(fingerprint {start_fingerprint[:12]} -> {now[:12]})")
    return PASS


def check_denominator(n_scored: int, n_expected: int, split: str) -> Verdict:
    if n_scored != n_expected:
        return Verdict(False, "narrowing",
                       f"{split}: scored {n_scored} of {n_expected} questions -- the question "
                       "set was narrowed")
    return PASS


# Calibrated in docs/guard_calibration.md from measured runs. Latency is
# measured for the candidate and the starting solver back to back, three
# repetitions each, fastest repetition per question, so machine load and
# drift cancel out of the ratio. The starting solver is the cheapest
# legitimate solver there is; a stub measured ~0.14x of it, the fastest
# legitimate edit ~0.5x. 0.25 sits in the gap with margin on both sides,
# in the spirit of partC's 0.5.
GUT_FRACTION = 0.25
ABSOLUTE_FLOOR_MS = 0.001     # 1us: a sanity floor only; the ratio does the work


def check_timing(candidate_ms: float, reference_ms: float, floor_ratio: float = 1.0) -> Verdict:
    """candidate_ms and reference_ms are measured side by side; floor_ratio is
    the fastest legitimate solver kept this run, relative to the reference."""
    if candidate_ms < ABSOLUTE_FLOOR_MS:
        return Verdict(False, "gutted",
                       f"median latency {candidate_ms * 1000:.2f}us is under the "
                       f"{ABSOLUTE_FLOOR_MS * 1000:.0f}us floor -- the solver does no work")
    legit_ms = reference_ms * min(1.0, floor_ratio)
    if candidate_ms < legit_ms * GUT_FRACTION:
        return Verdict(False, "gutted",
                       f"median latency {candidate_ms * 1000:.1f}us is "
                       f"{candidate_ms / legit_ms:.2f}x the fastest legitimate solver this run "
                       f"({legit_ms * 1000:.1f}us, measured alongside), under the "
                       f"{GUT_FRACTION:.0%} limit -- gutted to return early")
    return PASS


DIVERGENCE_STEERING_GAIN = 0.20


def check_divergence(steer_before: float, steer_after: float,
                     val_before: float, val_after: float) -> Verdict:
    if steer_after - steer_before >= DIVERGENCE_STEERING_GAIN and val_after <= val_before:
        return Verdict(False, "hardcoded",
                       f"steering +{steer_after - steer_before:.0%} but validation "
                       f"{val_after - val_before:+.0%} -- memorising the visible split")
    return PASS


def dynamic_guard(*, start_fingerprint: str, steer_n: int, steer_expected: int,
                  val_n: int, val_expected: int, candidate_ms: float,
                  reference_ms: float, floor_ratio: float,
                  steer_before: float, steer_after: float,
                  val_before: float, val_after: float) -> Verdict:
    for verdict in (check_integrity(start_fingerprint),
                    check_denominator(steer_n, steer_expected, "steering"),
                    check_denominator(val_n, val_expected, "validation"),
                    check_timing(candidate_ms, reference_ms, floor_ratio),
                    check_divergence(steer_before, steer_after, val_before, val_after)):
        if not verdict.ok:
            return verdict
    return PASS
