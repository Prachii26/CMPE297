"""Tests for the Gemini CLI tool. The CLI subprocess itself is stubbed, so
these run offline, instantly, and without spending API quota."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from gemini_cli_agent import cli_tool  # noqa: E402
from gemini_cli_agent.cli_tool import (  # noqa: E402
    SANDBOX_ROOT,
    find_gemini_executable,
    gemini_cli,
    list_sandbox,
)


class FakeProc:
    """Stands in for Popen: records argv/cwd/env and replays a canned result."""

    def __init__(self, stdout="", stderr="", returncode=0, timeout=False):
        self._out, self._err = stdout, stderr
        self.returncode = returncode
        self._timeout = timeout
        self.pid = 4242
        self.killed = False

    def communicate(self, timeout=None):
        if self._timeout:
            self._timeout = False  # the post-kill drain succeeds
            raise subprocess.TimeoutExpired(cmd="gemini", timeout=timeout or 0)
        return self._out, self._err

    def kill(self):
        self.killed = True


@pytest.fixture
def spy(monkeypatch):
    """Capture what the tool would have executed."""
    calls = {}

    def fake_popen(argv, **kw):
        calls["argv"] = argv
        calls["cwd"] = kw.get("cwd")
        calls["env"] = kw.get("env")
        calls["shell"] = kw.get("shell")
        return calls["proc"]

    calls["proc"] = FakeProc(stdout="ok")
    monkeypatch.setattr(cli_tool.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli_tool, "find_gemini_executable", lambda: "C:/fake/gemini.cmd")
    return calls


# --------------------------------------------------------------------------
# Executable discovery
# --------------------------------------------------------------------------


def test_find_executable_uses_shutil_which_and_accepts_the_windows_cmd_shim(
    monkeypatch,
):
    seen = []

    def fake_which(name):
        seen.append(name)
        return "C:/Users/x/AppData/Roaming/npm/gemini.CMD" if name == "gemini" else None

    monkeypatch.setattr(cli_tool.shutil, "which", fake_which)
    assert find_gemini_executable().lower().endswith("gemini.cmd")
    assert "gemini" in seen


def test_missing_cli_returns_an_install_hint_not_an_exception(monkeypatch):
    monkeypatch.setattr(cli_tool.shutil, "which", lambda n: None)
    monkeypatch.delenv("APPDATA", raising=False)
    r = gemini_cli("anything")
    assert r["ok"] is False
    assert "npm install -g @google/gemini-cli" in r["error"]


# --------------------------------------------------------------------------
# How the subprocess is invoked
# --------------------------------------------------------------------------


def test_runs_argv_without_a_shell_so_the_prompt_cannot_inject(spy):
    nasty = 'explain this" ; rm -rf / ; echo "'
    gemini_cli(nasty)

    assert spy["shell"] is False
    # The whole prompt is exactly one argv element, quotes and semicolons intact.
    # The prompt is the value of -p, wherever -p lands in the argv.
    i = spy["argv"].index("-p")
    assert spy["argv"][i + 1] == nasty
    assert len(spy["argv"]) == i + 2


def test_never_passes_an_auto_approve_flag(spy):
    gemini_cli("summarise the code")
    joined = " ".join(spy["argv"])
    for flag in ("--yolo", "--approval-mode", "-y", "--allow-all"):
        assert flag not in joined


def test_cwd_is_pinned_inside_the_sandbox(spy):
    gemini_cli("summarise", cwd="taskqueue")
    assert Path(spy["cwd"]) == (SANDBOX_ROOT / "taskqueue").resolve()


@pytest.mark.parametrize(
    "escape", ["..", "../..", "../../../Windows", "C:/Windows", "/etc"]
)
def test_cwd_outside_the_sandbox_is_refused(escape, spy):
    r = gemini_cli("summarise", cwd=escape)
    assert r["ok"] is False
    assert "sandbox" in r["error"] or "no such directory" in r["error"]
    # Nothing was executed.
    assert "argv" not in spy


def test_unknown_subdir_is_refused(spy):
    r = gemini_cli("summarise", cwd="does_not_exist")
    assert r["ok"] is False
    assert "no such directory" in r["error"]


def test_workspace_trust_is_set_for_the_child_only(spy, monkeypatch):
    monkeypatch.delenv("GEMINI_CLI_TRUST_WORKSPACE", raising=False)
    gemini_cli("summarise")
    assert spy["env"]["GEMINI_CLI_TRUST_WORKSPACE"] == "true"
    # It did not leak into this process.
    import os

    assert "GEMINI_CLI_TRUST_WORKSPACE" not in os.environ


# --------------------------------------------------------------------------
# Input validation and output handling
# --------------------------------------------------------------------------


def test_empty_and_oversized_prompts_are_refused(spy):
    assert gemini_cli("")["ok"] is False
    assert gemini_cli("   ")["ok"] is False
    big = gemini_cli("x" * (cli_tool.MAX_PROMPT_CHARS + 1))
    assert big["ok"] is False
    assert "limit is" in big["error"]


def test_output_is_capped_and_flagged(spy, monkeypatch):
    monkeypatch.setattr(cli_tool, "MAX_OUTPUT_CHARS", 100)
    spy["proc"] = FakeProc(stdout="A" * 500)
    r = gemini_cli("summarise")
    assert r["ok"] is True
    assert r["truncated"] is True
    assert len(r["output"]) < 300
    assert "truncated" in r["output"]


def test_short_output_is_not_flagged_as_truncated(spy):
    spy["proc"] = FakeProc(stdout="a short answer")
    r = gemini_cli("summarise")
    assert r["truncated"] is False
    assert r["output"] == "a short answer"


def test_nonzero_exit_becomes_an_error_string_not_an_exception(spy):
    spy["proc"] = FakeProc(stdout="", stderr="boom: bad auth", returncode=55)
    r = gemini_cli("summarise")
    assert r["ok"] is False
    assert "exited 55" in r["error"]
    assert "boom: bad auth" in r["error"]


def test_timeout_kills_the_tree_and_returns_an_error_string(spy, monkeypatch):
    killed = {}
    monkeypatch.setattr(cli_tool, "_kill_tree", lambda p: killed.setdefault("yes", True))
    spy["proc"] = FakeProc(stdout="partial", timeout=True)

    r = gemini_cli("summarise")

    assert r["ok"] is False
    assert "timed out" in r["error"]
    assert killed.get("yes") is True


def test_oserror_on_spawn_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(cli_tool, "find_gemini_executable", lambda: "C:/fake/gemini.cmd")

    def boom(*a, **k):
        raise OSError("access denied")

    monkeypatch.setattr(cli_tool.subprocess, "Popen", boom)
    r = gemini_cli("summarise")
    assert r["ok"] is False
    assert "could not start" in r["error"]


def test_successful_result_is_structured(spy):
    spy["proc"] = FakeProc(stdout="queue.py holds the priority queue.")
    r = gemini_cli("what does each module do?", cwd="taskqueue")
    assert r["ok"] is True
    for field in (
        "folder", "files_visible", "file_count", "prompt",
        "output", "truncated", "elapsed_seconds", "exit_code",
    ):
        assert field in r, field
    assert r["folder"] == "taskqueue"
    assert "queue.py" in r["files_visible"]
    assert r["exit_code"] == 0


# --------------------------------------------------------------------------
# list_sandbox
# --------------------------------------------------------------------------


def test_list_sandbox_shows_the_sample_project():
    r = list_sandbox()
    assert r["ok"] is True
    assert "taskqueue" in r["directories"]
    assert "README.md" in r["files"]


def test_list_sandbox_refuses_to_escape():
    r = list_sandbox("../..")
    assert r["ok"] is False
    assert "sandbox" in r["error"]
