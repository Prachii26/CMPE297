"""Stage 12: permissions.

A rule table rates every shell command allow / ask / deny before bash()
ever runs it. Compound commands (`a && b`, `a | b`) are split into pieces
and each piece is classified on its own; the overall verdict is the
STRICTEST one among the pieces, because "ls && rm -rf /" must not be
allowed just because `ls` alone is harmless.

Honesty note, expanded on in this stage's README: this only inspects
command TEXT. It has no idea what a variable expands to, doesn't parse
shell quoting, and can be defeated by anyone who wants to defeat it (an
alias, a script that wraps the dangerous call, base64-encoding it, and so
on). It is a speed bump for an honest, well-behaved model, not a security
boundary. Stage 13 adds OS-level enforcement that doesn't have this
problem.
"""
import re

RULES = [
    (re.compile(r"^\s*rm\s+-rf\b"), "deny"),
    (re.compile(r"^\s*rm\b"), "ask"),
    (re.compile(r"^\s*git\s+push\b"), "ask"),
    (re.compile(r"^\s*curl\b"), "ask"),
    (re.compile(r"^\s*wget\b"), "ask"),
    (re.compile(r"^\s*(ls|cat|pwd|echo|git|grep|find|head|tail|dir|type)\b"), "allow"),
]
DEFAULT_VERDICT = "ask"

VERDICT_RANK = {"allow": 0, "ask": 1, "deny": 2}


def classify_one(command: str) -> str:
    for pattern, verdict in RULES:
        if pattern.search(command):
            return verdict
    return DEFAULT_VERDICT


def split_compound(command: str):
    """Split on && and | -- textual, not shell-aware. A pipe or && that
    appears inside quotes still gets split here. That's a real limitation,
    not an oversight; see the README."""
    parts = re.split(r"&&|\|", command)
    return [p.strip() for p in parts if p.strip()]


def classify(command: str):
    """Returns (overall_verdict, [(sub_command, verdict), ...])."""
    parts = split_compound(command)
    if not parts:
        return DEFAULT_VERDICT, []
    graded = [(part, classify_one(part)) for part in parts]
    overall = max((verdict for _, verdict in graded), key=lambda v: VERDICT_RANK[v])
    return overall, graded


def ask_user(command: str) -> bool:
    """The interactive prompt for the 'ask' tier. Kept as its own named
    function, separate from bash(), so tests -- and any future
    non-interactive frontend -- can swap it out instead of stubbing
    builtins.input."""
    answer = input(f"allow running: {command!r}? [y/N] ")
    return answer.strip().lower() in ("y", "yes")
