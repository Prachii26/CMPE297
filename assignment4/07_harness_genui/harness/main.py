"""Stage 15: subagents -- extended in assignment 4 with a render_ui tool.

[A4] marks every line assignment 4 added; everything else is stage 15 as
written in assignment 2. Additions: the render_ui tool (render_ui.py), two
surfaces for it (terminal_surface.py, and the browser via ../server.py with
--web), a --mode flag for the four generation modes, and a scripted client
(scripted_client.py) used instead of OpenRouter unless HARNESS_SCRIPTED=0.

Stage 15: subagents.

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
import render_ui as genui                                          # [A4]
from render_ui import RENDER_UI_SCHEMA, render_ui                  # [A4]
from scripted_client import ScriptedClient                         # [A4]
from terminal_surface import TerminalSurface                       # [A4]

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "liquid/lfm-2.5-2.6b:free")
MAX_TURNS = 10

# The top-level agent gets everything, including task. Subagents spawned
# by task() get tools.TOOLS/FUNCTIONS filtered down (see subagent.py) --
# this is the one place `task` itself is added back in, for the top level
# only, since subagent.py deliberately withholds it.
ALL_TOOLS = TOOLS + [TASK_SCHEMA, RENDER_UI_SCHEMA]                # [A4] + render_ui
ALL_FUNCTIONS = {**FUNCTIONS, "task": task, "render_ui": render_ui}  # [A4] + render_ui


def make_client():
    if os.environ.get("HARNESS_SCRIPTED", "1") == "1":            # [A4] offline, no key
        return ScriptedClient()                                    # [A4]
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


def _flag(argv, name, default=None):                               # [A4]
    return argv[argv.index(name) + 1] if name in argv else default  # [A4]


def run_turn(client, messages, session_id, user_input):            # [A4] one turn, shared by
    genui.CURRENT_REQUEST = user_input                             # [A4] the REPL, --prompt
    user_msg = {"role": "user", "content": user_input}             # [A4] and web actions
    messages.append(user_msg)                                      # [A4]
    log_message(session_id, user_msg)                              # [A4]
    reply = run_loop(client, messages, session_id)                 # [A4]
    assistant_msg = {"role": "assistant", "content": reply}        # [A4]
    messages.append(assistant_msg)                                 # [A4]
    log_message(session_id, assistant_msg)                         # [A4]
    ui.print_reply(reply)                                          # [A4]
    return reply                                                   # [A4]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    resume = "--resume" in argv
    genui.MODE = _flag(argv, "--mode", "declarative")              # [A4]
    genui.SURFACES[:] = [TerminalSurface()]                        # [A4]

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
    if "--web" in argv:                                            # [A4] second surface
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # [A4]
        import server                                              # [A4]
        server.attach(lambda text: run_turn(client, messages, session_id, text),  # [A4]
                      port=int(_flag(argv, "--port", "8007")))     # [A4]
    ui.banner(MODEL if not isinstance(client, ScriptedClient) else "scripted (offline)", sandbox_status())  # [A4]
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

    if "--prompt" in argv:                                         # [A4] non-interactive turn
        run_turn(client, messages, session_id, _flag(argv, "--prompt"))  # [A4]
        if "--web" not in argv:                                    # [A4]
            return messages                                        # [A4]
        server.serve_forever()                                     # [A4]
        return messages                                            # [A4]

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

        run_turn(client, messages, session_id, user_input)         # [A4] (same steps as before)


if __name__ == "__main__":
    main()
