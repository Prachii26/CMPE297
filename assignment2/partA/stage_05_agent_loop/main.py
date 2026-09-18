"""Stage 05: the agent loop.

Stage 04 stopped after one tool call: the model asked, our code ran the
tool, and the result went to the screen instead of back to the model. Here
we close that loop -- keep calling the model, feeding each tool result
back as a message, until the model responds with plain text instead of
another tool call.

Two rules the OpenAI-compatible API enforces, both easy to get wrong:

1. A "tool" role message must be immediately preceded (earlier in the
   list, not necessarily adjacent) by the "assistant" message whose
   tool_calls entry it is answering. If you only ever store tool RESULTS
   and never store the assistant message that requested them, the API
   rejects the request on the next turn -- it has a tool message with no
   matching tool_calls to point back to.
2. When one assistant turn makes several tool calls at once, each result
   must carry the tool_call_id of the specific call it answers, so the
   model can match them up.
"""
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

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
    except Exception as exc:  # a tool failure is a result, not a crash
        return f"error running {name}: {exc}"


def run_loop(client, messages):
    """Mutates `messages` in place as the transcript grows, and returns the
    model's final text answer once it stops calling tools."""
    for _ in range(MAX_TURNS):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content

        # Rule 1: store the assistant message WITH its tool_calls, exactly
        # as the model sent them, before adding any tool results. This is
        # what the next turn's tool messages will be validated against.
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )

        for call in message.tool_calls:
            args = json.loads(call.function.arguments)
            result = run_tool(call.function.name, args)

            # Rule 2: tool_call_id ties this specific result to the specific
            # call that requested it, so parallel calls in one turn don't
            # get crossed.
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result),
                }
            )

    return "(gave up after MAX_TURNS without a final text answer)"


def main():
    client = make_client()
    messages = [
        {
            "role": "user",
            "content": "Read tools.py, then tell me how many tools are registered in it.",
        }
    ]
    final = run_loop(client, messages)
    print(f"reply: {final}")


if __name__ == "__main__":
    main()
