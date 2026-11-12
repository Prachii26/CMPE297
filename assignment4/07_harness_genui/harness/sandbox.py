"""Stage 13: sandbox.

Stage 12's permission table only inspects command TEXT -- it's a speed
bump, not a boundary. This stage adds actual OS-level enforcement where
the platform provides a primitive for it:

- macOS: wrap the command with `sandbox-exec` (Seatbelt) and a profile
  that denies writes outside the current working directory.
- Linux: wrap the command with `bwrap` (bubblewrap), read-only bind
  mounting the root filesystem and only allowing writes under the cwd.
- Windows: there is no equivalent available to an ordinary unprivileged
  process. AppContainer profiles need a signed manifest and admin setup;
  WSL or a Hyper-V container is a different environment, not a wrapper
  around this process. Rather than fake enforcement we can't actually
  provide, the banner prints "sandbox: none" and says why, and commands
  run exactly as they did in stage 12 -- rated by the permission table,
  not confined by the OS.

Independent of any of that, every command gets a timeout, and a timeout
comes back as a normal tool result string, never an uncaught
subprocess.TimeoutExpired.
"""
import os
import platform
import shutil
import subprocess

SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"


def sandbox_status() -> str:
    if SYSTEM == "Darwin":
        return "seatbelt" if shutil.which("sandbox-exec") else "none (sandbox-exec not found)"
    if SYSTEM == "Linux":
        return "bubblewrap" if shutil.which("bwrap") else "none (bwrap not found)"
    return "none (no OS-level sandbox primitive on Windows)"


def wrap_command(command: str):
    """Returns (argv_or_string, use_shell) ready for subprocess.run."""
    status = sandbox_status()

    if status == "seatbelt":
        profile = (
            "(version 1)(deny default)(allow process-fork)(allow file-read*)"
            f'(allow file-write* (subpath "{os.getcwd()}"))(allow network*)'
        )
        return ["sandbox-exec", "-p", profile, "/bin/sh", "-c", command], False

    if status == "bubblewrap":
        cwd = os.getcwd()
        return (
            [
                "bwrap",
                "--ro-bind", "/", "/",
                "--dev", "/dev",
                "--proc", "/proc",
                "--tmpfs", "/tmp",
                "--bind", cwd, cwd,
                "--chdir", cwd,
                "--",
                "/bin/sh", "-c", command,
            ],
            False,
        )

    # "none" -- run directly, same as every earlier stage.
    return command, True


def run_sandboxed(command: str, timeout: int = 30) -> str:
    argv, use_shell = wrap_command(command)
    try:
        result = subprocess.run(argv, shell=use_shell, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout}s"
    output = result.stdout
    if result.stderr:
        output += result.stderr
    return output.strip() or "(no output)"
