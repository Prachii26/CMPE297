"""Stage 11: reminder() now also carries the todo list.

Same rule as stage 09: this whole block is spliced into the outgoing
request only, never stored in `messages`. The todo list added here is a
second example of a "volatile fact" -- it changes turn to turn just like
the clock does, so it belongs in the same late block, not in the
transcript.
"""
import os
import subprocess
from datetime import datetime, timezone

from todos import todos_block


def _git_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "(git not available)"
    if result.returncode != 0:
        return "(not a git repo)"
    return result.stdout.strip()


def reminder():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "<system-reminder>",
        f"current_time: {now}",
        f"git_branch: {_git_branch()}",
        f"cwd: {os.getcwd()}",
    ]
    todos_text = todos_block()
    if todos_text:
        lines.append(todos_text)
    lines.append("</system-reminder>")
    return {"role": "user", "content": "\n".join(lines)}
