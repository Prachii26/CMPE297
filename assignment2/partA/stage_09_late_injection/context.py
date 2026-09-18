"""Stage 09: late injection.

Volatile facts -- the current time, the git branch, the working directory
-- change on every call. If they lived in the persisted `messages` list,
every request would start with a slightly different prefix, and a
provider that caches repeated prompt prefixes (see stage 01's
cached_tokens) would never get a hit past the point that block sits.

reminder() builds this block fresh every time it's called. main.py sends
it as `messages + [reminder()]` -- appended only to the list actually sent
over the wire -- and never appends it to `messages` itself. The stored
transcript keeps the exact same prefix turn after turn; only the tail of
the live request changes.
"""
import os
import subprocess
from datetime import datetime, timezone


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
    content = (
        "<system-reminder>\n"
        f"current_time: {now}\n"
        f"git_branch: {_git_branch()}\n"
        f"cwd: {os.getcwd()}\n"
        "</system-reminder>"
    )
    return {"role": "user", "content": content}
