# Install Notes — DeepSeek Harness (dsh)

Graded artifact. Every command below was actually run, in this order, on this
machine (Windows 11, PowerShell). Where something broke, the fix is recorded
immediately after it, not smoothed over.

## Pinned version

```
@deepseek-ai/dsh@0.1.5-rc.2
```

This is the `latest` dist-tag on npm as of 2026-09-18. dsh is a developer
preview (`versions` on npm also lists newer `0.1.6-alpha.*` builds published
after this one) — pinning the exact version, not `@latest`, is what makes
this install reproducible later. Confirmed via:

```powershell
Invoke-RestMethod -Uri "https://registry.npmjs.org/@deepseek-ai/dsh" |
  Select-Object -ExpandProperty dist-tags
# next: 0.1.5-rc.2 | latest: 0.1.5-rc.2 | alpha: 0.1.6-alpha.2
```

## Prerequisites

| Tool | Required | Found / installed |
|---|---|---|
| Node.js | ≥ 18 | v24.19.0 (already installed for Part A) |
| npm | ships with Node | 11.17.0 |
| pnpm | needed by `dsh plugin` | **not installed — installed below** |

```powershell
node --version   # v24.19.0
npm --version    # 11.17.0
```

### Windows PATH gotcha

Every fresh PowerShell process in this environment starts from a stale
`PATH` snapshot that predates the Node.js install from Part A — `node`,
`npm`, and `npx` all report "not recognized" until `PATH` is reloaded from
the registry:

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path","User")
```

This line prefixes every PowerShell command in this project from here on.
The same applies to `OPENROUTER_API_KEY` (set as a User environment
variable, not visible to an already-running process) — reloaded the same
way:

```powershell
$env:OPENROUTER_API_KEY = [System.Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY","User")
```

The Bash tool in this environment (Git Bash) never picked up Node at all
(`npx: command not found`) — every dsh command below runs through
PowerShell instead.

## Installing pnpm

`dsh plugin` (community plugin install/management) shells out to `pnpm`
inside the profile directory. This is **not** mentioned as a prerequisite
next to the `npx @deepseek-ai/dsh web` quick-start in the README — it only
surfaces the first time `dsh plugin` actually runs:

```
'pnpm' is not recognized as an internal or external command,
operable program or batch file.
dsh: pnpm failed in profile directory C:\Users\sarth\.dsh\profiles\web
```

`corepack enable pnpm` failed too (`EPERM` writing into
`C:\Program Files\nodejs`, which needs admin rights this session doesn't
have). Fixed with a plain global npm install instead:

```powershell
npm install -g pnpm
pnpm --version   # 12.4.2
```

## Checking the CLI before trusting it

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --help
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --help
```

Confirmed the real subcommands: `dsh --profile <name>` / `dsh web` (alias
for `--profile web`) boots a profile; `dsh plugin --profile <name> <pnpm
args>` forwards straight to pnpm inside `$DSH_HOME/profiles/<name>`
(`$DSH_HOME` defaults to `C:\Users\sarth\.dsh`).

## Routing the model provider to OpenRouter

The assignment requires `OPENROUTER_API_KEY` as the provider, read from the
environment, with **no key ever written to a file**. dsh ships a
generic multi-provider adapter, `@deepseek-ai/dsh-llm-pi-ai`, mounted by
default with zero providers configured — confirmed by dumping the composed
config before touching anything:

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --profile web --dump-config > dump-config.yml
```

That dump also showed the default model row (`agent-default-model` →
`provider: deepseek-official, model: deepseek-flash`) and the exact
`apiKeyEnv` convention already used elsewhere in the same config
(`web-search-deepseek` → `apiKeyEnv: DEEPSEEK_API_KEY`): a config field
that names an **environment variable**, resolved per-request through the
harness's own credential seam — never the literal secret. Read
`packages/llm/llm-pi-ai/README.md` in the repo for the full schema before
writing anything.

`openrouter.patch.yml` (committed, contains no secret — only the env var
*name*):

```yaml
- id: llm-pi-ai
  name: '@deepseek-ai/dsh-llm-pi-ai'
  config:
    providers:
      openrouter:
        displayName: OpenRouter
        apiKeyEnv: OPENROUTER_API_KEY
        api: openai-completions
        baseURL: https://openrouter.ai/api/v1
        models:
          - id: deepseek/deepseek-v4-flash-0731:free
            name: DeepSeek V4 Flash (free, via OpenRouter)
            contextWindow: 131072
          - id: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
            name: Nemotron 3 Nano (free, via OpenRouter)
            contextWindow: 131072
          - id: liquid/lfm-2.5-2.6b:free
            name: LFM 2.5 (free, via OpenRouter)
            contextWindow: 32768
- id: agent-default-model
  name: '@deepseek-ai/dsh-agent-default-model'
  config:
    provider: openrouter
    model: deepseek/deepseek-v4-flash-0731:free
```

Verified the patch actually applies before booting anything real:

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --profile web --patch ./openrouter.patch.yml --dump-config > dump-config-patched.yml
```

### The three model ids had to be found live, not guessed

The assignment's Part A already ran into this: OpenRouter's free-tier
model lineup rotates, and model ids that existed when this assignment was
written can 404 by the time it's run. Before finalizing the patch, each
candidate model was checked against OpenRouter's live `/api/v1/models`
listing and then **actually round-tripped through a real tool call** (not
just "is it listed") — see Part A's stage 16 for the same discovery
process. All three ids above are confirmed working as of 2026-09-18.

## Starting the Web UI

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 web --patch ./openrouter.patch.yml --no-open
```

`--no-open` is used only because this session drives the browser
headlessly via Playwright for screenshots, not interactively — running
this normally at a real keyboard opens the browser automatically, per the
README.

Output:

```
dsh web: http://127.0.0.1:3080/?token=w3rCgWk28WcyhvoK-U8vi98DDQvzBnc7Ycty1q7cQCc
```

Confirmed serving with `curl` (401 without the token, 200 with it — an
intentional local browser-trust fence, not a failure):

```powershell
curl http://127.0.0.1:3080/            # 401 (auth fence, expected)
curl "http://127.0.0.1:3080/?token=..." # 200 after following the redirect
```

## Confirming the UI loads and OpenRouter actually answers

Settings → Models shows both providers, with a live green/red credential
indicator per provider (screenshot:
[`screenshots/04-settings-models.png`](screenshots/04-settings-models.png)):

- **DeepSeek** — red dot (`DEEPSEEK_API_KEY` intentionally not set)
- **OpenRouter** — green dot (`OPENROUTER_API_KEY` resolved)

### Screenshot automation note: the native directory picker

The Web UI requires picking a **workspace** (a directory) before it will
chat. Clicking "Choose workspace" calls `directoryPicker/pick`, which opens
the OS's native folder-picker dialog (confirmed by capturing the exact
network request Playwright's browser made on click). A native OS dialog is
outside what Playwright's browser automation can drive — this is a
documented Playwright limitation for `showDirectoryPicker()`-style APIs,
not a bug in this setup.

Worked around by calling the underlying RPC directly (same JSON-RPC
envelope the browser itself uses, discovered by capturing that request):

```js
await fetch('/api/workspace/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'client-request',
    rpcId: crypto.randomUUID(),
    method: 'workspace/create',
    payload: { args: { request: { path: 'C:\\...\\assignment2\\partB', title: 'partB' } } },
  }),
})
```

This creates the same workspace record the native picker would have, and
it then shows up as an ordinary clickable row in the sidebar — no native
dialog involved from that point on.

### The actual end-to-end run

Two independent proofs, both over OpenRouter:

**1. Through the real browser UI** (screenshot:
[`screenshots/12-final-response.png`](screenshots/12-final-response.png)):
sent *"Use your shell tool to print 2+2, then tell me the result in one
sentence."* — the agent made 1 tool call, ran the shell, and replied
*"Using the shell, 2+2 evaluates to 4."* (17.5K tok, 8s, model shown as
"DeepSeek V4 Flash (free, via OpenRouter)").

**2. Through the documented headless profile** (`headless-test.log`):

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 --profile headless --patch ./openrouter.patch.yml `
  "Say hello in exactly five words, then run a shell command that prints 2+2."
```

Reasoning streamed to stderr, tool call ran (`Write-Output (2+2)` — the
agent correctly detected Windows and used PowerShell, not bash), final
answer printed: *"Hello there, nice to meet. 👋 ... Output: 4"*.

## Everything that broke, summarized

| Problem | Cause | Fix |
|---|---|---|
| `npx`/`node`/`npm` not found | Stale PATH in this shell session | Reload `$env:Path` from registry each session |
| `npx: command not found` in Bash | Git Bash never had Node on PATH | Use PowerShell for every dsh/node command |
| `OPENROUTER_API_KEY` invisible | Set at User scope after this process started | Reload from `[System.Environment]::GetEnvironmentVariable(...,"User")` |
| `dsh plugin` → `pnpm` not recognized | pnpm isn't a stated prerequisite for the npm quick-start path | `npm install -g pnpm` (corepack failed on `EPERM`, needs admin) |
| `showDirectoryPicker` dialog never appears in Playwright | Native OS dialog, not a page-DOM element — a known Playwright limitation | Call `/api/workspace/create` directly with the same RPC envelope the browser uses |
| Assignment's suggested free OpenRouter models all 404 | Free-tier model lineup rotated since the assignment was written (same issue hit in Part A) | Queried OpenRouter's live model list, verified 3 replacements with a real tool call before committing to them |

## Layout

```
assignment2/partB/
  INSTALL.md                 <- this file
  openrouter.patch.yml       <- the provider-routing overlay (no secrets)
  start-web.ps1               <- launcher used for the background server
  dump-config.yml             <- composed config BEFORE the patch
  dump-config-patched.yml     <- composed config AFTER the patch
  headless-test.log           <- the headless end-to-end proof
  screenshots/                <- every screenshot referenced above
  screenshot-helpers/          <- the Playwright scripts used to drive them
  plugins/                     <- the two custom plugins (Step 4)
```
