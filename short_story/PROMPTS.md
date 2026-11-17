# Prompts

Every prompt sent for this assignment, in order.

---

## Prompt 1

```text
Short story assignment for CMPE 297. Build everything end to end.

## Location
Create a short_story folder at the root of the CMPE297 repo, parallel to assignment1 through assignment5. List the repo root first and match the existing lowercase convention.

Structure:
  short_story/
    README.md
    article/
      article.md              the Medium article, final text
      figures/                all generated images
    deck/
      slides.pptx
      slides.pdf
    video/                    the recording goes here later
    research/
      paper_notes.md          my notes from reading the survey
      sources.md              every paper cited, with links
    PROMPTS.md

I am on Windows PowerShell. Write every command in PowerShell syntax.

## The paper
Primary: "A Survey on Agentic Security: Applications, Threats and Defenses", arXiv 2510.06445 (v3, 12 June 2026). Authors: Shahriar, Rahman, Ahmed, Sadeque (BRAC University), Parvez (QCRI).
PDF: https://arxiv.org/pdf/2510.06445
Companion repo: https://github.com/kagnlp/Awesome-Agentic-Security

Read the actual paper before writing anything. Do not work from my summary or from search snippets. Pull the real section structure, the real taxonomy, and the real numbers. If a figure or number I describe below does not match the paper, follow the paper and tell me what differed.

The rubric says to pull in additional survey content, so also read and cite at least two of:
- Survey on Evaluation of LLM-based Agents, arXiv 2503.16416
- From Question Answering to Task Completion: A Survey on Agent System and Harness Design, arXiv 2606.20683
- Memory for Autonomous LLM Agents, arXiv 2603.07670
Use them for contrast, not bulk. One or two paragraphs each where they sharpen a point.

## What the rubric requires
- Summarize the main taxonomy, meaning the various approaches the survey organizes
- Explain the important techniques that appear in the survey's leaderboards and benchmark tables, with their actual numbers
- Focus on architecture, ablation studies and metrics. Not math depth. No derivations.
- Many pictures and visualizations
- My own two cents on the papers
- Written from scratch. Paraphrased and rewritten, never cut and paste. This is checked.

## The article (article/article.md)
Target 2500 to 3500 words. Structure it roughly like this, but adapt to what the paper actually says:

1. Open with the counterintuitive finding, not with background. The MCP-SafetyBench result where safety prompts reduced attack success by a statistically insignificant amount is a good hook if the paper supports it. Verify the exact number.
2. Why agentic security is a different problem from LLM security. The survey's framing is that agents are structurally fragile by default because the attack surface is the whole lifecycle, not the prompt.
3. The three pillars, one section each, with the sub-taxonomy under each:
   - Applications: offensive red-teaming, defensive blue-teaming, domain-specific. Cover the dual-use analysis.
   - Threats: injection, poisoning, jailbreak, agent manipulation, pre-execution cognitive attacks. Cover attack entry points and which stage of the agent loop fails.
   - Defenses: secure-by-design, multi-agent security, runtime protection, security operations, plus how defenses get evaluated.
4. The numbers section. Pull the real attack-success rates and defense results from the paper's tables. Name the specific systems. This is the "leaderboard techniques" the rubric asks for.
5. Where the field is weak. The survey discusses benchmark fragmentation and the inherited vs amplified vs agent-native threat distinction. That is the most interesting analytical content in the paper.
6. My own two cents. This section must be grounded in work in THIS repo, and it is what makes the article original:
   - assignment2/partA stages 12 and 13 built a permission rule table and an OS-level sandbox for a coding agent, and the stage 12 README states honestly that inspecting command text is not real security. That maps directly onto the survey's runtime protection category and its critique of shallow defenses.
   - assignment4/06_mcp_apps demonstrated a host refusing cancel_all_bookings even though the MCP server offered it, and a CSP blocking fetch() inside the sandboxed app. That is the secure-by-design boundary the survey describes, measured locally.
   - assignment5 built a reward-hacking guard that rejected 41 real proposals across five categories. That is adjacent to the survey's agent-native threat class.
   - assignment3 wired MCP toolsets into ADK agents, which is the exact surface MCP-SafetyBench attacks.
   Read those folders before writing this section so the details are accurate. Link to them. Keep it concrete: what I built, what the survey says about that class of defense, and where my version is weaker than what the literature describes.
7. Close with what I would watch next. No grand claims.

Rules for the prose:
- Not one sentence lifted from the paper or any source. Paraphrase everything.
- Student voice. First person where it fits. Direct.
- Explain jargon the first time it appears.
- Every number attributed to its source.

## Figures (article/figures/)
Generate at least 8 real images, not placeholders. Use matplotlib and graphviz. Save as PNG at 1600px wide minimum, readable in both light and dark Medium themes, so use dark text on light backgrounds with no transparency.

At minimum:
1. The three-pillar taxonomy as a tree, with the sub-categories
2. The agent loop with attack entry points annotated at each stage
3. A bar chart of attack success rates for the systems the survey reports
4. A defense coverage matrix: defense category on one axis, threat category on the other, shaded by how well covered each pair is according to the survey
5. Inherited vs amplified vs agent-native threats, as a comparison figure
6. Red-team vs blue-team paper counts or lifecycle coverage, whatever the survey actually reports
7. A diagram of the MCP host/server trust boundary from my assignment4 work, showing where the host's allow-list sits
8. A "what I built vs what the survey describes" mapping figure

Every figure needs a caption in the article explaining what to look at. Do not generate a figure whose numbers you cannot source.

## The deck (deck/)
20 to 25 slides for a 15 to 17 minute talk. Build it with python-pptx, then export a PDF.
- Title, me, the paper with its arXiv link
- Why this paper, in one slide
- The three pillars, one overview slide then one slide per pillar with its sub-taxonomy
- Three to four slides on the numbers, using the figures
- Two slides on the field's weaknesses
- Three to four slides on my own work mapped to the survey's categories, using screenshots from assignment2, assignment4 and assignment5 where they exist
- One slide on what I would watch next
- References
Reuse the article figures. Large text, one idea per slide, speaker notes on every slide since I am recording from them.

## README.md
- What this is, the paper with a link, and a one-paragraph summary
- Links section with placeholders: MEDIUM_ARTICLE_LINK, SLIDESHARE_LINK, YOUTUBE_VIDEO_LINK
- The taxonomy summarized as a table
- A figures gallery embedding every image with its caption
- How the article connects to the other assignments in this repo, with links
- Sources, every paper with its arXiv link
- A note that the article is original writing, not a reproduction of the paper

## PROMPTS.md
Every prompt I send for this assignment, verbatim, in order, from session history. Invent nothing.

## Rules
- Python 3.11, one .venv. matplotlib, python-pptx, graphviz, requests.
- Verify every factual claim against the actual paper. If you cannot source a number, leave it out and say so.
- Do not ask me questions. Make a call and log one line in DECISIONS.md.
- Commit and push when each stage is done.

## Order
1. Read the primary paper fully. Write research/paper_notes.md with the real section structure, the real taxonomy, and every number worth quoting, each with its page or section.
2. Report the notes to me before writing the article. I want to check the taxonomy is right before you build on it.
3. Then figures, then article, then deck, then README.
```

## Prompt 2

```text
Taxonomy approved. Use v4 throughout — 31 Oct 2026, TMLR. Do not build on v3.

Four changes to the article plan before you continue.

1. Restructure the opening around the §4.3 ablation instead of MCP-SafetyBench alone. The sequence is: same GPT-4o, 100% refusals standalone, dropping to 93.3%, 73.3%, 53.3% as the goal moves into the system prompt, multi-step actions are added, and an event stream is added. Then the MCP-SafetyBench counterpoint: safety prompts move host-side attack success by 1.22%, which the authors call statistically insignificant. Safety degrades as autonomy is added, and the obvious fix does not work. That is the hook.

Give the ablation its own figure: refusal rate on the y-axis, the four autonomy configurations on the x-axis. Add the HPTSA 13x pass@1 coordination-layer result alongside it if the axes allow, otherwise as a second panel.

2. Add a short section on the v3-to-v4 differences. 274 papers vs "over 260", 56.8% vs 55% for prompt-entry attacks, 124 vs 108 benchmarks, and the conclusion reversing from perception stage to reasoning stage. Treat it as an observation about reading a living survey: the headline claim moved between revisions, and anyone citing v3 now cites a conclusion the authors have changed. Do not speculate about why unless the paper says.

3. Put the internal contradictions in the two-cents section, not a footnote. Name the exact numbers and the sections they came from. State what it is — a discrepancy in a published survey — without inflating it into a claim about the paper's quality.

4. Keep the Fig. 12 labelling as you planned. Say in the caption and in the body that it counts research attention per attack/defense pair, not how well each defense works. That distinction is worth a sentence of its own.

On tooling: install graphviz with winget, but if it is not working within 10 minutes, draw the taxonomy and the trust-boundary diagrams with matplotlib instead and move on. Do not lose an hour to a PATH problem.

Read the three secondary surveys now, but keep them light — one or two paragraphs each, used for contrast where they sharpen a point. They are enrichment, not bulk.

Then continue: figures, article, deck, README. Report when the figures are done so I can look at them before the article is written around them.
```

## Prompt 3

```text
Figures approved. Three structural changes to the article before you write it.

1. New section: "The numbers do not agree with each other." Build it from fig 3's second panel plus the discrepancies in the notes. WASP 85.7% vs 16.7% and AgentPoison 81.2% vs 62.6% for the same attacks measured differently, MSB's peak at 76.5% in one section and 75.8% in another, AgentPoison's poison rate under 0.1% in §4.1.2 and under 1% in §4.4.1, and the survey's own finding of 124 distinct benchmarks. The point is that attack success rate is not a stable quantity across papers, so cross-paper comparison is weaker than the tables imply. State it as an observation about the literature, not an accusation about the authors — the survey itself identifies benchmark fragmentation as a problem.

2. Connect fig 6 and fig 7 explicitly in the prose. The ablation shows clear-denial dropping from 100% to 53.3% as autonomy is added. Fig 6 shows offensive agents operating at full autonomy 83.0% of the time against 14.3% for defensive ones. Write the synthesis: the capability that most degrades safety behaviour is the one most freely granted to offensive systems, and least to the defensive systems meant to counter them. Keep it to a paragraph and do not overstate — the two results come from different parts of the survey and are not a controlled comparison. Say that.

3. Close on the reflection gap instead of a generic outlook. Fig 2 shows zero papers attacking the reflection stage. Du treats memory and reflection as core agent components. I have built reflection twice in this repo: assignment5's SO-RSI diagnostic inquiry, which detects recurrence, opposing edits and expectation mismatch in its own trace, and assignment2 stage 14's summarizer that writes a handoff note when the context fills. Both read and act on the agent's own history, which is exactly the surface nobody has attacked. Make the closing concrete about what that surface looks like rather than calling for more research.

Keep the three caveats about my own work in the two-cents section, worded as plainly as you listed them: the assignment5 guard's 41 rejections came from a scripted proposer that planted the hacks deliberately and the live LLM never attempted one; stage 13 prints sandbox: none on this Windows machine; assignment3 filters MCP tools by name only. Those make the section credible.

Then write the article, the deck and the README. Report when the article draft is done, before the deck.
```

## Prompt 4

```text
Finish the short story assignment end to end. Work through all five stages without stopping unless something is unrecoverable. Report at the end.

## Stage 1 — Article fixes

1. The dual-use paragraph (Fang et al. / CVE-Genie / ARTEMIS) states the economics and stops. Add one or two sentences on what I take from them, connected to the autonomy paragraph below it: the cost of running an offensive agent is now low enough that the binding constraint is no longer expertise or budget, and the survey's own autonomy data shows that is also the side given the least human oversight. Two sentences, no moralising.

2. Verify every "X et al." attribution against the paper. Line 9 credits the harness ablation to Chiang et al. — check it, and check all the others. Where the survey names no author for a result, write "the survey reports" instead of inventing one. List every correction you make.

3. Change the title to "GPT-4o Refuses Every Request, Until You Wrap It in an Agent", move the current title to the subtitle line, and rename the opening section heading so it does not repeat the title.

4. Make sure the transition into "My two cents" signals that my own reading is starting, so §6 and §7.1 do not read as the same argument twice. One sentence is enough.

5. Create article/article-medium.md: the same article with every repo link rewritten as an absolute https://github.com/Prachii26/CMPE297/... URL, plus a short block at the top listing the figure filenames in the order they appear, so I know which image to upload where when pasting into Medium. Keep article.md as the repo version with relative links.

## Stage 2 — The deck

deck/slides.pptx, exported to deck/slides.pdf. 25 slides for a 15 to 17 minute talk. Build it with python-pptx. Reuse the existing figures — do not regenerate them.

Slide plan, adjust only if the article changed:
1. Title, my name, CMPE 297, the paper with its arXiv link
2. The paper: Shahriar et al., TMLR 2026, 274 papers, three pillars, Jan 2023 to May 2026 corpus
3. The hook — fig 7 left panel. 100 / 93.3 / 73.3 / 53.3, same model
4. Why it drops: system-prompt trust promotion, and multi-step vs plan-first
5. The obvious fix fails — MCP-SafetyBench, 245 tasks, 13 models, 81.94%, 1.22%
6. Which version I read — the four v3-to-v4 differences, and the reversed conclusion
7. The agent loop — fig 2
8. Entry point vs failure stage, and the black-box threat model
9. Taxonomy overview — fig 1
10. Applications: red team, blue team, domain-specific
11. Dual-use economics — $8.80, $2.77, ARTEMIS vs human pen testers
12. Autonomy asymmetry — fig 6
13. Synthesis: autonomy degrades refusals, and offense gets the most autonomy. State on the slide that these are separate results, not a controlled comparison
14. Threats: the seven classes
15. Inherited vs amplified vs agent-native — fig 5
16. Defenses: the four groups, and 53.3% being an LLM watching an LLM
17. Defense gaps — fig 10
18. Research attention, not effectiveness — fig 4, with that caveat on the slide itself
19. The numbers — fig 3 panel A
20. MCP results: MCPTox, MSB, stronger models more vulnerable
21. The numbers do not agree — fig 3 panel B, plus the MSB and AgentPoison discrepancies
22. What I built — fig 9
23. The MCP trust boundary — fig 8
24. Where mine is weaker: sandbox none on Windows, name-only tool filtering, scripted proposer behind the 41 rejections
25. What I'd watch: the reflection gap. Stage 14's handoff note and SO-RSI's inquiry memory
26. References

Every slide needs speaker notes written as spoken sentences, because I record from them. Large text, one idea per slide, no paragraph dumps. Copy slides.pdf into video/ as well, since the rubric asks for the slides in the GitHub directory alongside the recording.

## Stage 3 — README.md

- What this is, the paper with a link, and a one-paragraph summary
- A links block with four placeholders: MEDIUM_ARTICLE_LINK, SLIDESHARE_LINK, YOUTUBE_VIDEO_LINK, and the deck PDF path
- The three-pillar taxonomy as a table
- A figures gallery embedding all 10 images with their captions
- A short section on how this connects to the rest of the repo, linking assignment2 stages 12 to 14, assignment3, assignment4 theme 06 and assignment5
- Sources: the primary paper and the three secondary surveys, each with its arXiv link
- A line stating the article is original writing, not a reproduction of the survey

## Stage 4 — PROMPTS.md

Every prompt I sent for this assignment, verbatim, in order, pulled from session history. Invent nothing.

## Stage 5 — Final check

- Every figure referenced in the article and the deck exists and renders
- Every arXiv link resolves
- No number in the article is unsourced
- slides.pdf opens and the text is readable at a distance
- Grep for AIza and sk-, confirm no hits
- .venv is gitignored
- Commit and push

Report at the end: the attribution corrections you made, the final word count, the slide count, and anything you could not verify.
```

## Prompt 5

```text
continue
```
