"""Our own parser for an OpenUI-Lang-style line-oriented UI language.

    root = Column([title, metrics, chart])
    title = Text("Study rooms", "h1")
    metrics = Row([m0, m1, m2])
    m0 = MetricCard("Rooms free now", "3 / 6")

Grammar (one statement per line):
    statement := IDENT "=" value
    value     := Component "(" [value ("," value)*] ")"
               | "[" [value ("," value)*] "]" | "{" [key ":" value ...] "}"
               | STRING | NUMBER | true | false | null | IDENT (a reference)

Arguments are POSITIONAL; the catalog says which prop each position is.
That is most of why the language is compact: no prop names, no quotes on
keys, no braces around every node.

Forward references are allowed: `root` may list `chart` before `chart` is
defined. Resolution is lazy, so a renderer can draw what is defined and show
placeholders for what is not yet -- which is what makes it streaming-first:
feed it text as it arrives and it re-resolves after every complete line.

The catalog is theme 03's (A2UI-flavoured component names and props).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# theme 03's catalog, with the positional order of each component's props
CATALOG = {
    "Column": ["children"],
    "Row": ["children"],
    "Text": ["text", "usageHint"],
    "MetricCard": ["label", "value"],
    "RoomTable": ["rows"],
    "OccupancyChart": ["series"],
    "BookingForm": ["rooms", "slots"],
    "Button": ["label", "action"],
}
HTML_ARTIFACT = {"HtmlArtifact": ["html", "title"]}
MODE_CATALOG = {"static": {}, "declarative": CATALOG,
                "open_ended": dict(HTML_ARTIFACT), "mixed": {**CATALOG, **HTML_ARTIFACT}}

TOKEN = re.compile(r'\s*(?:(?P<str>"(?:[^"\\]|\\.)*")|(?P<num>-?\d+(?:\.\d+)?)'
                   r'|(?P<ident>[A-Za-z_][A-Za-z0-9_]*)|(?P<punct>[=(),\[\]{}:]))')


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    name: str


@dataclass
class Node:
    component: str
    args: list


@dataclass
class Program:
    statements: dict[str, object] = field(default_factory=dict)   # name -> value
    errors: list[str] = field(default_factory=list)
    order: list[str] = field(default_factory=list)


def _tokens(line: str):
    pos, out = 0, []
    while pos < len(line):
        if line[pos:].strip() == "":
            break
        m = TOKEN.match(line, pos)
        if not m:
            raise ParseError(f"unexpected character {line[pos]!r} at column {pos + 1}")
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if tok[0] is None or (value is not None and tok[1] != value):
            raise ParseError(f"expected {value or 'a value'}, got {tok[1]!r}")
        self.i += 1
        return tok

    def value(self):
        kind, text = self.take()
        if kind == "str":
            return bytes(text[1:-1], "utf-8").decode("unicode_escape")
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "punct" and text == "[":
            return self._seq("]")
        if kind == "punct" and text == "{":
            out = {}
            while self.peek()[1] != "}":
                key = self.take()[1].strip('"')
                self.take(":")
                out[key] = self.value()
                if self.peek()[1] == ",":
                    self.take(",")
            self.take("}")
            return out
        if kind == "ident":
            if text in ("true", "false"):
                return text == "true"
            if text == "null":
                return None
            if self.peek()[1] == "(":
                self.take("(")
                return Node(text, self._seq(")"))
            return Ref(text)
        raise ParseError(f"unexpected {text!r}")

    def _seq(self, close):
        items = []
        while self.peek()[1] != close:
            items.append(self.value())
            if self.peek()[1] == ",":
                self.take(",")
            elif self.peek()[1] != close:
                raise ParseError(f"expected ',' or {close!r}, got {self.peek()[1]!r}")
        self.take(close)
        return items


def parse_line(line: str):
    toks = _tokens(line)
    if not toks:
        return None
    p = _Parser(toks)
    kind, name = p.take()
    if kind != "ident":
        raise ParseError(f"a statement starts with an identifier, got {name!r}")
    p.take("=")
    value = p.value()
    if p.i != len(toks):
        raise ParseError(f"trailing input {toks[p.i][1]!r}")
    return name, value


def parse(text: str, complete: bool = True) -> Program:
    """Parse every complete line. If complete=False (streaming), the text
    after the last newline is an unfinished line and is left alone."""
    prog = Program()
    lines = text.split("\n")
    if not complete:
        lines = lines[:-1]
    for n, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            stmt = parse_line(line)
        except ParseError as exc:
            prog.errors.append(f"line {n}: {exc}")
            continue
        if stmt:
            prog.statements[stmt[0]] = stmt[1]
            prog.order.append(stmt[0])
    return prog


def validate(prog: Program, catalog: dict) -> list[str]:
    errors = list(prog.errors)

    def walk(v, where):
        if isinstance(v, Node):
            if v.component not in catalog:
                errors.append(f"{where}: component '{v.component}' is not in the catalog")
                return
            if len(v.args) > len(catalog[v.component]):
                errors.append(f"{where}: {v.component} takes {len(catalog[v.component])} args, got {len(v.args)}")
            for a in v.args:
                walk(a, where)
        elif isinstance(v, list):
            for x in v:
                walk(x, where)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x, where)
        elif isinstance(v, Ref) and v.name not in prog.statements:
            errors.append(f"{where}: reference '{v.name}' is never defined")

    for name, v in prog.statements.items():
        walk(v, name)
    return errors


def to_components(prog: Program, catalog: dict) -> dict:
    """Resolve to theme 03's component shape: {id: {Type: {prop: value}}}.
    Unresolved references stay as {"$ref": name} so a renderer can show a
    placeholder (that is the streaming case)."""
    def res(v):
        if isinstance(v, Ref):
            target = prog.statements.get(v.name)
            if isinstance(target, Node):
                return {"$ref": v.name}
            return res(target) if v.name in prog.statements else {"$ref": v.name}
        if isinstance(v, list):
            return [res(x) for x in v]
        if isinstance(v, dict):
            return {k: res(x) for k, x in v.items()}
        if isinstance(v, Node):
            return {"$inline": {v.component: dict(zip(catalog.get(v.component, []), map(res, v.args)))}}
        return v
    out = {}
    for name, v in prog.statements.items():
        if isinstance(v, Node):
            names = catalog.get(v.component, [f"arg{i}" for i in range(len(v.args))])
            out[name] = {v.component: dict(zip(names, (res(a) for a in v.args)))}
    return out
