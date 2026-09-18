"""Stage 04: a second tool, added by only editing this file.

read_file is appended to TOOLS and FUNCTIONS. main.py -- the loop/dispatch
file -- is byte-for-byte identical to stage 03. That is the payoff of the
registry: main.py's dispatch code has no idea how many tools exist or what
they're named.
"""
import subprocess


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

# One new entry in each collection. main.py did not change.
TOOLS = [BASH_SCHEMA, READ_FILE_SCHEMA]
FUNCTIONS = {"bash": bash, "read_file": read_file}
