// Theme 02 page: a hand-written AG-UI client. One transport, four modes.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
let CFG, MODE, STATE = {}, MESSAGES = [];
const THREAD = "thread_" + Math.random().toString(16).slice(2, 10);

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

// ------------------------------------------------------------ catalog
const COMPONENTS = {
  Stack: (p, kids) => h("div", { class: `stack ${p.direction || "column"}` }, kids),
  Heading: (p) => h("h3", { class: "heading" }, p.text),
  Text: (p) => h("div", { class: "toast" }, p.text),
  MetricCard: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {},
    h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    (p.rooms || []).map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building || ""), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  OccupancyChart: (p) => h("div", { class: "chart" }, (p.series || []).map((o) =>
    h("div", { class: "b", style: `height:${o.pct}%` }, h("span", {}, `${o.hour}h`)))),
  BookingForm: (p) => h("form", { class: "booking", onsubmit: (e) => e.preventDefault() },
    h("select", { id: "room" }, (p.rooms || []).map((r) => h("option", {}, r))),
    h("select", { id: "slot" }, (p.slots || []).map((s) => h("option", {}, s)))),
  Button: (p) => h("button", { id: "act", onclick: () => requestBooking($("room").value, $("slot").value) }, p.label),
  SandboxedHtml: (p) => h("div", {}, h("div", { class: "sandbox-label" },
    `⚠ open-ended region · sandbox="${CFG.sandbox}" · CSP injected by the server`), mountSandbox(p.html, 200)),
};

function renderFlat(spec) {
  const draw = (id) => {
    const el = spec.elements[id];
    if (!el) return h("div", { class: "slot" }, `${id}…`);
    const fn = COMPONENTS[el.type];
    if (!fn) return h("div", { class: "reject" }, `rejected: ${el.type} is not in the catalog`);
    return fn(el.props, (el.children || []).map(draw));
  };
  return draw(spec.root);
}

// ------------------------------------------------------------ sandbox
const FRAMES = new Set();
function mountSandbox(html, height) {
  const f = h("iframe", { class: "sandbox", sandbox: CFG.sandbox, referrerpolicy: "no-referrer", style: `height:${height}px` });
  f.srcdoc = html; FRAMES.add(f); return f;
}
window.addEventListener("message", (e) => {
  const ok = [...FRAMES].some((f) => f.contentWindow === e.source);
  if (ok && e.data && e.data.type === "book" && typeof e.data.room === "string") requestBooking(e.data.room, e.data.slot);
});

// ------------------------------------------------------------ JSON Patch
function applyPatch(doc, ops) {
  doc = structuredClone(doc);
  for (const op of ops) {
    const parts = op.path.split("/").slice(1).map((p) => p.replace(/~1/g, "/").replace(/~0/g, "~"));
    if (!parts.length) { doc = structuredClone(op.value); continue; }
    let parent = doc;
    for (const p of parts.slice(0, -1)) parent = parent[p];
    const last = parts[parts.length - 1];
    if (Array.isArray(parent)) {
      const i = last === "-" ? parent.length : Number(last);
      if (op.op === "add") parent.splice(i, 0, structuredClone(op.value));
      else if (op.op === "replace") parent[i] = structuredClone(op.value);
      else if (op.op === "remove") parent.splice(i, 1);
    } else if (op.op === "remove") delete parent[last];
    else parent[last] = structuredClone(op.value);
  }
  return doc;
}

// ------------------------------------------------------------ the client
const COUNTS = {}, TOOL_ARGS = {}, TOOL_NAMES = {};
function logEvent(ev) {
  COUNTS[ev.type] = (COUNTS[ev.type] || 0) + 1;
  $("counts").replaceChildren(...Object.entries(COUNTS).map(([t, n]) => h("span", {}, `${t} ×${n}`)));
  const detail = ev.delta !== undefined ? JSON.stringify(ev.delta).slice(0, 70) : (ev.toolCallName || ev.role || ev.message || "");
  $("log").append(h("div", {}, h("span", { class: "t" }, ev.type), " ", detail));
  $("log").scrollTop = 1e9;
}

let currentBubble = null;
function handle(ev) {
  logEvent(ev);
  switch (ev.type) {
    case "RUN_STARTED": $("status").textContent = `run ${ev.runId} started`; break;
    case "TEXT_MESSAGE_START": currentBubble = h("div", { class: "bubble" }); $("chat").append(currentBubble); break;
    case "TEXT_MESSAGE_CONTENT": currentBubble.textContent += ev.delta; break;
    case "TEXT_MESSAGE_END": MESSAGES.push({ id: ev.messageId, role: "assistant", content: currentBubble.textContent }); break;
    case "TOOL_CALL_START": TOOL_ARGS[ev.toolCallId] = ""; TOOL_NAMES[ev.toolCallId] = ev.toolCallName; break;
    case "TOOL_CALL_ARGS": TOOL_ARGS[ev.toolCallId] += ev.delta; break;
    case "TOOL_CALL_END": frontendTool(TOOL_NAMES[ev.toolCallId], JSON.parse(TOOL_ARGS[ev.toolCallId])); break;
    case "STATE_SNAPSHOT": STATE = ev.snapshot; render(); break;
    case "STATE_DELTA": STATE = applyPatch(STATE, ev.delta); render(); break;
    case "RUN_ERROR": $("status").textContent = `RUN_ERROR: ${ev.message}`; break;
    case "RUN_FINISHED": $("status").textContent = `run finished`; document.body.dataset.done = MODE; break;
  }
}

// Frontend tools: the agent calls them, the PAGE executes them.
const STATIC_SLOTS = {};
function frontendTool(name, args) {
  if (name === "show_component") {
    const fn = args.component === "MetricCard"
      ? (p) => h("div", { class: "stack row" }, p.metrics.map(COMPONENTS.MetricCard))
      : COMPONENTS[args.component];
    if (!fn) return;
    STATIC_SLOTS[args.component] = h("div", { class: "card" }, h("h4", {}, args.component), fn(args.props));
    $("surface").replaceChildren(h("div", { class: "static-grid" }, ...Object.values(STATIC_SLOTS)));
  } else if (name === "render_html") {
    $("surface").replaceChildren(h("div", { class: "sandbox-label" }, `⚠ whole surface written by the agent · sandbox="${CFG.sandbox}"`),
                                 mountSandbox(args.html, 260));
  }
}

function render() {
  $("state").textContent = JSON.stringify({ ...STATE, ui: STATE.ui ? `{${Object.keys(STATE.ui.elements).length} elements}` : null,
                                            rooms: (STATE.rooms || []).map((r) => `${r.id}:${r.available ? "free" : "busy"}`) }, null, 1);
  if (STATE.ui) $("surface").replaceChildren(renderFlat(STATE.ui));
}

async function runAgent(extraMessage) {
  if (extraMessage) { MESSAGES.push(extraMessage); $("chat").append(h("div", { class: "bubble user" }, extraMessage.content)); }
  const body = { threadId: THREAD, runId: "run_" + Math.random().toString(16).slice(2, 8), state: STATE.rooms ? STATE : null,
                 messages: MESSAGES, tools: [], context: [], forwardedProps: { mode: MODE, delay: Number(qs.get("delay") || 0.04) } };
  const resp = await fetch("/agent", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
                                       body: JSON.stringify(body) });
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) handle(JSON.parse(line.slice(6)));
    }
  }
}

// The state patch demo: the USER changes shared state, then the agent runs
// again with that state and acts on what it finds there.
function requestBooking(room, slot) {
  STATE = applyPatch(STATE, [{ op: "replace", path: "/booking", value: { room, slot: slot || "14:00-15:00", status: "requested" } }]);
  render();
  delete document.body.dataset.done;
  runAgent({ id: "u" + Date.now(), role: "user", content: `Please book ${room}.` });
}

async function start() {
  CFG = await (await fetch("/config")).json();
  MODE = qs.get("mode") || CFG.default_mode;
  $("modes").replaceChildren(...CFG.modes.map((m) => h("a", { href: `?mode=${m}`, class: m === MODE ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Rendered surface · ${MODE}`;
  runAgent();
}
start();
