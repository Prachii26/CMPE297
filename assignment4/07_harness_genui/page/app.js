// Theme 07: the browser surface of the stage 15 harness. It draws whatever
// spec the harness's render_ui tool accepted, and sends clicks back as turns.
"use strict";

const $ = (id) => document.getElementById(id);
let CFG;

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

// The same six components as harness/render_ui.py CATALOG (+ HtmlArtifact).
const REGISTRY = {
  Stack: (p, kids) => h("div", { class: `stack ${p.direction || "column"}` }, kids),
  Heading: (p) => h("div", { class: `h1 tone-${p.tone || "normal"}` }, p.text),
  Metric: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {}, h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    p.rooms.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building || ""), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  BarChart: (p) => h("div", {}, h("div", { class: "l" }, p.title || ""), h("div", { class: "chart" },
    p.bars.map((b) => h("div", { class: "b", style: `height:${b.value}%` }, h("span", {}, b.label))))),
  Button: (p) => h("button", { id: "act", onclick: () => act(p.action.name, p.action.params || {}) }, p.label),
  HtmlArtifact: (p) => h("div", {}, h("div", { class: "sandbox-label" },
    `⚠ HtmlArtifact · sandbox="${CFG.sandbox}" · CSP injected by render_ui`), mountSandbox(p.html)),
};

const FRAMES = new Set();
function mountSandbox(html) {
  const f = h("iframe", { class: "sandbox", sandbox: CFG.sandbox, referrerpolicy: "no-referrer", style: "height:230px" });
  f.srcdoc = html; FRAMES.add(f); return f;
}
window.addEventListener("message", (e) => {
  if ([...FRAMES].some((f) => f.contentWindow === e.source) && e.data && e.data.type === "book" && typeof e.data.room === "string")
    act("book", { room: e.data.room, slot: e.data.slot });
});

async function act(name, params) {
  delete document.body.dataset.done;
  $("status").textContent = `action ${name} → harness turn…`;
  const r = await (await fetch("/action", { method: "POST", headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({ name, params }) })).json();
  $("turns").append(h("div", { class: "bubble user" }, r.user_turn || name), h("div", { class: "bubble" }, r.reply || ""));
}

function render(msg) {
  const spec = msg.spec;
  const draw = (id) => { const el = spec.elements[id]; const fn = REGISTRY[el.type];
    return fn ? fn(el.props, (el.children || []).map(draw)) : h("div", { class: "reject" }, `unknown ${el.type}`); };
  let body = draw(spec.root);
  if (msg.mode === "static") body = h("div", { class: "card" }, h("h4", {}, "[harness frame] the agent named one prebuilt component"), body);
  $("surface").replaceChildren(body);
  $("raw").textContent = JSON.stringify(spec, (k, v) => (k === "html" && typeof v === "string" ? `<${v.length} bytes, CSP injected>` : k === "rooms" ? `[${v.length} rooms]` : v), 1);
  $("status").textContent = `render_ui spec v${msg.version} · ${msg.mode}`;
  document.body.dataset.done = msg.mode;
}

async function start() {
  CFG = await (await fetch("/config")).json();
  $("mode").textContent = CFG.mode;
  new EventSource("/events").onmessage = (e) => render(JSON.parse(e.data));
}
start();
