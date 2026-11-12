// Theme 06: a minimal MCP Apps HOST. It owns the page; the app is a guest.
"use strict";

const qs = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
let MODE, TOOLS = [];

// The host's policy: the ONLY tool a mounted app may call through the bridge.
const ALLOWED_FROM_APP = new Set(["book_room"]);
const SANDBOX = "allow-scripts";          // no allow-same-origin, no forms, no popups, no top navigation

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
function logLine(dir, text, cls = "") {
  $("log").append(h("div", { class: cls }, h("span", { class: "t" }, dir), " ", text));
  $("log").scrollTop = 1e9;
}

// ---------------------------------------------------------- MCP client
let rpcId = 1;
async function mcp(method, params) {
  const r = await fetch("/mcp", { method: "POST", headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ jsonrpc: "2.0", id: rpcId++, method, params }) });
  const j = await r.json();
  logLine("host→server", `${method}${params && params.name ? " " + params.name : params && params.uri ? " " + params.uri : ""}`);
  if (j.error) throw new Error(j.error.message);
  return j.result;
}

// ---------------------------------------------------------- mounting a ui:// resource
// The HOST builds the CSP from the resource's _meta.ui.csp. The app asks for
// origins; the host decides. Here the app asked for none, so connect-src is 'none'.
function cspFor(meta) {
  const csp = (meta && meta.ui && meta.ui.csp) || {};
  const connect = (csp.connectDomains || []).join(" ") || "'none'";
  const res = (csp.resourceDomains || []).join(" ");
  return `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: ${res}; ` +
         `connect-src ${connect}; base-uri 'none'; form-action 'none'`;
}
const FRAMES = [];                      // {frame, toolName, args, result}, matched by contentWindow at message time
async function mountApp(uri, toolName, args, result, height) {
  const read = await mcp("resources/read", { uri });
  const c = read.contents[0];
  const csp = cspFor(c._meta);
  const html = c.text.replace("<head>", `<head><meta http-equiv="Content-Security-Policy" content="${csp}">`);
  const frame = h("iframe", { class: "sandbox", sandbox: SANDBOX, referrerpolicy: "no-referrer",
                              title: uri, style: `height:${height}px` });
  frame.srcdoc = html;
  const box = h("div", {}, h("div", { class: "sandbox-label" }, `⚠ ${uri} · ${c.mimeType} · sandbox="${SANDBOX}" · CSP: ${csp}`), frame);
  FRAMES.push({ frame, toolName, args, result });
  return box;
}

// ---------------------------------------------------------- the bridge (host side)
function reply(win, id, payload) { win.postMessage({ jsonrpc: "2.0", id, ...payload }, "*"); }
window.addEventListener("message", async (e) => {
  const ctx = FRAMES.find((c) => c.frame.contentWindow === e.source);
  if (!ctx) return;                                     // only frames this host mounted
  const m = e.data || {};
  if (m.jsonrpc !== "2.0") return;
  logLine("app→host", `${m.method}${m.params && m.params.name ? " " + m.params.name : ""}`);
  if (m.method === "ui/initialize") {
    reply(e.source, m.id, { result: { protocolVersion: "2026-01-26", hostInfo: { name: "theme06-host", version: "1.0" },
      hostCapabilities: { serverTools: { listChanged: false } }, hostContext: { theme: "light", displayMode: "inline" } } });
  } else if (m.method === "ui/notifications/initialized") {
    // the app is ready: pass the tool's input and result IN
    e.source.postMessage({ jsonrpc: "2.0", method: "ui/notifications/tool-input", params: { arguments: ctx.args } }, "*");
    e.source.postMessage({ jsonrpc: "2.0", method: "ui/notifications/tool-result", params: ctx.result }, "*");
    logLine("host→app", "tool-input + tool-result");
    document.body.dataset.done = MODE;
  } else if (m.method === "tools/call") {
    const name = m.params && m.params.name;
    if (!ALLOWED_FROM_APP.has(name)) {                  // the app asked; the host says no
      logLine("host", `REFUSED tools/call ${name}: not on this host's allowlist`, "e");
      reply(e.source, m.id, { error: { code: -32001, message: `host policy: '${name}' may not be called from an app` } });
      return;
    }
    try {
      const res = await mcp("tools/call", { name, arguments: m.params.arguments || {} });
      reply(e.source, m.id, { result: res });
      logLine("host→app", `result of ${name}: ${res.content[0].text}`);
      $("model").textContent = res.content.map((c) => c.text).join("\n");
    } catch (err) { reply(e.source, m.id, { error: { code: -32000, message: err.message } }); }
  } else if (m.id) {
    reply(e.source, m.id, { error: { code: -32601, message: `host does not support ${m.method}` } });
  }
});

// ---------------------------------------------------------- the host's own catalog
const CATALOG = {
  Stack: (p, kids) => h("div", { class: `stack ${p.direction || "column"}` }, kids),
  Heading: (p) => h("div", { class: "h1" }, p.text),
  MetricCard: (p) => h("div", { class: "metric" }, h("div", { class: "v" }, p.value), h("div", { class: "l" }, p.label)),
  RoomTable: (p) => h("table", {}, h("tr", {}, ["Room", "Building", "Seats", "Status"].map((t) => h("th", {}, t))),
    p.rooms.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, r.building), h("td", {}, String(r.capacity)),
      h("td", {}, h("span", { class: `pill ${r.available ? "free" : "busy"}` }, r.available ? "free now" : `free at ${r.next_free}`))))),
  OccupancyChart: (p) => h("div", { class: "chart" }, p.series.map((o) => h("div", { class: "b", style: `height:${o.pct}%` }, h("span", {}, `${o.hour}h`)))),
};
async function renderPayload(payload, toolName, result) {
  if (payload.kind === "static") {
    const fn = CATALOG[payload.component];
    return fn ? h("div", { class: "card" }, h("h4", {}, `${payload.component} (static: one prebuilt component)`), fn(payload.props))
              : h("div", { class: "reject" }, `rejected: ${payload.component} not in host catalog`);
  }
  const draw = async (id) => {
    const el = payload.elements[id];
    if (el.type === "AppRegion") return mountApp(el.props.resourceUri, toolName, {}, result, 210);
    const fn = CATALOG[el.type];
    if (!fn) return h("div", { class: "reject" }, `rejected: ${el.type} not in host catalog`);
    const kids = [];
    for (const c of el.children || []) kids.push(await draw(c));
    return fn(el.props, kids);
  };
  return draw(payload.root);
}

// ---------------------------------------------------------- run
const TOOL_FOR_MODE = { static: "show_rooms_static", declarative: "show_rooms_declarative",
                        open_ended: "show_rooms_app", mixed: "show_rooms_mixed" };
async function start() {
  const cfg = await (await fetch("/config")).json();
  MODE = qs.get("mode") || cfg.default_mode;
  $("modes").replaceChildren(...cfg.modes.map((m) => h("a", { href: `?mode=${m}`, class: m === MODE ? "on" : "" }, m.replace("_", "-"))));
  $("surface-title").textContent = `Host surface · ${MODE}`;
  await fetch("/reset", { method: "POST" });
  const init = await mcp("initialize", { protocolVersion: "2025-06-18", clientInfo: { name: "theme06-host" },
                                         capabilities: { extensions: { "io.modelcontextprotocol/ui": {} } } });
  TOOLS = (await mcp("tools/list", {})).tools;
  $("tools").replaceChildren(...TOOLS.map((t) => h("span", {}, t.name + (t._meta && t._meta.ui ? ` → ${t._meta.ui.resourceUri}` : ""))));
  const name = TOOL_FOR_MODE[MODE];                     // the scripted "model" picks the tool
  const tool = TOOLS.find((t) => t.name === name);
  const result = await mcp("tools/call", { name, arguments: {} });
  $("model").textContent = result.content.map((c) => c.text).join("\n");
  let node;
  if (MODE === "open_ended") node = await mountApp(tool._meta.ui.resourceUri, name, {}, result, 420);
  else node = await renderPayload(result.structuredContent.render, name, result);
  $("surface").replaceChildren(node);
  if (MODE === "static" || MODE === "declarative") document.body.dataset.done = MODE;
  logLine("host", `server ${init.serverInfo.name}, protocol ${init.protocolVersion}`);
}
start();
