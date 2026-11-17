# Figure captions (draft, for review before the article is written)

All survey numbers come from Shahriar et al., arXiv 2510.06445 v4 (TMLR, 2026), with the
section and page on each figure. Regenerate with `scripts/make_figures.py`.

| # | File | Draft caption |
|---|---|---|
| 1 | `fig01_taxonomy.png` | The survey's three pillars and their sub-categories, with two or three systems it names under each leaf (Fig. 1, p. 4). Pillar counts overlap: 113 + 86 + 123 > 274 because some papers sit in two pillars. |
| 2 | `fig02_agent_loop.png` | The eight-stage agent loop. Orange boxes are the channels attacks enter through (§4.4.1); box shading is how many papers' attacks first land at each stage (§4.4.2). Look at the gap between where attacks enter (mostly the prompt) and where they bite (reasoning, 54; action selection, 41). Reflection: zero on both counts. |
| 3 | `fig03_asr.png` | A: headline attack success rates the survey reports, grouped by threat class, each with its qualifier and page. They come from different papers, benchmarks and models, so compare within a row only. B: the same attack measured two ways. WASP's hijack rate is 85.7% but only 16.7% of attacks finish end-to-end (§4.4.5, p. 29). |
| 4 | `fig04_attention_matrix.png` | Papers per primary-attack × primary-defense pair (Fig. 12, 81 papers). **This counts research attention, not how well a defense works.** A dark cell means many papers studied that pairing. |
| 5 | `fig05_inherited_native.png` | Threat labels split into inherited from the base LLM, amplified by the agent setting, and agent-native (Fig. 9b). Across all 111 labels, 50.5% are agent-native. Jailbreaks are the one class with no native cases. |
| 6 | `fig06_lifecycle_autonomy.png` | A/B: offensive and defensive application papers per lifecycle stage (Fig. 5). C: the autonomy level each side grants its agents (Fig. 6). 83.0% of offensive systems run at L3, against 14.3% of defensive ones. |
| 7 | `fig07_ablation_hptsa.png` | A: Chiang et al.'s harness ablation as reported in §4.3. The model stays GPT-4o, and its clear-denial rate falls from 100% to 53.3% as agent components are added. B: HPTSA loses a factor of 13 in pass@1 without its coordination layer (§3.4, §4.4.3). The same scaffold that weakens refusals also produces the offensive capability. |
| 8 | `fig08_mcp_trust_boundary.png` | My assignment4 theme 06 MCP host. The server lists `cancel_all_bookings`. The host's allow-list (`ALLOWED_FROM_APP = {"book_room"}`) forwards only `book_room` and answers anything else with error -32001, and the host-built CSP blocks `fetch()` from the sandboxed app. |
| 9 | `fig09_built_vs_survey.png` | What I built in this repo, mapped to the survey category it belongs to. Each edge label says where my version is weaker than what the survey describes. |
| 10 | `fig10_defense_gaps.png` | A: share of the 92 analysed defense papers using each strategy (§5.3.1). B: the survey's gap rating for each strategy on scalability, robustness, latency and coverage (Fig. 10a). No cell is rated Low, and eight of ten strategies have at least one Critical. |
