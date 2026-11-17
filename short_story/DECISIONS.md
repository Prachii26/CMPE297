# Decisions

One line per judgement call made without asking.

1. Folder is `short_story` at the repo root, lowercase like `assignment1`–`assignment5`.
2. The primary paper is read from arXiv 2510.06445 **v4** (31 Oct 2026, TMLR-published), which is what arXiv serves; v3 (12 Jun 2026, named in the brief) was also downloaded and diffed. v4 is used because it is the peer-reviewed version and revises v3's numbers and one qualitative finding (most-attacked stages).
3. Paper notes keep the paper's seven threat classes (adding red-teaming and interface-level attacks to the five in the brief).
4. Figure 9b's per-class numbers were read from the rendered PDF page (PyMuPDF), because text extraction dropped zero-valued segments.
5. Where the paper quotes one result two ways (MSB 76.5% vs 75.8%, WebInject, VisualTrap), the article will use the figure stated with its condition and note the other.
6. The defense coverage figure will be shaded by paper count (the survey's Fig. 12), labelled as research attention, because the survey states the cells are not effectiveness.
7. PyMuPDF is installed in the venv only to render PDF pages for reading figures; it is not used to produce any output.
8. v4 (31 Oct 2026, TMLR) is used throughout, as confirmed by the user; v3 appears only in the article's section on revisions.
9. The article opens with the §4.3 harness ablation (100% → 93.3% → 73.3% → 53.3% clear denial) followed by the MCP-SafetyBench 1.22% counterpoint, per the user.
10. The paper's internal discrepancies go in the two-cents section with their numbers and sections, stated as discrepancies and nothing more.
11. Graphviz installed with winget (16.1.1) and worked within three minutes, so the taxonomy and trust-boundary diagrams use graphviz; the venv scripts add `C:\Program Files\Graphviz\bin` to PATH themselves.
12. The three secondary surveys are used for one contrast each: Yehudai et al. on metrics and model/harness decoupling, Guo et al. on mechanically enforced governance, Du on memory and reflection as unattacked surfaces.
13. Figure 8 (MCP trust boundary) is drawn with matplotlib after the graphviz version collided its edge labels and dropped the ✓/✗ glyphs; graphviz is kept for the taxonomy (fig 1) and the mapping (fig 9).
14. Fig. 2 attaches each entry channel to a loop stage using the survey's own stage definitions in §2.1 (query/system prompt → perception, RAG and memory → retrieval, tool and environment results → observation); inter-agent messages are drawn entering the loop as a whole because §2.1 places that channel outside the loop.
15. The §4.3 ablation figure labels the y-axis "clear-denial rate", the survey's metric, rather than "refusal rate".
16. The HPTSA panel shows the 13× pass@1 effect as a relative bar (1× vs 13×) because the survey reports only the ratio, not absolute pass@1.
17. Persistent memory appears in Fig. 2 without a paper count: §4.4.1 names it as a channel but gives no count (Fig. 8's memory column counts threat labels, not papers).
18. "The numbers do not agree with each other" is a subsection of "My two cents", so the discrepancies sit in the two-cents section (prompt 2) and get their own heading (prompt 3).
19. The v3-to-v4 note is placed right after the opening, so a reader knows which version every later number comes from.
20. Attribution check (prompt 4): Chiang et al. (harness ablation, §4.3), Fang et al. (2024), Zhan et al. (2025) and the WASP authors' "security by incompetence" (Evtimov et al.) all match v4. Two corrections: the 1.22% significance judgement is now "the survey reports" (v4 states it without crediting the benchmark authors), and ToolHijacker bypasses four named defenses, not three.
21. The deck follows the user's 26-item slide plan (the prompt says 25 but lists 26 numbered slides); no slide was dropped.
22. The humanizer skill named in the brief is not available in this session, so the pass was done by hand against the brief's checklist, with before/after snapshots, a word-level diff, and a script check that every number and section reference is unchanged.
23. "Still, I find it hard to look at both figures and not connect them." was cut in the humanizer pass: the paragraph now ends on the caveat the user asked for, which it was softening.
24. article-medium.md is generated from article.md by scripts/make_medium.py, so the humanizer edits reach it by regeneration, not by a second hand edit.
25. Speaker notes are 2,302 words, about 15 to 16 minutes at a normal speaking pace for 26 slides.
