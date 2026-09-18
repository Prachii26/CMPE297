"""Stage 15: subagents.

`task` runs a SECOND, independent agent loop: its own empty message list,
its own turn limit, and -- critically -- a restricted tool set that
excludes `task` itself (no recursion), `write_todos`, `write_file`, and
`str_replace` (no editing). A subagent can read, search, and run shell
commands to gather information, but it cannot change anything on disk and
cannot spawn a further subagent. Only its FINAL text answer is returned to
whoever called it -- the parent never sees the subagent's intermediate
tool calls or their raw results, so a long exploratory side-investigation
only costs the parent's transcript one tool result: the summary.
"""
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

from tools import FUNCTIONS, TOOLS

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")
MAX_SUBAGENT_TURNS = 10

# Everything the top-level agent can do, MINUS editing anything and MINUS
# spawning another subagent. Withheld by leaving them out of both the
# schema list (the model never even learns they exist) and the function
# dict (even a hallucinated call would resolve to nothing).
WITHHELD = {"task", "write_todos", "write_file", "str_replace"}
SUBAGENT_TOOLS = [t for t in TOOLS if t["function"]["name"] not in WITHHELD]
SUBAGENT_FUNCTIONS = {name: fn for name, fn in FUNCTIONS.items() if name not in WITHHELD}


def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def _run_tool(name, args):
    fn = SUBAGENT_FUNCTIONS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as exc:
        return f"error running {name}: {exc}"


def task(prompt: str) -> str:
    """The tool function itself. Everything from here down is a fresh,
    private conversation: it starts from an empty list (just the task
    prompt), and it never sees -- or can affect -- the parent's own
    `messages`."""
    client = make_client()
    messages = [{"role": "user", "content": prompt}]

    for _ in range(MAX_SUBAGENT_TURNS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=SUBAGENT_TOOLS)
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content  # only this crosses back to the parent

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                    for call in message.tool_calls
                ],
            }
        )
        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            result = _run_tool(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    return "(subagent gave up after MAX_SUBAGENT_TURNS without a final answer)"


TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "Delegate a self-contained investigation to a fresh subagent. It "
            "gets its own empty conversation and a read-focused tool set (no "
            "file writing, no todos, no spawning further subagents) -- only "
            "its final text answer comes back. Use this for exploratory work "
            "you don't want cluttering the main conversation, e.g. 'search "
            "these files for X and summarize what you find.'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The task to hand to the subagent, in full detail."},
            },
            "required": ["prompt"],
        },
    },
}
