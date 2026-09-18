"""Stage 10: sessions.

Every message is appended to a JSONL file the instant it happens, not
buffered in memory and flushed at exit -- if the process dies mid
conversation, everything up to that point is already on disk.

/rewind does not delete anything. It appends a marker event that says
"the effective transcript from here on is the first N entries." The raw
log still has the full history; only the in-memory replay in
load_messages() respects the cut, the same way a database's append-only
log plus a "tombstone" record keeps history intact while changing what
reads see.
"""
import json
import time
from pathlib import Path

SESSIONS_DIR = Path(__file__).parent / "sessions"


def new_session_id():
    return time.strftime("%Y%m%d_%H%M%S")


def session_path(session_id):
    return SESSIONS_DIR / f"{session_id}.jsonl"


def append_event(session_id, event):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    with open(session_path(session_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def log_message(session_id, message):
    append_event(session_id, {"type": "message", "message": message})


def log_rewind(session_id, to_index):
    append_event(session_id, {"type": "rewind", "to_index": to_index})


def load_messages(session_id):
    """Replay the JSONL log into the effective `messages` list: every
    logged message, except whatever a later rewind marker cut off."""
    path = session_path(session_id)
    if not path.exists():
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            if event["type"] == "message":
                messages.append(event["message"])
            elif event["type"] == "rewind":
                messages = messages[: event["to_index"]]
    return messages


def latest_session_id():
    """For --resume: the most recently written session file, if any."""
    if not SESSIONS_DIR.exists():
        return None
    files = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1].stem if files else None
