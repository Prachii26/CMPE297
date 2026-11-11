"""The solver as data, and the code generator that turns it into solver.py.

A solver is an ordered list of components (handlers) plus a few flags. Every
edit any method makes is an edit to this state, and every state renders to a
complete, readable Python module -- so the guard always scans real source
text, never a summary of it, and every run can write its final solver to
disk for inspection.

Generated code is compiled with the filename "<solver:...>", which is how
task.boundary recognises it on the call stack.

The rendered module exposes:
  trace(question) -> (handler_name, sql)   used by the evaluator and probes
  solve(question) -> sql                   the public interface
"""
from __future__ import annotations

import hashlib
import textwrap
import types
from dataclasses import dataclass, field, replace

HEADER = '''"""solver.py -- natural language to SQL for the university database.

GENERATED from a SolverState by task/solver_state.py. Each RSI method edits
the state, never this text directly. Components run in dispatch order; the
first one that returns SQL wins.
"""
import re

from task.db import schema_info

SCHEMA = schema_info()
SUBJECTS = set(SCHEMA["subjects"])
CODE = r"([A-Za-z]{{2,5}}[ -]?\\d{{3}})\\b"
TERM = r"((?:[Ff]all|[Ss]pring) \\d{{4}})"

FLAGS = {flags}


def sql_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def count_expr(column):
    return f"COUNT(DISTINCT {{column}})" if FLAGS["COUNT_DISTINCT"] else "COUNT(*)"


def link_entities(q):
    """Rewrite user-style entity mentions to the stored canonical values."""
    for name in SCHEMA["departments"]:
        q = re.sub(re.escape(name), name, q, flags=re.I)
    for term in SCHEMA["terms"]:
        q = re.sub(re.escape(term), term, q, flags=re.I)

    def _code(m):
        subject = m.group(1).upper()
        return f"{{subject}} {{m.group(2)}}" if subject in SUBJECTS else m.group(0)

    q = re.sub(r"\\b([A-Za-z]{{2,5}})[ -]?(\\d{{3}})\\b", _code, q)
    return re.sub(r"\\b([a-z]{{2,5}})\\b",
                  lambda m: m.group(1).upper() if m.group(1).upper() in SUBJECTS
                  else m.group(0), q)


HANDLERS = []


def handler(name, priority=50):
    def register(fn):
        HANDLERS.append((name, priority, fn))
        return fn
    return register

'''

FOOTER = '''

def dispatch_order():
    if FLAGS["DISPATCH"] == "priority":
        return sorted(HANDLERS, key=lambda h: -h[1])     # stable: ties keep list order
    return HANDLERS


def trace(question):
    q = link_entities(question) if FLAGS["LINK_ENTITIES"] else question
    for name, _priority, fn in dispatch_order():
        sql = fn(q)
        if sql:
            return name, sql
    return "fallback", "SELECT NULL WHERE 0"


def solve(question):
    return trace(question)[1]


if __name__ == "__main__":
    import sys
    print(solve(" ".join(sys.argv[1:])))
'''

DEFAULT_FLAGS = {"DISPATCH": "list", "LINK_ENTITIES": False, "COUNT_DISTINCT": False}


@dataclass(frozen=True)
class Component:
    cid: str            # stable identity, e.g. "j1_courses_by_dept"
    body: str           # the function body, unindented
    priority: int = 50
    origin: str = "base"  # strategy id or "llm:<model>"

    def render(self) -> str:
        fn = "h_" + "".join(ch if ch.isalnum() else "_" for ch in self.cid)
        body = textwrap.indent(textwrap.dedent(self.body).strip("\n"), "    ")
        return f'@handler("{self.cid}", {self.priority})\ndef {fn}(q):\n{body}\n'


@dataclass(frozen=True)
class SolverState:
    components: tuple[Component, ...]
    flags: tuple[tuple[str, object], ...] = field(
        default_factory=lambda: tuple(sorted(DEFAULT_FLAGS.items())))
    # A whole-module rewrite (edit kind "replace_solver"). When set, it IS the
    # solver and the components above are ignored.
    override: str | None = None

    def flag(self, name: str):
        return dict(self.flags)[name]

    def has(self, cid: str) -> bool:
        return any(c.cid == cid for c in self.components)

    def cids(self) -> list[str]:
        return [c.cid for c in self.components]

    def with_flag(self, name: str, value) -> "SolverState":
        flags = dict(self.flags)
        flags[name] = value
        return replace(self, flags=tuple(sorted(flags.items())))

    def with_component(self, comp: Component, position: str) -> "SolverState":
        rest = tuple(c for c in self.components if c.cid != comp.cid)
        comps = (comp,) + rest if position == "prepend" else rest + (comp,)
        return replace(self, components=comps)

    def without(self, cid: str) -> "SolverState":
        return replace(self, components=tuple(c for c in self.components if c.cid != cid))

    def render(self) -> str:
        if self.override is not None:
            return self.override
        flags = "{" + ", ".join(f"{k!r}: {v!r}" for k, v in self.flags) + "}"
        parts = [HEADER.format(flags=flags)]
        parts += ["\n" + c.render() for c in self.components]
        parts.append(FOOTER)
        return "".join(parts)

    def key(self) -> str:
        """Content hash: two states that render identically share a key."""
        return hashlib.sha256(self.render().encode()).hexdigest()[:16]


def load(source: str, tag: str = "candidate") -> types.SimpleNamespace:
    """Compile generated solver source into a callable solver object."""
    code = compile(source, f"<solver:{tag}>", "exec")
    ns: dict = {"__name__": "rsi_solver"}
    exec(code, ns)
    return types.SimpleNamespace(solve=ns["solve"], trace=ns["trace"], source=source)


def load_state(state: SolverState, tag: str = "candidate") -> types.SimpleNamespace:
    return load(state.render(), tag)
