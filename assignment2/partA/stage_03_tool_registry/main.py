"""Stage 03: dispatch tool calls through the registry instead of an if-chain."""
import json
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

from tools import FUNCTIONS, TOOLS

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")


def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def main():
    client = make_client()
    messages = [
        {"role": "user", "content": "List the files in the current directory using a shell command."}
    ]

    response = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
    message = response.choices[0].message

    if message.tool_calls:
        call = message.tool_calls[0]
        name = call.function.name
        args = json.loads(call.function.arguments)
        print(f"model called: {name}({args})")

        # The dispatch is generic: look the name up, call it. No branch has
        # to be added here when a new tool shows up in the registry.
        fn = FUNCTIONS.get(name)
        if fn is None:
            print(f"error: model called unknown tool '{name}'")
            return

        output = fn(**args)
        print("--- tool output ---")
        print(output)
    else:
        print(f"reply: {message.content}")


if __name__ == "__main__":
    main()
