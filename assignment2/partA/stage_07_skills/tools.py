"""Stage 07: same registry pattern, one more tool: read_skill."""
import subprocess

from skills import read_skill


def bash(command: str) -> str:
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout
    if result.stderr:
        output += result.stderr
    return output.strip() or "(no output)"


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        return f"error reading {path}: {exc}"


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

TOOLS = [BASH_SCHEMA, READ_FILE_SCHEMA, READ_SKILL_SCHEMA]
FUNCTIONS = {"bash": bash, "read_file": read_file, "read_skill": read_skill}
