# Stage 02 — A Bash Tool

**The idea:** give the model one tool. A JSON schema describes it, a Python
function implements it. The model can only *propose* a call; our code
decides whether to run it. There is still no loop — we run the tool once,
print the result, and stop.

## Run it

```powershell
cd stage_02_bash_tool
..\.venv\Scripts\python.exe chat.py
```

## The code

Two halves, and they only agree by name:

```python
BASH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command and return its stdout and stderr.",
        "parameters": {...},
    },
}

def bash(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    ...
```

`BASH_TOOL_SCHEMA` is sent to the model as part of `tools=[...]`. It is pure
JSON — the model reads the `description` and `parameters` and decides
whether calling `bash` would help answer the user's request. The model
never runs anything itself.

`bash()` is the function that actually runs a command, on our machine,
under our control. The schema and the function are connected by nothing
more than the string `"bash"` appearing in both places — that fragile
naming link is exactly what stage 03 fixes by making it a registry.

### The model proposes, your code disposes

When the model wants to use a tool, it doesn't run it — it returns a
`tool_calls` entry on the assistant message: a call id, the tool name, and
a JSON-encoded arguments string. Our code is the one that:

1. Checks the tool name against what we're willing to run.
2. Parses the arguments.
3. Calls the real Python function.
4. Prints the output.

```python
if message.tool_calls:
    call = message.tool_calls[0]
    args = json.loads(call.function.arguments)
    if call.function.name == "bash":
        output = bash(args["command"])
```

If the model asked for a tool we hadn't registered, or asked for `bash`
with a shape of arguments we don't like, we can simply not run it. That
trust boundary — model proposes, code disposes — is the core safety
property of every tool-using agent in this course, and every later stage
sits on top of it.

### No loop yet

Notice `main()` never sends the tool's output back to the model. The model
never gets to see the result, react to it, or produce a final natural
language answer. That is intentional and is called out explicitly here so
stage 05's loop feels like an addition, not a rewrite.

## Diff

```powershell
git diff --no-index stage_01_minimal_chat stage_02_bash_tool
```
