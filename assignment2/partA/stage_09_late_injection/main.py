"""Stage 09: identical to stage 08's loop, except the request sent to the
model is `messages + [reminder()]` instead of `messages` -- see context.py
for why that one line matters.
"""
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

import ui
from context import reminder
from skills import skills_system_prompt
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
    for _ in range(MAX_TURNS):
        # `messages` itself is never touched here -- the reminder is spliced
        # in only for this one outgoing request.
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages + [reminder()],
            tools=TOOLS,
        )
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
    system_prompt = skills_system_prompt()
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

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
