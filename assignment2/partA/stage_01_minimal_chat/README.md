# Stage 01 — Minimal Chat

**The idea:** make one API call, print the reply, print the token usage.
Nothing else. This is the floor every later stage stands on.

## Run it

```powershell
cd stage_01_minimal_chat
..\.venv\Scripts\python.exe chat.py
```

You need `OPENROUTER_API_KEY` set (in `partA\.env`, copied from `.env.example`).

## The code

`chat.py` does four things:

1. Loads `.env` with `python-dotenv`, using `find_dotenv()` so it finds
   `partA\.env` no matter which stage directory you run from.
2. Builds an `OpenAI` client pointed at OpenRouter's base URL
   (`https://openrouter.ai/api/v1`) instead of OpenAI's. OpenRouter is a
   drop-in replacement for the OpenAI chat completions API, so the same
   client class works — only `base_url` and the API key change.
3. Sends one message and calls `client.chat.completions.create(...)`.
4. Prints `response.choices[0].message.content` (the reply) and
   `response.usage` (prompt/completion/total tokens).

```python
def make_client():
    return OpenAI(api_key=os.environ.get("OPENROUTER_API_KEY", ""), base_url=BASE_URL)
```

`make_client()` is a function, not a client built once at import time. That
one choice is what lets `run_tests.py` swap in a fake client later — it
monkeypatches `make_client` on the imported module before calling `main()`,
so no real network call ever has to happen to test the logic.

### Why print `cached_tokens`

Providers that support prompt caching return the cache hit count under
`usage.prompt_tokens_details.cached_tokens`. Not every model/provider
populates this field, so the code reads it defensively with `getattr` and
prints `n/a` rather than crashing when it's absent:

```python
details = getattr(usage, "prompt_tokens_details", None)
cached = getattr(details, "cached_tokens", None) if details else None
```

Stage 09 explains why cached tokens matter for this harness specifically:
once we start injecting volatile facts (time, git branch) into every
request, keeping that block *out* of the stored transcript is what lets the
provider still hit the cache on the unchanged prefix.

## Model choice

The model comes from the `MODEL` env var, defaulting to
`deepseek/deepseek-v4-flash-0731:free`. If a later stage's tool-calling
request fails because a model doesn't support tools (or OpenRouter has
retired that model id — free-tier models get swapped out over time), the
fix is to change `MODEL`, not the code — the architecture doesn't change
per model.

## Diff

First stage — nothing to diff against.
