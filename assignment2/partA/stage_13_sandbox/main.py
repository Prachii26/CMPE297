"""Stage 13: sandbox.

Identical loop to stage 12. The only change here is the banner now shows
sandbox_status() -- see sandbox.py for what enforces what, and honestly,
where -- and bash() (in tools.py) now runs commands through the sandbox
wrapper instead of calling subprocess directly.
"""
import json
import os
import sys

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

import ui
from context import reminder
from sandbox import sandbox_status
from sessions import latest_session_id, load_messages, log_message, log_rewind, new_session_id
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


def run_loop(client, messages, session_id):
    for _ in range(MAX_TURNS):
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

        assistant_msg = {
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
        messages.append(assistant_msg)
        log_message(session_id, assistant_msg)

        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            ui.print_tool_call(call.function.name, args)
            result = run_tool(call.function.name, args)
            ui.print_tool_result(result)
            tool_msg = {"role": "tool", "tool_call_id": call.id, "content": str(result)}
            messages.append(tool_msg)
            log_message(session_id, tool_msg)

    return "(gave up after MAX_TURNS without a final text answer)"


def handle_slash_command(command, session_id, messages):
    """Slash commands are resolved entirely here. None of this ever
    becomes a message, so it never reaches the model."""
    if command == "/rewind":
        turn_starts = [i for i, m in enumerate(messages) if m["role"] == "user"]
        if not turn_starts:
            ui.print_system("nothing to rewind")
            return
        to_index = turn_starts[-1]
        del messages[to_index:]
        log_rewind(session_id, to_index)
        ui.print_system(f"rewound to before the last message ({to_index} messages remain)")
    else:
        ui.print_system(f"unknown command: {command}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    resume = "--resume" in argv

    if resume:
        session_id = latest_session_id()
        if session_id is None:
            session_id = new_session_id()
            messages = []
        else:
            messages = load_messages(session_id)
    else:
        session_id = new_session_id()
        messages = []

    client = make_client()
    ui.banner(MODEL, sandbox_status())
    if resume and messages:
        ui.print_system(f"resumed session {session_id} ({len(messages)} messages)")
    else:
        ui.print_system(f"session {session_id}")

    if not any(m["role"] == "system" for m in messages):
        system_prompt = skills_system_prompt()
        if system_prompt:
            sys_msg = {"role": "system", "content": system_prompt}
            messages.append(sys_msg)
            log_message(session_id, sys_msg)

    while True:
        try:
            user_input = ui.get_input()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input.strip():
            continue

        if user_input.startswith("/"):
            handle_slash_command(user_input.strip(), session_id, messages)
            continue

        user_msg = {"role": "user", "content": user_input}
        messages.append(user_msg)
        log_message(session_id, user_msg)

        reply = run_loop(client, messages, session_id)
        assistant_msg = {"role": "assistant", "content": reply}
        messages.append(assistant_msg)
        log_message(session_id, assistant_msg)
        ui.print_reply(reply)


if __name__ == "__main__":
    main()
