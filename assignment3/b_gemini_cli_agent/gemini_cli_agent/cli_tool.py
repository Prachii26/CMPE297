"""Run the Gemini CLI as an ADK function tool.

Design rules, all of which differ from the reference implementation:

- **argv, never a shell string.** The reference builds `gemini -p "{task}"` and
  runs it with `shell=True`, so a prompt containing a quote or a `;` becomes
  shell syntax. We pass a list, so the prompt is always one argument.
- **`shutil.which`, because on Windows the executable is `gemini.cmd`.**
  A bare `"gemini"` does not resolve without a shell there.
- **The working directory is pinned to a sandbox.** The reference clones an
  arbitrary GitHub URL into /tmp and runs there. We only ever run inside one
  folder that the operator chose.
- **No auto-approve flags, ever.** The CLI runs with `-p` only, which is
  non-interactive and read-only by default.
- **Errors come back as strings in the result, not exceptions.** A tool that
  raises kills the agent turn; a tool that reports lets the model recover.
- **Output is capped**, so one enormous answer cannot blow up the context.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

# The only folder tree the CLI is allowed to run in.
SANDBOX_ROOT = Path(
    os.environ.get(
        "GEMINI_CLI_SANDBOX", Path(__file__).resolve().parent.parent / "sandbox"
    )
).resolve()

TIMEOUT_SECONDS = int(os.environ.get("GEMINI_CLI_TIMEOUT", "120"))
MAX_OUTPUT_CHARS = int(os.environ.get("GEMINI_CLI_MAX_OUTPUT", "16000"))
MAX_PROMPT_CHARS = 4000

# Anything that would let the CLI act without a human in the loop. We refuse to
# run if one of these ever shows up in the argv we are about to execute.
FORBIDDEN_FLAGS = {
    "--yolo",
    "-y",
    "--approval-mode",
    "--approval-mode=auto_edit",
    "--approval-mode=yolo",
    "--sandbox",
    "--allow-all",
}

# Executable names to try, in order. gemini.cmd is the Windows npm shim.
_CANDIDATES = ("gemini", "gemini.cmd", "gemini.exe")


def find_gemini_executable() -> str | None:
    """Locate the Gemini CLI, or None if it is not installed.

    `shutil.which` is what makes this work on Windows: npm installs the real
    entry point as `gemini.cmd`, and a bare "gemini" will not resolve without
    going through a shell, which we are deliberately not doing.
    """
    for name in _CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    # npm's global bin is not always on PATH for a subprocess on Windows.
    appdata = os.environ.get("APPDATA")
    if appdata:
        for name in _CANDIDATES:
            candidate = Path(appdata) / "npm" / name
            if candidate.is_file():
                return str(candidate)
    return None


def _resolve_cwd(cwd: str) -> Path:
    """Resolve a requested working directory inside the sandbox, or raise."""
    if not cwd or not str(cwd).strip():
        return SANDBOX_ROOT
    p = Path(str(cwd).strip())
    if not p.is_absolute():
        p = SANDBOX_ROOT / p
    p = p.resolve()
    try:
        p.relative_to(SANDBOX_ROOT)
    except ValueError:
        raise ValueError(
            f"cwd must be inside the sandbox {SANDBOX_ROOT}; refused {p}"
        ) from None
    if not p.is_dir():
        raise ValueError(f"no such directory inside the sandbox: {p}")
    return p


def _process_group_kwargs() -> dict[str, Any]:
    """Start the child in its own group so we can kill its descendants too."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(proc: "subprocess.Popen") -> None:
    """Kill a process and everything it spawned. Best effort, never raises."""
    try:
        if os.name == "nt":
            # taskkill /T walks the child tree, which plain Process.kill does not.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=20,
                shell=False,
            )
        else:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    head = text[:MAX_OUTPUT_CHARS]
    return (
        head + f"\n\n[... truncated, {len(text) - MAX_OUTPUT_CHARS} more characters]",
        True,
    )


def gemini_cli(prompt: str, cwd: str = "") -> dict[str, Any]:
    """Ask the Gemini CLI a question about the code in a sandbox folder.

    The CLI reads the files in `cwd` and answers the prompt. It runs
    non-interactively and read-only: it will not edit, create, or delete files.

    Args:
        prompt: The question to ask about the code, in plain English. Be
            specific, for example "list every module and say what each one does"
            rather than "explain this".
        cwd: Folder to analyse, relative to the sandbox root. Empty means the
            sandbox root itself. Paths outside the sandbox are refused.

    Returns:
        A dict with `ok`, the CLI's `output`, which folder and which files it
        could see, how long it took, and whether the output was truncated. On
        failure, `ok` is False and `error` says what went wrong; the tool never
        raises.
    """
    started = time.time()

    prompt = (prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt must not be empty"}
    if len(prompt) > MAX_PROMPT_CHARS:
        return {
            "ok": False,
            "error": f"prompt is {len(prompt)} characters, limit is {MAX_PROMPT_CHARS}",
        }

    try:
        work_dir = _resolve_cwd(cwd)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    exe = find_gemini_executable()
    if exe is None:
        return {
            "ok": False,
            "error": (
                "Gemini CLI not found. Install it with: "
                "npm install -g @google/gemini-cli"
            ),
        }

    argv = [exe, "-p", prompt]

    # Belt and braces: never execute an argv containing an auto-approve flag.
    for arg in argv:
        bare = arg.split("=", 1)[0]
        if arg in FORBIDDEN_FLAGS or bare in FORBIDDEN_FLAGS:
            return {
                "ok": False,
                "error": f"refusing to run with auto-approve flag {arg!r}",
            }

    env = os.environ.copy()
    # The CLI uses AI Studio with this key, matching the rest of the project.
    if not env.get("GEMINI_API_KEY") and env.get("GOOGLE_API_KEY"):
        env["GEMINI_API_KEY"] = env["GOOGLE_API_KEY"]

    # Since 0.6x the CLI refuses to run in an "untrusted" directory and exits
    # 55. The documented headless escape is this env var. We set it only for
    # this subprocess, and only because `work_dir` is already pinned inside our
    # own sandbox by _resolve_cwd above.
    #
    # Trusting a workspace is NOT the same as auto-approving tool calls: we
    # still pass no --yolo and no --approval-mode, so the CLI stays read-only
    # and non-interactive.
    env["GEMINI_CLI_TRUST_WORKSPACE"] = "true"

    visible = sorted(
        p.name for p in work_dir.iterdir() if not p.name.startswith(".")
    )[:40]

    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(work_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            **_process_group_kwargs(),
        )
    except OSError as e:
        return {"ok": False, "error": f"could not start Gemini CLI: {e}"}

    try:
        out, err = proc.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # proc.kill() alone is not enough here. On Windows `gemini.cmd` is a
        # shim that spawns node.exe; killing the shim leaves node holding the
        # stdout pipe, so a second communicate() would block forever. Kill the
        # whole tree, then drain with a short grace period.
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return {
            "ok": False,
            "error": f"Gemini CLI timed out after {TIMEOUT_SECONDS} seconds",
            "folder": str(work_dir.relative_to(SANDBOX_ROOT)) or ".",
            "elapsed_seconds": round(time.time() - started, 1),
            "partial_output": _truncate(out or "")[0],
        }

    elapsed = round(time.time() - started, 1)
    stdout, truncated = _truncate(out or "")
    stderr = (err or "").strip()

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": (
                f"Gemini CLI exited {proc.returncode}: "
                f"{stderr[:800] or 'no stderr'}"
            ),
            "exit_code": proc.returncode,
            "folder": str(work_dir.relative_to(SANDBOX_ROOT)) or ".",
            "elapsed_seconds": elapsed,
        }

    return {
        "ok": True,
        "folder": str(work_dir.relative_to(SANDBOX_ROOT)) or ".",
        "files_visible": visible,
        "file_count": len(visible),
        "prompt": prompt,
        "output": stdout,
        "truncated": truncated,
        "elapsed_seconds": elapsed,
        "exit_code": 0,
        "stderr_tail": stderr[-400:] if stderr else "",
    }


def list_sandbox(subdir: str = "") -> dict[str, Any]:
    """List the files available in the sandbox, so you can pick a folder.

    Args:
        subdir: Folder relative to the sandbox root. Empty means the root.

    Returns:
        The folder's directories and files, or an error string.
    """
    try:
        target = _resolve_cwd(subdir)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    dirs, files = [], []
    for p in sorted(target.iterdir()):
        if p.name.startswith("."):
            continue
        (dirs if p.is_dir() else files).append(p.name)

    return {
        "ok": True,
        "folder": str(target.relative_to(SANDBOX_ROOT)) or ".",
        "directories": dirs,
        "files": files,
        "sandbox_root": str(SANDBOX_ROOT),
    }
