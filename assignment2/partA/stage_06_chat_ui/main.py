"""Stage 06: chat UI.

Stage 05's run_loop resolved one user message down to a final answer. Here
we wrap it in an outer loop that keeps asking for the next message, so the
conversation continues rather than exiting after one exchange. All screen
output is delegated to ui.py -- this file only decides WHEN to print
something, never HOW.
"""
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

import ui
from tools import FUNCTIONS, TOOLS

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")
MAX_TURNS = 10


def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def run_tool(name, args):
    fn = FUNCTIONS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as exc:
        return f"error running {name}: {exc}"


def run_loop(client, messages):
    """Same tool-resolution loop as stage 05, plus a usage line -- printed
    through ui.py, using only plain numbers -- after every single call."""
    for _ in range(MAX_TURNS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        message = response.choices[0].message

        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details else None
        ui.print_usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, cached)

        if not message.tool_calls:
            return message.content

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
            ui.print_tool_call(call.function.name, args)
            result = run_tool(call.function.name, args)
            ui.print_tool_result(result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})

    return "(gave up after MAX_TURNS without a final text answer)"


def main():
    client = make_client()
    ui.banner(MODEL)
    messages = []

    while True:
        try:
            user_input = ui.get_input()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input.strip():
            continue

        messages.append({"role": "user", "content": user_input})
        reply = run_loop(client, messages)
        messages.append({"role": "assistant", "content": reply})
        ui.print_reply(reply)


if __name__ == "__main__":
    main()
