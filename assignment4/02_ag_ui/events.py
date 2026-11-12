"""The AG-UI event types this theme needs, written by hand.

AG-UI is a transport: a run is a stream of typed JSON events. Each event is
one SSE `data:` line carrying a `type` field, which is how the official
encoder frames them. We implement the subset the study-room demo uses:

  lifecycle   RUN_STARTED, RUN_FINISHED, RUN_ERROR
  text        TEXT_MESSAGE_START, TEXT_MESSAGE_CONTENT, TEXT_MESSAGE_END
  tool calls  TOOL_CALL_START, TOOL_CALL_ARGS, TOOL_CALL_END
  state       STATE_SNAPSHOT, STATE_DELTA (RFC 6902 JSON Patch)

Field names follow the AG-UI spec (camelCase: threadId, runId, messageId,
toolCallId, toolCallName, delta, snapshot).
"""
from __future__ import annotations

import copy
import json
import uuid

EVENT_TYPES = {
    "RUN_STARTED": {"threadId", "runId"},
    "RUN_FINISHED": {"threadId", "runId"},
    "RUN_ERROR": {"message"},
    "TEXT_MESSAGE_START": {"messageId", "role"},
    "TEXT_MESSAGE_CONTENT": {"messageId", "delta"},
    "TEXT_MESSAGE_END": {"messageId"},
    "TOOL_CALL_START": {"toolCallId", "toolCallName"},
    "TOOL_CALL_ARGS": {"toolCallId", "delta"},
    "TOOL_CALL_END": {"toolCallId"},
    "STATE_SNAPSHOT": {"snapshot"},
    "STATE_DELTA": {"delta"},
}


def event(type_: str, **fields) -> dict:
    missing = EVENT_TYPES[type_] - fields.keys()
    if missing:
        raise ValueError(f"{type_} missing {sorted(missing)}")
    return {"type": type_, **fields}


def encode(ev: dict) -> str:
    return f"data: {json.dumps(ev)}\n\n"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def text_message(text: str, chunk: int = 18):
    mid = new_id("msg")
    yield event("TEXT_MESSAGE_START", messageId=mid, role="assistant")
    for i in range(0, len(text), chunk):
        yield event("TEXT_MESSAGE_CONTENT", messageId=mid, delta=text[i:i + chunk])
    yield event("TEXT_MESSAGE_END", messageId=mid)


def tool_call(name: str, args: dict, chunk: int = 60):
    """A tool call whose JSON arguments stream as string deltas, exactly the
    way a model's function-call arguments arrive."""
    tid = new_id("call")
    yield event("TOOL_CALL_START", toolCallId=tid, toolCallName=name)
    text = json.dumps(args)
    for i in range(0, len(text), chunk):
        yield event("TOOL_CALL_ARGS", toolCallId=tid, delta=text[i:i + chunk])
    yield event("TOOL_CALL_END", toolCallId=tid)


# ------------------------------------------------------------ JSON Patch
def _parts(path: str) -> list[str]:
    return [p.replace("~1", "/").replace("~0", "~") for p in path.split("/")[1:]]


def apply_patch(doc, ops: list[dict]):
    """Minimal RFC 6902: add, replace, remove. Returns a new document."""
    doc = copy.deepcopy(doc)
    for op in ops:
        parts = _parts(op["path"])
        if not parts:
            doc = copy.deepcopy(op["value"])
            continue
        parent = doc
        for p in parts[:-1]:
            parent = parent[int(p)] if isinstance(parent, list) else parent[p]
        last = parts[-1]
        if isinstance(parent, list):
            idx = len(parent) if last == "-" else int(last)
            if op["op"] == "add":
                parent.insert(idx, copy.deepcopy(op["value"]))
            elif op["op"] == "replace":
                parent[idx] = copy.deepcopy(op["value"])
            elif op["op"] == "remove":
                parent.pop(idx)
        else:
            if op["op"] in ("add", "replace"):
                parent[last] = copy.deepcopy(op["value"])
            elif op["op"] == "remove":
                parent.pop(last)
    return doc
