// Theme 01 page: four generation modes, one hand-written renderer, no library.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
const raw = $("raw"), surface = $("surface"), statusEl = $("status");

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

// ---------------------------------------------------------------- components
// The renderer is keyed by component name. Anything not in this object
// cannot be drawn: that is what a catalog means on the client side.
const COMPONENTS = {
  Stack: (p, kids) => h("div", { class: `stack ${p.direction || "column"}` }, kids),
  Heading: (p) => h("h3", { class: "heading" }, p.text),
  Text: (p) => h("p", {}, p.text),
  MetricCard: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {},
    h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    (p.rooms || []).map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building || ""),
      h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` },
        r.available ? "free now" : `free at ${r.next_free}`))))),
  OccupancyChart: (p) => h("div", { class: "chart", title: "occupancy by hour" },
    (p.series || []).map((o) => h("div", { class: "b", style: `height:${o.pct}%`, title: `${o.pct}%` },
      h("span", {}, `${o.hour}h`)))),
  BookingForm: (p) => h("form", { class: "booking", onsubmit: (e) => e.preventDefault() },
    h("select", { id: "room" }, (p.rooms || []).map((r) => h("option", {}, r))),
    h("select", { id: "slot" }, (p.slots || []).map((s) => h("option", {}, s)))),
  Button: (p) => h("button", { onclick: () => doAction(p.action) }, p.label),
  SandboxedHtml: (p, _k, cfg) => h("div", {}, h("div", { class: "sandbox-label" },
    `⚠ open-ended region: ${p.title || "generated HTML"} · sandbox="${cfg.sandbox}" · CSP enforced`),
    mountSandbox(p.html, cfg, 220)),
};

// ------------------------------------------------------------ the sandbox
// The ONLY way generated HTML reaches the page. sandbox comes from the server
// (allow-scripts, and nothing else): no same-origin, so the frame cannot read
// this page, its cookies or storage; no top navigation; no forms; no popups.
// The server has already injected a CSP meta tag into the document.
function mountSandbox(html, cfg, height) {
  const f = h("iframe", { class: "sandbox", sandbox: cfg.sandbox, referrerpolicy: "no-referrer",
                          title: "sandboxed generated UI", style: `height:${height}px` });
  f.srcdoc = html;
  SANDBOXES.add(f);
  return f;
}
const SANDBOXES = new Set();
window.addEventListener("message", (e) => {
  // one message shape is accepted, and only from a frame we mounted
  const from = [...SANDBOXES].find((f) => f.contentWindow === e.source);
  const m = e.data;
  if (!from || !m || m.type !== "book" || typeof m.room !== "string") return;
  doAction("book", m.room, m.slot);
});

async function doAction(action, room, slot) {
  room = room || ($("room") && $("room").value);
  slot = slot || ($("slot") && $("slot").value) || "14:00-15:00";
  const r = await fetch("/action", { method: "POST", headers: { "Content-Type": "application/json" },
                                     body: JSON.stringify({ action, room, slot }) });
  const j = await r.json();
  $("toast").replaceChildren(h("div", { class: "toast" }, `${j.ok ? "✓" : "✗"} ${j.message}`));
}

// ---------------------------------------------- tolerant partial-JSON parser
// Same algorithm as partial_json.py: cut back to a point outside a string,
// drop a trailing comma/colon, close what is open, try to parse.
function scan(text) {
  let inStr = false, esc = false; const stack = [];
  for (const ch of text) {
    if (inStr) { if (esc) esc = false; else if (ch === "\\") esc = true; else if (ch === '"') inStr = false; }
    else if (ch === '"') inStr = true;
    else if (ch === "{" || ch === "[") stack.push(ch);
    else if (ch === "}" || ch === "]") stack.pop();
  }
  return { inStr, stack };
}
function parsePartial(text) {
  try { return JSON.parse(text); } catch (_) {}
  for (let cut = text.length; cut > 0; cut--) {
    let head = text.slice(0, cut);
    if (scan(head).inStr) continue;
    head = head.replace(/[\s,:]+$/, "");
    if (!head) continue;
    const closers = scan(head).stack.reverse().map((c) => (c === "{" ? "}" : "]")).join("");
    try { return JSON.parse(head + closers); } catch (_) {}
  }
  return null;
}

// ---------------------------------------------------- declarative renderers
function renderFlat(spec, cfg) {
  if (!spec || !spec.elements) return h("div", { class: "slot" }, "waiting for the root element…");
  const draw = (id) => {
    const el = spec.elements[id];
    if (!el || !el.type || !el.props) return h("div", { class: "slot" }, `${id} · not streamed yet`);
    const fn = COMPONENTS[el.type];
    if (!fn) return h("div", { class: "reject" }, `rejected: ${el.type} is not in the catalog`);
    return fn(el.props, (el.children || []).map(draw), cfg);
  };
  return draw(spec.root || Object.keys(spec.elements)[0]);
}
function renderNested(node, cfg) {
  if (!node || !node.type) return h("div", { class: "slot" }, "waiting…");
  const fn = COMPONENTS[node.type];
  if (!fn) return h("div", { class: "reject" }, `rejected: ${node.type} is not in the catalog`);
  return fn(node.props || {}, (node.children || []).map((c) => renderNested(c, cfg)), cfg);
}

// ------------------------------------------------------------------ modes
const STATIC_SLOTS = { MetricCard: "metrics", OccupancyChart: "chart", RoomTable: "rooms" };
function staticLayout() {
  // static mode: WE own the layout; the agent can only fill these three slots
  return h("div", { class: "static-grid" },
    h("div", { class: "card full", id: "slot-metrics" }, h("h4", {}, "MetricCard"), h("div", { class: "slot" }, "empty")),
    h("div", { class: "card", id: "slot-chart" }, h("h4", {}, "OccupancyChart"), h("div", { class: "slot" }, "empty")),
    h("div", { class: "card", id: "slot-rooms" }, h("h4", {}, "RoomTable"), h("div", { class: "slot" }, "empty")));
}

async function start() {
  const cfg = await (await fetch("/config")).json();
  const mode = qs.get("mode") || cfg.default_mode;
  const shape = qs.get("shape") || "flat";
  $("modes").replaceChildren(...cfg.modes.map((m) =>
    h("a", { href: `?mode=${m}`, class: m === mode ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Rendered surface · ${mode}${mode === "declarative" ? " · " + shape : ""}`;
  if (mode === "static") surface.replaceChildren(staticLayout());

  let buf = "", chunks = 0;
  const es = new EventSource(`/stream?mode=${mode}&shape=${shape}${qs.get("delay") ? "&delay=" + qs.get("delay") : ""}`);
  es.addEventListener("run_started", () => { statusEl.textContent = `run started · ${mode}`; });
  es.addEventListener("component", (e) => {
    const item = JSON.parse(e.data);
    raw.textContent += JSON.stringify(item).slice(0, 220) + "…\n\n";
    const fn = { MetricCard: (p) => h("div", { class: "stack row" }, p.metrics.map(COMPONENTS.MetricCard)),
                 OccupancyChart: COMPONENTS.OccupancyChart, RoomTable: COMPONENTS.RoomTable }[item.component];
    const slot = $(`slot-${STATIC_SLOTS[item.component]}`);
    if (!fn || !slot) return;
    slot.replaceChildren(h("h4", {}, item.component), fn(item.props));
  });
  es.addEventListener("chunk", (e) => {
    const c = JSON.parse(e.data); buf += c.text; chunks++;
    raw.textContent = buf;
    const spec = parsePartial(buf);
    surface.replaceChildren(shape === "nested" && mode === "declarative" ? renderNested(spec, cfg) : renderFlat(spec, cfg));
    statusEl.textContent = `chunk ${chunks} · ${buf.length} chars`;
  });
  es.addEventListener("validation", (e) => {
    const v = JSON.parse(e.data);
    statusEl.textContent = v.ok ? `spec valid against the catalog (${chunks} chunks)` : `INVALID: ${v.errors.join("; ")}`;
  });
  es.addEventListener("html_chunk", (e) => {
    const c = JSON.parse(e.data);
    surface.replaceChildren(h("div", { class: "slot" }, `receiving generated HTML… ${c.bytes} / ${c.total} bytes (nothing can render until it is complete)`));
  });
  es.addEventListener("html", (e) => {
    const p = JSON.parse(e.data);
    raw.textContent = p.html;
    surface.replaceChildren(h("div", { class: "sandbox-label" }, `⚠ whole page is generated · sandbox="${p.sandbox}" · CSP: ${p.csp}`),
                            mountSandbox(p.html, p, 460));
  });
  es.addEventListener("run_finished", () => {
    es.close(); document.body.dataset.done = mode;
    if (statusEl.textContent.startsWith("run started")) statusEl.textContent = `run finished · ${mode}`;
  });
}
start();
