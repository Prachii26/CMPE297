"""FunctionTools for the code review agent.

Every tool takes a *file path*, not a blob of source text. That is the main
departure from the reference assistant, which reviews code pasted into the
chat. Working from paths means the agent reviews what is actually on disk, the
fixer can diff against the real file, and nothing depends on the model
faithfully echoing a hundred lines of source back to itself.

Paths are confined to a sandbox root so a prompt cannot talk the agent into
reading or writing somewhere else on the machine.
"""

from __future__ import annotations

import ast
import difflib
import io
import os
import tokenize
from pathlib import Path
from typing import Any

import pycodestyle

# Everything the agent may read or write lives under here. Defaults to this
# project folder, which contains samples/.
SANDBOX_ROOT = Path(
    os.environ.get("CODE_REVIEW_SANDBOX", Path(__file__).resolve().parent.parent)
).resolve()

MAX_FILE_BYTES = 200_000

# Style codes we treat as more than cosmetic.
SERIOUS_STYLE_CODES = {
    "E722",  # bare except
    "E711",  # comparison to None
    "E712",  # comparison to True/False
    "E731",  # lambda assignment
    "E741",  # ambiguous variable name
    "W605",  # invalid escape sequence
    "F401",
}

COMPLEXITY_WARN = 10
COMPLEXITY_FAIL = 15


class SandboxError(Exception):
    pass


def _resolve(file_path: str) -> Path:
    """Resolve a user-supplied path inside the sandbox, or raise."""
    if not file_path or not str(file_path).strip():
        raise SandboxError("file_path must not be empty")
    p = Path(str(file_path).strip())
    if not p.is_absolute():
        p = SANDBOX_ROOT / p
    p = p.resolve()
    try:
        p.relative_to(SANDBOX_ROOT)
    except ValueError:
        raise SandboxError(
            f"path escapes the sandbox: {p} is not under {SANDBOX_ROOT}"
        ) from None
    return p


def _read(file_path: str) -> tuple[Path, str]:
    p = _resolve(file_path)
    if not p.is_file():
        raise SandboxError(f"no such file: {p}")
    if p.suffix != ".py":
        raise SandboxError(f"not a Python file: {p.name}")
    if p.stat().st_size > MAX_FILE_BYTES:
        raise SandboxError(f"file is larger than {MAX_FILE_BYTES} bytes")
    return p, p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Tool 1: AST structure
# --------------------------------------------------------------------------


def parse_python_file(file_path: str) -> dict[str, Any]:
    """Parse a Python file with `ast` and report its structure.

    Use this first. If it reports a syntax error, nothing else will work and
    the syntax error is the only finding that matters.

    Args:
        file_path: Path to the .py file, relative to the project folder or
            absolute. Must be inside the sandbox.

    Returns:
        On success: the module docstring presence, and a list of functions and
        classes with their line numbers, argument counts, and whether they have
        a docstring. On failure: an error describing the syntax problem.
    """
    try:
        path, source = _read(file_path)
    except SandboxError as e:
        return {"error": str(e)}

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return {
            "error": f"syntax error at line {e.lineno}: {e.msg}",
            "error_type": "syntax",
            "line": e.lineno,
            "offset": e.offset,
            "parses": False,
        }

    functions, classes, imports = [], [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": len(node.args.args) + len(node.args.kwonlyargs),
                "has_docstring": ast.get_docstring(node) is not None,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "methods": sum(
                    1
                    for b in node.body
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))
                ),
                "has_docstring": ast.get_docstring(node) is not None,
            })
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    return {
        "parses": True,
        "file": str(path.relative_to(SANDBOX_ROOT)),
        "line_count": len(source.splitlines()),
        "has_module_docstring": ast.get_docstring(tree) is not None,
        "functions": sorted(functions, key=lambda f: f["line"]),
        "classes": sorted(classes, key=lambda c: c["line"]),
        "imports": sorted(set(i for i in imports if i)),
    }


# --------------------------------------------------------------------------
# Tool 2: pycodestyle
# --------------------------------------------------------------------------


class _CollectingReport(pycodestyle.BaseReport):
    """Captures violations instead of printing them to stdout."""

    def __init__(self, options):
        super().__init__(options)
        self.collected: list[dict[str, Any]] = []

    def error(self, line_number, offset, text, check):
        code = super().error(line_number, offset, text, check)
        if code:
            self.collected.append({
                "line": line_number,
                "column": offset + 1,
                "code": text[:4],
                "message": text[5:],
            })
        return code


def check_style(file_path: str, max_line_length: int = 100) -> dict[str, Any]:
    """Run pycodestyle (PEP 8) over a Python file.

    Args:
        file_path: Path to the .py file inside the sandbox.
        max_line_length: Allowed line length. Default 100.

    Returns:
        The violation count, the violations themselves with line and code, and
        a separate list of the ones that are more than cosmetic (bare excepts,
        `== None` comparisons, ambiguous names and similar).
    """
    try:
        path, _ = _read(file_path)
    except SandboxError as e:
        return {"error": str(e)}

    style = pycodestyle.StyleGuide(
        quiet=True, max_line_length=int(max_line_length), reporter=_CollectingReport
    )
    checker = pycodestyle.Checker(
        str(path), options=style.options, report=style.options.report
    )
    try:
        checker.check_all()
    except Exception as e:  # tokenising a pathological file
        return {"error": f"style check failed: {type(e).__name__}: {e}"}

    violations = getattr(style.options.report, "collected", [])
    serious = [v for v in violations if v["code"] in SERIOUS_STYLE_CODES]
    by_code: dict[str, int] = {}
    for v in violations:
        by_code[v["code"]] = by_code.get(v["code"], 0) + 1

    return {
        "file": str(path.relative_to(SANDBOX_ROOT)),
        "violation_count": len(violations),
        "serious_count": len(serious),
        "by_code": dict(sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0]))),
        "violations": violations[:50],
        "serious": serious,
        "clean": len(violations) == 0,
    }


# --------------------------------------------------------------------------
# Tool 3: cyclomatic complexity
# --------------------------------------------------------------------------

_BRANCHING = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.comprehension,
)


def _complexity_of(node: ast.AST) -> int:
    """McCabe-style count: 1 plus one per decision point."""
    score = 1
    for child in ast.walk(node):
        if isinstance(child, _BRANCHING):
            score += 1
        elif isinstance(child, ast.BoolOp):
            # `a and b and c` is two decision points, not one.
            score += len(child.values) - 1
    return score


def measure_complexity(file_path: str) -> dict[str, Any]:
    """Measure cyclomatic complexity per function.

    Complexity is 1 plus the number of branch points (if, for, while, except,
    with, assert, ternary, comprehension, and each extra operand of a boolean
    operator).

    Args:
        file_path: Path to the .py file inside the sandbox.

    Returns:
        Per-function complexity sorted worst first, the file maximum, and which
        functions exceed the warn (10) and fail (15) thresholds.
    """
    try:
        path, source = _read(file_path)
    except SandboxError as e:
        return {"error": str(e)}

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return {
            "error": f"syntax error at line {e.lineno}: {e.msg}",
            "error_type": "syntax",
        }

    results = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            c = _complexity_of(node)
            results.append({
                "function": node.name,
                "line": node.lineno,
                "complexity": c,
                "rating": (
                    "fail" if c > COMPLEXITY_FAIL
                    else "warn" if c > COMPLEXITY_WARN
                    else "ok"
                ),
            })
    results.sort(key=lambda r: (-r["complexity"], r["line"]))

    return {
        "file": str(path.relative_to(SANDBOX_ROOT)),
        "function_count": len(results),
        "max_complexity": max((r["complexity"] for r in results), default=0),
        "over_warn": [r["function"] for r in results if r["complexity"] > COMPLEXITY_WARN],
        "over_fail": [r["function"] for r in results if r["complexity"] > COMPLEXITY_FAIL],
        "functions": results,
        "clean": all(r["complexity"] <= COMPLEXITY_WARN for r in results),
    }


# --------------------------------------------------------------------------
# Tool 4: propose a patch, diff it, re-run every check
# --------------------------------------------------------------------------


def propose_patch(file_path: str, fixed_source: str) -> dict[str, Any]:
    """Submit rewritten source for a file, and get back a diff plus fresh checks.

    This never touches the original file. The candidate is written alongside it
    as `<name>.fixed.py`, so the original stays reviewable and a bad patch
    cannot destroy the input.

    Call this with the complete corrected contents of the file, not a fragment.

    Args:
        file_path: The ORIGINAL .py file being fixed, inside the sandbox.
        fixed_source: The full corrected source text for that file.

    Returns:
        A unified diff of original vs proposed, whether the patch parses, and
        the re-run style and complexity results for the patched version.
        `checks_pass` is True only when the patch parses, has zero style
        violations, and no function is over the complexity warn threshold.
        When `checks_pass` is True, call `exit_loop`.
    """
    try:
        path, original = _read(file_path)
    except SandboxError as e:
        return {"error": str(e)}

    if not fixed_source or not fixed_source.strip():
        return {"error": "fixed_source must not be empty"}

    # Normalise so the diff is not pure line-ending noise.
    fixed_source = fixed_source.replace("\r\n", "\n")
    if not fixed_source.endswith("\n"):
        fixed_source += "\n"
    original_norm = original.replace("\r\n", "\n")

    diff = "".join(
        difflib.unified_diff(
            original_norm.splitlines(keepends=True),
            fixed_source.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
            n=3,
        )
    )

    if not diff.strip():
        return {
            "error": "the proposed source is identical to the original; "
                     "either make a real change or call exit_loop",
            "unified_diff": "",
            "checks_pass": False,
        }

    # Must parse before we bother writing it.
    try:
        ast.parse(fixed_source, filename=str(path))
    except SyntaxError as e:
        return {
            "unified_diff": diff,
            "patch_parses": False,
            "checks_pass": False,
            "error": f"proposed patch has a syntax error at line {e.lineno}: {e.msg}",
        }

    candidate = path.with_suffix(".fixed.py")
    candidate.write_text(fixed_source, encoding="utf-8")

    style = check_style(str(candidate))
    complexity = measure_complexity(str(candidate))

    style_ok = bool(style.get("clean"))
    complexity_ok = bool(complexity.get("clean"))
    checks_pass = style_ok and complexity_ok

    return {
        "unified_diff": diff,
        "diff_line_count": len(diff.splitlines()),
        "patch_parses": True,
        "written_to": str(candidate.relative_to(SANDBOX_ROOT)),
        "style_after": {
            "violation_count": style.get("violation_count"),
            "by_code": style.get("by_code"),
            "remaining": style.get("violations", [])[:15],
        },
        "complexity_after": {
            "max_complexity": complexity.get("max_complexity"),
            "over_warn": complexity.get("over_warn"),
        },
        "style_ok": style_ok,
        "complexity_ok": complexity_ok,
        "checks_pass": checks_pass,
        "next_step": (
            "All checks pass. Call exit_loop now."
            if checks_pass
            else "Checks still failing. Fix the remaining items and call "
                 "propose_patch again with the full corrected source."
        ),
    }
