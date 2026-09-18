"""Stage 02: a bash tool.

A JSON schema tells the model a `bash` function exists. A Python function
does the actual work. We send one request, and if the model calls the
tool, we run it and print the result -- but we do NOT send that result
back to the model. There is no loop yet: the model proposes a call, our
code disposes of it, and the conversation ends there. Stage 05 adds the
loop that feeds results back.
"""
import os
import subprocess

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")

# The schema is how the model learns the tool exists and how to call it.
# Nothing here executes anything -- it is pure description.
BASH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command and return its stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
            },
            "required": ["command"],
        },
    },
}


def bash(command: str) -> str:
    """The Python side of the tool: actually runs the command."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout
    if result.stderr:
        output += result.stderr
    return output.strip() or "(no output)"


def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def main():
    client = make_client()
    messages = [
        {"role": "user", "content": "List the files in the current directory using a shell command."}
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[BASH_TOOL_SCHEMA],
    )

    message = response.choices[0].message

    if message.tool_calls:
        # The model proposes: it names a tool and gives arguments as a JSON
        # string. We are the ones who decide whether to actually run it.
        call = message.tool_calls[0]
        import json

        args = json.loads(call.function.arguments)
        print(f"model called: {call.function.name}({args})")

        if call.function.name == "bash":
            output = bash(args["command"])
            print("--- tool output ---")
            print(output)
    else:
        print(f"reply: {message.content}")


if __name__ == "__main__":
    main()
