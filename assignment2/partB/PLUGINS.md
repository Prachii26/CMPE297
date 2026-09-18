# Community Plugins — Step 3

Six plugins installed from [`awesome-dsh-plugin`](https://github.com/awesome-dsh-plugin/awesome-dsh-plugin), one per
category (UI, theming, tools, workflow, memory, security), each verified
against `@deepseek-ai/dsh@0.1.5-rc.2`. Verification means: installed via
`dsh plugin add`, the server restarted, and the plugin confirmed
**Enabled** with no load errors on the Settings → Plugins → Plugin list
page (screenshot:
[`screenshots/16-all-plugins-final.png`](screenshots/16-all-plugins-final.png)).

## Install command used for all six

```powershell
npx --yes @deepseek-ai/dsh@0.1.5-rc.2 plugin --profile web add `
  dsh-composer-expand dsh-cool-theme dsh-engineer-tools dsh-init dsh-instruction-memory dsh-write-protect
```

(`dsh-engineer-tools` was actually added separately after two other picks
turned out to be broken — see **Dropped plugins** below.)

---

## 1. dsh-composer-expand — UI Enhancements

**What it does:** adds a ⬆/⬇ button to the composer's tool row that
toggles the input between the default capped height and a tall 70vh
writing view, for long drafts.

**Why picked:** the simplest possible proof that a third-party plugin can
touch the chat UI itself — one visible button, zero configuration, zero
external dependency. Good first plugin to point at on camera because the
effect is immediate and visual.

**Install:** `dsh plugin --profile web add dsh-composer-expand`

**Demo:** open a session, point at the "⬆ Expand" control next to the
composer (visible in
[`screenshots/12-final-response.png`](screenshots/12-final-response.png)
and every later chat screenshot), click it, show the input grow.

---

## 2. dsh-cool-theme — Themes & Appearance

**What it does:** a theme plugin with 34 built-in palettes (Nord, One
Dark, GitHub, etc.), full light/dark support, added as its own **Theme**
entry in Settings.

**Why picked:** themes are the most common category in the catalog by a
wide margin; this one is popular, has no fandom-skin baggage (some
alternatives reskin the whole app with anime characters or wallpapers,
which is fun but harder to show cleanly on an academic video), and adds a
real, inspectable settings surface (`Settings → Theme`) rather than just a
CSS file.

**Install:** `dsh plugin --profile web add dsh-cool-theme`

**Demo:** Settings → Theme, pick a palette from the 34 options, show the
whole UI recolor live.

---

## 3. dsh-engineer-tools — Tools & Capabilities

**What it does:** registers two model-facing tools — a scoped `git`
runner and a package-manager runner (`dev`) that auto-detects
npm/pnpm/yarn/bun from the workspace lockfile — both dispatched through
dsh's own sandboxed shell, returning structured `stdout`/`stderr`/`exitCode`
instead of raw bash text.

**Why picked:** this is the *second* attempt at the "Tools" slot — see
**Dropped plugins**. It fits the category cleanly (a genuinely new
model-facing capability, not a UI or policy change) and is simple enough
to demo without a database, cloud account, or API key: ask the agent to
check `git status` in the workspace and it uses the new tool instead of a
raw shell command.

**Install:** `dsh plugin --profile web add dsh-engineer-tools`

**Demo:** ask the agent *"what's the git status of this workspace?"* and
show the tool call card naming the `git` tool (not `bash`/`pwsh`), with
structured exit-code output.

---

## 4. dsh-init — Workflow & Automation

**What it does:** a Claude-Code-style `/init` command and tool that
writes a minimal `CLAUDE.md` and symlinks `AGENTS.md` to it — bootstrapping
a project's standing instructions file.

**Why picked:** genuinely a workflow/automation plugin (it changes *what
happens once*, not an ongoing policy or a UI surface), trivial to verify
(a file either appears or it doesn't), and directly relevant to a course
about harness engineering — Part A's own `AGENTS.md` research showed how
central that file is to a real harness.

**Install:** `dsh plugin --profile web add dsh-init`

**Demo:** run `/init` in a session, show `CLAUDE.md` created in the
workspace and `AGENTS.md` symlinked to it.

---

## 5. dsh-instruction-memory — Memory

**What it does:** long-term instructions maintained **only** by the user
in the Settings UI (the model has no write access), auto-injected into
every conversation's system prompt.

**Why picked:** the "Memory" category on the catalog has hundreds of
entries, most of them elaborate (vector search, knowledge graphs, SQLite
FTS5, cross-agent daemons). This one is deliberately the simplest: no
database, no embeddings, no model-writable state — a clean contrast to
show what "memory" means at its most basic, and it composes well with
`session-cost-panel` and `leakage-guard` (Step 4) without touching either.

**Install:** `dsh plugin --profile web add dsh-instruction-memory`

**Demo:** Settings → 指令记忆 (its sidebar label ships in Chinese only —
noted below), add a standing instruction ("always answer in one
sentence"), start a new session, show the model actually follows it
without being told again.

**Note:** its Settings sidebar entry is labeled in Chinese
(`指令记忆`) even though the rest of this deployment's UI is English —
a minor i18n gap in the plugin itself, not a functional problem. Called
out here rather than smoothed over.

---

## 6. dsh-write-protect — Security & Permissions

**What it does:** protects declared workspace subpaths (e.g. `.git`) from
writes, and can grant extra writable roots under `workspace-write` mode.
Registers as two entries: `write-protect` (policy) and `write-protect/fs`
(the filesystem hook).

**Why picked:** pairs thematically with this assignment's own
`leakage-guard` custom plugin (Step 4) — both are "inspect before letting
a write/execute happen" policy plugins — and demonstrates the same
`tools/pre-execute`-family hook point a community author reached for
independently, which is useful to point out on camera.

**Install:** `dsh plugin --profile web add dsh-write-protect`

**Demo:** ask the agent to modify a file under `.git/`, show the write
gets refused with a clear reason instead of silently succeeding.

---

## Dropped plugins (and why)

Two plugins were installed, found broken, and removed — exactly the
"don't leave a broken plugin in and call it installed" case the
assignment calls out.

### dsh-receipts (was going to be the "Tools" pick)

**What it claimed to do:** mine local session logs into Markdown/HTML
usage reports.

**What actually happened:** installing it broke the **entire** plugin
tree, not just itself:

```
Error: failed to import loader entry tools (@deepseek-ai/dsh-tools):
  The requested module '@deepseek-ai/dsh-llm' does not provide an export named 'CallId'
Error: failed to import loader entry receipts (dsh-receipts/lib/index.js):
  The requested module '@deepseek-ai/dsh-llm' does not provide an export named 'CallId'
```

The web server failed to boot at all — every session, every other
plugin, everything. `dsh-receipts` pulled in a version of
`@deepseek-ai/dsh-llm` (or a peer that resolves differently) that no
longer exports `CallId`, and pnpm's hoisting let that mismatched copy
shadow the one `@deepseek-ai/dsh-tools` itself needs.

**Fix:** `dsh plugin --profile web remove dsh-receipts`, confirmed the
server boots clean again, then picked a different candidate.

### dsh-a11y-scan (first replacement attempt)

**What it claimed to do:** run `axe-core` over local HTML for WCAG
violations.

**What actually happened:** the **identical** failure, verbatim
(`CallId` not exported by `dsh-llm`), for the identical reason. This
plugin is by the same author as `dsh-receipts` (`988hj7tczd-oss`) — strong
evidence their whole batch of plugins was built against an
incompatible/older `@deepseek-ai/dsh-llm` release and never republished
against this `dsh` version.

**Fix:** removed it, and deliberately picked the next candidate
(`dsh-engineer-tools`) from a **different author** to avoid the same
dependency chain. That one installed clean, and the server booted
successfully on the first try — see
[`screenshots/16-all-plugins-final.png`](screenshots/16-all-plugins-final.png).

**Lesson for the write-up:** "actively maintained" isn't verifiable from
the catalog description alone. Actually installing and restarting is the
only real test — a plugin can look simple and safe on paper and still take
the whole deployment down.

## One cosmetic warning, checked and dismissed

`pnpm peers check` in the profile directory reports `dsh-write-protect`
wanting `@deepseek-ai/dsh-fs`, `dsh-sandbox`, `dsh-settings`, etc. at
`^0.1.2-rc.1` as declared peers. This is a **static** semver check against
the plugin's own `package.json` — it does not reflect what actually
happened at runtime. The server booted clean and `dsh-write-protect` (both
`write-protect` and `write-protect/fs` rows) shows **Enabled** with zero
load errors in the Plugin list — the functional test that actually
matters. Recorded here rather than silently ignored, per the same
"verify, don't assume" rule the two dropped plugins above needed.
