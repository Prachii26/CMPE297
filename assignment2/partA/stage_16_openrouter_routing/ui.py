"""Stage 16: all screen drawing lives here.

Every function in this file takes plain strings, numbers, and dicts. It
never imports openai or tools -- it has no idea what a "model" or a "tool"
is, only how to print things. That separation is what makes it possible to
swap in a totally different backend (a different provider, a different
tool set) later without touching a single line here.
"""
from prompt_toolkit import prompt as pt_prompt
from rich.console import Console

console = Console()


def banner(model_name, sandbox_status):
    console.print(f"[bold cyan]agent[/bold cyan] -- model: {model_name}")
    console.print(f"sandbox: {sandbox_status}")
    console.print("type your message, /models, /route, /rewind, Ctrl+C to quit\n")


def get_input():
    return pt_prompt("you> ")


def print_reply(text):
    console.print(f"[bold green]agent>[/bold green] {text}\n")


def print_tool_call(name, args):
    console.print(f"[dim]  -> calling {name}({args})[/dim]")


def print_tool_result(result):
    text = str(result)
    if len(text) > 200:
        text = text[:200] + "... (truncated)"
    console.print(f"[dim]  <- {text}[/dim]")


def print_usage(prompt_tokens, completion_tokens, total_tokens, cached_tokens=None, cost=None):
    cached = cached_tokens if cached_tokens is not None else "n/a"
    cost_text = f"${cost:.6f}" if cost is not None else "n/a"
    console.print(
        f"[dim]usage: prompt={prompt_tokens} completion={completion_tokens} "
        f"total={total_tokens} cached_tokens={cached} cost={cost_text}[/dim]"
    )


def print_system(text):
    """For local, non-model status lines: session ids, /rewind confirmation,
    unknown-command notices, the route. Never sent to the model."""
    console.print(f"[yellow]* {text}[/yellow]")
