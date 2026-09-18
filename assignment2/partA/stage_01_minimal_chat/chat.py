"""Stage 01: one API call.

Send a single message to the model over the OpenRouter-compatible chat
completions endpoint, print the reply, and print token usage -- including
cached_tokens, which providers use to report a prompt-cache discount.
"""
import os

from dotenv import find_dotenv, load_dotenv
from openai import OpenAI

load_dotenv(find_dotenv())

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")


def make_client():
    # A thin factory, not a module-level singleton, so tests can swap in a
    # fake client without touching real network code or the OpenAI package.
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)


def print_usage(usage):
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details else None
    print(
        f"usage: prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
        f"total={usage.total_tokens} cached_tokens={cached if cached is not None else 'n/a'}"
    )


def main():
    client = make_client()
    messages = [{"role": "user", "content": "Say hello in exactly five words."}]

    response = client.chat.completions.create(model=MODEL, messages=messages)

    print(f"model: {MODEL}")
    print(f"reply: {response.choices[0].message.content}")
    print_usage(response.usage)


if __name__ == "__main__":
    main()
