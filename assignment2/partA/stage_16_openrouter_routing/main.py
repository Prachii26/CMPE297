"""Stage 16: OpenRouter routing and cost.

The single `model=MODEL` call from every earlier stage is replaced with
`call_with_fallback(client, MODELS, ...)`, which tries the ordered
MODELS route until one model answers. Every response now also carries
`usage.cost` (thanks to `usage.include: true`, set inside
call_with_fallback), which gets printed per call and added to a running
SESSION_COST that prints again on exit.
"""
import json
import os
import sys

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

import ui
import routing
from compaction import cap_fresh_result, compact
from context import reminder
from routing import call_with_fallback, format_route, set_route
from sandbox import sandbox_status
from sessions import latest_session_id, load_messages, log_message, log_rewind, new_session_id
from skills import skills_system_prompt
from subagent import TASK_SCHEMA, task
from tools import FUNCTIONS, TOOLS

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MAX_TURNS = 10

ALL_TOOLS = TOOLS + [TASK_SCHEMA]
ALL_FUNCTIONS = {**FUNCTIONS, "task": task}

# Session-scoped state: how much this run has spent, and which model in
# the route last actually answered (so /models can mark it).
SESSION_COST = 0.0
LAST_MODEL_USED = None


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
    global SESSION_COST, LAST_MODEL_USED
    for _ in range(MAX_TURNS):
        # Read routing.MODELS through the module, not a name imported
        # from it -- /route rebinds routing.MODELS to a NEW list object
        # (see set_route), and a `from routing import MODELS` binding here
        # would keep pointing at the old one forever.
        compact(messages, client, routing.MODELS[0])

        response, model_used = call_with_fallback(
            client, routing.MODELS, messages=messages + [reminder()], tools=ALL_TOOLS
        )
        if model_used != routing.MODELS[0]:
            ui.print_system(f"fell back to {model_used}")
        LAST_MODEL_USED = model_used
        message = response.choices[0].message

        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details else None
        cost = getattr(usage, "cost", None)
        if cost is not None:
            SESSION_COST += cost
        ui.print_usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, cached, cost)

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
    elif command == "/models":
        ui.print_system(format_route(routing.MODELS, active=LAST_MODEL_USED))
    elif command.startswith("/route"):
        rest = command[len("/route"):].strip()
        if not rest:
            ui.print_system(f"current route: {', '.join(routing.MODELS)}")
        else:
            names = [name.strip() for name in rest.split(",") if name.strip()]
            ui.print_system(set_route(names))
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
    ui.banner(routing.MODELS[0], sandbox_status())
    ui.print_system(format_route(routing.MODELS))
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

    ui.print_system(f"session cost: ${SESSION_COST:.6f}")


if __name__ == "__main__":
    main()
