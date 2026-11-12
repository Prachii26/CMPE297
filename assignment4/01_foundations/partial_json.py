"""A tolerant partial-JSON parser.

Given any prefix of a JSON document, return the largest value that the
prefix already determines. Strategy: walk back from the end of the prefix
to a cut point that is outside a string, drop a trailing comma or colon,
close every open object and array, and try to parse. The first cut that
parses wins. Half-written strings and dangling keys are dropped rather than
guessed, so what the renderer sees is always a prefix of the final value.

The same algorithm is implemented in page/app.js for the browser.
"""
from __future__ import annotations

import json


def _scan(text: str) -> tuple[list[bool], list[list[str]]]:
    """For each index: are we inside a string there, and what is open."""
    in_str, esc, stack = False, False, []
    inside, stacks = [], []
    for ch in text:
        inside.append(in_str)
        stacks.append(list(stack))
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    inside.append(in_str)
    stacks.append(list(stack))
    return inside, stacks


def parse_partial(text: str):
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    inside, stacks = _scan(text)
    for cut in range(len(text), 0, -1):
        if inside[cut]:
            continue
        head = text[:cut].rstrip()
        while head and head[-1] in ",:":
            head = head[:-1].rstrip()
        if not head:
            continue
        _, st = _scan(head)
        closers = "".join("}" if c == "{" else "]" for c in reversed(st[-1]))
        try:
            return json.loads(head + closers)
        except json.JSONDecodeError:
            continue
    return None
