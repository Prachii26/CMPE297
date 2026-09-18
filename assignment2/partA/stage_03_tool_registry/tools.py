"""Stage 03: the tool registry.

Every tool has two halves: a JSON schema the model reads, and a Python
function we run. Keeping them in a list and a dict, both keyed by the same
name string, means adding a tool is ONE new entry in each -- never a change
to how the loop dispatches calls. Stage 04 proves this by adding read_file
here without touching main.py at all.
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

# The schema list is what gets sent to the model as `tools=`.
TOOLS = [BASH_SCHEMA]

# The function dict is what the loop dispatches into. Same key -- "bash" --
# links the two. A new tool means one entry appended to each collection.
FUNCTIONS = {"bash": bash}
