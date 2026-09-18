# Stage 13 — Sandbox

**The idea:** stage 12's permission table only inspects command text —
it's a speed bump for an honest model, not a boundary. This stage adds
actual OS-level enforcement, where the OS gives us a primitive to enforce
it with. Where it doesn't (Windows), the banner says so honestly instead
of pretending.

## Run it

```powershell
.venv\Scripts\python.exe stage_13_sandbox\main.py
```

On this machine, the banner will print `sandbox: none (no OS-level
sandbox primitive on Windows)`.

## The code

`sandbox.py` picks a strategy from `platform.system()`:

```python
def sandbox_status() -> str:
    if SYSTEM == "Darwin":
        return "seatbelt" if shutil.which("sandbox-exec") else "none (sandbox-exec not found)"
    if SYSTEM == "Linux":
        return "bubblewrap" if shutil.which("bwrap") else "none (bwrap not found)"
    return "none (no OS-level sandbox primitive on Windows)"
```

On **macOS**, commands get wrapped with `sandbox-exec` and a Seatbelt
profile that denies everything by default except reads, forks, network,
and writes under the current directory:

```python
profile = (
    "(version 1)(deny default)(allow process-fork)(allow file-read*)"
    f'(allow file-write* (subpath "{os.getcwd()}"))(allow network*)'
)
return ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command], False
```

On **Linux**, commands get wrapped with `bwrap` (bubblewrap): the root
filesystem is bind-mounted read-only, `/tmp` is a fresh tmpfs, and only
the current directory is writable:

```python
return ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
        "--tmpfs", "/tmp", "--bind", cwd, cwd, "--chdir", cwd,
        "--", "/bin/sh", "-c", command], False
```

On **Windows** — this machine — there is no equivalent an ordinary
process can apply to itself. AppContainer profiles need a signed manifest
and admin setup; WSL or a Hyper-V container is a different environment
entirely, not a wrapper around this process. `wrap_command` falls through
to running the command directly, exactly as every earlier stage did:

```python
# "none" -- run directly, same as every earlier stage.
return command, True
```

**Honesty over faking it:** it would be easy to print `sandbox: enabled`
here and let the user believe something is enforcing a boundary that
isn't. The banner prints the true status, and this README says outright
that unprivileged Windows has no equivalent primitive available — a
limitation, stated, not hidden.

### Every command gets a timeout, sandboxed or not

```python
def run_sandboxed(command: str, timeout: int = 30) -> str:
    argv, use_shell = wrap_command(command)
    try:
        result = subprocess.run(argv, shell=use_shell, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    ...
```

A hung command is a common failure mode once a model starts running its
own shell commands unattended. `subprocess.run`'s `timeout=` kills it, and
the `except` turns that into an ordinary tool-result string — same "errors
are results" rule as every tool since stage 05 — instead of an unhandled
exception that would take the whole loop down with it.

### tools.py's bash() barely changed

```python
from sandbox import run_sandboxed
...
def bash(command: str) -> str:
    verdict, parts = classify(command)
    if verdict == "deny": ...
    if verdict == "ask": ...
    return run_sandboxed(command, timeout=30)
```

The permission check from stage 12 runs exactly as before; only the final
`subprocess.run(...)` call was replaced with `run_sandboxed(...)`. Stage
12's rule table and this stage's OS enforcement are two independent
layers stacked in front of the same call.

## Diff

```powershell
git diff --no-index stage_12_permissions stage_13_sandbox
```
