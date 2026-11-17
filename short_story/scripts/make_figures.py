"""Generate every figure in short_story/article/figures/.

Each number below is copied from the paper notes (research/paper_notes.md),
which record the section and page of arXiv 2510.06445 v4 it came from. Nothing
here is estimated. Run from the short_story folder:

    .\.venv\Scripts\python.exe scripts\make_figures.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
import graphviz  # noqa: E402

GV_BIN = r"C:\Program Files\Graphviz\bin"
if os.path.isdir(GV_BIN) and GV_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + GV_BIN

OUT = Path(__file__).resolve().parent.parent / "article" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- style
SURFACE = "#ffffff"
INK = "#1a1a1a"
INK2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
BLUE_DARK = "#184f95"
RED = "#c23b3a"
SEQ = LinearSegmentedColormap.from_list(
    "seqblue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
SRC = "Source: Shahriar et al., A Survey on Agentic Security, arXiv 2510.06445 v4 (TMLR, 2026)"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 13,
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": MUTED,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 12,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "savefig.transparent": False,
})

DPI = 200


def clean(ax, grid_axis="x"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    ax.tick_params(length=0)


def finish(fig, name, source=SRC, note=None):
    y = 0.012
    if note:
        fig.text(0.01, y + 0.028, note, fontsize=10.5, color=INK2, ha="left", va="bottom")
    fig.text(0.01, y, source, fontsize=10, color=MUTED, ha="left", va="bottom")
    path = OUT / name
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print("wrote", path.name)


def esc(t: str) -> str:
    return t.replace("&", "&amp;")


def gv_render(dot: graphviz.Digraph, name: str):
    dot.format = "png"
    stem = OUT / name.replace(".png", "")
    dot.render(filename=str(stem), cleanup=True)
    print("wrote", name)


# ======================================================== fig 01 taxonomy
def fig01_taxonomy():
    g = graphviz.Digraph("taxonomy", graph_attr={
        "rankdir": "LR", "bgcolor": SURFACE, "dpi": "170", "nodesep": "0.16",
        "ranksep": "0.55", "fontname": "Helvetica", "pad": "0.3", "splines": "spline",
        "label": f"<<font point-size='11' color='{MUTED}'>{SRC}; Fig. 1, p. 4</font>>",
        "labeljust": "l", "labelloc": "b",
    }, node_attr={"shape": "box", "style": "rounded,filled", "fontname": "Helvetica",
                  "color": "#b9b8b3", "fontcolor": INK, "penwidth": "1.2"},
       edge_attr={"color": "#9b9a95", "arrowhead": "none", "penwidth": "1.1"})

    tint = {"A": "#e3eefb", "T": "#fde6dc", "D": "#dcf3ea"}
    deep = {"A": "#c6dcf6", "T": "#f9cbb7", "D": "#b4e6d2"}

    def leaf(name, examples):
        name = esc(name)
        return (f"<<b>{name}</b><br/><font point-size='10' color='{INK2}'>"
                f"{examples}</font>>")

    g.node("root", "<<b>Agentic security</b><br/><font point-size='11'>274 papers, Jan 2023 to May 2026</font>>",
           fillcolor="#f2f1ee", fontsize="16")
    pillars = {
        "A": ("Applications", "113 papers · §3", {
            "Red teaming": [("Autonomous pentesting", "PentestGPT, HackSynth, Incalmo"),
                            ("Vulnerability discovery & fuzzing", "Locus, ChatAFL, FuzzGPT"),
                            ("Exploit generation & adaptation", "MalGen, CVE-Genie")],
            "Blue teaming": [("Threat detection & incident response", "IRCopilot, CORTEX"),
                             ("Threat hunting", "ProvSEEK, LLMCloudHunter"),
                             ("Automated forensics", "RepoAudit, CyberSleuth, GALA"),
                             ("Patching & remediation", "RepairAgent")],
            "Domain-specific": [("Cloud & infrastructure", "KubeIntellect, BARTPredict"),
                                ("Web & application", "MAPTA, AIOS, Progent, PFI"),
                                ("Specialized", "LISA, HIPAA, OneShield")],
        }),
        "T": ("Threats", "86 papers · §4", {
            "Attack surface\n(7 classes)": [("Injection", "AgentDojo, InjecAgent"),
                                ("Poisoning & extraction", "AgentPoison, PoisonBench"),
                                ("Jailbreak", "BrowserART, JAWS-BENCH"),
                                ("Agent manipulation", "goal/action hijack, reward hacking"),
                                ("Pre-execution cognitive", "ScamAgents, RSP"),
                                ("Red-teaming attacks", "AI-Oops, AgentDoS"),
                                ("Interface-level (GUI)", "Pop-up Attack, MIP")],
            "Evaluation": [("Adversarial benchmarks", "ASB, SafeArena, DoomArena"),
                           ("Execution environments", "AgentDojo, CVE-Bench")],
        }),
        "D": ("Defenses", "123 papers · §5", {
            "Defenses &\noperations": [("Secure-by-design", "ACE, Task Shield"),
                                      ("Multi-agent security", "D-CIPHER, PhishDebate"),
                                      ("Runtime protection", "R2-Guard, AgentSpec, SentinelAgent"),
                                      ("Security operations", "IRIS, CORTEX, GALA")],
            "Evaluation": [("Benchmarking platforms", "ASB, RAS-Eval"),
                           ("Defense testing", "AI Agents Under Threat"),
                           ("Domain-specific", "CloudInfra, PrivacyMedical")],
        }),
    }
    for key, (title, sub, branches) in pillars.items():
        pid = f"p{key}"
        g.node(pid, f"<<b>{title}</b><br/><font point-size='11'>{sub}</font>>",
               fillcolor=deep[key], fontsize="15")
        g.edge("root", pid)
        for bi, (branch, leaves) in enumerate(branches.items()):
            bid = f"{pid}b{bi}"
            g.node(bid, f"<<b>{esc(branch).replace(chr(10), '<br/>')}</b>>", fillcolor=tint[key], fontsize="13")
            g.edge(pid, bid)
            for li, (name, ex) in enumerate(leaves):
                lid = f"{bid}l{li}"
                g.node(lid, leaf(name, ex), fillcolor=SURFACE, fontsize="12")
                g.edge(bid, lid)
    gv_render(g, "fig01_taxonomy.png")


# ======================================================== fig 02 agent loop
def fig02_agent_loop():
    import numpy as np
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

    stages = ["Perception", "Retrieval", "Reasoning", "Planning",
              "Action\nselection", "Execution", "Observation", "Reflection"]
    fails = [6, 5, 54, 7, 41, 9, 5, 0]          # §4.4.2, Fig. 9a, p27 (78 papers)

    fig = plt.figure(figsize=(12, 9.4))
    ax = fig.add_axes([0, 0.075, 1, 0.835])
    ax.set_xlim(-7.2, 7.2)
    ax.set_ylim(-4.3, 5.95)
    ax.set_aspect("equal")
    ax.axis("off")

    R = 3.3
    angles = np.deg2rad(90 - np.arange(8) * 45)
    pos = [(R * np.cos(a), R * np.sin(a)) for a in angles]
    w, h = 2.1, 1.05
    norm = max(fails)

    # loop arrows (clockwise), reflection feeds back to reasoning
    for i in range(7):
        (x0, y0), (x1, y1) = pos[i], pos[i + 1]
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), connectionstyle="arc3,rad=-0.18",
                                     arrowstyle="-|>", mutation_scale=16, color="#9b9a95",
                                     lw=1.6, shrinkA=40, shrinkB=40, zorder=1))
    ax.add_patch(FancyArrowPatch(pos[7], pos[2], connectionstyle="arc3,rad=0.25",
                                 arrowstyle="-|>", mutation_scale=16, color="#9b9a95",
                                 lw=1.6, ls=(0, (4, 3)), shrinkA=40, shrinkB=40, zorder=1))
    ax.text(0.15, 1.05, "reflection output\nreturns to reasoning", ha="center", va="center",
            fontsize=10.5, color=INK2, style="italic")

    for (x, y), name, n in zip(pos, stages, fails):
        frac = n / norm
        fc = SEQ(0.08 + 0.85 * frac)
        tc = SURFACE if frac > 0.45 else INK
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle="round,pad=0.02,rounding_size=0.18",
                                    fc=fc, ec="#9fb9da", lw=1.3, zorder=3))
        ax.text(x, y + 0.14, name, ha="center", va="center", fontsize=13,
                weight="bold", color=tc, zorder=4, linespacing=0.95)
        lab = f"{n} papers fail here" if n else "0 papers"
        ax.text(x, y - 0.33 if "\n" not in name else y - 0.40, lab, ha="center", va="center",
                fontsize=10.5, color=tc, zorder=4)

    # entry channels, attached to the stage that reads them (per §2.1 definitions)
    def edge_pt(c, toward, a, b):
        dx, dy = toward[0] - c[0], toward[1] - c[1]
        t = min(a / abs(dx) if dx else 1e9, b / abs(dy) if dy else 1e9)
        return (c[0] + dx * t, c[1] + dy * t)

    entries = [
        ("User query + system prompt", "56.8% of located attacks", 0, (0.0, 5.35)),
        ("Retrieved documents (RAG)", "17 papers", 1, (5.35, 4.9)),
        ("Persistent memory", "count not given; 1 benchmark", 1, (5.35, 4.9 - 2.15)),
        ("Tool / API responses", "24 papers", 6, (-5.35, 1.75)),
        ("Environment observation", "20 papers", 6, (-5.35, -2.4)),
        ("Reflection output", "0 papers", 7, (-5.3, 4.9)),
        ("Inter-agent messages", "5 papers · enter the whole loop", None, (5.35, -1.75)),
    ]
    for title, sub, tgt, (ex, ey) in entries:
        hot = sub.startswith(("56.8", "24", "20", "17"))
        ax.add_patch(FancyBboxPatch((ex - 1.75, ey - 0.5), 3.5, 1.0,
                                    boxstyle="round,pad=0.02,rounding_size=0.15",
                                    fc="#fdf0ea" if hot else "#f4f3f0",
                                    ec=ORANGE if hot else "#bdbcb7", lw=1.3, zorder=5))
        ax.text(ex, ey + 0.18, title, ha="center", va="center", fontsize=11.5,
                weight="bold", color=INK, zorder=6)
        ax.text(ex, ey - 0.2, sub, ha="center", va="center", fontsize=10.5, color=INK2, zorder=6)
        tx, ty = pos[tgt] if tgt is not None else (0.0, 0.0)
        p0 = edge_pt((ex, ey), (tx, ty), 1.8, 0.55)
        p1 = edge_pt((tx, ty), (ex, ey), w / 2 + 0.1, h / 2 + 0.1) if tgt is not None             else (1.0, -0.55)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=16,
                                     color=ORANGE if hot or tgt is None else "#9b9a95", lw=1.6,
                                     ls="-" if tgt is not None else (0, (4, 3)),
                                     shrinkA=0, shrinkB=0, zorder=6))
    fig.text(0.02, 0.965, "Where attacks enter the agent loop, and where it breaks",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.935, "Orange: entry channels (74 threat papers, §4.4.1). "
             "Box shade: papers whose attack first lands at that stage (78 papers, §4.4.2).",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig02_agent_loop.png",
           source=SRC + "; §2.1, §4.4.1–4.4.2, Fig. 8–9a, pp. 5, 25–27",
           note="Channel-to-stage arrows follow the survey's stage definitions (§2.1); "
                "a paper can use several channels.")


# ======================================================== fig 03 ASR
def fig03_asr():
    rows = [  # (class, system, value, qualifier, page)
        ("Injection", "ToolHijacker", 96.7, "up to", 19),
        ("Injection", "WebInject", 96.0, "over", 19),
        ("Injection", "HOUYI (31 of 36 apps)", 86.1, "", 19),
        ("Injection", "ASB mixed attack", 84.3, "avg, 13 LLMs", 19),
        ("Injection", "MCTS fuzzing on AgentDojo", 71.0, "", 19),
        ("MCP tools", "MCP-SafetyBench, host side", 81.94, "avg, 13 LLMs", 23),
        ("MCP tools", "MCPTox", 72.8, "up to", 23),
        ("MCP tools", "MSB (MCP Security Bench)", 40.35, "avg", 23),
        ("Poisoning", "Poison-with-Style", 95.0, "", 20),
        ("Poisoning", "AgentPoison (retrieval)", 81.2, "", 20),
        ("Poisoning", "MINJA", 76.8, "avg", 20),
        ("Jailbreak", "ROBOPAIR (3 robots)", 100.0, "", 21),
        ("Jailbreak", "LLMFuzzer (GPT-3.5)", 93.14, "ensemble", 20),
        ("Manipulation", "Role-identification (GPT-4o)", 92.0, "", 21),
        ("Manipulation", "AIOps telemetry attack", 90.0, "avg", 21),
        ("Manipulation", "AI2 action hijacking", 84.3, "avg", 21),
        ("Cognitive", "Reasoning backdoor (30 samples)", 100.0, "up to", 21),
        ("Red-teaming", "Planner/attacker vs Claude 3.7", 96.2, "", 22),
        ("Interface", "Pop-ups clicked by GUI agents", 86.0, "click rate", 22),
    ]
    import numpy as np
    fig = plt.figure(figsize=(13, 11))
    ax = fig.add_axes([0.36, 0.33, 0.57, 0.57])
    ax2 = fig.add_axes([0.36, 0.105, 0.57, 0.12])

    ys, labels, y, prev = [], [], 0, None
    group_pos = {}
    for cls, name, v, q, p in rows:
        if prev is not None and cls != prev:
            y += 0.7
        group_pos.setdefault(cls, []).append(y)
        ys.append(y)
        labels.append(name)
        prev = cls
        y += 1
    vals = [r[2] for r in rows]
    ax.barh(ys, vals, height=0.72, color=BLUE, edgecolor=SURFACE, linewidth=2)
    for yy, (cls, name, v, q, p) in zip(ys, rows):
        txt = f"{v:g}%" + (f"  ({q})" if q else "") + f"  p.{p}"
        ax.text(v + 1.0, yy, txt, va="center", fontsize=10.5, color=INK)
    ax.set_yticks(ys, labels, fontsize=11.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 128)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    clean(ax)
    for cls, yl in group_pos.items():
        ax.text(-0.62, (yl[0] + yl[-1]) / 2, cls, transform=ax.get_yaxis_transform(),
                ha="left", va="center", fontsize=12, weight="bold", color=INK)
    ax.set_title("A   Headline attack success rates, by threat class", pad=14)

    # panel B: same attack, two metrics
    pairs = [("AgentPoison", 81.2, 62.6), ("WASP", 85.7, 16.7)]
    yb = np.arange(len(pairs))
    ax2.barh(yb - 0.19, [p[1] for p in pairs], height=0.36, color=BLUE, edgecolor=SURFACE,
             linewidth=2, label="intermediate (retrieval / hijack) ASR")
    ax2.barh(yb + 0.19, [p[2] for p in pairs], height=0.36, color=ORANGE, edgecolor=SURFACE,
             linewidth=2, label="end-to-end ASR")
    for i, (n, a, b) in enumerate(pairs):
        ax2.text(a + 1, i - 0.19, f"{a:g}%", va="center", fontsize=10.5)
        ax2.text(b + 1, i + 0.19, f"{b:g}%", va="center", fontsize=10.5)
    ax2.set_yticks(yb, [p[0] for p in pairs], fontsize=11.5, color=INK)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 128)
    ax2.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    clean(ax2)
    ax2.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=10.5)
    ax2.set_title("B   Same attack, two metrics (§4.4.5, p. 29)", pad=30, fontsize=13.5)

    fig.text(0.02, 0.965, "Attack success rates are high, but they are not one measurement",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.937, "Each bar is a figure reported in a different paper, on a different "
             "benchmark and model. Compare within a row, not across rows.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig03_asr.png", source=SRC + "; §4.1–4.2, pp. 19–23, 29",
           note="Qualifiers are the survey's own: 'up to' and 'over' are peaks, 'avg' is an "
                "average across models or attack types. The pop-up value is a click rate, not ASR.")


# ======================================================== fig 04 attention matrix
def fig04_attention():
    import numpy as np
    cols = ["Input\nsanitization", "Structured\nqueries", "LLM\nmonitoring", "Moving\ntarget",
            "Capability-\nscoped exec.", "Crypto\nverification", "Dataset\nsanitation",
            "Sandbox &\nformal", "Red-team\nsimulation", "Consensus\n& vaccine"]
    rows = ["Injection", "Prompt infection", "Poisoning", "Jailbreak",
            "Agent manipulation", "Pre-execution", "Red-teaming"]
    M = np.array([
        [5, 8, 5, 1, 7, 1, 0, 0, 3, 0],
        [0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
        [4, 0, 2, 1, 1, 3, 0, 0, 1, 3],
        [3, 0, 2, 1, 0, 0, 0, 0, 3, 0],
        [0, 0, 10, 0, 1, 0, 0, 3, 2, 2],
        [2, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 0, 0, 0, 4, 0],
    ])
    fig = plt.figure(figsize=(14, 8.6))
    ax = fig.add_axes([0.17, 0.17, 0.72, 0.62])
    ax.imshow(M, cmap=SEQ, vmin=0, vmax=10, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, str(v) if v else "·", ha="center", va="center",
                    fontsize=14 if v else 13, weight="bold" if v else "normal",
                    color=SURFACE if v >= 6 else (INK if v else MUTED))
    ax.set_xticks(range(len(cols)), cols, fontsize=11, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(rows)), rows, fontsize=12.5, color=INK)
    ax.set_xticks(np.arange(-0.5, len(cols)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(rows)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2.5)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    tot = M.sum(axis=1)
    for i, t in enumerate(tot):
        ax.text(len(cols) - 0.3, i, f"{t}", ha="left", va="center", fontsize=12.5, color=INK2)
    ax.text(len(cols) - 0.3, -0.85, "papers", ha="left", va="center", fontsize=11, color=INK2)

    fig.text(0.02, 0.955, "Research attention per attack/defense pair, not effectiveness",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.922, "Each cell counts papers whose primary attack and primary defense meet "
             "there (81 papers). A dark cell means many papers, not a strong defense.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig04_attention_matrix.png", source=SRC + "; §6, Fig. 12, p. 39",
           note="'·' = no paper. Agent manipulation is studied mostly with LLM monitors (10); "
                "dataset sanitation is never anyone's primary defense here.")


# ======================================================== fig 05 inherited / amplified / native
def fig05_native():
    import numpy as np
    rows = ["Injection", "Poisoning & extraction", "Jailbreak", "Agent manipulation",
            "Pre-execution cognitive", "Red-teaming"]
    inh = np.array([9, 7, 11, 2, 1, 2])
    amp = np.array([3, 1, 9, 0, 1, 0])
    nat = np.array([23, 7, 0, 14, 5, 7])
    fig = plt.figure(figsize=(13, 7.6))
    ax = fig.add_axes([0.24, 0.20, 0.70, 0.60])
    y = np.arange(len(rows))
    segs = [(inh, BLUE, "Inherited from the base LLM"),
            (amp, ORANGE, "Amplified by the agent setting"),
            (nat, AQUA, "Agent-native")]
    left = np.zeros(len(rows))
    for vals, col, lab in segs:
        ax.barh(y, vals, left=left, color=col, edgecolor=SURFACE, linewidth=2, height=0.66, label=lab)
        for yi, (l, v) in enumerate(zip(left, vals)):
            if v >= 2:
                ax.text(l + v / 2, yi, str(v), ha="center", va="center", fontsize=12,
                        color=SURFACE if col != ORANGE else INK, weight="bold")
        left += vals
    for yi, t in enumerate(left):
        ax.text(t + 0.5, yi, f"{int(t)}", va="center", fontsize=11.5, color=INK2)
    ax.set_yticks(y, rows, fontsize=12.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("Threat labels (a paper can carry several)", fontsize=11.5, color=INK2)
    clean(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=3, frameon=False, fontsize=11.5)
    fig.text(0.02, 0.955, "About half of all threat labels are agent-native",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.922, "Across all 111 labels: 50.5% agent-native, 41.4% inherited or amplified, "
             "8.1% unclassified (not shown). Jailbreaks are the exception: none are native.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig05_inherited_native.png", source=SRC + "; §4.4.3, Fig. 9b, pp. 27–28",
           note="Counts read from the rendered Fig. 9b, because PDF text extraction dropped "
                "zero-valued segments.")


# ======================================================== fig 06 lifecycle + autonomy
def fig06_lifecycle():
    import numpy as np
    red = [("Reconnaissance", 35), ("Scanning", 22), ("Vulnerability discovery", 52),
           ("Exploitation", 50), ("Post-exploitation", 13), ("Persistence", 2), ("Exfiltration", 3)]
    blue = [("Detection", 27), ("Triage", 9), ("Threat hunting", 11), ("Forensics", 17),
            ("Root-cause analysis", 10), ("Remediation", 19), ("Response", 6)]
    fig = plt.figure(figsize=(15, 8.4))
    axr = fig.add_axes([0.13, 0.42, 0.33, 0.43])
    axb = fig.add_axes([0.63, 0.42, 0.33, 0.43])
    axa = fig.add_axes([0.13, 0.10, 0.83, 0.17])

    for ax, data, col, title in ((axr, red, ORANGE, "A   Offensive (red-team) papers per stage"),
                                 (axb, blue, BLUE, "B   Defensive (blue-team) papers per stage")):
        y = np.arange(len(data))
        ax.barh(y, [d[1] for d in data], color=col, height=0.66, edgecolor=SURFACE, linewidth=2)
        for yi, (_, v) in enumerate(data):
            ax.text(v + 0.8, yi, str(v), va="center", fontsize=11.5, color=INK)
        ax.set_yticks(y, [d[0] for d in data], fontsize=11.5, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(0, 60)
        clean(ax)
        ax.set_title(title, fontsize=13.5)

    # autonomy (ordinal ramp, levels 0..3)
    lv_cols = ["#cde2fb", "#86b6ef", "#3987e5", "#184f95"]
    data = {"Offensive (47 systems)": [0, 3, 5, 39], "Defensive (35 systems)": [5, 15, 10, 5]}
    for yi, (name, counts) in enumerate(data.items()):
        tot = sum(counts)
        left = 0
        for lv, c in enumerate(counts):
            if c == 0:
                continue
            frac = c / tot * 100
            axa.barh(yi, frac, left=left, color=lv_cols[lv], edgecolor=SURFACE, linewidth=2, height=0.62)
            if frac >= 5:
                axa.text(left + frac / 2, yi, f"L{lv}: {c}", ha="center", va="center", fontsize=11,
                         color=SURFACE if lv >= 2 else INK, weight="bold")
            left += frac
    axa.set_yticks([0, 1], list(data.keys()), fontsize=11.5, color=INK)
    axa.invert_yaxis()
    axa.set_xlim(0, 100)
    axa.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    clean(axa)
    axa.set_title("C   Autonomy level granted (L0 advice only … L3 end-to-end): 83.0% of offensive systems "
                  "are L3, 14.3% of defensive", fontsize=13.5)

    fig.text(0.02, 0.955, "Attackers' agents get the keys; defenders' agents get a supervisor",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.922, "Offensive work piles up at discovery and exploitation; persistence and "
             "exfiltration barely appear. Only 17.0% of offensive systems have an approval gate vs 85.7% of defensive.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig06_lifecycle_autonomy.png", source=SRC + "; §3.4, Fig. 5–6, pp. 14–16")


# ======================================================== fig 07 ablation + HPTSA
def fig07_ablation():
    fig = plt.figure(figsize=(14, 7.4))
    ax = fig.add_axes([0.095, 0.20, 0.55, 0.60])
    axh = fig.add_axes([0.75, 0.20, 0.22, 0.60])

    labels = ["Standalone\nGPT-4o", "+ goal moved into\nsystem prompt",
              "+ multi-step\naction generation", "+ event\nstream"]
    vals = [100, 93.3, 73.3, 53.3]
    shades = ["#184f95", "#256abf", "#3987e5", "#6da7ec"]
    x = range(len(vals))
    ax.bar(x, vals, color=shades, width=0.62, edgecolor=SURFACE, linewidth=2)
    for xi, v in zip(x, vals):
        ax.text(xi, v + 2, f"{v:g}%", ha="center", fontsize=14, weight="bold")
    for xi in range(1, 4):
        d = vals[xi - 1] - vals[xi]
        ax.text(xi, vals[xi] + 8.5, f"−{d:.1f} pts", ha="center", fontsize=11.5, color=RED)
    ax.set_xticks(list(x), labels, fontsize=11.5, color=INK)
    ax.set_ylim(0, 116)
    ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("Clear-denial rate on the same\nmalicious instructions", fontsize=11.5, color=INK2)
    clean(ax, grid_axis="y")
    ax.set_title("A   Same model, more harness: refusals fall (Chiang et al., §4.3, p. 25)", fontsize=13.5)

    axh.bar([0, 1], [1, 13], color=[GRID, ORANGE], width=0.6, edgecolor=SURFACE, linewidth=2)
    axh.text(0, 1.4, "1×", ha="center", fontsize=14, weight="bold")
    axh.text(1, 13.4, "13×", ha="center", fontsize=14, weight="bold")
    axh.set_xticks([0, 1], ["without\nhierarchical\ncoordination", "full\nHPTSA"], fontsize=11.5, color=INK)
    axh.set_ylim(0, 15.5)
    axh.set_yticks([0, 5, 10])
    axh.set_ylabel("pass@1, relative", fontsize=11.5, color=INK2)
    clean(axh, grid_axis="y")
    axh.set_title("B   HPTSA: scaffold as weapon", fontsize=13.5)

    fig.text(0.02, 0.955, "Adding autonomy erodes safety and adds capability, with the model held fixed",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.922, "With the goal left in the user turn, every jailbreak failed even with the other "
             "components in place. Disabling goal paraphrasing recovered 13.3 points.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig07_ablation_hptsa.png", source=SRC + "; §3.4 p. 18, §4.3 pp. 24–25, §4.4.3 p. 28",
           note="Panel B: HPTSA zero-day web exploitation loses a factor of 13 in pass@1 without its "
                "hierarchical coordination. The survey reports the ratio, not absolute pass@1.")


# ======================================================== fig 08 MCP trust boundary (assignment4)
def fig08_trust_boundary():
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    fig = plt.figure(figsize=(16, 8.6))
    ax = fig.add_axes([0.0, 0.07, 1.0, 0.83])
    ax.set_xlim(0, 16)
    ax.set_ylim(0.6, 8.2)
    ax.axis("off")

    def box(x0, y0, x1, y1, fc=SURFACE, ec="#b9b8b3", lw=1.3, ls="-", z=2):
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0,
                                    boxstyle="round,pad=0.02,rounding_size=0.18",
                                    fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))

    def node(x0, y0, x1, y1, title, lines, fc=SURFACE, ec="#b9b8b3", lw=1.3, ls="-", tcol=INK):
        box(x0, y0, x1, y1, fc, ec, lw, ls, z=3)
        cx = (x0 + x1) / 2
        n = len(lines)
        top = (y0 + y1) / 2 + 0.2 * n
        ax.text(cx, top, title, ha="center", va="center", fontsize=13, weight="bold", color=tcol, zorder=4)
        for i, (t, c) in enumerate(lines):
            ax.text(cx, top - 0.4 * (i + 1), t, ha="center", va="center", fontsize=11.5,
                    color=c, zorder=4, family="DejaVu Sans Mono")

    def arrow(p0, p1, col, label=None, lp=None, ls="-", lw=2.0, rad=0.0, lcol=None, ha="center"):
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=18, color=col, lw=lw,
                                     ls=ls, connectionstyle=f"arc3,rad={rad}", zorder=5,
                                     shrinkA=0, shrinkB=0))
        if label:
            ax.text(*lp, label, ha=ha, va="center", fontsize=11.5, color=lcol or col, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec="none"))

    # MCP server
    box(0.3, 1.2, 4.5, 7.6, fc="#f4f3f0", ec="#9b9a95", lw=1.4)
    ax.text(0.5, 7.25, "MCP server", fontsize=14, weight="bold", ha="left")
    ax.text(0.5, 6.88, "mcp_server.py · offers every tool", fontsize=11, color=INK2, ha="left")
    node(0.6, 4.4, 4.2, 6.4, "tools/list",
         [("show_rooms_app", INK), ("book_room", INK), ("cancel_all_bookings", RED)])
    node(0.6, 1.6, 4.2, 3.5, "ui://rooms/dashboard",
         [("text/html;profile=mcp-app", INK), ("connectDomains: [ ]", INK)])

    # Host
    box(5.2, 0.9, 12.7, 7.9, fc="#e3eefb", ec=BLUE, lw=2.6, z=1)
    ax.text(5.45, 7.5, "Host", fontsize=14, weight="bold", ha="left")
    ax.text(5.45, 7.13, "page/app.js · owns the page, so the trust boundary is here",
            fontsize=11, color=INK2, ha="left")
    node(5.5, 5.4, 9.1, 6.7, "Host allow-list", [('ALLOWED_FROM_APP = {"book_room"}', INK)],
         fc="#fde6dc", ec=ORANGE, lw=2.6)
    node(5.5, 3.2, 9.1, 4.4, "error -32001", [("may not be called from an app", RED)],
         fc="#fbe3e3", ec=RED, lw=1.8)
    node(5.5, 1.2, 9.1, 2.75, "CSP built by the host", [("default-src 'none'", INK), ("connect-src 'none'", INK)])
    box(9.75, 1.9, 12.4, 6.4, fc=SURFACE, ec="#8a8985", lw=1.6, ls=(0, (5, 3)), z=2)
    ax.text(11.07, 6.05, "Sandboxed iframe", fontsize=12, weight="bold", ha="center", zorder=4)
    ax.text(11.07, 5.7, 'sandbox="allow-scripts"', fontsize=10.5, ha="center", color=INK2,
            family="DejaVu Sans Mono", zorder=4)
    node(10.0, 3.3, 12.15, 5.0, "App", [("agent-written", INK2), ("HTML", INK2)])

    # Network
    node(13.4, 3.55, 15.6, 4.75, "Network", [("any origin", INK2)], ls=(0, (5, 3)))

    # arrows
    arrow((4.2, 2.3), (5.5, 1.95), "#8a8985", "resources/read", (4.85, 2.55), lcol=INK2)
    arrow((9.1, 1.95), (10.6, 3.3), "#8a8985", "mounts the HTML", (10.25, 2.35), lcol=INK2)
    arrow((10.4, 5.0), (9.1, 5.85), INK2, "tools/call", (9.85, 5.15), lcol=INK)
    arrow((5.5, 6.05), (4.2, 5.75), AQUA, "book_room:\nforwarded", (4.85, 6.55), lcol="#13744f", lw=2.6)
    arrow((7.3, 5.4), (7.3, 4.4), RED, "cancel_all_bookings: refused", (7.3, 4.9), lw=2.6)
    arrow((12.15, 4.15), (13.4, 4.15), RED, None, ls=(0, (4, 2)), lw=2.6)
    ax.text(12.7, 4.15, "✕", fontsize=22, color=RED, ha="center", va="center", weight="bold", zorder=7,
            bbox=dict(boxstyle="circle,pad=0.1", fc=SURFACE, ec=RED, lw=1.5))
    ax.text(14.5, 3.05, "fetch() blocked\nby the CSP", fontsize=11.5, color=RED, ha="center", va="center")

    fig.text(0.02, 0.955, "Where my MCP host's allow-list sits (assignment4, theme 06)",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.918, "The server offers cancel_all_bookings. The host never forwards it from the app, "
             "and the app cannot reach the network or the server directly.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig08_mcp_trust_boundary.png",
           source="Source: my assignment4/06_mcp_apps (page/app.js, mcp_server.py, README real-run log). "
                  "Code names are verbatim.")


# ======================================================== fig 09 what I built vs survey
def fig09_mapping():
    g = graphviz.Digraph("map", graph_attr={
        "rankdir": "LR", "bgcolor": SURFACE, "dpi": "160", "fontname": "Helvetica",
        "pad": "0.35", "nodesep": "0.35", "ranksep": "1.6",
        "label": (f"<<font point-size='11' color='{MUTED}'>Left: this repo (assignment2/partA, assignment3, "
                  "assignment4/06_mcp_apps, assignment5/guard). Right: survey categories with v4 counts. "
                  "Edge text: where my version is weaker.</font>>"),
        "labeljust": "l", "labelloc": "b",
    }, node_attr={"shape": "box", "style": "rounded,filled", "fontname": "Helvetica",
                  "fontcolor": INK, "fontsize": "13", "color": "#b9b8b3", "width": "4.2"},
       edge_attr={"fontname": "Helvetica", "fontsize": "11.5", "color": "#6f6e6a", "fontcolor": RED,
                  "penwidth": "1.6"})

    mine = [
        ("a2s12", "assignment2 · stage 12", "regex rule table: allow / ask / deny,<br/>strictest verdict wins"),
        ("a2s13", "assignment2 · stage 13", "OS sandbox: Seatbelt (macOS), bubblewrap (Linux)"),
        ("a4", "assignment4 · theme 06", "MCP host allow-list, host-built CSP,<br/>sandboxed iframe"),
        ("a3", "assignment3 · agents C and E", "ADK McpToolset over stdio,<br/>tool_filter by tool name"),
        ("a5", "assignment5 · guard", "reward-hacking guard: 41 rejections<br/>in 5 categories"),
    ]
    survey = [
        ("cap", "Runtime protection · capability-scoped execution", "32.6% of 92 defense papers (§5.3.1)"),
        ("sbx", "Sandboxing & formal verification", "27.2% of defense papers; sandbox boundary 13 papers"),
        ("sbd", "Secure-by-design boundary", "ACE, Task Shield (§5.1.1)"),
        ("mcp", "Tool / API response entry point (MCP)", "24 papers; MCP-SafetyBench 81.94% host-side ASR"),
        ("nat", "Agent-native: specification & reward gaming", "under agent manipulation (§4.1.4, §4.4.3)"),
    ]
    with g.subgraph() as L:
        L.attr(rank="same")
        for nid, t, d in mine:
            L.node(nid, f"<<b>{t}</b><br/><font point-size='11.5' color='{INK2}'>{d}</font>>",
                   fillcolor="#e3eefb", color=BLUE)
    with g.subgraph() as R:
        R.attr(rank="same")
        for nid, t, d in survey:
            R.node(nid, f"<<b>{esc(t)}</b><br/><font point-size='11.5' color='{INK2}'>{d}</font>>",
                   fillcolor="#f4f3f0")
    edges = [
        ("a2s12", "cap", "reads command text only; my README says so"),
        ("a2s13", "sbx", "prints 'sandbox: none' on Windows, where it ran"),
        ("a4", "sbd", "allowed tool still takes any arguments"),
        ("a4", "cap", ""),
        ("a3", "mcp", "trusted local servers; outputs reach the model unchecked"),
        ("a5", "nat", "hacks planted by a scripted proposer; live LLM tried none"),
    ]
    for a, b, lab in edges:
        g.edge(a, b, label=f" {lab} " if lab else "", style="solid" if lab else "dashed")
    gv_render(g, "fig09_built_vs_survey.png")


# ======================================================== fig 10 defense strategies + gaps
def fig10_defenses():
    import numpy as np
    strat = [("LLM-based monitoring", 53.3), ("Capability-scoped execution", 32.6),
             ("Input sanitization & filtering", 31.5), ("Sandboxing & formal verification", 27.2),
             ("Red-team simulation", 21.7), ("Structured queries", 19.6),
             ("Cryptographic verification", 18.5), ("Consensus & vaccine seeding", 14.1),
             ("Dataset sanitation & DP", 6.5), ("Moving target defense", 5.4)]
    gaps = {  # Scalability, Robustness, Latency, Coverage (Fig. 10a / §5.3, p36)
        "Input sanitization & filtering": "MCMH", "Structured queries": "MCMH",
        "LLM-based monitoring": "MHCH", "Moving target defense": "HMHC",
        "Capability-scoped execution": "HMHH", "Cryptographic verification": "CMCM",
        "Dataset sanitation & DP": "HHMH", "Sandboxing & formal verification": "CMHH",
        "Red-team simulation": "HHHC", "Consensus & vaccine seeding": "HMCH",
    }
    lvl = {"M": 0, "H": 1, "C": 2}
    word = {"M": "Moderate", "H": "High", "C": "Critical"}
    gap_cols = ["#fbe0cf", "#f2a07c", "#c23b3a"]

    fig = plt.figure(figsize=(15, 8.2))
    ax = fig.add_axes([0.25, 0.10, 0.30, 0.68])
    axg = fig.add_axes([0.60, 0.10, 0.36, 0.68])
    y = np.arange(len(strat))
    ax.barh(y, [s[1] for s in strat], color=BLUE, height=0.66, edgecolor=SURFACE, linewidth=2)
    for yi, (_, v) in enumerate(strat):
        ax.text(v + 1, yi, f"{v:g}%", va="center", fontsize=11.5)
    ax.set_yticks(y, [s[0] for s in strat], fontsize=12, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 65)
    ax.set_xticks([0, 20, 40, 60], ["0%", "20%", "40%", "60%"])
    clean(ax)
    ax.set_title("A   Share of 92 defense papers", fontsize=13.5)

    dims = ["Scalability", "Robustness", "Latency", "Coverage"]
    for yi, (name, _) in enumerate(strat):
        for xi, ch in enumerate(gaps[name]):
            axg.add_patch(plt.Rectangle((xi - 0.47, yi - 0.42), 0.94, 0.84, color=gap_cols[lvl[ch]]))
            axg.text(xi, yi, word[ch], ha="center", va="center", fontsize=11,
                     color=SURFACE if ch == "C" else INK, weight="bold" if ch == "C" else "normal")
    axg.set_xlim(-0.5, 3.5)
    axg.set_ylim(len(strat) - 0.5, -0.5)
    axg.set_xticks(range(4), dims, fontsize=12, color=INK)
    axg.xaxis.tick_top()
    axg.set_yticks([])
    for s in axg.spines.values():
        s.set_visible(False)
    axg.tick_params(length=0)
    axg.set_title("B   Gap rating per strategy (none rated Low)", fontsize=13.5, pad=40)

    fig.text(0.02, 0.955, "Most defenses ask another model to watch the agent, and every strategy has a serious gap",
             fontsize=17, weight="bold", ha="left")
    fig.text(0.02, 0.922, "A paper can use several strategies (212 assignments over 92 papers). "
             "Eight of ten strategies have at least one Critical gap.",
             fontsize=11.5, color=INK2, ha="left")
    finish(fig, "fig10_defense_gaps.png", source=SRC + "; §5.3.1, Fig. 10a, pp. 35–36")


if __name__ == "__main__":
    fig01_taxonomy()
    fig02_agent_loop()
    fig03_asr()
    fig04_attention()
    fig05_native()
    fig06_lifecycle()
    fig07_ablation()
    fig08_trust_boundary()
    fig09_mapping()
    fig10_defenses()
