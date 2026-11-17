# Prompts

Every prompt sent for this assignment, verbatim and in order.

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

## Humanizer pass — do this last, and do it properly
After all prose is written, run the humanizer skill over article/article.md, README.md, and every slide's speaker notes. The skill is enabled in this session.

Strip: not-X-but-Y constructions, one-line closers, staged openers, forced triads, em-dashes used as a tic, inflated claims, stock AI words, bold inline labels, and filler. Keep technical precision and every number intact. Do not let the humanizer change a fact or drop a citation.

After the pass, read the article start to finish and fix anything that reads mechanically. Report what the humanizer changed most often so I know the tells to watch for when I speak.

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
3. Then figures, then article, then deck, then README, then the humanizer pass.
```
