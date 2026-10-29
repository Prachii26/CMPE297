"""Tests for the three analysis tools and the patch tool. No model involved."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from code_review.tools import (  # noqa: E402
    SANDBOX_ROOT,
    check_style,
    measure_complexity,
    parse_python_file,
    propose_patch,
)

SAMPLE = "samples/buggy_module.py"


# --------------------------------------------------------------------------
# AST
# --------------------------------------------------------------------------


def test_parse_finds_the_structure_of_the_buggy_sample():
    r = parse_python_file(SAMPLE)
    assert r["parses"] is True

    names = {f["name"] for f in r["functions"]}
    assert {"load_config", "get_discount", "cart_total_items", "apply"} <= names
    assert [c["name"] for c in r["classes"]] == ["orderProcessor"]

    # The sample deliberately ships with no docstrings anywhere.
    assert r["has_module_docstring"] is False
    assert all(not f["has_docstring"] for f in r["functions"])


def test_parse_reports_syntax_errors_with_a_line_number(tmp_path, monkeypatch):
    bad = SANDBOX_ROOT / "samples" / "_tmp_broken.py"
    bad.write_text("def f(:\n    pass\n", encoding="utf-8")
    try:
        r = parse_python_file("samples/_tmp_broken.py")
        assert r.get("parses") is False
        assert r["error_type"] == "syntax"
        assert r["line"] == 1
        assert "syntax error" in r["error"]
    finally:
        bad.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------


def test_style_finds_the_planted_serious_violations():
    r = check_style(SAMPLE)
    assert r["clean"] is False
    assert r["violation_count"] > 15

    codes = {v["code"] for v in r["serious"]}
    # Bare except, == None, == True, and the ambiguous name `l`.
    assert "E722" in codes
    assert "E711" in codes
    assert "E712" in codes
    assert "E741" in codes
    assert r["serious_count"] == len(r["serious"])


def test_style_counts_group_by_code():
    r = check_style(SAMPLE)
    assert sum(r["by_code"].values()) == r["violation_count"]


def test_style_respects_max_line_length():
    long_line = SANDBOX_ROOT / "samples" / "_tmp_long.py"
    long_line.write_text("x = '" + "a" * 90 + "'\n", encoding="utf-8")
    try:
        strict = check_style("samples/_tmp_long.py", max_line_length=50)
        loose = check_style("samples/_tmp_long.py", max_line_length=200)
        assert any(v["code"] == "E501" for v in strict["violations"])
        assert not any(v["code"] == "E501" for v in loose["violations"])
    finally:
        long_line.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Complexity
# --------------------------------------------------------------------------


def test_complexity_flags_the_deliberately_tangled_function():
    r = measure_complexity(SAMPLE)
    assert r["clean"] is False
    assert "get_discount" in r["over_warn"]
    assert "get_discount" in r["over_fail"]
    assert r["max_complexity"] >= 15

    worst = r["functions"][0]
    assert worst["function"] == "get_discount"
    assert worst["rating"] == "fail"


def test_complexity_is_one_for_a_straight_line_function():
    f = SANDBOX_ROOT / "samples" / "_tmp_simple.py"
    f.write_text('"""Doc."""\n\n\ndef add(a, b):\n    """Add."""\n    return a + b\n',
                 encoding="utf-8")
    try:
        r = measure_complexity("samples/_tmp_simple.py")
        assert r["functions"][0]["complexity"] == 1
        assert r["clean"] is True
    finally:
        f.unlink(missing_ok=True)


def test_boolean_operands_each_count_as_a_branch():
    f = SANDBOX_ROOT / "samples" / "_tmp_bool.py"
    f.write_text(
        '"""D."""\n\n\ndef f(a, b, c):\n    """D."""\n'
        "    if a and b and c:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    try:
        r = measure_complexity("samples/_tmp_bool.py")
        # 1 base + 1 if + 2 extra boolop operands
        assert r["functions"][0]["complexity"] == 4
    finally:
        f.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Sandbox
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "escape",
    [
        "../../../../Windows/System32/drivers/etc/hosts",
        "../../../setup.py",
        "C:/Windows/win.ini",
        "/etc/passwd",
    ],
)
def test_paths_outside_the_sandbox_are_refused(escape):
    for tool in (parse_python_file, check_style, measure_complexity):
        r = tool(escape)
        assert "error" in r, f"{tool.__name__} accepted {escape}"
        assert "sandbox" in r["error"] or "no such file" in r["error"] or \
               "not a Python file" in r["error"]


def test_empty_and_non_python_paths_are_refused():
    assert "error" in parse_python_file("")
    assert "error" in parse_python_file("   ")
    readme = SANDBOX_ROOT / "samples" / "_tmp_notes.txt"
    readme.write_text("hi", encoding="utf-8")
    try:
        r = parse_python_file("samples/_tmp_notes.txt")
        assert "not a Python file" in r["error"]
    finally:
        readme.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# propose_patch: the unified diff, our second change from the reference
# --------------------------------------------------------------------------


CLEAN_SOURCE = '''"""A tidy module."""


def add(a, b):
    """Add two numbers."""
    return a + b
'''


def _tmp_target() -> Path:
    p = SANDBOX_ROOT / "samples" / "_tmp_patch_me.py"
    p.write_text("import os,sys\ndef add( a,b ):\n    return a+b\n", encoding="utf-8")
    return p


def _cleanup(p: Path):
    p.unlink(missing_ok=True)
    p.with_suffix(".fixed.py").unlink(missing_ok=True)


def test_propose_patch_emits_a_real_unified_diff_and_passes_checks():
    target = _tmp_target()
    try:
        r = propose_patch("samples/_tmp_patch_me.py", CLEAN_SOURCE)

        assert r["patch_parses"] is True
        diff = r["unified_diff"]
        # A genuine unified diff: headers, a hunk marker, and +/- lines.
        assert diff.startswith("---")
        assert "+++ b/_tmp_patch_me.py" in diff
        assert "@@" in diff
        assert any(l.startswith("-") and not l.startswith("---")
                   for l in diff.splitlines())
        assert any(l.startswith("+") and not l.startswith("+++")
                   for l in diff.splitlines())

        assert r["checks_pass"] is True
        assert r["style_ok"] is True
        assert "exit_loop" in r["next_step"]
    finally:
        _cleanup(target)


def test_propose_patch_never_touches_the_original_file():
    target = _tmp_target()
    before = target.read_text(encoding="utf-8")
    try:
        propose_patch("samples/_tmp_patch_me.py", CLEAN_SOURCE)
        assert target.read_text(encoding="utf-8") == before
        # The candidate went to a sibling .fixed.py instead.
        assert target.with_suffix(".fixed.py").read_text(encoding="utf-8") == CLEAN_SOURCE
    finally:
        _cleanup(target)


def test_propose_patch_rejects_a_patch_that_does_not_parse():
    target = _tmp_target()
    try:
        r = propose_patch("samples/_tmp_patch_me.py", "def broken(:\n  pass\n")
        assert r["patch_parses"] is False
        assert r["checks_pass"] is False
        assert "syntax error" in r["error"]
        # Nothing was written.
        assert not target.with_suffix(".fixed.py").exists()
    finally:
        _cleanup(target)


def test_propose_patch_reports_still_failing_checks_rather_than_passing():
    target = _tmp_target()
    try:
        # Parses, but still has style problems.
        still_dirty = ("import os,sys\ndef add( a,b ):\n    x=1\n    return a+b\n")
        r = propose_patch("samples/_tmp_patch_me.py", still_dirty)
        assert r["patch_parses"] is True
        assert r["checks_pass"] is False
        assert r["style_after"]["violation_count"] > 0
        assert "propose_patch again" in r["next_step"]
    finally:
        _cleanup(target)


def test_propose_patch_rejects_a_no_op_patch():
    target = _tmp_target()
    try:
        same = target.read_text(encoding="utf-8")
        r = propose_patch("samples/_tmp_patch_me.py", same)
        assert r["checks_pass"] is False
        assert "identical" in r["error"]
    finally:
        _cleanup(target)


def test_propose_patch_refuses_empty_source_and_bad_paths():
    target = _tmp_target()
    try:
        assert "error" in propose_patch("samples/_tmp_patch_me.py", "")
        assert "error" in propose_patch("samples/_tmp_patch_me.py", "   ")
        assert "error" in propose_patch("../../outside.py", CLEAN_SOURCE)
    finally:
        _cleanup(target)


# --------------------------------------------------------------------------
# Public-API preservation
#
# A live run produced a patch that was style-clean and under the complexity
# threshold, and had quietly replaced the module's whole discount feature:
# get_discount(user, cart_total, coupon, is_member, region) came back as
# get_discount(total, is_member, items, is_holiday, is_birthday). Style and
# complexity cannot see that, so propose_patch compares the API explicitly.
# --------------------------------------------------------------------------

RENAMED_ARGS = '''"""Tidy."""


def add(x, y):
    """Add."""
    return x + y
'''

EXTRACTED_HELPER = '''"""Tidy."""


def _combine(a, b):
    """Private helper."""
    return a + b


def add(a, b):
    """Add."""
    return _combine(a, b)
'''

DROPPED_FUNCTION = '''"""Tidy."""


def something_else(a, b):
    """Not the original."""
    return a + b
'''


def _api_target() -> Path:
    p = SANDBOX_ROOT / "samples" / "_tmp_api.py"
    p.write_text(
        '"""Doc."""\n\n\ndef add(a, b):\n    """Add."""\n    return a+b\n',
        encoding="utf-8",
    )
    return p


def test_renaming_a_public_argument_fails_the_patch():
    target = _api_target()
    try:
        r = propose_patch("samples/_tmp_api.py", RENAMED_ARGS)
        assert r["style_ok"] is True          # it really is clean...
        assert r["complexity_ok"] is True     # ...and simple...
        assert r["api_preserved"] is False    # ...but it changed the contract.
        assert r["checks_pass"] is False
        assert any("add signature changed" in c for c in r["api_changes"])
        assert "rewrite rather than a fix" in r["next_step"]
    finally:
        _cleanup(target)


def test_extracting_a_private_helper_is_allowed():
    """Decomposition is how complexity gets fixed, so it must not be blocked."""
    target = _api_target()
    try:
        r = propose_patch("samples/_tmp_api.py", EXTRACTED_HELPER)
        assert r["api_preserved"] is True
        assert r["api_changes"] == []
        assert r["checks_pass"] is True
    finally:
        _cleanup(target)


def test_dropping_a_public_function_fails_the_patch():
    target = _api_target()
    try:
        r = propose_patch("samples/_tmp_api.py", DROPPED_FUNCTION)
        assert r["api_preserved"] is False
        assert r["checks_pass"] is False
        assert any(c.startswith("removed add") for c in r["api_changes"])
        assert any(c.startswith("added something_else") for c in r["api_changes"])
    finally:
        _cleanup(target)


def test_renaming_a_public_class_fails_the_patch():
    p = SANDBOX_ROOT / "samples" / "_tmp_cls.py"
    p.write_text(
        '"""Doc."""\n\n\nclass orderProcessor:\n    """C."""\n\n'
        '    def process(self):\n        """P."""\n        return 1\n',
        encoding="utf-8",
    )
    try:
        renamed = p.read_text(encoding="utf-8").replace(
            "orderProcessor", "OrderProcessor"
        )
        r = propose_patch("samples/_tmp_cls.py", renamed)
        assert r["api_preserved"] is False
        assert any("orderProcessor" in c for c in r["api_changes"])
    finally:
        p.unlink(missing_ok=True)
        p.with_suffix(".fixed.py").unlink(missing_ok=True)


def test_style_violations_carry_the_real_source_line():
    """A live run showed the reviewer inventing variable names for lines it
    could not see (it reported `is_holiday`/`is_birthday`, which appear nowhere
    in the sample). Returning the source removes the need to guess."""
    r = check_style(SAMPLE)

    by_line = {v["line"]: v["source"] for v in r["serious"]}
    assert "is_member == True" in by_line[14]
    assert "coupon != None" in by_line[21]
    assert by_line[40].strip() == "except:"
    assert "l = cart_total - d" in by_line[45]

    # Every violation has one, and none mentions the hallucinated names.
    assert all("source" in v for v in r["violations"])
    joined = " ".join(v["source"] for v in r["violations"])
    assert "is_holiday" not in joined
    assert "is_birthday" not in joined
