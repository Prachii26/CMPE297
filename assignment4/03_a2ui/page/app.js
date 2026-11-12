// Theme 03 page: a hand-written A2UI client.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
let CFG, MODE;
const SURFACES = {};                    // surfaceId -> {components, root, data, rendered}

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

// ---------------------------------------------------- data model helpers
const parts = (p) => p.split("/").filter(Boolean);
function getPath(data, p) { return parts(p).reduce((o, k) => (o == null ? o : o[k]), data); }
function setPath(data, p, v) {
  const ks = parts(p); if (!ks.length) return v;
  let o = data; for (const k of ks.slice(0, -1)) o = o[k] ??= {};
  o[ks[ks.length - 1]] = v; return data;
}
function fromContents(entries) {
  const out = {};
  for (const e of entries) {
    if (e.valueMap) {
      const inner = fromContents(e.valueMap);
      out[e.key] = e.isList ? Object.keys(inner).sort((a, b) => a - b).map((k) => inner[k]) : inner;
    } else out[e.key] = e.valueString ?? e.valueNumber ?? e.valueBoolean;
  }
  return out;
}
// A BoundValue is a literal or a pointer into the data model.
function bound(v, data) {
  if (v == null) return undefined;
  if ("path" in v) return getPath(data, v.path);
  return v.literalString ?? v.literalNumber ?? v.literalBoolean;
}

// ---------------------------------------------------- the catalog (renderers)
const RENDERERS = {
  Column: (p, s, kids) => h("div", { class: "stack column" }, kids),
  Row: (p, s, kids) => h("div", { class: "stack row" }, kids),
  Text: (p, s) => h("div", { class: p.usageHint || "body" }, bound(p.text, s.data) ?? ""),
  MetricCard: (p, s) => h("div", { class: "metric" }, h("div", { class: "v" }, bound(p.value, s.data)), h("div", { class: "l" }, bound(p.label, s.data))),
  RoomTable: (p, s) => h("table", {}, h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    (bound(p.rows, s.data) || []).map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  OccupancyChart: (p, s) => h("div", { class: "chart" }, (bound(p.series, s.data) || []).map((o) =>
    h("div", { class: "b", style: `height:${o.pct}%` }, h("span", {}, `${o.hour}h`)))),
  // two-way binding: the form writes into the data model at the paths it was given
  BookingForm: (p, s) => {
    const sel = (opts, path) => {
      const el = h("select", { onchange: (e) => setPath(s.data, path, e.target.value) }, (opts || []).map((o) => h("option", {}, o)));
      el.value = getPath(s.data, path) ?? ""; return el;
    };
    return h("form", { class: "booking", onsubmit: (e) => e.preventDefault() },
      sel(bound(p.rooms, s.data), p.roomPath), sel(bound(p.slots, s.data), p.slotPath));
  },
  Button: (p, s, _k, id) => h("button", { id: "act", onclick: () => sendAction(p.action, s, id) }, bound(p.label, s.data)),
  HtmlArtifact: (p, s) => h("div", {}, h("div", { class: "sandbox-label" },
    `⚠ HtmlArtifact (client escape hatch, not standard A2UI) · sandbox="${CFG.sandbox}"`), mountSandbox(bound(p.html, s.data), MODE === "open_ended" ? 330 : 200)),
};
// What this client tells the agent it can render, per mode. The agent may use nothing else.
const ADVERTISE = {
  static: [],
  declarative: ["Column", "Row", "Text", "MetricCard", "RoomTable", "OccupancyChart", "BookingForm", "Button"],
  open_ended: ["HtmlArtifact"],
  mixed: ["Column", "Row", "Text", "MetricCard", "RoomTable", "OccupancyChart", "BookingForm", "Button", "HtmlArtifact"],
};

// Static mode: THIS CLIENT owns the surface. The agent may only send data.
const STATIC_SURFACE = {
  root: "root",
  components: {
    root: { Column: { children: { explicitList: ["note", "row", "grid"] } } },
    note: { Text: { text: { literalString: "Client-owned layout - the agent sent only dataModelUpdate" }, usageHint: "h2" } },
    row: { Row: { children: { explicitList: ["m0", "m1", "m2"] } } },
    m0: { MetricCard: { label: { path: "/metrics/0/label" }, value: { path: "/metrics/0/value" } } },
    m1: { MetricCard: { label: { path: "/metrics/1/label" }, value: { path: "/metrics/1/value" } } },
    m2: { MetricCard: { label: { path: "/metrics/2/label" }, value: { path: "/metrics/2/value" } } },
    grid: { Row: { children: { explicitList: ["chart", "table"] } } },
    chart: { OccupancyChart: { series: { path: "/occupancy" } } },
    table: { RoomTable: { rows: { path: "/rooms" } } },
  },
};

// ---------------------------------------------------- rendering
function render(sid) {
  const s = SURFACES[sid];
  if (!s || !s.rendered) return;
  const draw = (id) => {
    const def = s.components[id];
    if (!def) return h("div", { class: "slot" }, `${id}…`);
    const [type, props] = Object.entries(def)[0];
    const fn = RENDERERS[type];
    if (!fn) return h("div", { class: "reject" }, `rejected: ${type} not in this client's catalog`);
    const kids = props.children ? props.children.explicitList.map(draw) : [];
    return fn(props, s, kids, id);
  };
  $("surface").replaceChildren(draw(s.root));
  $("state").textContent = JSON.stringify({ ...s.data, rooms: (s.data.rooms || []).map((r) => `${r.id}:${r.available ? "free" : "busy"}`),
                                            occupancy: "[...]" }, null, 1);
}

const COUNTS = {};
function handle(msg) {
  const [kind, body] = Object.entries(msg)[0];
  COUNTS[kind] = (COUNTS[kind] || 0) + 1;
  $("counts").replaceChildren(...Object.entries(COUNTS).map(([t, n]) => h("span", {}, `${t} ×${n}`)));
  const cls = kind === "dataModelUpdate" ? "d" : kind === "error" ? "e" : "t";
  const what = kind === "surfaceUpdate" ? body.components.map((c) => `${c.id}:${Object.keys(c.component)[0]}`).join(", ")
             : kind === "dataModelUpdate" ? `path ${body.path} (${body.contents.map((c) => c.key).join(", ")})` : JSON.stringify(body).slice(0, 80);
  $("log").append(h("div", {}, h("span", { class: cls }, kind), " ", what)); $("log").scrollTop = 1e9;
  if (kind === "error") return;
  const sid = body.surfaceId;
  const s = SURFACES[sid] ??= { components: {}, root: null, data: {}, rendered: false };
  if (kind === "surfaceUpdate") for (const c of body.components) s.components[c.id] = c.component;   // merge by id
  else if (kind === "dataModelUpdate") {
    const incoming = fromContents(body.contents);
    const at = getPath(s.data, body.path);
    if (body.path === "/") Object.assign(s.data, incoming);
    else setPath(s.data, body.path, { ...(at || {}), ...incoming });
  } else if (kind === "beginRendering") { s.root = body.root; s.rendered = true; }
  else if (kind === "deleteSurface") delete SURFACES[sid];
  render(sid);
}

async function readJsonl(resp) {
  const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) { const line = buf.slice(0, i); buf = buf.slice(i + 1); if (line.trim()) handle(JSON.parse(line)); }
  }
}

// ---------------------------------------------------- user actions
async function sendAction(action, s, sourceComponentId) {
  const context = {};
  for (const c of action.context || []) context[c.key] = bound(c.value, s.data);   // resolved on the client
  const userAction = { name: action.name, surfaceId: s.id || (MODE === "static" ? "static" : "rooms"),
                       sourceComponentId, timestamp: new Date().toISOString(), context };
  $("log").append(h("div", {}, h("span", { class: "e" }, "→ userAction"), " ", JSON.stringify(context)));
  delete document.body.dataset.done;
  await readJsonl(await fetch("/a2ui/action", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: MODE, userAction, clientCapabilities: { catalog: ADVERTISE[MODE] }, delay: 0.02 }) }));
  document.body.dataset.done = MODE;
}

const FRAMES = new Set();
function mountSandbox(html, height) {
  const f = h("iframe", { class: "sandbox", sandbox: CFG.sandbox, referrerpolicy: "no-referrer", style: `height:${height}px` });
  f.srcdoc = html; FRAMES.add(f); return f;
}
window.addEventListener("message", (e) => {
  if (![...FRAMES].some((f) => f.contentWindow === e.source) || !e.data || e.data.type !== "book") return;
  const s = SURFACES[MODE === "static" ? "static" : "rooms"];
  sendAction({ name: "book", context: [{ key: "room", value: { literalString: e.data.room } },
                                       { key: "slot", value: { literalString: e.data.slot } }] }, s, "sandbox");
});

async function start() {
  CFG = await (await fetch("/config")).json();
  MODE = qs.get("mode") || CFG.default_mode;
  $("modes").replaceChildren(...CFG.modes.map((m) => h("a", { href: `?mode=${m}`, class: m === MODE ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Rendered surface · ${MODE}`;
  $("adv").replaceChildren(...(ADVERTISE[MODE].length ? ADVERTISE[MODE] : ["(nothing: the client owns the surface)"]).map((n) => h("span", {}, n)));
  if (MODE === "static") {
    SURFACES.static = { components: STATIC_SURFACE.components, root: "root", data: {}, rendered: true };
    STATIC_SURFACE.components.root.Column.children.explicitList.push("book");
    STATIC_SURFACE.components.book = { Button: { label: { literalString: "Book first free room" },
      action: { name: "book", context: [{ key: "room", value: { path: "/freeRooms/0" } }, { key: "slot", value: { literalString: "15:00-16:00" } }] } } };
  }
  await readJsonl(await fetch("/a2ui/run", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: MODE, clientCapabilities: { catalog: ADVERTISE[MODE] }, delay: Number(qs.get("delay") || 0.06) }) }));
  for (const sid of Object.keys(SURFACES)) SURFACES[sid].id = sid;
  document.body.dataset.done = MODE;
}
start();
