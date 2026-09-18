# Stage 16 — OpenRouter Routing and Cost

**The idea:** stop calling a single hardcoded model. Try an ordered list
of models, falling back to the next one if a call fails. Ask OpenRouter
to report the real dollar cost of every call, and keep a running session
total.

## Run it

```powershell
.venv\Scripts\python.exe stage_16_openrouter_routing\main.py
```

Try `/models` to see the route and its prices, `/route model-a, model-b`
to change it, and watch the `usage:` line grow a `cost=` field. The
session total prints on exit.

## The code

`routing.py`'s `MODELS` is the fallback route, tried in order:

```python
MODELS = [DEFAULT_MODEL, "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "liquid/lfm-2.5-2.6b:free"]

def call_with_fallback(client, models, **kwargs):
    last_exc = None
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                extra_body={"usage": {"include": True}},
                **kwargs,
            )
            return response, model
        except Exception as exc:
            last_exc = exc
            continue
    raise last_exc
```

Any failure — a rate limit, an outage, a model that rejects `tools=` —
falls through to the next model in the list. If every model fails, the
*last* error is re-raised; there's nothing left to fall back to, and
swallowing it would hide a real outage from the user.

### `usage.include: true` is what makes cost real

```python
extra_body={"usage": {"include": True}}
```

This is an OpenRouter-specific extension of the request body. With it
set, the response's `usage` object carries a `cost` field: the actual
dollar amount OpenRouter billed for that specific call. Nothing in this
codebase estimates cost from a price table — `PRICES` in `routing.py` is
explicitly a rough, hardcoded guide for `/models` to *display*, labeled
as such, not the number anything gets billed by. The real number always
comes from the API response itself:

```python
cost = getattr(usage, "cost", None)
if cost is not None:
    SESSION_COST += cost
ui.print_usage(usage.prompt_tokens, usage.completion_tokens, usage.total_tokens, cached, cost)
```

### /models and /route

```python
elif command == "/models":
    ui.print_system(format_route(routing.MODELS, active=LAST_MODEL_USED))
elif command.startswith("/route"):
    rest = command[len("/route"):].strip()
    ...
    ui.print_system(set_route(names))
```

Both are slash commands, resolved in `handle_slash_command` — same as
`/rewind` since stage 10 — and never seen by the model.

### A binding bug worth naming

`main.py` does `import routing` and reads `routing.MODELS[0]` everywhere,
instead of `from routing import MODELS`. That's deliberate, not a style
choice: `set_route()` does `global MODELS; MODELS = model_names`, which
*rebinds* the name `MODELS` inside `routing.py` to a brand-new list
object. A `from routing import MODELS` in `main.py` would have copied the
*old* list reference at import time and never seen the change — `/route`
would print a confirmation while every subsequent call kept using the old
route. Reading `routing.MODELS` through the module, on every access,
means it's always the current object. (This is the same class of bug
`stage_12_permissions`'s tests caught with `ask_user` — see that stage's
README.)

### Session cost on exit

```python
ui.print_system(f"session cost: ${SESSION_COST:.6f}")
```

Printed once, right after the input loop breaks — the running total of
every real `usage.cost` seen across the whole session.

## Diff

```powershell
git diff --no-index stage_15_subagents stage_16_openrouter_routing
```
