"""Stage 15: subagents.

One addition to stage 14's registry: ALL_TOOLS / ALL_FUNCTIONS layer the
`task` tool (from subagent.py) on top of the base registry from tools.py.
The top-level loop is otherwise unchanged -- `task` is dispatched exactly
like `bash` or `read_file`, it just happens to run an entire second agent
loop internally.
"""
import json
import os
import sys

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

import ui
from compaction import cap_fresh_result, compact
from context import reminder
from sandbox import sandbox_status
from sessions import latest_session_id, load_messages, log_message, log_rewind, new_session_id
from skills import skills_system_prompt
from subagent import TASK_SCHEMA, task
from tools import FUNCTIONS, TOOLS

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")
MAX_TURNS = 10

# The top-level agent gets everything, including task. Subagents spawned
# by task() get tools.TOOLS/FUNCTIONS filtered down (see subagent.py) --
# this is the one place `task` itself is added back in, for the top level
# only, since subagent.py deliberately withholds it.
ALL_TOOLS = TOOLS + [TASK_SCHEMA]
ALL_FUNCTIONS = {**FUNCTIONS, "task": task}


def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def run_tool(name, args):
    fn = ALL_FUNCTIONS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as exc:
        return f"error running {name}: {exc}"


def run_loop(client, messages, session_id):
    for _ in range(MAX_TURNS):
        compact(messages, client, MODEL)

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages + [reminder()],
            tools=ALL_TOOLS,
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
            # A task call may take a while (it's a whole second loop) --
            # from here it looks like any other tool call: one name, one
            # args dict, one string result.
            result = cap_fresh_result(str(run_tool(call.function.name, args)))
            ui.print_tool_result(result)
            tool_msg = {"role": "tool", "tool_call_id": call.id, "content": result}
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
