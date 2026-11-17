"""Build deck/slides.pptx with python-pptx, reusing the article figures.

Every number on a slide is from arXiv 2510.06445 v4 (section and page on the
slide) or from this repo. Speaker notes are written to be read aloud.
Run from the short_story folder:

    .\.venv\Scripts\python.exe scripts\make_deck.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "article" / "figures"
ASSETS = ROOT / "deck" / "assets"
OUT = ROOT / "deck" / "slides.pptx"

NAVY = RGBColor(0x14, 0x24, 0x40)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
RED = RGBColor(0xC2, 0x3B, 0x3A)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x52, 0x51, 0x4E)
TINT = RGBColor(0xEE, 0xF4, 0xFC)
WARM = RGBColor(0xFD, 0xEE, 0xE7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ICE = RGBColor(0xCA, 0xDC, 0xFC)
HEAD, BODY = "Cambria", "Calibri"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
COUNT = {"n": 0}


# ------------------------------------------------------------------ helpers
def text(slide, x, y, w, h, runs, size=18, color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, name=None):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, overrides)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(size * 0.45)
        segs = para if isinstance(para, list) else [(para, {})]
        for seg, ov in segs:
            r = p.add_run()
            r.text = seg
            f = r.font
            f.name = ov.get("font", font)
            f.size = Pt(ov.get("size", size))
            f.bold = ov.get("bold", bold)
            f.italic = ov.get("italic", italic)
            f.color.rgb = ov.get("color", color)
    return tb


def box(slide, x, y, w, h, fill=TINT, line=None, radius=0.08, name=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.adjustments[0] = radius
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1.5)
    shp.shadow.inherit = False
    if name:
        shp.name = name
    return shp


def circle_num(slide, x, y, n, fill=BLUE, d=Inches(0.55), size=18):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, d, d)
    c.fill.solid()
    c.fill.fore_color.rgb = fill
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(n)
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = BODY, Pt(size), True, WHITE


def picture(slide, path, x, y, w, h):
    """Fit an image inside the box, keeping its aspect ratio, centred."""
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = int(iw * scale), int(ih * scale)
    return slide.shapes.add_picture(str(path), x + (w - pw) // 2, y + (h - ph) // 2, pw, ph)


def new_slide(title=None, section=None, notes="", dark=False, source=None):
    COUNT["n"] += 1
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY if dark else WHITE
    if section:
        chip_w = Inches(0.25 + 0.12 * len(section))
        chip = box(s, MARGIN, Inches(0.38), chip_w, Inches(0.36), fill=ICE if dark else TINT, radius=0.5)
        tf = chip.text_frame
        tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = section.upper()
        r.font.name, r.font.size, r.font.bold, r.font.color.rgb = BODY, Pt(12), True, NAVY
    if title:
        text(s, MARGIN, Inches(0.8), W - 2 * MARGIN, Inches(0.95), title, size=34, font=HEAD,
             bold=True, color=WHITE if dark else NAVY, anchor=MSO_ANCHOR.MIDDLE, name="Title")
    if source:
        text(s, MARGIN, H - Inches(0.5), Inches(10.5), Inches(0.35), source, size=11,
             color=ICE if dark else MUTED)
    text(s, W - Inches(1.3), H - Inches(0.5), Inches(0.75), Inches(0.35), str(COUNT["n"]), size=11,
         color=ICE if dark else MUTED, align=PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = " ".join(notes.split())
    return s


def stat_card(slide, x, y, w, h, big, label, fill=TINT, big_color=NAVY, big_size=44, label_size=16,
              label_color=INK):
    box(slide, x, y, w, h, fill=fill)
    text(slide, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5), Inches(1.0), big, size=big_size,
         font=HEAD, bold=True, color=big_color)
    text(slide, x + Inches(0.25), y + Inches(0.2) + Pt(big_size * 1.45), w - Inches(0.5),
         h - Inches(0.3) - Pt(big_size * 1.45), label, size=label_size, color=label_color)


CONTENT_Y = Inches(1.9)
CONTENT_H = H - CONTENT_Y - Inches(0.65)
SRC = "Shahriar et al., arXiv 2510.06445 v4"

# ================================================================= slides
# 1 Title
s = new_slide(dark=True, notes="""
Hi, I'm Prachi, and this is my CMPE 297 short story. I read "A Survey on Agentic Security:
Applications, Threats and Defenses" by Shahriar and colleagues, published in TMLR this year. The title
of my talk comes from one experiment in that survey. GPT-4o refuses every malicious request on its own,
and refuses barely half of them once you put it inside an agent. I'll walk through the survey's map of
the field, the numbers it reports, and then what I think after comparing it with things I built in this
course.""")
text(s, MARGIN, Inches(1.5), Inches(11.5), Inches(2.4),
     "GPT-4o Refuses Every Request, Until You Wrap It in an Agent", size=48, font=HEAD, bold=True,
     color=WHITE)
text(s, MARGIN, Inches(4.0), Inches(11.5), Inches(0.8),
     "Reading “A Survey on Agentic Security: Applications, Threats and Defenses”",
     size=22, color=ICE, italic=True)
text(s, MARGIN, Inches(5.2), Inches(11.5), Inches(1.2),
     ["Prachi  ·  CMPE 297 short story",
      "Shahriar, Rahman, Ahmed, Sadeque, Parvez · TMLR 2026 · arxiv.org/abs/2510.06445"],
     size=18, color=WHITE)

# 2 The paper
s = new_slide("One survey, 274 papers, three questions", "The paper", source=SRC + "; App. A–B, pp. 67–68", notes="""
Some context on the paper. It's by five authors from BRAC University and the Qatar Computing Research
Institute, and the version I read is version four, published in TMLR. It covers 274 papers from
January 2023 to May 2026. It organises them into three pillars, which are three questions:
what can agents do for security, how do agents get attacked, and how do you defend them. The counts
overlap, 113, 86 and 123, because some papers sit in more than one pillar. What I liked is that the
authors coded every paper on the same fields, so they can count things across the whole field.""")
cw = Inches(2.85)
gap = Inches(0.25)
for i, (big, lab) in enumerate([("274", "papers, deduplicated"), ("3", "pillars: applications, threats, defenses"),
                                ("2026", "corpus window: Jan 2023 to May 2026"), ("TMLR", "published version, v4, Oct 2026")]):
    stat_card(s, MARGIN + i * (cw + gap), CONTENT_Y + Inches(0.2), cw, Inches(2.3), big, lab)
text(s, MARGIN, Inches(4.9), Inches(12), Inches(1.5),
     [[("Pillar counts overlap: ", {"bold": True}), ("113 applications · 86 threats · 123 defenses", {})],
      [("Authors: ", {"bold": True}), ("BRAC University and Qatar Computing Research Institute", {})]],
     size=20)

# 3 The hook
s = new_slide("Same model, more harness: refusals fall by almost half", "The hook",
              source=SRC + "; §4.3, p. 25 (Chiang et al.)", notes="""
Chiang and colleagues took GPT-4o and a fixed set of malicious instructions, and
measured the clear-denial rate, which is how often the model refuses outright. On its own, GPT-4o
refused all of them, a hundred percent. Then they added agent parts one at a time. Moving the user's goal
into the system prompt dropped it to 93.3 percent. Adding multi-step action generation took it to 73.3.
Adding an event stream, the running log of actions and observations, took it to 53.3. The model never
changed, only the scaffolding around it.""")
picture(s, ASSETS / "fig07_left.png", MARGIN, CONTENT_Y, Inches(8.0), CONTENT_H)
box(s, Inches(9.0), CONTENT_Y + Inches(0.5), Inches(3.7), Inches(3.9), fill=WARM)
text(s, Inches(9.25), CONTENT_Y + Inches(0.7), Inches(3.3), Inches(3.6),
     [[("100%", {"size": 54, "bold": True, "font": HEAD, "color": NAVY})],
      [("refused, model alone", {"size": 18})],
      [("53.3%", {"size": 54, "bold": True, "font": HEAD, "color": RED})],
      [("refused, full harness", {"size": 18})]], size=18)

# 4 Why it drops
s = new_slide("Why it drops: trust and step-by-step checks", "The hook",
              source=SRC + "; §4.3, pp. 24–25", notes="""
The survey gives two reasons. The first is trust. Models are trained to defer more to the system prompt
than to the user. When an orchestration layer rewrites the user's goal into the system prompt, that goal
gets promoted to a higher level of trust before the model has judged it. And when the researchers left
the goal in the user turn, every jailbreak failed. The second reason is how steps get checked.
Generating actions step by step was 20 points more permissive than planning up front, because each
step is judged alone and nobody looks at the combined intent.""")
for i, (head, lines, fill) in enumerate([
        ("Trust promotion", ["Orchestration rewrites the user's goal into the system prompt",
                             "Models defer to the system prompt",
                             "Goal left in the user turn: every jailbreak failed"], TINT),
        ("Step-by-step blindness", ["Multi-step generation: 20 points more permissive than planning first",
                                    "Each step is judged alone",
                                    "The combined intent is never checked"], WARM)]):
    x = MARGIN + i * Inches(6.2)
    box(s, x, CONTENT_Y + Inches(0.1), Inches(5.9), Inches(4.5), fill=fill)
    circle_num(s, x + Inches(0.3), CONTENT_Y + Inches(0.4), i + 1, fill=BLUE if i == 0 else ORANGE)
    text(s, x + Inches(1.05), CONTENT_Y + Inches(0.38), Inches(4.6), Inches(0.7), head, size=26,
         font=HEAD, bold=True, color=NAVY)
    text(s, x + Inches(0.4), CONTENT_Y + Inches(1.35), Inches(5.2), Inches(3.1),
         [[("•  " + l, {})] for l in lines], size=20)

# 5 The obvious fix fails
s = new_slide("The obvious fix barely moves the number", "The hook",
              source=SRC + "; §4.2.1, p. 23 (MCP-SafetyBench)", notes="""
So the obvious fix is to tell the model to be careful. MCP-SafetyBench tested exactly that. MCP, the
Model Context Protocol, is the standard way agents now connect to external tool servers. Across 245
tasks and 13 models, attacks on the host side succeeded 81.94 percent of the time on average. Adding
safety prompts lowered that by 1.22 percent, which the survey reports as statistically insignificant.
So safety drops as autonomy goes up, and asking the model to be safe doesn't fix it.""")
cards = [("81.94%", "average host-side attack success", TINT, NAVY),
         ("−1.22%", "change from adding safety prompts, reported as not significant", WARM, RED),
         ("245 · 13", "tasks · models", TINT, NAVY)]
cw = Inches(3.8)
for i, (big, lab, fill, col) in enumerate(cards):
    stat_card(s, MARGIN + i * (cw + Inches(0.3)), CONTENT_Y + Inches(0.3), cw, Inches(2.8), big, lab,
              fill=fill, big_color=col, big_size=54, label_size=18)
text(s, MARGIN, Inches(5.5), Inches(12), Inches(0.8),
     "Safety drops as autonomy rises, and prompting for safety doesn't bring it back.", size=22,
     italic=True, color=NAVY)

# 6 Which version
s = new_slide("Which version I read: v4, and the conclusion changed", "Reading note",
              source="arXiv 2510.06445 v3 (Jun 2026) and v4 (31 Oct 2026, TMLR)", notes="""
A quick note on versions. The brief pointed me to version three from June. The version arXiv serves now
is version four from October, the TMLR one, and that's what I used. The numbers moved: 274 papers
instead of "over 260", 56.8 percent of attacks through the prompt instead of 55, 124 benchmarks instead
of 108. The one that matters is the conclusion. Version three says the most-attacked stages are
perception and action selection. Version four says reasoning and action selection. The paper doesn't
say why, and I won't guess. If you cite a living survey, pin the version, like you'd pin a library.""")
rows = [("Corpus", "“over 260”", "274"), ("Attacks via prompt", "55%", "56.8%"),
        ("Distinct benchmarks", "108", "124"),
        ("Most-attacked stages", "perception + action selection", "reasoning + action selection")]
tbl = s.shapes.add_table(len(rows) + 1, 3, MARGIN, CONTENT_Y + Inches(0.1), Inches(9.0), Inches(3.9)).table
tbl.columns[0].width, tbl.columns[1].width, tbl.columns[2].width = Inches(3.0), Inches(3.0), Inches(3.0)
for r, row in enumerate([("", "v3 (Jun 2026)", "v4 (Oct 2026)")] + rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if r == 0 else (WARM if r == len(rows) else (TINT if r % 2 else WHITE))
        tf = cell.text_frame
        tf.text = ""
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = val
        run.font.name, run.font.size = BODY, Pt(19)
        run.font.bold = r == 0 or c == 0
        run.font.color.rgb = WHITE if r == 0 else INK
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
box(s, Inches(9.9), CONTENT_Y + Inches(0.1), Inches(2.85), Inches(3.9), fill=NAVY)
text(s, Inches(10.1), CONTENT_Y + Inches(0.35), Inches(2.5), Inches(3.5),
     [[("Pin the version", {"size": 26, "bold": True, "font": HEAD, "color": WHITE})],
      [("Citing v3 today means citing a conclusion the authors have replaced.", {"size": 18, "color": ICE})]],
     size=18)

# 7 The agent loop
s = new_slide("Where attacks enter, and where the loop breaks", "Why agents differ",
              source=SRC + "; §2.1, §4.4.1–4.4.2, Fig. 8–9a", notes="""
This is the agent loop the survey uses, eight stages from perception to reflection. The orange boxes are
the channels attacks come in through, and the shading shows the stage where an attack first does damage.
Those are different places. Most attacks still enter through the user
prompt or system prompt, but they take effect in reasoning, 54 papers, and in action selection, 41.
Up in the top left, reflection has zero on both counts. I'll come back to that at the end.""")
picture(s, FIG / "fig02_agent_loop.png", MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, CONTENT_H + Inches(0.1))

# 8 Entry vs failure + threat model
s = new_slide("Attacks need no special access", "Why agents differ",
              source=SRC + "; §4.4.1, §4.4.2, §4.4.4, pp. 25–28", notes="""
56.8 percent of attacks with a known entry point come in through the
user query or system prompt. The authors think part of that is convenience, since you don't need tools
or memory to study it. Where they land is different: reasoning and action selection. And the attacker
the field assumes is weak. Of 77 papers that state the attacker's access, 51.9 percent assume black-box
access and 27.3 percent assume no model access at all. That's why the survey calls agents fragile by
default: attacks work without special privileges.""")
cards = [("56.8%", "of located attacks enter through the user query or system prompt"),
         ("54 · 41", "papers whose attack first lands in reasoning · action selection"),
         ("51.9%", "assume black-box access; 27.3% assume no model access at all")]
cw = Inches(3.8)
for i, (big, lab) in enumerate(cards):
    stat_card(s, MARGIN + i * (cw + Inches(0.3)), CONTENT_Y + Inches(0.3), cw, Inches(3.2), big, lab,
              fill=WARM if i == 2 else TINT, big_size=54, label_size=19)

# 9 Taxonomy overview
s = new_slide("The taxonomy: three pillars", "Taxonomy", source=SRC + "; Fig. 1, p. 4", notes="""
This is the full taxonomy as a tree. You don't need to read every leaf. On the left are the three pillars.
Applications splits into red teaming, blue teaming and domain-specific work. Threats has seven attack
classes plus how attacks get evaluated. Defenses has four groups plus how defenses get evaluated. Each
leaf has two or three systems the survey names as examples. I'll go through each pillar on the next
few slides.""")
picture(s, FIG / "fig01_taxonomy.png", MARGIN, Inches(1.75), Inches(3.4), Inches(5.15))
for i, (head, sub, lines, fill) in enumerate([
        ("Applications", "113 papers · §3", "red team · blue team · domain-specific", TINT),
        ("Threats", "86 papers · §4", "7 attack classes · evaluation", WARM),
        ("Defenses", "123 papers · §5", "4 groups · evaluation", RGBColor(0xE3, 0xF5, 0xEC))]):
    y = Inches(1.95) + i * Inches(1.62)
    box(s, Inches(4.5), y, Inches(8.2), Inches(1.42), fill=fill)
    text(s, Inches(4.8), y + Inches(0.12), Inches(7.7), Inches(1.2),
         [[(head, {"size": 28, "bold": True, "font": HEAD, "color": NAVY}), ("    " + sub, {"size": 18, "color": MUTED})],
          [(lines, {"size": 20})]], size=20)

# 10 Applications
s = new_slide("Applications: agents as attackers and defenders", "Applications",
              source=SRC + "; §3.1–3.3; Fig. 5, pp. 14–15", notes="""
The applications pillar is about agents doing security work. Red teaming covers autonomous
penetration testing, finding vulnerabilities and generating exploits. Blue teaming covers detection,
threat hunting, forensics and patching. Domain-specific covers cloud, web and specialised areas like
healthcare. The research is lopsided. Vulnerability discovery has 52 papers and exploitation has 50.
Persistence has 2 and exfiltration has 3.""")
cols = [("Red teaming", ["Autonomous pentesting", "Vulnerability discovery", "Exploit generation"], ORANGE),
        ("Blue teaming", ["Detection and response", "Threat hunting", "Forensics and patching"], BLUE),
        ("Domain-specific", ["Cloud and infrastructure", "Web and application", "Healthcare, blockchain, privacy"], NAVY)]
cw = Inches(3.8)
for i, (head, items, col) in enumerate(cols):
    x = MARGIN + i * (cw + Inches(0.3))
    box(s, x, CONTENT_Y + Inches(0.1), cw, Inches(3.2), fill=TINT)
    circle_num(s, x + Inches(0.3), CONTENT_Y + Inches(0.35), i + 1, fill=col)
    text(s, x + Inches(1.0), CONTENT_Y + Inches(0.33), cw - Inches(1.1), Inches(0.6), head, size=24,
         font=HEAD, bold=True, color=NAVY)
    text(s, x + Inches(0.35), CONTENT_Y + Inches(1.15), cw - Inches(0.6), Inches(2.0),
         [[("•  " + it, {})] for it in items], size=19)
text(s, MARGIN, Inches(5.45), Inches(12), Inches(0.9),
     [[("Lopsided: ", {"bold": True}), ("vulnerability discovery 52 papers, exploitation 50 · persistence 2, exfiltration 3", {})]],
     size=21)

# 11 Dual-use economics
s = new_slide("Offensive agents now cost a few dollars a task", "Applications",
              source=SRC + "; §3.4.3, pp. 17–18", notes="""
This is where I slowed down. 60 of the 113 application systems, about 53 percent, carry offensive or
dual-use capability. Fang and colleagues report an agent that exploits 87 percent of one-day CVEs at
about 8 dollars 80 per exploit. CVE-Genie reproduces 428 of 841 CVEs at 2 dollars 77 each. ARTEMIS beat
9 of 10 human penetration testers in a live enterprise test, at about 18 dollars an hour against 60.
What I take from this is that money and expertise no longer hold an attacker back. And as the next
slide shows, this is also the side with the least human oversight.""")
cards = [("$8.80", "per exploit; 87% of one-day CVEs (Fang et al.)"),
         ("$2.77", "per CVE; 428 of 841 reproduced (CVE-Genie)"),
         ("$18/h", "vs $60/h for humans; beat 9 of 10 pen testers (ARTEMIS)")]
cw = Inches(3.8)
for i, (big, lab) in enumerate(cards):
    stat_card(s, MARGIN + i * (cw + Inches(0.3)), CONTENT_Y + Inches(0.3), cw, Inches(2.8), big, lab,
              fill=WARM, big_color=RED, big_size=56, label_size=19)
text(s, MARGIN, Inches(5.4), Inches(12), Inches(0.9),
     [[("60 of 113", {"bold": True}), (" application systems (53.1%) are offensive or dual-use. Expertise and budget are no longer the bottleneck.", {})]],
     size=21)

# 12 Autonomy asymmetry
s = new_slide("Who gets full autonomy: offense, not defense", "Applications",
              source=SRC + "; §3.4.2, Fig. 5–6, pp. 14–16", notes="""
This figure shows the autonomy split. Panel C at the bottom is the one to look at. 83 percent of
offensive systems run end to end at level three, with minimal oversight. Only 14.3 percent of defensive
systems do. Most defensive systems sit at level one or two, where a human approves the important steps.
Only 17 percent of offensive systems keep a human approval gate, against 85.7 percent of
defensive ones.""")
picture(s, FIG / "fig06_lifecycle_autonomy.png", MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, CONTENT_H + Inches(0.1))

# 13 Synthesis
s = new_slide("Autonomy erodes refusals, and offense gets most of it", "My reading",
              source=SRC + "; §4.3 p. 25 and §3.4.2 p. 16", notes="""
The ablation shows refusals falling as autonomy
is added. The autonomy data shows that offensive systems get full autonomy 83 percent of the time, and
defensive systems 14.3 percent. So the capability that most weakens a model's refusals is the one handed
most freely to attack tools, and least to the defensive tools meant to counter them. These are two separate results from different parts of the survey, measured on different systems.
It's a pattern I noticed, not a controlled comparison.""")
stat_card(s, MARGIN, CONTENT_Y + Inches(0.1), Inches(5.8), Inches(2.6), "100% → 53.3%",
          "clear denial as autonomy is added (§4.3)", big_size=48, label_size=19)
stat_card(s, Inches(6.9), CONTENT_Y + Inches(0.1), Inches(5.8), Inches(2.6), "83.0% vs 14.3%",
          "offensive vs defensive systems at full autonomy (§3.4.2)", fill=WARM, big_color=RED,
          big_size=48, label_size=19)
box(s, MARGIN, Inches(4.95), Inches(12.1), Inches(1.4), fill=WHITE, line=MUTED)
text(s, MARGIN + Inches(0.3), Inches(5.05), Inches(11.5), Inches(1.2),
     [[("Caveat: ", {"bold": True, "color": RED}),
       ("these are separate results from different sections and different systems. A pattern, not a controlled comparison.", {})]],
     size=21, anchor=MSO_ANCHOR.MIDDLE)

# 14 Threats
s = new_slide("Threats: seven ways in", "Threats", source=SRC + "; §4.1, pp. 19–23", notes="""
The threats pillar has seven attack classes. Injection hides instructions in content the agent reads.
Poisoning corrupts memory, retrieval stores or training data. Jailbreaks get past safety training.
Agent manipulation hijacks goals or actions, and includes reward hacking. Pre-execution cognitive
attacks bend the agent's reasoning or plan before any tool runs. Red-teaming attacks are automated attack
generation aimed at agents. And interface-level attacks target agents that operate a screen, like pop-ups
that agents click.""")
classes = [("Injection", "instructions hidden in content the agent reads"),
           ("Poisoning & extraction", "memory, retrieval stores, training data"),
           ("Jailbreak", "getting past safety training"),
           ("Agent manipulation", "goal and action hijacking, reward hacking"),
           ("Pre-execution cognitive", "bending reasoning or plans before tools run"),
           ("Red-teaming attacks", "automated attack generation against agents"),
           ("Interface-level", "attacks on agents that operate a GUI")]
for i, (head, sub) in enumerate(classes):
    col, row = (0, i) if i < 4 else (1, i - 4)
    x = MARGIN + col * Inches(6.2)
    y = CONTENT_Y + row * Inches(1.18)
    circle_num(s, x, y + Inches(0.1), i + 1, fill=ORANGE)
    text(s, x + Inches(0.75), y, Inches(5.3), Inches(1.1),
         [[(head, {"bold": True, "size": 22, "color": NAVY})], [(sub, {"size": 17, "color": MUTED})]], size=18)

# 15 Inherited / amplified / native
s = new_slide("Half the threat labels are agent-native", "Threats",
              source=SRC + "; §4.4.3, Fig. 9b, pp. 27–28", notes="""
This is the analysis I found most useful. Each threat gets labelled by origin. Inherited means it
already worked on the bare model. Amplified means the agent setting makes it worse. Agent-native means
it couldn't exist without the scaffold, things like memory, tools or other agents. Across 111 labels,
50.5 percent are agent-native. Jailbreaks are the exception, with no native cases at all. Agent
manipulation is the opposite, almost entirely native, and that's where reward hacking sits.""")
picture(s, FIG / "fig05_inherited_native.png", MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, CONTENT_H + Inches(0.1))

# 16 Defenses
s = new_slide("Defenses: mostly an LLM watching an LLM", "Defenses",
              source=SRC + "; §5.1, §5.3.1–5.3.2, pp. 30–36", notes="""
The defenses pillar has four groups. Secure-by-design isolates untrusted data in the architecture.
Multi-agent security uses consensus and debate between agents. Runtime protection means guardrails
that intercept behaviour during execution. Security operations covers verification, auditing and incident
response. 53.3 percent of the 92 analysed defense
papers use a second LLM to watch the first. A human in the loop is the primary trust boundary in
only 2 papers.""")
groups = [("Secure-by-design", "isolate untrusted data in the architecture"),
          ("Multi-agent security", "consensus and debate between agents"),
          ("Runtime protection", "guardrails during execution"),
          ("Security operations", "verification, auditing, response")]
for i, (head, sub) in enumerate(groups):
    y = CONTENT_Y + i * Inches(1.18)
    circle_num(s, MARGIN, y + Inches(0.1), i + 1, fill=BLUE)
    text(s, MARGIN + Inches(0.75), y, Inches(6.0), Inches(1.1),
         [[(head, {"bold": True, "size": 22, "color": NAVY})], [(sub, {"size": 17, "color": MUTED})]], size=18)
stat_card(s, Inches(7.6), CONTENT_Y, Inches(5.1), Inches(2.5), "53.3%",
          "of 92 defense papers use an LLM-based monitor", big_size=60, label_size=19)
stat_card(s, Inches(7.6), CONTENT_Y + Inches(2.75), Inches(5.1), Inches(1.9), "2 papers",
          "use a human in the loop as the main trust boundary", fill=WARM, big_color=RED,
          big_size=40, label_size=18)

# 17 Defense gaps
s = new_slide("Every defense strategy has a serious gap", "Defenses",
              source=SRC + "; §5.3.1, Fig. 10a, pp. 34–36", notes="""
On the left is how often each of the ten defense strategies appears. On the right is the survey's own
gap rating for each one, on scalability, robustness, latency and coverage. No strategy is rated low on any
of the four. Eight of the ten have at least one critical gap. The authors' conclusion is to layer
defenses, because none of them holds up alone.""")
picture(s, FIG / "fig10_defense_gaps.png", MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, CONTENT_H + Inches(0.1))

# 18 Attention matrix
s = new_slide("Research attention per attack/defense pair", "Defenses",
              source=SRC + "; §6.1, Fig. 12, p. 39", notes="""
This matrix is easy to misread, so I put the caveat on the slide. Each cell counts papers whose main
attack and main defense meet there. A dark cell means a lot of papers studied that pairing. It does not
mean the defense works. The survey says this about its own figure. So ten papers using LLM monitors
against agent manipulation tells you what's popular. The empty column for dataset sanitation and the
single paper on prompt infection tell you where nobody has looked yet.""")
picture(s, FIG / "fig04_attention_matrix.png", MARGIN, CONTENT_Y - Inches(0.05), Inches(9.0), CONTENT_H)
box(s, Inches(9.85), CONTENT_Y + Inches(0.6), Inches(2.9), Inches(3.4), fill=WARM)
text(s, Inches(10.05), CONTENT_Y + Inches(0.8), Inches(2.55), Inches(3.1),
     [[("Counts attention, not effectiveness", {"size": 24, "bold": True, "font": HEAD, "color": RED})],
      [("A dark cell means many papers, not a strong defense.", {"size": 18})]], size=18)

# 19 The numbers
s = new_slide("The numbers: high attack success across every class", "Numbers",
              source=SRC + "; §4.1–4.2, pp. 19–23", notes="""
The survey doesn't have one leaderboard. It reports results paper by paper, so I collected the headline
attack success rates in one chart. They're high everywhere. ToolHijacker reaches up to 96.7 percent
against GPT-4o, and gets past two prevention defenses and two detection defenses to do it. MINJA poisons
memory to 76.8 percent using ordinary queries, with no write access. But each bar comes from a different
paper, benchmark and model, so compare within a row, not across.""")
picture(s, ASSETS / "fig03_panelA.png", MARGIN, CONTENT_Y - Inches(0.15), W - 2 * MARGIN, CONTENT_H + Inches(0.15))

# 20 MCP results
s = new_slide("MCP: stronger models were more vulnerable", "Numbers", source=SRC + "; §4.2.1, p. 23", notes="""
MCP gets its own slide because it's the surface I worked with. MCPTox poisoned tool descriptions on 45
real MCP servers and reached up to 72.8 percent attack success. The best-refusing model, Claude 3.7
Sonnet, refused under 3 percent of the time. MSB, the MCP Security Bench, averaged 40.35 percent, with a
peak of 76.5 percent. In both benchmarks, stronger models were more
vulnerable, which I didn't expect. A model that follows tool instructions well also follows malicious ones well.""")
cards = [("81.94%", "MCP-SafetyBench: average host-side attack success, 13 models"),
         ("72.8%", "MCPTox: peak, 45 real servers; best refusal under 3%"),
         ("40.35%", "MSB: average across 12 attack types; peak 76.5%")]
cw = Inches(3.8)
for i, (big, lab) in enumerate(cards):
    stat_card(s, MARGIN + i * (cw + Inches(0.3)), CONTENT_Y + Inches(0.2), cw, Inches(2.8), big, lab,
              big_size=54, label_size=19)
box(s, MARGIN, Inches(5.1), Inches(12.1), Inches(1.25), fill=WARM)
text(s, MARGIN + Inches(0.3), Inches(5.15), Inches(11.5), Inches(1.15),
     "Better tool-following meant better compliance with malicious tools.", size=22, bold=True,
     color=NAVY, anchor=MSO_ANCHOR.MIDDLE)

# 21 Numbers disagree
s = new_slide("The numbers do not agree with each other", "My reading",
              source=SRC + "; §4.1.2 p. 20, §4.2.1 p. 23, §4.4.1 p. 26, §4.4.5 p. 29", notes="""
This is where my own reading starts. The same attack gives very different numbers depending on where
you measure. AgentPoison is 81.2 percent at retrieval and 62.6 end to end. WASP is 85.7 percent at the
point of hijack and 16.7 when the attacker's goal has to finish, which its authors call security by
incompetence. Even inside the survey, MSB's peak is 76.5 percent in one section and 75.8 in another,
and AgentPoison's poison rate is under 0.1 percent in one place and under 1 in another. And there are 124
benchmarks, 93 used only once. The survey flags this fragmentation itself. My point is that cross-paper
comparisons are weaker than the tables make them look.""")
picture(s, ASSETS / "fig03_panelB.png", MARGIN, CONTENT_Y - Inches(0.15), Inches(7.6), Inches(2.6))
items = [("MSB peak", "76.5% (§4.2.1) vs 75.8% (§4.4.1)"),
         ("AgentPoison poison rate", "under 0.1% (§4.1.2) vs under 1% (§4.4.1)"),
         ("Benchmarks", "124 distinct; 93 used by one paper")]
for i, (head, sub) in enumerate(items):
    y = CONTENT_Y + i * Inches(1.5)
    box(s, Inches(8.5), y, Inches(4.25), Inches(1.3), fill=WARM if i < 2 else TINT)
    text(s, Inches(8.7), y + Inches(0.1), Inches(3.9), Inches(1.15),
         [[(head, {"bold": True, "size": 20, "color": NAVY})], [(sub, {"size": 17})]], size=17)
text(s, MARGIN, Inches(4.75), Inches(7.6), Inches(1.6),
     "Attack success rate is not a stable quantity across papers, so cross-paper comparison is weaker than the tables imply.",
     size=20, italic=True, color=NAVY)

# 22 What I built
s = new_slide("What I built, mapped to the survey", "My work",
              source="This repo: assignment2/partA, assignment3, assignment4/06_mcp_apps, assignment5", notes="""
Now for my own work. These are five things I built this semester, and the survey category each one
belongs to. The red text on each arrow is where my version is weaker than what the survey describes.
Stage 12's permission table is capability-scoped execution. Stage 13's sandbox is sandboxing. The
assignment 4 MCP host is a secure-by-design boundary. The assignment 3 agents sit right on the
tool-response entry point. And the assignment 5 guard is next to reward gaming, which the survey counts
as agent-native.""")
picture(s, FIG / "fig09_built_vs_survey.png", MARGIN, CONTENT_Y, W - 2 * MARGIN, CONTENT_H)

# 23 MCP trust boundary
s = new_slide("My MCP host: the allow-list is the boundary", "My work",
              source="assignment4/06_mcp_apps: page/app.js, mcp_server.py, README run log", notes="""
This is the piece I'm most confident in. The MCP server offers an admin tool, cancel all bookings. The
host only forwards tools on its allow-list, which contains just book room, and answers anything else with
error 32001. The host also builds a content security policy with connect-src none, so fetch fails
inside the sandboxed app. I saw both happen in a real browser run. This control is in code the model
can't argue with, which is what the 1.22 percent result says you need. The weakness is that an allowed tool
takes any arguments, and nothing asks the user to confirm.""")
picture(s, FIG / "fig08_mcp_trust_boundary.png", MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, CONTENT_H + Inches(0.1))

# 24 Where mine is weaker
s = new_slide("Where mine is weaker", "My work", source="assignment2 stage 13 · assignment3 · assignment5/guard", notes="""
Three things I want to say plainly. First, stage 13's sandbox wraps commands in Seatbelt on macOS or
bubblewrap on Linux, but on this Windows machine the banner prints sandbox none. Where my agent actually
ran, it did nothing. Second, assignment 3 filters MCP tools by name only. Nothing checks tool
descriptions or tool outputs. Third, the assignment 5 guard rejected 41 proposals, but those came from a
scripted proposer that planted the hacks on purpose. The live LLM never attempted one.""")
weak = [("Stage 13 sandbox", "prints “sandbox: none” on this Windows machine"),
        ("Assignment 3", "filters MCP tools by name only; no check on descriptions or outputs"),
        ("Assignment 5 guard", "41 rejections came from a scripted proposer that planted the hacks; the live LLM never attempted one")]
for i, (head, sub) in enumerate(weak):
    y = CONTENT_Y + i * Inches(1.55)
    box(s, MARGIN, y, Inches(12.1), Inches(1.35), fill=WARM)
    circle_num(s, MARGIN + Inches(0.3), y + Inches(0.4), i + 1, fill=RED)
    text(s, MARGIN + Inches(1.1), y + Inches(0.12), Inches(10.8), Inches(1.15),
         [[(head, {"bold": True, "size": 23, "color": NAVY})], [(sub, {"size": 19})]], size=19)

# 25 Reflection gap
s = new_slide("What I'd watch: the reflection stage nobody attacks", "What's next",
              source=SRC + "; §4.4.1–4.4.5, §7 · Du, arXiv 2603.07670 §9.3", notes="""
To finish, back to the loop. No paper attacks reflection, none record it as the stage that fails, and no
benchmark instruments it. I've built reflection twice. In stage 14, when the context fills, the model
writes a handoff note, and that note comes back as a user message. It summarises tool output, the
lowest-trust content, so a planted instruction can come back with user-level trust. That's the same
promotion from the opening slide. In SO-RSI, a confirmed finding in the inquiry memory triggers the next
edit and vetoes retries, so one false finding pushes a wrong change and blocks the right one. What I'll
watch for is the first benchmark that plants attacker text in a summary or self-diagnosis.""")
stat_card(s, MARGIN, CONTENT_Y, Inches(3.6), Inches(4.45), "0",
          "papers attack reflection; 0 benchmarks instrument it", fill=NAVY, big_color=WHITE,
          big_size=96, label_size=20, label_color=ICE)
for i, (head, sub) in enumerate([
        ("Stage 14 handoff note", "tool output → summary → re-enters as a user message"),
        ("SO-RSI inquiry memory", "one false “confirmed” finding pushes a wrong edit and vetoes the right fix")]):
    y = CONTENT_Y + i * Inches(1.6)
    box(s, Inches(4.5), y, Inches(8.2), Inches(1.4), fill=TINT)
    text(s, Inches(4.75), y + Inches(0.12), Inches(7.8), Inches(1.2),
         [[(head, {"bold": True, "size": 23, "color": NAVY})], [(sub, {"size": 19})]], size=19)
text(s, Inches(4.5), CONTENT_Y + Inches(3.35), Inches(8.2), Inches(1.1),
     "Watching for: the first benchmark that plants attacker text in a summary or self-diagnosis.",
     size=20, italic=True, color=NAVY)

# 26 References
s = new_slide("References", "Sources", dark=True, notes="""
These are my sources. The primary paper is the agentic security survey, version four, on arXiv and in
TMLR. I also used three surveys for contrast: Yehudai and colleagues on agent evaluation, Guo and
colleagues on harness design, and Du on agent memory. Every number in this talk comes from the survey at
the section and page shown on the slide. The article, the figures and all the code are in the short
story folder of my CMPE 297 repository. Thanks for listening.""")
text(s, MARGIN, CONTENT_Y - Inches(0.1), W - 2 * MARGIN, Inches(4.8),
     [[("Shahriar, Rahman, Ahmed, Sadeque, Parvez. ", {"bold": True}),
       ("A Survey on Agentic Security: Applications, Threats and Defenses. TMLR 2026. arxiv.org/abs/2510.06445", {})],
      [("Yehudai et al. ", {"bold": True}), ("A Survey on Evaluation of LLM-based Agents. arxiv.org/abs/2503.16416", {})],
      [("Guo et al. ", {"bold": True}),
       ("From Question Answering to Task Completion: A Survey on Agent System and Harness Design. arxiv.org/abs/2606.20683", {})],
      [("Du. ", {"bold": True}),
       ("Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers. arxiv.org/abs/2603.07670", {})],
      [("This repo: ", {"bold": True}), ("github.com/Prachii26/CMPE297 → short_story/", {})]],
     size=19, color=WHITE)

prs.save(OUT)
print(f"wrote {OUT} with {len(prs.slides)} slides")
