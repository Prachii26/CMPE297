"""Stage 11: todos.

The todo list is one global list of {content, status} dicts. write_todos
REPLACES it wholesale on every call -- there is no separate add/update/
remove API, so there is exactly one place a bad status can sneak in: the
validation inside write_todos itself. That validation requires exactly
one item to be in_progress whenever the list is non-empty, so it's always
unambiguous which single thing is being worked on right now.

The list is a plain Python variable, not a message. It never enters
`messages` directly -- it only reaches the model by riding along inside
context.reminder()'s late block, rebuilt fresh every call exactly like
the current time or git branch.
"""
TODOS = []

VALID_STATUSES = {"pending", "in_progress", "completed"}


def write_todos(todos: list) -> str:
    for item in todos:
        status = item.get("status")
        if status not in VALID_STATUSES:
            return f"error: invalid status {status!r} on todo {item.get('content')!r}. No changes made."

    in_progress = [item for item in todos if item["status"] == "in_progress"]
    if todos and len(in_progress) != 1:
        return (
            f"error: exactly one todo must be in_progress, got {len(in_progress)}. "
            "No changes made."
        )

    global TODOS
    TODOS = todos
    return f"todo list updated, {len(TODOS)} item(s)"


def todos_block():
    """Rendered for the late-injection block. Empty string when there's
    nothing to show, so an unused todo list costs zero tokens."""
    if not TODOS:
        return ""
    marks = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
    lines = ["current todos:"]
    for item in TODOS:
        lines.append(f"{marks.get(item['status'], '[?]')} {item['content']}")
    return "\n".join(lines)
