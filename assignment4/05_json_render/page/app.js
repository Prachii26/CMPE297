// Theme 05 page: the web renderer for a json-render style spec built by patches.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
let CFG, MODE, SPEC = {};

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

// Same catalog names as terminal.py's REGISTRY.
const REGISTRY = {
  Stack: (p, kids) => h("div", { class: `stack ${p.direction || "column"}` }, kids),
  Heading: (p) => h("div", { class: "h1" }, p.text),
  Text: (p) => h("div", { class: `tone-${p.tone || "muted"}` }, p.text),
  Metric: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {}, h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    p.rooms.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building || ""), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  BarChart: (p) => h("div", {}, p.title ? h("div", { class: "l" }, p.title) : null,
    h("div", { class: "chart" }, p.bars.map((b) => h("div", { class: "b", style: `height:${b.value}%` }, h("span", {}, b.label))))),
  BookingForm: (p) => h("form", { class: "booking", onsubmit: (e) => e.preventDefault() },
    h("select", { id: "room" }, p.rooms.map((r) => h("option", {}, r))),
    h("select", { id: "slot" }, p.slots.map((s) => h("option", {}, s)))),
  Button: (p) => h("button", { id: "act", onclick: () => runAction(p.action.name, { room: $("room") && $("room").value, slot: $("slot") && $("slot").value }) }, p.label),
  HtmlArtifact: (p) => h("div", {}, h("div", { class: "sandbox-label" }, `⚠ HtmlArtifact · sandbox="${CFG.sandbox}" · CSP injected by the server`),
    mountSandbox(p.html, MODE === "open_ended" ? 360 : 200)),
};

function render() {
  $("state").textContent = JSON.stringify(SPEC, (k, v) => (k === "html" && typeof v === "string" ? `<${v.length} bytes of HTML>` : k === "rooms" && Array.isArray(v) && typeof v[0] === "object" ? v.map((r) => `${r.id}:${r.available ? "free" : "busy"}`) : v), 1).slice(0, 3000);
  if (!SPEC.root || !SPEC.elements || !SPEC.elements[SPEC.root]) return;
  const draw = (id) => {
    const el = SPEC.elements[id];
    if (!el) return h("div", { class: "slot" }, `${id}…`);
    const fn = REGISTRY[el.type];
    if (!fn) return h("div", { class: "reject" }, `rejected: ${el.type} not in catalog`);
    return fn(el.props, (el.children || []).map(draw));
  };
  $("surface").replaceChildren(draw(SPEC.root));
}

// RFC 6902 add / replace / remove, applied to the live spec in place.
function apply(op) {
  const parts = op.path.split("/").slice(1).map((p) => p.replace(/~1/g, "/").replace(/~0/g, "~"));
  let parent = SPEC;
  for (const p of parts.slice(0, -1)) parent = parent[p];
  const last = parts[parts.length - 1];
  if (Array.isArray(parent)) {
    const i = last === "-" ? parent.length : Number(last);
    if (op.op === "add") parent.splice(i, 0, structuredClone(op.value));
    else if (op.op === "replace") parent[i] = structuredClone(op.value);
    else parent.splice(i, 1);
  } else if (op.op === "remove") delete parent[last];
  else parent[last] = structuredClone(op.value);
}

const COUNTS = {};
function handle(line) {
  if (line.error) {
    $("log").append(h("div", {}, h("span", { class: "e" }, "rejected"), " ", `${line.error.op}: ${line.error.rejected.join("; ")}`));
    return;
  }
  COUNTS[line.op] = (COUNTS[line.op] || 0) + 1;
  $("counts").replaceChildren(...Object.entries(COUNTS).map(([t, n]) => h("span", {}, `${t} ×${n}`)));
  $("log").append(h("div", {}, h("span", { class: line.op === "replace" ? "d" : "t" }, line.op), " ", line.path));
  $("log").scrollTop = 1e9;
  apply(line); render();
}

async function readJsonl(resp) {
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) { const l = buf.slice(0, i); buf = buf.slice(i + 1); if (l.trim()) handle(JSON.parse(l)); }
  }
}

async function runAction(name, params) {
  $("log").append(h("div", {}, h("span", { class: "e" }, "→ action"), ` ${name} ${JSON.stringify(params)}`));
  delete document.body.dataset.done;
  await readJsonl(await fetch("/action", { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ mode: MODE, name, params }) }));
  document.body.dataset.done = MODE;
}

const FRAMES = new Set();
function mountSandbox(html, height) {
  for (const f of FRAMES) if (f.srcdoc === html && f.isConnected) return f;   // keep the frame across re-renders
  const f = h("iframe", { class: "sandbox", sandbox: CFG.sandbox, referrerpolicy: "no-referrer", style: `height:${height}px` });
  f.srcdoc = html; FRAMES.add(f); return f;
}
window.addEventListener("message", (e) => {
  if ([...FRAMES].some((f) => f.contentWindow === e.source) && e.data && e.data.type === "book")
    runAction("confirm_booking", { room: e.data.room, slot: e.data.slot });
});

async function start() {
  CFG = await (await fetch("/config")).json();
  MODE = qs.get("mode") || CFG.default_mode;
  $("modes").replaceChildren(...CFG.modes.map((m) => h("a", { href: `?mode=${m}`, class: m === MODE ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Rendered surface · ${MODE}`;
  const cat = await (await fetch(`/catalog?mode=${MODE}`)).json();
  $("adv").replaceChildren(...cat.components.map((n) => h("span", {}, n)));
  if (MODE === "static") { SPEC = structuredClone(CFG.skeleton); render(); }   // the client owns this skeleton
  await readJsonl(await fetch(`/spec/stream?mode=${MODE}&delay=${qs.get("delay") || 0.05}`));
  document.body.dataset.done = MODE;
}
start();
