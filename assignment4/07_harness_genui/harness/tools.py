"""Stage 08: file editing. write_file and str_replace, both added here --
main.py is untouched, same as stage 04's read_file.

The important design decision is in str_replace: it refuses to act unless
old_str appears in the file EXACTLY once. Zero matches means it typo'd the
target text; more than one means the edit is ambiguous about which spot to
change. Both refusals come back as ordinary tool results (a string), not
exceptions -- so the model sees the refusal in its own transcript and gets
a chance to retry with better-targeted text instead of the program
crashing.
"""
from permissions import ask_user, classify
from sandbox import run_sandboxed
from skills import read_skill
from todos import write_todos


def bash(command: str) -> str:
    # Every command is rated before it runs. "deny" refuses outright;
    # "ask" pauses for a human yes/no; only "allow" (or a "yes" to the
    # ask prompt) reaches the sandbox. The verdict comes back as the
    # tool result either way -- never an exception -- so the model sees
    # exactly why a command didn't run.
    verdict, parts = classify(command)
    if verdict == "deny":
        denied = ", ".join(f"{p!r}" for p, v in parts if v == "deny")
        return f"refused: denied by permission rules ({denied})."
    if verdict == "ask":
        if not ask_user(command):
            return "refused: user declined to run this command."

    return run_sandboxed(command, timeout=30)


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        return f"error reading {path}: {exc}"


def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return f"error writing {path}: {exc}"
    return f"wrote {len(content)} bytes to {path}"


def str_replace(path: str, old_str: str, new_str: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        return f"error reading {path}: {exc}"

    count = text.count(old_str)
    if count == 0:
        return f"error: old_str not found in {path}. No changes made."
    if count > 1:
        return (
            f"error: old_str matches {count} times in {path}, must match exactly "
            "once. Add more surrounding context to old_str to make it unique. "
            "No changes made."
        )

    new_text = text.replace(old_str, new_str, 1)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
    except OSError as exc:
        return f"error writing {path}: {exc}"
    return f"replaced 1 match in {path}"


BASH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command and return its stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
            },
            "required": ["command"],
        },
    },
}

READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file from disk and return its contents.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
            },
            "required": ["path"],
        },
    },
}

READ_SKILL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_skill",
        "description": (
            "Load the full instructions for a named skill. Only call this "
            "after deciding, from the name and description already in your "
            "system prompt, that the skill is relevant."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The skill's name, exactly as listed."},
            },
            "required": ["name"],
        },
    },
}

WRITE_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create a file, or overwrite it completely, with the given content.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Full content to write to the file."},
            },
            "required": ["path", "content"],
        },
    },
}

STR_REPLACE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "str_replace",
        "description": (
            "Replace exactly one occurrence of old_str with new_str in a file. "
            "Fails if old_str appears zero times or more than once -- make "
            "old_str include enough surrounding context to be unique."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit."},
                "old_str": {"type": "string", "description": "The exact text to find, must be unique in the file."},
                "new_str": {"type": "string", "description": "The text to replace it with."},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
}

WRITE_TODOS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_todos",
        "description": (
            "Replace the entire todo list. Exactly one item must have "
            "status 'in_progress' whenever the list is non-empty."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
}

TOOLS = [
    BASH_SCHEMA,
    READ_FILE_SCHEMA,
    READ_SKILL_SCHEMA,
    WRITE_FILE_SCHEMA,
    STR_REPLACE_SCHEMA,
    WRITE_TODOS_SCHEMA,
]
FUNCTIONS = {
    "bash": bash,
    "read_file": read_file,
    "read_skill": read_skill,
    "write_file": write_file,
    "str_replace": str_replace,
    "write_todos": write_todos,
}
