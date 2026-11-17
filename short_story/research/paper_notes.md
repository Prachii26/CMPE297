# Paper notes: A Survey on Agentic Security: Applications, Threats and Defenses

My reading notes on the primary paper. Everything below was taken from the
PDF itself, not from summaries or search snippets. Page numbers are the
printed page numbers of the version I read; section numbers follow that
version. Notes are in my own words.

## Which version these notes are from

- **Read in full: arXiv 2510.06445 v4, dated 31 Oct 2026**, which carries the
  header "Published in Transactions on Machine Learning Research (11/2026)" and
  links its OpenReview page (id `Od4ZnAUv9T`). 69 pages including references and
  appendix. This is what `https://arxiv.org/pdf/2510.06445` serves today.
- The brief named **v3 (12 June 2026)**. I downloaded v3 as well and compared.
  The two differ in ways that matter, so I am building on v4. See
  [v3 vs v4](#v3-vs-v4-what-changed) at the end.
- Authors: Asif Shahriar, Md Nafiu Rahman, Sadif Ahmed (equal contribution),
  Farig Sadeque (BRAC University), Md Rizwan Parvez (QCRI).
- Companion list of all papers: <https://github.com/kagnlp/Awesome-Agentic-Security>
  (resolves; README links the TMLR version).

---

## 1. Real section structure (v4)

| § | Title | Pages |
|---|---|---|
| 1 | Introduction (definition of an LLM agent, three questions, findings, contributions) | 1–3 |
| 2 | Background and Related Work | 5–7 |
| 2.1 | Anatomy of an Agent (the eight-stage loop) | 5 |
| 2.2 | Agentic Architecture (cardinality, autonomy levels 0–3) | 5–6 |
| 2.3 | Security Preliminaries (red/blue, lifecycles, threat models) | 6 |
| 2.4 | Related Work Comparison (Table 1) | 6–7 |
| 3 | Applications of Agents in Security | 7–18 |
| 3.1 | Offensive (Red-Teaming): 3.1.1 penetration testing, 3.1.2 vulnerability discovery & fuzzing, 3.1.3 exploit generation & adaptation | 7–10 |
| 3.2 | Defensive (Blue-Teaming): 3.2.1 detection & incident response, 3.2.2 threat hunting, 3.2.3 forensics & root cause, 3.2.4 vulnerability remediation | 10–12 |
| 3.3 | Domain-specific: 3.3.1 cloud & infrastructure, 3.3.2 web & application, 3.3.3 specialized (finance, reverse engineering, OT, healthcare, privacy) | 12–14 |
| 3.4 | Analysis: 3.4.1 lifecycle coverage map, 3.4.2 red vs blue, 3.4.3 dual-use | 14–18 |
| 4 | Threats to Agentic Systems | 18–30 |
| 4.1 | Attack Surface: 4.1.1 injection, 4.1.2 poisoning, 4.1.3 jailbreak, 4.1.4 agent manipulation, 4.1.5 pre-execution cognitive, **4.1.6 red-teaming attacks**, **4.1.7 interface-level attacks** | 19–23 |
| 4.2 | Evaluation Frameworks: 4.2.1 adversarial benchmarking, 4.2.2 execution environments | 23–24 |
| 4.3 | Why Alignment Fails in Agentic Settings | 24–25 |
| 4.4 | Analysis: 4.4.1 entry points, 4.4.2 failure stages, 4.4.3 inherited/amplified/agent-native, 4.4.4 threat models & objectives, 4.4.5 benchmarks, metrics & evaluation gaps | 25–30 |
| 5 | Defense: Hardening the Agents | 30–38 |
| 5.1 | Defense and Operations: 5.1.1 secure-by-design, 5.1.2 multi-agent security, 5.1.3 runtime protection, 5.1.4 security operations | 30–32 |
| 5.2 | Evaluation Frameworks: 5.2.1 benchmarking platforms, 5.2.2 defense testing, 5.2.3 domain-specific | 32–33 |
| 5.3 | Analysis: 5.3.1 ten strategies, 5.3.2 six trust-boundary compositions, 5.3.3 cost/security trade-offs (Table 3), 5.3.4 placement in the lifecycle | 33–38 |
| 6 | Cross-Cutting Analysis and Trends: 6.1 defense coverage by attack class, 6.2 architecture, 6.3 backbone models, 6.4 data modalities | 39–45 |
| 7 | Conclusion (future work, limitations, broader impact) | 45–46 |
| App. A | Paper collection methodology | 67–68 |
| App. B | Coding procedure, pillar overlaps, decision rules, corpus schema | 68–69 |

Figures and tables I expect to draw on: Fig. 1 taxonomy tree (p4), Fig. 2 agent
loop (p5), Fig. 5 lifecycle coverage (p14), Fig. 6 autonomy (p16), Fig. 7
dual-use cost/effectiveness (p19), Fig. 8 threat × entry point (p26), Fig. 9
failure stages and agent-specificity (p27), Fig. 10 defense strategies and
trust boundaries (p36), Table 3 cost magnitudes (p37), Fig. 11 cost and
placement (p38), Fig. 12 defense × attack heatmap (p39), Fig. 17 corpus
overlap (p68).

---

## 2. The corpus

- **274 papers** after deduplication (abstract, p1; App. B, p68).
- Pillar counts overlap: **Applications 113, Threats 86, Defenses 123**
  (App. B, p68). Fig. 17 Venn: applications only 84, threats only 63, defenses
  only 81, applications ∩ threats 4, applications ∩ defenses 23, threats ∩
  defenses 17, all three 2. Those add to 274.
- Search window: **January 2023 to May 2026**, over ACL Anthology, IEEE Xplore,
  ACM DL and arXiv, plus manual scans of security and ML venues and
  snowballing (App. A, p67).
- Coding: three authors, one per pillar, each pillar re-checked by a second
  author, a third resolving disagreements (App. B, p68). The coded corpus (274
  rows, 43 fields) is released (p69).
- Percentages inside a pillar section use that pillar's count as the
  denominator; §6 percentages use 274 (App. B, p68). This matters when quoting.

---

## 3. The taxonomy (Fig. 1, p4)

Three pillars, framed as three questions a security person would ask (§1,
p2): what can agents do for my security, how can they be attacked, how do I
stop them.

### Pillar 1 — Applications (§3)

| Branch | Sub-category | Representative systems named in Fig. 1 |
|---|---|---|
| Red teaming (§3.1) | Autonomous penetration testing | PentestGPT, HackSynth, Incalmo |
| | Vulnerability discovery & fuzzing | Locus, ChatAFL, LLM-Fuzzer, FuzzGPT |
| | Exploit generation & adaptation | MalGen, CVE-Genie |
| Blue teaming (§3.2) | Threat detection & incident response | IRCopilot, CORTEX, CyberSOCEval |
| | Intelligent threat hunting | ProvSEEK, LLMCloudHunter |
| | Automated forensics | RepoAudit, CyberSleuth, GALA |
| | Patching & remediation | RepairAgent |
| Domain-specific (§3.3) | Cloud & infrastructure | KubeIntellect, BARTPredict |
| | Web & application | MAPTA, AIOS, Progent, PFI |
| | Specialized | LISA (blockchain), HIPAA (healthcare), OneShield (privacy) |

### Pillar 2 — Threats (§4)

Attack surface, seven classes (§4.1):

| Class | What it targets | Fig. 1 examples |
|---|---|---|
| Injection (§4.1.1) | instructions smuggled into the agent's input, directly or through content it reads | AgentDojo, InjecAgent, PromptInfection |
| Poisoning (§4.1.2) | memory / retrieval store at inference time, or the model at training time | AgentPoison, PoisonBench |
| Jailbreak (§4.1.3) | the model's safety training | BrowserART, JAWS-BENCH, LLMFuzzer |
| Agent manipulation (§4.1.4) | goals, planning, reasoning: goal and action hijacking, reward hacking, Byzantine agents, resource exhaustion | PromptInject, AEA, InfoRM |
| Pre-execution cognitive (§4.1.5) | internal state before any tool runs: epistemic (thought steps), teleological (plans), metacognitive (self-checking) | Backdoor Threats, ScamAgents, RSP |
| Red-teaming attacks (§4.1.6) | automated attack generation and fuzzing aimed at agents | AI-Oops, AgentDoS |
| Interface-level (§4.1.7) | agents that act through a GUI: screenshots, accessibility trees, clicks | CUA Systematization, Pop-up Attack, MIP |

Evaluation (§4.2): adversarial benchmarks (DoomArena, SafeArena,
ST-WebAgentBench, ASB) and execution environments (AgentDojo, CVE-Bench,
DoomArena).

### Pillar 3 — Defenses (§5)

| Branch | Sub-category | Fig. 1 examples |
|---|---|---|
| Defenses & operations (§5.1) | Secure-by-design | ACE, Task Shield |
| | Multi-agent security | D-CIPHER, PhishDebate |
| | Runtime protection | R2-Guard (guardrail), AgentSpec (human in the loop), SentinelAgent (behavioral monitoring) |
| | Security operations | IRIS (formal verification), CORTEX (SOC triage), ExCyTIn-Bench (threat hunting), GALA (forensics) |
| Evaluation (§5.2) | Benchmarking platforms | ASB, RAS-Eval |
| | Defense testing | AI Agents Under Threat, Safety at Scale |
| | Domain-specific | CloudInfra, LISA, FinetuningAgents, PrivacyMedical, PrivacyGuardrails, EmbodiedAI |

The analysis sections add two more defense groupings that the article needs:

- **Ten strategies** (§5.3.1): input sanitization & filtering, structured
  queries, LLM-based monitoring, moving target defense, capability-scoped
  execution, cryptographic verification, dataset sanitation & differential
  privacy, sandboxing & formal verification, red-team simulation, consensus &
  vaccine seeding.
- **Six trust-boundary compositions** (§5.3.2): base LLM alignment, external
  monitor, formal verification, sandbox/isolation, cryptographic/structural
  integrity, human in the loop.

### Shared vocabulary from §2

- **Eight-stage agent loop** (§2.1, Fig. 2, p5): perception, retrieval,
  reasoning, planning, action selection, execution, observation, reflection;
  reflection feeds back into reasoning. Memory, the tool/environment
  interface and the inter-agent channel sit outside the loop and persist
  across it.
- **Autonomy levels** (§2.2, p6): 0 recommendations only, 1 copilot, 2
  executes parts with approval at critical points, 3 end-to-end with minimal
  oversight. The level is about the authority a system is given, not the
  model's capability.
- **Threat models** (§2.3, p6): black-box (query only), gray-box (e.g. system
  prompt or tool schema), white-box (weights/gradients); agents add
  capabilities such as writing to memory or controlling a tool. *Attack
  surface* = all channels into the agent; *entry point* = one channel.

---

## 4. Applications pillar — numbers

### Lifecycle coverage (§3.4.1, Fig. 5, p14–15)

Papers per stage (an agent can count in several stages):

| Offensive stage | Papers | | Defensive stage | Papers |
|---|---|---|---|---|
| Reconnaissance | 35 | | Detection | 27 |
| Scanning | 22 | | Triage | 9 |
| Vulnerability discovery | **52** (most of any stage) | | Threat hunting | 11 |
| Exploitation | 50 | | Forensics | 17 |
| Post-exploitation | 13 | | Root-cause analysis | 10 |
| Persistence | **2** | | Remediation | 19 |
| Exfiltration | **3** | | Response | 6 |

The authors' reading: work piles up where feedback is immediate and
checkable (discover, exploit, detect, remediate) and thins out where sustained
stealth or long reasoning is needed. They suggest ethics and model
limitations explain the near-empty persistence and exfiltration stages (p15).

### Autonomy asymmetry (§3.4.2, Fig. 6, p16–17)

- 47 offensive systems: **39 (83.0%) at Level 3**, 5 at Level 2, 3 at Level 1,
  none at Level 0.
- 35 defensive systems: **5 (14.3%) at Level 3**, 10 (28.6%) at Level 2, 15
  (42.9%) at Level 1, 5 (14.3%) at Level 0.
- Keeping an approval gate (Levels 0–2): **17.0% of offensive vs 85.7% of
  defensive** systems. Some autonomous execution (Levels 1–3): 100.0% vs 85.7%.
- Recurring failure modes: offense loses the plot over long horizons (planning
  errors, context loss); defense drowns in false positives (alert fatigue),
  CTI contradictions and hallucinated audit findings (p16).

### Dual use (§3.4.3, Fig. 7, p17–19)

- **60 of 113 application systems (53.1%)** expose offensive or broadly
  dual-use capability (p17).
- MalGEN averages 11.3 ATT&CK techniques per sample and roughly half of its
  samples evaded every VirusTotal engine (p18).
- Cost and effectiveness (p18, Fig. 7):
  - Fang et al.: exploits **87%** of one-day CVEs at about **$8.80** per exploit,
    roughly 2.8× cheaper than the human estimate.
  - CVE-Genie: reproduces **428 of 841 CVEs (51%)** at **$2.77** each.
  - HPTSA: zero-day exploitation at about **$24.4** vs an estimated **$75** for a
    human; **42% pass@5** on zero-day web vulnerabilities; up to **4.3×** over
    prior single-agent systems.
  - ARTEMIS: up to eight agents over about 8,000 hosts; placed second overall,
    outperformed **9 of 10** human professionals, at about **$18/hour vs $60/hour**.
- **Ablation that matters:** HPTSA loses **13× in pass@1** when its hierarchical
  coordination is removed (p18; repeated in §4.4.3, p28). The ARTEMIS models
  often refused the same offensive tasks when asked directly. The authors'
  conclusion: the offensive power comes from the scaffold, not the base model.

Other application numbers worth having: Co-RedTeam over 60% exploitation
success (p8); a fine-tuned open model near 80% sub-task completion (Luong et
al., p8); Wang & Zhou self-validate 104 Android zero-days (p9); RepairAgent
fixed 164 defects (p11); LLMCloudHunter 92% precision / 98% recall on rule
candidates (p11); Progent blocks all successful attacks in its red-team
evaluation (p13).

---

## 5. Threats pillar — numbers

### The hook: MCP-SafetyBench (§4.2.1, p23) — verified

Zong et al. (2026): **245 tasks over 13 models**; host-side attacks average
**81.94% ASR**; Identity Injection succeeds on every model; **adding safety
prompts lowers ASR by 1.22%, which the authors report as not statistically
significant**. The same paragraph:

- MCPTox (Wang et al., 2026b): poisoned tool metadata on 45 real MCP servers,
  1,312 cases, **up to 72.8% ASR**, while the best refusal rate (Claude 3.7
  Sonnet) stays **under 3%**.
- MSB (Zhang et al., 2025b): 2,000 instances, 12 attack types, **40.35%
  average ASR**, out-of-scope-parameter attacks peaking at **76.5%**.
- In both MCPTox and MSB, *more capable models are more vulnerable*, because
  better tool use means better compliance with a malicious tool call.
- WASP (Evtimov et al., 2026): simple injections hijack o1 and Claude Sonnet
  3.7 in up to **86%** of cases, but the attacker's goal completes end to end in
  only **17%**; the WASP authors call this "security by incompetence" (p23–24).

### Attack success rates by class (§4.1, p19–23)

| Class | System | Reported result | Page |
|---|---|---|---|
| Injection | HOUYI | compromises 31 of 36 real apps (incl. Notion), 86.1% | 19 |
| Injection | MCTS fuzzing (Wang et al., 2025h) | 71% ASR on AgentDojo | 19 |
| Injection | ASB mixed attack | 84.30% average ASR over 13 backbones | 19 |
| Injection | Zhan et al. (2025) | all 8 evaluated defenses bypassed by adaptive attacks | 19 |
| Injection | ToolHijacker | up to 96.7% ASR on MetaTool vs GPT-4o, past StruQ, SecAlign, DataSentinel | 19 |
| Injection | Imprompter | ~80% PII extraction precision on production agents | 19 |
| Injection | WebInject | over 96% ASR across five agents | 19 |
| Injection | Johnson et al. (accessibility tree) | above 0.83 ASR on five sites; 0.55 credential exfiltration | 20 |
| Poisoning | MINJA | 76.8% average ASR, 98.2% injection success, no memory-write access needed | 20 |
| Poisoning | AgentPoison | 81.2% retrieval ASR, 62.6% end-to-end, <0.1% of entries poisoned, <1% benign drop | 20 |
| Poisoning | PoisonBench | 0.01% poisoned preference data measurably shifts behaviour | 20 |
| Poisoning | Bowen et al. | 2% poisoned data: GPT-4o refusal 94% → 4% | 20 |
| Poisoning | Poison-with-Style | 95% ASR on CWE-20 at <6% pass@1 drop | 20 |
| Poisoning | VisualTrap | over 90% ASR on GUI agents, survives clean fine-tuning | 20 |
| Jailbreak | BrowserART | GPT-4o: 12% (chat) → 74% (browser agent, direct ask) → 100% (attack ensemble) | 20 |
| Jailbreak | Chiang et al. | 46.6% non-denial on tasks the standalone model refuses entirely | 20 |
| Jailbreak | AgentHarm | Mistral Large 2 harm score 82.2% with no jailbreak | 20 |
| Jailbreak | JAWS-BENCH | code-agent wrapper raises ASR 1.6× on average, ~75% in multi-file repos | 20 |
| Jailbreak | LLMFuzzer | 93.14% ensemble ASR on GPT-3.5 | 20 |
| Jailbreak | Paper Summary Attack | 97–98% on Claude 3.5 Sonnet and DeepSeek-R1 | 21 |
| Jailbreak | ROBOPAIR | 100% ASR on three LLM-controlled robots | 21 |
| Manipulation | role-identification attack | 92% ASR on GPT-4o | 21 |
| Manipulation | AI2 action hijacking | 84.30% average ASR | 21 |
| Manipulation | o3 vs chess engine | hacked the environment in 88% of runs, unprompted | 21 |
| Manipulation | AIOps telemetry attack | 90% average ASR vs GPT-4o / GPT-4.1 | 21 |
| Manipulation | AgentDoS | 36 zero-days (15 CVEs) in 16 of 20 agents, 100% precision, 94.7% recall | 21 |
| Cognitive | reasoning backdoor (Yang et al.) | up to 100% ASR with 30 poisoned samples | 21 |
| Cognitive | ScamAgents | refusal 84–100% → 17–32%; full scam dialogue in up to 74% | 21 |
| Cognitive | epistemic-tone rewriting | up to +194% token cost or ~22% accuracy drop | 21 |
| Red-teaming | Agent-in-the-Middle | >70% ASR in most setups, 98.5% on chains, 100% on MetaGPT | 22 |
| Red-teaming | multi-agent planner/attacker | 96.2% ASR vs Claude 3.7 Sonnet | 22 |
| Red-teaming | AgentFuzz | 34 zero-days in 20 agents, 23 CVEs, 100% precision | 22 |
| Interface | pop-ups | agents click them 86% of the time; task success −47%; telling them to ignore pop-ups does not help | 22 |

### Benchmarks and environments (§4.2, p23–24)

ASB 10 scenarios / 27 attack classes; RAS-Eval 80 scenarios, 3,802 tasks,
real tools, task completion −36.8%, 32 failure modes under real execution vs
16 in simulation; AgentDojo 97 tasks; AgentHarm 110 tasks / 11 categories;
SafeArena 250 malicious requests, GPT-4o completes 34.7%; ST-WebAgentBench 375
tasks, policy-compliant success ~38% below plain completion; SandboxEval 51
tests; InjecAgent 1,054 cases (17 user tools, 62 attacker tools); OS-Harm 150
tasks, judge F1 0.76 / 0.79; WebArena 812 tasks, best agent 14.41% vs humans
78.24%; HackWorld 36 apps, CUAs exploit under 12%.

### Why alignment fails — the ablation section (§4.3, p24–25)

- **Harness ablation (Chiang et al.):** standalone GPT-4o refuses every
  malicious request; putting the user goal in the system prompt drops clear
  denial to **93.3%**; adding multi-step action generation to **73.3%**; adding
  the event stream to **53.3%** (p25). With the goal left in the user turn,
  every jailbreak failed. Multi-step generation is **20 points** more
  permissive than planning up front. Turning off goal paraphrasing recovers
  **13.3%** clear denial.
- **Context length:** padding harmful requests with long benign reasoning
  raises ASR on S1-32B from **27% to 80%**, and to **94–100%** on Gemini 2.5 Pro,
  o4-mini, Grok 3 mini and Claude 4 Sonnet; ablating the responsible attention
  heads removes the effect (p24). On padded AgentHarm, GPT-4.1-nano's refusal
  rises ~5% → 40% while Grok 4 Fast's falls ~80% → 10% at 200K tokens (p25).
  The authors flag that these are padded prompts, not running agent loops.
- **Mechanisms named:** refusal is shallow (lives in the first few output
  tokens); refusal is governed by one direction in activation space; the
  instruction hierarchy assigns trust by role label, and orchestration
  rewrites user text into the system prompt, promoting its privilege.

### Threat analysis (§4.4)

**Entry points** (§4.4.1, Fig. 8, p25–26; 74 of 86 papers locate a channel):

- Conversational input (user query + system prompt) is **56.8%** of evaluated
  attacks. The authors attribute this partly to convenience: no tools, memory
  or multi-agent setup needed.
- Agent-specific channels: tool/API response **24 papers** (the leading
  autonomous surface, mostly injection), environment observation **20**,
  retrieved documents **17**, inter-agent messages **5**, reflection output
  **0**.
- Fig. 8 matrix (threat class × entry point; a paper can appear in several cells):

| | System prompt | User query | Tool/API resp. | Retrieved doc | Memory | Inter-agent | Env. observation | Reflection |
|---|---|---|---|---|---|---|---|---|
| Injection | 3 | 11 | 23 | 13 | 2 | 1 | 13 | 0 |
| Poisoning/Extraction | 1 | 7 | 6 | 4 | 3 | 0 | 4 | 0 |
| Jailbreak | 1 | 23 | 5 | 2 | 0 | 0 | 7 | 0 |
| Manipulation | 3 | 5 | 7 | 6 | 2 | 4 | 5 | 0 |
| Cognitive | 1 | 2 | 2 | 3 | 1 | 0 | 3 | 0 |
| Red-teaming | 0 | 4 | 2 | 0 | 0 | 0 | 2 | 0 |

**Failure stages** (§4.4.2, Fig. 9a, p27; 78 papers): reasoning **54**, action
selection **41**, execution 9, planning 7, perception 6, observation 5,
retrieval 5, reflection **0**. Entry and failure differ: memory poisoning
enters via a query or a write but is coded where it first bites, at
retrieval. No threat class reaches reflection.

**Inherited / amplified / agent-native** (§4.4.3, Fig. 9b, p27–28):

- **50.5% agent-native, 41.4% inherited or amplified, 8.1% unclassifiable.**
- Fig. 9b counts (read from the rendered figure):

| Class | Inherited | Amplified | Agent-native |
|---|---|---|---|
| Injection | 9 | 3 | 23 |
| Poisoning/Extraction | 7 | 1 | 7 |
| Jailbreak | 11 | 9 | 0 |
| Manipulation | 2 | 0 | 14 |
| Cognitive | 1 | 1 | 5 |
| Red-teaming | 2 | 0 | 7 |

  These 102 classified labels plus 9 unclassified give 111; 56/111 = 50.5%,
  46/111 = 41.4%, 9/111 = 8.1%, which reconciles the percentages. The text's
  "injection: 23 of 36 labels" and "jailbreak: 20 of 25 labels" also count the
  unclassified labels in the denominator.
- Amplification evidence: non-denial 0% → 46.6% as a web agent; GPT-4o 12% →
  74% as a browser agent; 1.6× in a code agent; refusals 84–100% → 17% when a
  goal is split across turns (p28).
- Five agent-native mechanisms (p28): persistent-state poisoning; inter-agent
  compromise; tool and protocol layer poisoning (mainly MCP); plan and action
  hijacking; specification and reward gaming.
- Definitions used for coding (App. B, p68): inherited = shown on a standalone
  model and unchanged in the agent; amplified = exists in the base model but
  succeeds more, refuses less or reaches further with the scaffold;
  agent-native = impossible without a scaffold component (memory, tool
  interface, inter-agent channel, planning loop).

**Threat models and objectives** (§4.4.4, p28):

- Of 77 papers stating access: **51.9% black-box**, **27.3% no model access at
  all**, 15.6% white-box, 5.2% gray-box.
- Capabilities beyond model access: 20.9% need training/gradient access, 5.8%
  tool-execution access, 3.5% an inter-agent channel, 2.3% memory-write access.
- Objectives (79 papers, multi-label): unauthorized action **65.8%**, data
  exfiltration 46.8%, content-policy violation 38.0%, financial harm 35.4%,
  deception 27.8%, denial of service 17.7%, privilege escalation 12.7%, IP
  theft 5.1%.
- The authors' read: one dominant threat model, an outsider with no
  privileges, working black-box through channels the agent already reads.
  "Structurally fragile by default" is their conclusion from black-box
  success being the norm (§1, p2).

**Benchmarks, metrics, gaps** (§4.4.5, p29–30):

- 25 of 86 threat papers (29.1%) are benchmark papers.
- **124 distinct benchmarks/datasets; 93 (75.0%) used by exactly one paper**;
  31 used more than once, and only **4** of those are built for agentic security
  (AgentDojo, InjecAgent, AgentHarm, BrowserART).
- What the 25 benchmark papers instrument: tool response 14, user query 9,
  persistent memory **1**, inter-agent messaging **0**, reflection **0**.
- Metrics: 66 of 86 (76.7%) headline ASR or a harm score; only **19** also
  report utility under the same attack; only **14** report token or latency cost.
- ASR is not one thing: ISR, EASR, TCR, retrieval / intermediate / targeted /
  end-to-end ASR, non-denial rate, harm score, leak velocity. AgentPoison
  81.2% retrieval vs 62.6% end-to-end; WASP 85.7% intermediate vs 16.7%
  end-to-end, so a quoted figure can move by a factor of five depending on
  where it was measured. Two different "84.30% average ASR" results (ASB and
  AI2) measure different events.
- Their three reporting fixes: state the denominator and success condition
  and give end-to-end ASR alongside any intermediate rate; report utility
  under the same attack; report cost in tokens and latency.
- Evaluation gaps found: single-turn only (6 papers), no multi-agent coverage
  (2), simulated rather than real tool execution (9).

---

## 6. Defenses pillar — numbers

123 defense papers; **92** propose or evaluate a technique and are the
denominator for §5.3 (p33–34).

### Ten strategies (§5.3.1, Fig. 10a, p34–36; multi-label, 212 assignments)

| Strategy | Papers | Share of 92 | Weakness the authors name |
|---|---|---|---|
| LLM-based monitoring | 49 | **53.3%** | latency, cost, can itself be manipulated |
| Capability-scoped execution | 30 | 32.6% | coordination overhead; wrong gating breaks long tasks |
| Input sanitization & filtering | 29 | 31.5% | misses obfuscated indirect injection |
| Sandboxing & formal verification | 25 | 27.2% | formal methods do not scale to open language |
| Red-team simulation | 20 | 21.7% | over-indexes on known attacks |
| Structured queries | 18 | 19.6% | the model can still be talked out of the schema |
| Cryptographic verification | 17 | 18.5% | heavy compute and integration cost |
| Consensus & vaccine seeding | 13 | 14.1% | multiplies tokens; vaccines go stale |
| Dataset sanitation & DP | 6 | 6.5% | over-sanitizing hurts utility |
| Moving target defense | 5 | **5.4%** | non-determinism hurts reliability |

Gap-severity heatmap (Fig. 10a right, p36) rates every strategy on
scalability, adversarial robustness, latency/overhead and coverage. **No
strategy is rated Low on any axis**; every row has at least one High or
Critical rating, and eight of the ten have a Critical (only capability-scoped
execution and dataset sanitation do not). Their conclusion: layer defenses.

### Six trust-boundary compositions (§5.3.2, Fig. 10b, p35–36)

Primary trust boundary per paper (sums to 92): external monitor **34**,
cryptographic/structural integrity 19, base LLM alignment 13, sandbox/isolation
13, formal verification 11, human in the loop **2**. Cross-tab with attack
classes (multi-label):

| | Injection | Agent manip. | Jailbreak | Red-teaming | Poisoning & extr. | Pre-exec. | Prompt infection |
|---|---|---|---|---|---|---|---|
| External monitor | 14 | 19 | 9 | 6 | 14 | 2 | 4 |
| Base LLM alignment | 7 | 5 | 7 | 4 | 8 | 1 | 1 |
| Formal verification | 4 | 5 | 0 | 0 | 2 | 1 | 0 |
| Crypto / structural | 13 | 5 | 4 | 1 | 8 | 0 | 2 |
| Sandbox / isolation | 8 | 5 | 3 | 4 | 3 | 2 | 0 |
| Human in the loop | 0 | 2 | 0 | 0 | 0 | 0 | 0 |

Totals across rows that the text quotes: 41 of 92 (44.6%) address agent
manipulation, 35 (38.0%) poisoning & extraction, 23 (25.0%) jailbreak, 15
(16.3%) red-teaming, 7 (7.6%) prompt infection, 6 (6.5%) pre-execution.
Their critique of base-model alignment: it trusts the very component under
attack (p35).

### Cost (§5.3.3, Fig. 11a, Table 3, p35–38)

How papers report cost: qualitative/theoretical only **36 (39.1%)**, security +
utility 23 (25.0%), security + compute 15 (16.3%), comprehensive 18 (19.6%).

Table 3 (p37), which the authors stress is **not a ranking**; each row is on
its own task and hardware:

| Defense | Security result | Latency | Cost | Utility |
|---|---|---|---|---|
| PPA (small model) | high, bypass resistant | ~0.06 ms | no overhead | minimal |
| MCP-GUARD | +23.4% F1 | ~455.9 ms | low | high |
| IPIGuard | ASR < 1% | ~13.88 s | 14,605 tokens/task | 67.7% |
| PhishDebate | 94.14% accuracy | ~37.50 s | high | n/a |
| GuardAgent | 81.4% accuracy | ~6.30 s | 6,116 tokens/task | moderate |
| ProvSEEK | 0.92 F1 | ~30 min | 440K tokens | n/a |

### Placement (§5.3.4, Fig. 11b, p38)

**72 of 92 (78.3%)** intervene before computation, **20 (21.7%)** after:
more than three to one. Post-computation examples: AgentSentry, ShieldAgent.
The authors note each paper gets one primary placement, so this does not
count layered systems.

---

## 7. Cross-cutting numbers (§6, p39–45)

### Defense coverage by attack class (§6.1, Fig. 12, p39–40)

81 defense papers, each assigned **one** primary attack class and **one**
primary defense mechanism; cells sum to 81. The authors say explicitly that
the cells measure *attention*, not effectiveness.

| Primary attack ↓ / defense → | Input san. | Struct. queries | LLM monitor | Moving target | Cap.-scoped | Crypto | Dataset san. | Sandbox & formal | Red-team sim. | Consensus | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Injection | 5 | 8 | 5 | 1 | 7 | 1 | 0 | 0 | 3 | 0 | **30** |
| Prompt infection | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **1** |
| Poisoning & extraction | 4 | 0 | 2 | 1 | 1 | 3 | 0 | 0 | 1 | 3 | **15** |
| Jailbreak | 3 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 3 | 0 | **9** |
| Agent manipulation | 0 | 0 | 10 | 0 | 1 | 0 | 0 | 3 | 2 | 2 | **18** |
| Pre-execution | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **3** |
| Red-teaming | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 4 | 0 | **5** |

Injection gets the most defensive attention (structured queries lead, 8);
agent manipulation is second (LLM monitoring leads, 10); prompt infection has
a single defense paper.

### Architecture (§6.2, Figs. 13–14, p40–42)

- Cardinality (274): single-agent **196 (71.5%)**, multi-agent 58 (21.2%),
  hybrid 20 (7.3%).
- Autonomy (221 papers with a system): Level 3 **148 (67.0%)**, Level 2 34
  (15.4%), Level 1 26 (11.8%), Level 0 13 (5.9%).
- Paradigms (257): monolithic 103 (40.1%), planner-executor 83 (32.3%), hybrid
  54 (21.0%), LLM-as-a-judge 10 (3.9%), debate 5 (1.9%), teacher-student 2 (0.8%).
- Roles (230 papers, 703 assignments, 3.06 per paper): executor 204 (88.7%),
  tool-caller 169 (73.5%), planner 153 (66.5%), critic 118 (51.3%), governor
  **59 (25.7%)**.

### Models and knowledge (§6.3, Fig. 15, p42–44)

GPT **237 papers (86.5%)**; LLaMA 137 (50.0%); Claude 120 (43.8%); Gemini 91
(33.2%); Qwen 78 (28.5%); DeepSeek 64 (23.4%); Mistral/Mixtral 48 (17.5%).
47 papers evaluate GPT alone. Knowledge: pre-trained 265 (96.7%), in-context
learning 209 (76.3%), fine-tuning 69 (25.2%), RAG 67 (24.5%), preference
learning 33 (12.0%).

### Modalities (§6.4, Fig. 16, p43–45)

272 papers, 582 assignments: text 267 (98.2%), code 158 (58.1%), logs 73
(26.8%), images 43 (15.8%), network traces **26 (9.6%)**, binaries **15 (5.5%)**.

---

## 8. Conclusion, future work, limitations (§7, p45–46)

- Future work they name: study persistence and exfiltration (and their
  defensive counterparts); raise defensive autonomy; build attacks,
  benchmarks and defenses aimed at memory, reflection and inter-agent
  channels; unified benchmarks that allow cross-paper comparison;
  lifecycle-wide, defense-in-depth designs with provable guarantees; more
  network-trace and binary coverage.
- Limitations they admit: software threats only (little on embodied or
  physical agents); academic, public literature only, so industry practice may
  be ahead of what they describe; few studies report cost, speed or energy;
  some taxonomy choices are subjective (amplified vs agent-native, and primary
  defense category, are the two judgment calls they single out in App. B).
- Broader impact: they publish no attacks; they note that reward hacking and
  manipulation that leave outputs clean are dangerous precisely because the
  operator sees a "working" system.

---

## 9. Where the brief and the paper differ

1. **Version.** The brief says v3 (12 June 2026); the paper online is v4 (31
   Oct 2026, TMLR). I used v4. Details in the next section.
2. **Seven threat classes, not five.** The brief lists injection, poisoning,
   jailbreak, agent manipulation and pre-execution cognitive. v4 §4.1 also has
   **red-teaming attacks (§4.1.6)** and **interface-level attacks (§4.1.7)**.
3. **"Structurally fragile by default."** In v4 the authors draw this
   conclusion from the fact that most attacks succeed **black-box** (§1, p2;
   §4.4.4, p28). The "whole lifecycle" idea is in the paper, but as two
   separate points: attacks reach every stage of the loop (§4.1 summary, p23),
   and defenses need to span the lifecycle (§7). I will keep those three
   claims separate rather than merging them.
4. **The MCP-SafetyBench hook is supported**, exactly as described: 1.22%,
   reported as statistically insignificant (§4.2.1, p23). In the survey's
   taxonomy, MCP-SafetyBench sits under threat evaluation (adversarial
   benchmarks), not under defenses.
5. **Red vs blue.** The survey reports lifecycle coverage (Fig. 5) and an
   autonomy comparison (Fig. 6), not raw red/blue paper totals per se. Both
   are usable for the brief's figure 6.
6. **Defense coverage matrix.** The survey's Fig. 12 counts papers per
   (attack, defense) pair. It measures *attention*, and the authors say it is
   not effectiveness. My figure will be shaded by paper count and labelled
   that way, not as "how well covered".
7. **Reward hacking** is in the survey under agent manipulation (§4.1.4) and is
   named as the fifth agent-native mechanism, "specification and reward
   gaming" (§4.4.3). That is the right anchor for the assignment 5 comparison.

## 10. Inconsistencies inside the paper (to quote carefully)

- **MSB peak ASR**: 76.5% for out-of-scope-parameter attacks in §4.2.1 (p23),
  but "75.8% peak" in §4.4.1 (p26). I will quote the §4.2.1 figure, which is
  given with its attack type, and note the other.
- **WebInject**: "over 96%" (p19), "97% ASR across web-agent backbones" (p26),
  "exceeding 0.96" (p22). Same result, rounded differently. I will say "over 96%".
- **VisualTrap**: "over 90%" (p20) vs "about 94%" (p26). I will say "over 90%".
- **AgentPoison poison rate**: "under 0.1% of entries poisoned" (§4.1.2, p20) and
  "a poison rate under 1%" (§4.4.1, p26). Both are true statements about the same
  result, but the second is ten times looser; quote the §4.1.2 figure.
- **WASP end-to-end**: "17%" (p24) and "16.7%" (p29). Same number.
- **Agent-specificity denominators**: the percentages use 111 labels
  including unclassified; the per-class "of 36", "of 25" also include
  unclassified labels; Fig. 9b shows only classified ones. Not a contradiction,
  but easy to misquote.
- In §5.3.2 each trust-boundary paragraph quotes an attack-class *total*
  across all boundaries (e.g. "41 papers address agent manipulation" inside the
  formal-verification paragraph). The per-boundary counts are in Fig. 10b.
  I will not attribute those totals to the boundary they appear next to.

## v3 vs v4: what changed

| | v3 (12 Jun 2026, 59 pp.) | v4 (31 Oct 2026, 69 pp., TMLR) |
|---|---|---|
| Corpus | "over 260 papers" | 274 papers, counted exactly |
| Background section | none (related work at the end, §6) | new §2: eight-stage loop, autonomy levels, threat models |
| Threat classes | 6 (no interface-level) | 7 (adds §4.1.7 interface-level attacks) |
| Why alignment fails | absent | new §4.3 with the harness ablation |
| Conversational-input share of attacks | 55% | 56.8% |
| Distinct benchmarks | 108 | 124 |
| LLM-based monitoring share | 40.0% | 53.3% |
| GPT backbone share | 95.7% (242 papers) | 86.5% (237 papers) |
| Most-attacked stages (conclusion) | perception and action selection | **reasoning** and action selection |
| MCP-SafetyBench 1.22% | present | present, unchanged |

The last two rows are why the version matters: v3's stage finding was
revised in v4, so an article built on v3 would state a conclusion the authors
have since changed.

## Secondary surveys (read lightly, for contrast)

**Yehudai et al., Survey on Evaluation of LLM-based Agents (arXiv 2503.16416v2).**
Organises agent evaluation into five perspectives (core capabilities, application
benchmarks, generalist agents, benchmark dimensions, evaluation frameworks). Its
gap list (§7 and conclusion) names cost-efficiency, safety and robustness as the
under-measured dimensions, says binary success metrics hide intermediate progress,
proposes "guardrail" metrics that penalise success reached through non-compliant
actions (§5, safety and robustness metrics), and asks for evaluations that vary the
backbone LLM and the harness independently (§7, decoupling LLM and harness).
Contrast used: the agentic-security survey reaches the same metric complaint from
the security side (66 of 86 threat papers report ASR; 19 report utility; 14 cost;
§4.4.5 p29), and its §4.3 ablation is exactly the harness-varied, model-fixed
experiment Yehudai et al. ask for.

**Guo et al., From Question Answering to Task Completion: A Survey on Agent System
and Harness Design (arXiv 2606.20683v1).** Treats an agent as a foundation model
coupled with an execution harness and splits the harness into six runtime
responsibilities: observation, context, control, action, state, and
verification/governance (§5). Governance covers approval gates, sandboxing, budget,
rollback and safe termination; §5.6 argues constraints should be mechanically
enforced instead of left to the model obeying its prompt, and §5.7 notes that more
expressive actions raise the burden on permissions and sandboxing. Safety is one of
its four open challenges and one term in its value-aware objective (§8.1).
Contrast used: the MCP-SafetyBench 1.22% result is the security-side evidence for
Guo et al.'s "mechanically enforced" point, and my assignment2 stages 12–13 and
assignment4 theme 06 are both governance-layer code in their vocabulary.

**Du, Memory for Autonomous LLM Agents (arXiv 2603.07670v1).** Models memory as a
write–manage–read loop with a three-axis taxonomy (temporal scope,
representational substrate, control policy) and five mechanism families. Its
write-path section (§7.1) is about filtering noise for retrieval quality, and its
privacy section (§7.5) is about encryption, scoping and deletion; reflection is
framed as a mechanism that can entrench mistakes through confirmation bias (§9.3).
Contrast used: the memory survey treats a bad write as an accuracy problem, while
the security survey counts persistent-state poisoning as an agent-native threat;
and the security survey finds 0 papers attacking reflection as an entry point
(§4.4.2 p25) and 1 benchmark instrumenting memory (§4.4.5 p29), even though Du
treats reflection and memory as core to adaptive agents.
