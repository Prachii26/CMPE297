# Step 5 — Verification

Both custom plugins loaded together via
[`custom-plugins.patch.yml`](custom-plugins.patch.yml) (an absolute-path
`insert`, the documented pattern for an unpublished local plugin) stacked
on top of [`openrouter.patch.yml`](openrouter.patch.yml):

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --patch ./custom-plugins.patch.yml
```

Both confirmed **Enabled**, zero load errors, in Settings → Plugins →
Plugin list:

- [`screenshots/18-leakage-guard-in-list.png`](screenshots/18-leakage-guard-in-list.png)
- [`screenshots/19-cost-panel-in-list.png`](screenshots/19-cost-panel-in-list.png)

## leakage-guard fires

Prompt sent to the agent (real turn, real OpenRouter model,
`deepseek/deepseek-v4-flash-0731:free`):

> Write a file called leaky_example.py with EXACTLY this code, do not fix
> or improve it, I want to see it as-is: `import pandas as pd; from
> sklearn.preprocessing import StandardScaler; from
> sklearn.model_selection import train_test_split; scaler =
> StandardScaler(); X_scaled = scaler.fit_transform(X); X_train, X_test,
> y_train, y_test = train_test_split(X_scaled, y, test_size=0.2)`

The `write` tool call was **not blocked** — `leaky_example.py` was created
exactly as requested. The agent's own reply then read and quoted the
warning directly:

> "For the record, the leakage-guard heuristic flagged two things
> (fit_transform on the full X before the split, and a scaler fit outside
> a Pipeline)."

Expanding the tool call's trajectory shows the model's own intermediate
`Think` step reacting to it: *"The feedback is a heuristic leak guard
message, but the user explicitly said to not fix it."* — direct proof the
warning arrived as part of the `write` tool's own result content (not a
separate injected message the model might not have read), and that the
model can act on it (self-correct) precisely because it's warned, not
blocked.

Screenshots:
- [`screenshots/24-leakage-guard-full-turn.png`](screenshots/24-leakage-guard-full-turn.png)
- [`screenshots/25-toolcall-expanded.png`](screenshots/25-toolcall-expanded.png)

## session-cost-panel fires

Ran two turns (the leakage-guard demo above, plus one earlier turn), then
typed `/cost` in the Web UI:

```
Session cost report -- ESTIMATED, not measured (DSH has no dollar-cost field;
this uses an illustrative price table, see the plugin README):

  total: ~$0.000000 across 2 model call(s), 6799 tokens

per-tool breakdown:
  write: 1 call(s), ~$0.000000, 4756 tokens

(persisted to ...\session-cost-panel\data\session-cost.json -- survives a reload/restart)
```

The `cost` row rendered as its own entry in the transcript, outside the
model's reply — confirmed visually (it sits below the assistant turn's
usage/footer line, not inside its bubble).

**Persistence was actually tested, not assumed:** the dsh server process
was killed (`TaskStop`) and restarted from scratch (new PowerShell
process, new auth token, new browser context — nothing carried over
except the file on disk). `/cost` was run again against that fresh
process and returned the **identical** numbers, read back from
`session-cost-panel/data/session-cost.json`:

```json
{
  "sessions": {
    "session-8a885056-368e-4a22-81a1-91ba8d44e158": {
      "totalCostEstimate": 0,
      "totalTokens": 6799,
      "calls": 2,
      "byTool": { "write": { "calls": 1, "costEstimate": 0, "tokens": 4756 } },
      "updatedAt": "2026-09-18T19:27:45.703Z"
    }
  }
}
```

Screenshots:
- [`screenshots/28-cost-report-expanded.png`](screenshots/28-cost-report-expanded.png) (before restart)
- [`screenshots/29-cost-after-restart.png`](screenshots/29-cost-after-restart.png) (after restart — same numbers)

## Both plugins loaded and firing

Confirmed: `leakage-guard` and `session-cost-panel` both load cleanly
alongside every Step 3 community plugin and the OpenRouter routing
patch, and both produced real, observable effects against a real model
call over OpenRouter — not a mocked or simulated run.
