# Prompts

Every prompt sent across all three parts of this assignment, verbatim, in
order, pulled from the actual session transcript. Interruption artifacts
and task notifications (not typed by the user) are excluded. One line
under each says what it produced or fixed.

---

## 1. Part A kickoff

Sent twice — the first send was interrupted mid-tool-call before any file
was written; it was then resent identically and work proceeded from
there.

```
I have to work on CMPE297's assignment2
You are building Part A of a graduate assignment on harness engineering. We are building a coding agent harness from scratch, progressively, in 16 stages. Each stage is its own runnable directory that adds exactly one idea to the stage before it.

Do not clone or copy any existing repo. Write every file yourself.

## Environment
I am on Windows using PowerShell. Use PowerShell syntax for all commands you run or give me.

Check Node.js (18+) and Python (3.10+). Install whatever is missing and tell me what you did. Create a Python venv at Assignment2/partA/.venv and install: openai, rich, prompt_toolkit, python-dotenv, pyyaml.

## API configuration
The harness talks to OpenRouter — this is a hard requirement of the assignment. Read OPENROUTER_API_KEY from the environment. BASE_URL is https://openrouter.ai/api/v1.

The harness needs reliable tool calling. Use google/gemini-2.0-flash-exp:free as the default, with the model id read from a MODEL env var. If a call fails because the model does not support tool calling, stop and tell me — we will switch models, not architecture.

Create .env.example with variable names and no values. Add .env and *.env to .gitignore, with !.env.example. Never write a real key into any file.

## Layout
Assignment2/partA/
  README.md
  requirements.txt
  .env.example
  run_tests.py
  stage_01_minimal_chat/ ... stage_16_openrouter_routing/

Each stage directory is self-contained and runnable on its own, with its own README.md showing the code, explaining it, and ending with a diff command against the previous stage.

## The 16 stages — one idea each

01 One API call. Send messages, print the reply and token usage including cached_tokens.
02 A bash tool. A JSON schema tells the model the function exists; a Python function does the work. Single tool call, no loop yet. The model proposes, your code disposes.
03 Tool registry. Schemas in a list, functions in a dict keyed by the same names. A new tool becomes one entry in each.
04 read_file tool, added without touching the main loop file. The README notes the content goes to the screen, not the model — which stage 05 fixes.
05 The agent loop. Feed tool results back until the model answers in text. Store the assistant message WITH its tool_calls, because the API rejects a tool message that does not follow the assistant message that requested it. Tie each result to its call with tool_call_id.
06 Chat UI. An outer loop asking for the next message. All drawing in ui.py, which knows nothing about models or tools. Usage line after every call.
07 Skills. SKILL.md with YAML front matter. Only name and description go in the system prompt; the body loads on demand via read_skill. Ship 2 example skills.
08 File editing. write_file and str_replace. str_replace refuses on zero or multiple matches, and the refusal is returned as the tool result so the model retries. Errors are results, never exceptions.
09 Late injection. Volatile facts (time, git branch, cwd) in a block appended to the REQUEST only, never stored in the transcript: messages + [reminder()]. README explains why this preserves prefix caching.
10 Sessions. Append every message to JSONL as it happens. /rewind writes a marker rather than deleting. --resume reopens the last session. Slash commands never reach the model.
11 Todos. write_todos replaces the whole list and validates that exactly one item is in_progress. The list lives in a variable and rides in the late block.
12 Permissions. A rule table rating commands allow/ask/deny. Compound commands split on && and |, strictest verdict wins. Verdict returned as the tool result. README states honestly that this only inspects command text and is not real security.
13 Sandbox. OS-level enforcement: Seatbelt on macOS, bubblewrap on Linux. On Windows print "sandbox: none" in the banner and explain the limitation rather than faking it. Every command gets a timeout that comes back as a result.
14 Compaction. Four mechanisms, cheapest first: cap fresh results over 10000 chars to a temp file, shrink finished-turn results to a 300-char stub, drop whole old results if still too big, and finally a no-tools summarizer agent that writes a handoff note when the prompt passes 85% of the window. Cut back to 35%.
15 Subagents. A task tool running a fresh loop with an empty transcript. It gets every tool EXCEPT task, write_todos, write_file and str_replace, so it cannot edit and cannot recurse. Only its final answer returns.
16 OpenRouter routing and cost. An ordered MODELS list as the fallback route, usage.include true to get cost back, /models showing the route and prices, /route to change it at runtime. Cost per call and a session total on exit.

## Testing
run_tests.py runs every stage against a fake model with no API key needed. One line per stage ending in "passed". I will demo this in the video, so it has to actually work.

## Rules
- Work stage by stage. After each stage, print 3-4 sentences on what changed and why it matters, then continue. I have to explain every file on camera.
- No frameworks. No langchain, no agent SDKs. The openai client and the standard library.
- Keep each stage small and readable.
- Comment the non-obvious parts: the tool_call_id pairing, the late-injection list building, the subagent tool withholding.

## When done
Run run_tests.py. Then run stage 16 against the real API to confirm the OpenRouter path works end to end, and report the model served and the cost.

Write Assignment2/partA/README.md last: what this is, a 16-row stage table, quick start, how to run the tests.

Start with environment setup. Tell me the Node and Python versions you find before building anything.
```

**Produced:** all 16 stage directories, `requirements.txt`, `run_tests.py`,
`.env.example`, and the environment setup (Node/Python version checks,
venv creation, package installs) that preceded them.

---

## 2. "done"

```
done
```

**Produced:** confirmed the `OPENROUTER_API_KEY` was in place after the
assistant said it would wait for that before running the live test —
unblocked the real end-to-end run of stage 16, which is what surfaced
the model-deprecation finding.

---

## 3. "commit the changes"

```
commit the changes
```

**Produced:** the git commit for all of Part A, after the full 16-stage
summary and the model-deprecation fix were reported.

---

## 4. Part B kickoff

```
Part B of the assignment. We are installing DeepSeek Harness (dsh), customizing it in Creator mode with community plugins, and writing two plugins from scratch.

I am on Windows using PowerShell. Work in Assignment2/partB/.

## Step 1 — Read the docs before writing anything
DSH is a developer preview and its plugin API changes. Do NOT rely on your training data or blog tutorials for the plugin API. Fetch and read, in this order:
- https://github.com/deepseek-ai/deepseek-harness (README, then AGENTS.md)
- https://deepseek-harness.github.io/deepseek-harness/ (the plugin authoring docs and the Cordis context API)
- https://github.com/awesome-dsh-plugin/awesome-dsh-plugin (the plugin catalog)

Summarize for me, before installing anything: the current plugin file structure, the exact shape of a plugin entry point, what the Cordis ctx object exposes, and which lifecycle events a plugin can hook. If the docs contradict what you expected, follow the docs and tell me what differed.

## Step 2 — Install
Check Node.js 18+. Install dsh and start the web UI (npx @deepseek-ai/dsh web, default port 3080). Configure it to use my OPENROUTER_API_KEY as the model provider rather than a DeepSeek key — read it from the environment. Confirm the UI loads and a simple task runs end to end before continuing.

Record in Assignment2/partB/INSTALL.md: the exact commands, the versions installed, anything that broke and how you fixed it. The install notes are a graded artifact.

## Step 3 — Install 5 to 7 community plugins
Pick from the catalog, favoring ones that are actively maintained and that demo well on video. Aim for variety across categories — UI, tools, workflow, memory — not five of the same kind.

For EACH plugin, record in Assignment2/partB/PLUGINS.md: what it does, why I picked it, the install command, and a one-line note on what to show in the demo. Verify each one actually loads and works. If one is broken or incompatible with the installed version, say so, drop it, and pick another — do not leave a broken plugin in and call it installed.

## Step 4 — Write two plugins from scratch
These are the graded centerpiece of Part B. Build them under Assignment2/partB/plugins/.

Plugin 1 — "leakage-guard": a pre-execute hook on tool calls that inspects Python code the agent is about to write or run, and flags common ML data-leakage patterns: fit_transform called on the full dataset before a split, scalers fit outside a Pipeline, shuffle=True on time series splits, test data touched during training. It warns with a clear reason rather than hard-blocking, and the warning goes back to the agent as the tool result so it can self-correct. This connects to my CMPE 297 work on leakage auditing.

Plugin 2 — "session-cost-panel": tracks tokens and cost per model call across a session, and surfaces a running total plus a per-tool-call breakdown in the UI. Persist it so the number survives a reload.

For each: follow the plugin structure from the docs exactly. Write a README in its folder covering what it does, how it hooks into the harness, how to install it, and how to demo it. Save the prompt used to build it — the assignment requires showing the prompt alongside the demo.

## Step 5 — Verify
Load both custom plugins into the harness and prove each one fires. For leakage-guard, give the agent a task that would produce leaky code and show the warning appearing. For session-cost-panel, run a few turns and show the total updating. Screenshot both.

## Rules
- Use Creator mode where the docs say it applies — the assignment specifically asks for it.
- Explain what you are doing as you go. I have to walk through every file on camera.
- If the docs and reality disagree, tell me rather than working around it silently.
- Never write an API key into a file.

Start with Step 1. Give me the docs summary before you install anything.
```

**Produced:** the real docs summary (plugin file structure, entry-point
shape, Cordis `ctx` surface, hookable lifecycle events) before anything
was installed.

---

## 5. "Continue with Step 2..."

```
Continue with Step 2. Keep going through Steps 3, 4 and 5 without stopping to check in, except in these cases: the install fails in a way you cannot resolve in 15 minutes, a community plugin turns out to be incompatible and you need to pick a different one, or the docs contradict what you expected badly enough that the plugin design has to change.

Pin the exact dsh version you install in INSTALL.md — this is a developer preview and the version matters for reproducibility.

For session-cost-panel, label the cost figures as estimated, not measured, since DSH has no dollar-cost field and the price table is illustrative.

Take screenshots as you go into Assignment2/partB/screenshots/. Commit after Step 3 and again after Step 4.

Tell me when both custom plugins are loaded and firing.
```

**Produced:** the pinned `@deepseek-ai/dsh@0.1.5-rc.2` install, six kept
community plugins (two others dropped after breaking the install), both
custom plugins (`leakage-guard`, `session-cost-panel`) built and verified
firing, all screenshots, and two commits.

---

## 6. Part C kickoff

```
Part C. Build a custom ML harness plugin for autoresearch, end to end. Work in Assignment2/partC/.

The assignment marks this part IMPORTANT, so it gets the most care.

## What autoresearch is
Karpathy's pattern: a program.md instructs a coding agent to edit one target file, run it against an evaluation metric under a fixed time budget, then keep the change if the metric improved or revert it if it did not, and loop. The structure is portable to any optimizable target.

## What to build
A DSH plugin called "autoresearch" that runs this loop end to end on a real ML task.

Components:
1. A target: train.py, a small ML training script that runs in under 60 seconds on CPU. Use a synthetic or sklearn built-in dataset — no downloads, no GPU, no API keys. The metric must be genuinely improvable, not already maxed out.
2. A held-out evaluation the optimizer cannot see or touch. This is the whole game — if the loop can tune against the eval set, the numbers are meaningless. Enforce the separation in code and say how in the README.
3. The loop itself, as a DSH plugin: propose an edit, run, measure, keep or revert, log the attempt, repeat for N iterations.
4. A run ledger: every iteration recorded with what changed, the metric before and after, the decision, and elapsed time. Append-only, JSON.
5. A reward-hacking guard. This is the part that separates a real autoresearch harness from a toy. Detect and reject: edits that touch the eval code or the held-out split, edits that hardcode or memorize expected outputs, edits that change the metric definition itself, runs that finish suspiciously fast. Log every rejection with its reason.
6. A results view: iteration history, metric trajectory, accept/reject counts, best-so-far.

## Requirements
- It must actually run and produce a real improvement trajectory. Run it for at least 10 iterations and show me the ledger.
- Honest reporting. If the loop plateaus or regresses, the README says so. A flat trajectory reported honestly beats a fabricated climb.
- Follow the DSH plugin structure from the Part B docs work, and use the Cordis API as it actually is, not as you expect it to be.
- README covering: what autoresearch is, how this implementation works, the leakage boundary, the reward-hacking guards and what each prevents, how to run it, and the actual results from the 10-iteration run.
- Save the prompt used to build this.

Start by writing train.py and confirming it runs and produces a baseline metric. Show me that baseline before building the loop around it.
```

**Produced:** `target/train.py`, `harness/data.py`, `harness/evaluate.py`,
and the confirmed baseline (67.11% held-out accuracy from a deliberately
weak depth-2 decision tree) — shown before any loop code was written.

---

## 7. "Baseline approved. Build the loop..."

```
Baseline approved. Build the loop.

One addition: log the wall-clock time of every iteration in the ledger and flag any run that finishes significantly faster than baseline. A run that skips actual training is one of the ways this loop gets gamed, and 0.016s is a low enough bar that a hollowed-out train.py would be obvious.

Also make sure the ledger records the reason for every revert, not just that one happened. The rejection log is the interesting artifact here — more so than the accepted edits.

Run it for at least 10 iterations and show me the ledger when it's done.
```

**Produced:** the DSH plugin itself (`guard.js`, `runner.js`,
`propose.js`, `loop.js`, `ledger.js`, `index.js`), the timing guard, and
the first attempt at the 10-iteration run.

---

## 8. "continue from where you left"

```
continue from where you left
```

**Produced:** resumed the 10-iteration run after it paused mid-run on a
Claude usage/spend-limit notification, rather than restarting from
scratch.

---

## 9. "kill the process its taking too longs and check the logs what happend"

```
kill the process its taking too longs and check the logs what happend
```

**Produced:** the run was stopped and diagnosed from the logs rather than
guessed at — found two `ctx.llm.stream` timeouts (iterations 2 and 6,
each retried 3× before being logged as a revert) and confirmed the real,
completed trajectory: 67.11% → 89.67%, 3 kept / 7 reverted.

---

## 10. "Before finalizing, add a guard verification test..."

```
Before finalizing, add a guard verification test. The 10-iteration run had zero guard rejections, so the guard's real function is currently unproven — we only know it produced two false positives and got fixed.

Write a small test suite under partC/tests/ that feeds the guard deliberately gaming edits and asserts each is rejected with the right reason:
1. an edit that reads the held-out split inside train.py
2. an edit that hardcodes expected predictions
3. an edit that modifies the metric definition in evaluate.py
4. a train.py gutted so it finishes in near-zero time without training

Each should be rejected. Also include 2 legitimate edits that must pass, so the test proves the guard discriminates rather than just rejecting everything.

Run it and show me the results. Then finalize the README with the real 10-iteration trajectory, the two false-positive bugs and their fixes, and this verification suite. Take screenshots, and commit.
```

**Produced:** `tests/guard.test.mjs` (13/13 passing), the timing-threshold
fix (15% → 50% of baseline) that the suite's first run surfaced, the
model-artifact restore fix the suite's own cleanup needed, the finalized
`partC/README.md`, three screenshots, and the Part C commit.

---

## 11. This prompt

```
Write the top-level Assignment2/README.md tying all three parts together:
- What the assignment was, in two sentences
- Part A: the 16-stage harness, the stage table, how to run it and the tests, the model-deprecation finding
- Part B: dsh install, the pinned version, the 5 community plugins kept and the 2 dropped with why, and the two custom plugins with what each does
- Part C: autoresearch, the real trajectory table, the two guard false-positives, the timing-threshold near-miss, and the verification suite results
- A YOUTUBE_LINK_PART_A / B / C placeholder near the top
- Quick start for each part

Then PROMPTS.md: every prompt I actually sent you across all three parts, verbatim in code blocks, in order, each with one line on what it produced or fixed. Pull them from session history — do not invent any.

Plain direct prose. No filler. Then commit and push.
```

**Produced:** `Assignment2/README.md` and this file, pulled from the
actual session transcript rather than reconstructed from memory.
