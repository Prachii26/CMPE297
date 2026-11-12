// Theme 04 page: an OpenUI-Lang-style parser and renderer in the browser.
// Same grammar as lang.py. Streaming-first: after every complete line the
// program is re-resolved; references to names not yet defined render as
// placeholders and fill in when their line arrives.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
let CFG, MODE, CAT;

function h(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
}

// ------------------------------------------------------------- the parser
const TOK = /\s*(?:("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|([=(),\[\]{}:]))/y;
function tokens(line) {
  const out = []; TOK.lastIndex = 0;
  while (TOK.lastIndex < line.length && line.slice(TOK.lastIndex).trim()) {
    const at = TOK.lastIndex, m = TOK.exec(line);
    if (!m) throw new Error(`unexpected character at column ${at + 1}`);
    out.push(m[1] ? ["str", m[1]] : m[2] ? ["num", m[2]] : m[3] ? ["ident", m[3]] : ["punct", m[4]]);
  }
  return out;
}
function parseLine(line) {
  const t = tokens(line); let i = 0;
  if (!t.length) return null;
  const peek = () => (t[i] || [null, null])[1];
  const take = (v) => { const tok = t[i++]; if (!tok || (v && tok[1] !== v)) throw new Error(`expected ${v || "value"}`); return tok; };
  const seq = (close) => { const a = []; while (peek() !== close) { a.push(value()); if (peek() === ",") take(","); } take(close); return a; };
  const value = () => {
    const [kind, text] = take();
    if (kind === "str") return JSON.parse(text);
    if (kind === "num") return Number(text);
    if (text === "[") return seq("]");
    if (text === "{") { const o = {}; while (peek() !== "}") { const k = take()[1].replace(/"/g, ""); take(":"); o[k] = value(); if (peek() === ",") take(","); } take("}"); return o; }
    if (kind === "ident") {
      if (text === "true" || text === "false") return text === "true";
      if (text === "null") return null;
      if (peek() === "(") { take("("); return { $node: text, args: seq(")") }; }
      return { $ref: text };
    }
    throw new Error(`unexpected ${text}`);
  };
  const [k, name] = take(); if (k !== "ident") throw new Error("statement must start with a name");
  take("="); const v = value(); if (i !== t.length) throw new Error("trailing input");
  return [name, v];
}
function parse(text) {        // only complete lines: the tail after the last \n is still arriving
  const stmts = {}, errors = [];
  for (const line of text.split("\n").slice(0, -1)) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    try { const s = parseLine(line); if (s) stmts[s[0]] = s[1]; } catch (e) { errors.push(e.message); }
  }
  return { stmts, errors };
}

// ------------------------------------------------------------- resolution
function resolve(v, stmts) {
  if (v && v.$ref !== undefined) {
    if (!(v.$ref in stmts)) return { $pending: v.$ref };
    return resolve(stmts[v.$ref], stmts);
  }
  if (Array.isArray(v)) return v.map((x) => resolve(x, stmts));
  if (v && v.$node) return v;
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolve(x, stmts)]));
  return v;
}
const pending = (v) => v && v.$pending !== undefined;

// ------------------------------------------------------------- renderer (theme 03's catalog)
const R = {
  Column: (p, kids) => h("div", { class: "stack column" }, kids),
  Row: (p, kids) => h("div", { class: "stack row" }, kids),
  Text: (p) => h("div", { class: p.usageHint || "body" }, p.text),
  MetricCard: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {}, h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    p.rows.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  OccupancyChart: (p) => h("div", { class: "chart" }, p.series.map((o) => h("div", { class: "b", style: `height:${o.pct}%` }, h("span", {}, `${o.hour}h`)))),
  BookingForm: (p) => h("form", { class: "booking", onsubmit: (e) => e.preventDefault() },
    h("select", {}, p.rooms.map((r) => h("option", {}, r))), h("select", {}, p.slots.map((s) => h("option", {}, s)))),
  Button: (p) => h("button", {}, p.label),
  HtmlArtifact: (p) => h("div", {}, h("div", { class: "sandbox-label" }, `⚠ HtmlArtifact · sandbox="${CFG.sandbox}" · CSP injected by the server`), mountSandbox(p.html, MODE === "open_ended" ? 330 : 200)),
};

function drawName(name, stmts, seen = new Set()) {
  if (!(name in stmts)) return h("div", { class: "ph" }, `${name} · referenced, not defined yet`);
  if (seen.has(name)) return h("div", { class: "reject" }, `cycle at ${name}`);
  const node = stmts[name];
  if (!node || !node.$node) return h("div", { class: "ph" }, `${name} is a value, not a component`);
  const params = CAT[node.$node];
  if (!params) return h("div", { class: "reject" }, `rejected: ${node.$node} is not in the catalog`);
  const props = {}; params.forEach((p, i) => (props[p] = node.args[i]));
  if (props.children) {
    const kids = props.children.map((c) => (c && c.$ref ? drawName(c.$ref, stmts, new Set([...seen, name])) : h("div", { class: "ph" }, "?")));
    return R[node.$node]({}, kids);
  }
  const resolved = Object.fromEntries(Object.entries(props).map(([k, v]) => [k, resolve(v, stmts)]));
  const missing = Object.entries(resolved).filter(([, v]) => pending(v) || (Array.isArray(v) && v.some(pending)));
  if (missing.length) return h("div", { class: "ph" }, `${name}: ${node.$node} waiting for ${missing.map(([, v]) => v.$pending || "values").join(", ")}`);
  return R[node.$node](resolved, []);
}

// Static mode: the CLIENT owns this layout program. The agent only defines the values it names.
const STATIC_LAYOUT = `root = Column([note, metrics, chart, table])
note = Text("Client-owned layout program - the agent streamed values only", "h2")
metrics = Row([m0, m1, m2])
m0 = MetricCard(free_label, free_value)
m1 = MetricCard(peak_label, peak_value)
m2 = MetricCard(today_label, today_value)
chart = OccupancyChart(occupancy)
table = RoomTable(rooms)
`;

const FRAMES = new Map();
function mountSandbox(html, height) {
  if (FRAMES.has(html)) return FRAMES.get(html);        // keep the frame across re-renders
  const f = h("iframe", { class: "sandbox", sandbox: CFG.sandbox, referrerpolicy: "no-referrer", style: `height:${height}px` });
  f.srcdoc = html; FRAMES.set(html, f); return f;
}

function render(text) {
  const prefix = MODE === "static" ? STATIC_LAYOUT : "";
  const { stmts, errors } = parse(prefix + text);
  const defined = Object.keys(stmts);
  const refs = new Set(); JSON.stringify(stmts, (k, v) => { if (v && v.$ref) refs.add(v.$ref); return v; });
  const waiting = [...refs].filter((r) => !(r in stmts));
  $("state").textContent = `defined (${defined.length}): ${defined.join(", ")}\n\nforward references still open (${waiting.length}): ${waiting.join(", ") || "none"}` +
    (errors.length ? `\n\nparse errors: ${errors.join("; ")}` : "");
  $("surface").replaceChildren(drawName("root", stmts));
}

async function start() {
  CFG = await (await fetch("/config")).json();
  MODE = qs.get("mode") || CFG.default_mode;
  CAT = { ...CFG.catalog.declarative, ...CFG.catalog.mixed };
  $("modes").replaceChildren(...CFG.modes.map((m) => h("a", { href: `?mode=${m}`, class: m === MODE ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Rendered surface · ${MODE}`;
  const allowed = CFG.catalog[MODE];
  $("adv").replaceChildren(...(Object.keys(allowed).length ? Object.entries(allowed).map(([n, a]) => h("span", {}, `${n}(${a.join(", ")})`))
                                                           : [h("span", {}, "(none for the agent: values only)")]));
  const resp = await fetch(`/stream?mode=${MODE}&delay=${qs.get("delay") || 0.03}`);
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let text = "";
  let lines = 0;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    text += dec.decode(value, { stream: true });
    $("log").textContent = text.length > 4000 ? text.slice(0, 1800) + "\n…\n" + text.slice(-1800) : text;
    const complete = text.split("\n").length - 1;
    if (complete !== lines) { lines = complete; render(text); $("counts").replaceChildren(h("span", {}, `${lines} lines`), h("span", {}, `${text.length} chars`)); }
  }
  render(text.endsWith("\n") ? text : text + "\n");
  document.body.dataset.done = MODE;
}
start();
