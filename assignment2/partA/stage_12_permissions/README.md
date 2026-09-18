# Stage 12 — Permissions

**The idea:** rate every shell command allow / ask / deny before it runs.
Compound commands get split on `&&` and `|`, each piece is rated on its
own, and the strictest verdict among the pieces wins the whole command.

## Run it

```powershell
.venv\Scripts\python.exe stage_12_permissions\main.py
```

Ask it to run `ls` (runs immediately), `rm somefile.txt` (you get a y/N
prompt in the terminal), or `rm -rf /` (refused outright, no prompt).

## The code

`permissions.py` is a rule table checked top to bottom, first match wins:

```python
RULES = [
    (re.compile(r"^\s*rm\s+-rf\b"), "deny"),
    (re.compile(r"^\s*rm\b"), "ask"),
    (re.compile(r"^\s*git\s+push\b"), "ask"),
    (re.compile(r"^\s*curl\b"), "ask"),
    (re.compile(r"^\s*wget\b"), "ask"),
    (re.compile(r"^\s*(ls|cat|pwd|echo|git|grep|find|head|tail|dir|type)\b"), "allow"),
]
DEFAULT_VERDICT = "ask"
```

Order matters: `git push origin main` matches the specific `git push`
rule (ask) before it ever reaches the general `git` rule (allow), because
`classify_one` returns on the **first** match. `git status` falls through
every specific rule and lands on the general one, so it's `allow`.

### Compound commands: strictest wins

```python
def split_compound(command: str):
    parts = re.split(r"&&|\|", command)
    return [p.strip() for p in parts if p.strip()]

def classify(command: str):
    parts = split_compound(command)
    graded = [(part, classify_one(part)) for part in parts]
    overall = max((verdict for _, verdict in graded), key=lambda v: VERDICT_RANK[v])
    return overall, graded
```

`"ls && rm -rf /"` splits into `["ls", "rm -rf /"]`, rated `["allow",
"deny"]`. The overall verdict is `deny` — the harmless first half doesn't
buy the dangerous second half a pass.

### The verdict is a tool result, never an exception

```python
def bash(command: str) -> str:
    verdict, parts = classify(command)
    if verdict == "deny":
        return f"refused: denied by permission rules (...)."
    if verdict == "ask":
        if not ask_user(command):
            return "refused: user declined to run this command."
    result = subprocess.run(command, shell=True, ...)
    ...
```

A refusal — whether from a hard deny or a declined ask — comes back as an
ordinary string, exactly like every other tool result in this codebase
since stage 05. The model sees *why* its command didn't run and can
propose something else instead of the program crashing or hanging.

`ask_user` is its own function specifically so it can be swapped out —
tests replace it with a canned yes/no instead of blocking on real stdin.

## Honesty note

This is **not real security**, and pretending otherwise would be
dishonest. `classify()` only looks at command *text*:

- It doesn't understand shell quoting, so `echo "rm -rf /"` is a string
  literal that never runs `rm`, but a cleverly-quoted real `rm -rf /`
  could slip past a naive pattern just as easily.
- It doesn't resolve aliases, functions, or wrapper scripts — a shell
  alias named `ls` that secretly does something destructive would be
  rated `allow`.
- The `&&`/`|` split is purely textual. A `|` or `&&` inside a quoted
  string still gets split, which can misclassify an otherwise-safe single
  command as multiple pieces (or vice versa, hide a dangerous piece
  inside what looks like one harmless string).
- Nothing here stops the process from doing anything the OS lets it do.
  This is a speed bump for an honest, well-behaved model — not a sandbox.

Stage 13 adds the thing that actually enforces a boundary: OS-level
sandboxing, where the operating system — not a regex — decides what a
process can touch.

## Diff

```powershell
git diff --no-index stage_11_todos stage_12_permissions
```
