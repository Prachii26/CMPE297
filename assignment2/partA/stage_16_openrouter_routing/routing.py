"""Stage 16: OpenRouter routing and cost.

MODELS is an ordered fallback route. call_with_fallback tries each model
in order and uses the first one that answers without raising -- the same
idea as retrying a flaky request, except each retry is a genuinely
different model, in case one is down, rate-limited, or (per this
project's hard rule) doesn't support tool calling at all.

Passing extra_body={"usage": {"include": True}} is an OpenRouter-specific
extension: it makes the response's usage object carry a `cost` field --
the actual dollar cost OpenRouter billed for that one call -- instead of
just token counts. That is the real source of the numbers this stage
prints; nothing here estimates cost from a price table.
"""
import os

DEFAULT_MODEL = os.environ.get("MODEL", "deepseek/deepseek-v4-flash-0731:free")

# The fallback route, in try-this-first order. /route changes this list
# at runtime; main.py always reads MODELS fresh, so a change takes effect
# on the very next call.
MODELS = [
    DEFAULT_MODEL,
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "liquid/lfm-2.5-2.6b:free",
]

# Illustrative USD price per MILLION tokens, as (prompt, completion).
# NOT fetched live -- OpenRouter's own /models endpoint is the
# authoritative, current source; this is a rough guide for `/models` to
# print, not a billing source of truth. The actual charge for any real
# call comes back from the API itself, in usage.cost, handled below.
PRICES = {
    "deepseek/deepseek-v4-flash-0731:free": (0.0, 0.0),
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": (0.0, 0.0),
    "liquid/lfm-2.5-2.6b:free": (0.0, 0.0),
}


def format_route(models=None, active=None):
    models = MODELS if models is None else models
    lines = ["route (tried in order, first success wins):"]
    for i, model in enumerate(models):
        prompt_price, completion_price = PRICES.get(model, (None, None))
        price_text = (
            f"${prompt_price}/M prompt, ${completion_price}/M completion"
            if prompt_price is not None
            else "price unknown"
        )
        marker = "  <- last used" if model == active else ""
        lines.append(f"  {i + 1}. {model} ({price_text}){marker}")
    return "\n".join(lines)


def set_route(model_names):
    """Replaces the route wholesale -- same "replace, don't merge" rule
    as write_todos in stage 11: one clear state, no partial edits."""
    global MODELS
    if not model_names:
        return "error: route must have at least one model. No change made."
    MODELS = model_names
    return f"route set to: {', '.join(MODELS)}"


def call_with_fallback(client, models, **kwargs):
    """Tries each model in `models`, in order. Returns (response,
    model_used) for the first one that doesn't raise. If every model
    fails, re-raises the LAST error -- there is nothing left to fall
    back to, and swallowing it would hide a real outage."""
    last_exc = None
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                extra_body={"usage": {"include": True}},
                **kwargs,
            )
            return response, model
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: a
            # rate limit, an outage, and "this model doesn't support tool
            # calling" should all fall through to the next model in line.
            last_exc = exc
            continue
    raise last_exc
