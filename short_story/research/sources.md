# Sources

Every paper cited in the article, with links. The published article is on Medium: <https://medium.com/@prachigupta2610/gpt-4o-refuses-every-request-until-you-wrap-it-in-an-agent-784d7aa24a46>

## Primary

- Shahriar, A., Rahman, M. N., Ahmed, S., Sadeque, F., Parvez, M. R. *A Survey on Agentic Security: Applications, Threats and Defenses.* Transactions on Machine Learning Research (11/2026). arXiv:2510.06445 (v4, 31 Oct 2026; v3, 12 Jun 2026 also consulted). <https://arxiv.org/abs/2510.06445> · OpenReview: <https://openreview.net/forum?id=Od4ZnAUv9T> · Companion list: <https://github.com/kagnlp/Awesome-Agentic-Security>

## Secondary surveys (for contrast)

- Yehudai, A., Eden, L., Li, A., Uziel, G., Zhao, Y., Bar-Haim, R., Cohan, A., Shmueli-Scheuer, M. *A Survey on Evaluation of LLM-based Agents.* arXiv:2503.16416. <https://arxiv.org/abs/2503.16416>
- Guo, J., Hao, Z., Wang, C., et al. *From Question Answering to Task Completion: A Survey on Agent System and Harness Design.* arXiv:2606.20683. <https://arxiv.org/abs/2606.20683>
- Du, P. *Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers.* arXiv:2603.07670. <https://arxiv.org/abs/2603.07670>

## Systems cited through the primary survey

These are cited through the primary survey: every number about them in the article is the survey's report, at the section and page given. I did not read these papers individually; full references are in the survey's bibliography.

| System or study | Citation as given in the survey | Where in the survey (v4) |
|---|---|---|
| Harness ablation (GPT-4o clear denial 100% → 53.3%) | Chiang et al. (2025) | §4.3, p. 25 |
| MCP-SafetyBench | Zong et al. (2026) | §4.2.1, p. 23 |
| MCPTox | Wang et al. (2026b) | §4.2.1, p. 23 |
| MSB, MCP Security Bench | Zhang et al. (2025b) | §4.2.1, p. 23; §4.4.1, p. 26 |
| WASP | Evtimov et al. (2026) | §4.2.1, pp. 23–24; §4.4.5, p. 29 |
| AgentPoison | Chen et al. (2024) | §4.1.2, p. 20; §4.4.1, p. 26 |
| MINJA | Dong et al. (2026) | §4.1.2, p. 20 |
| ToolHijacker; adaptive attacks on 8 defenses | as cited in §4.1.1; Zhan et al. (2025) | §4.1.1, p. 19 |
| BrowserART | Kumar et al. (2025) | §4.1.3, p. 20 |
| HPTSA | Zhu et al. (2025c) | §3.4.3, p. 18; §4.4.3, p. 28 |
| ARTEMIS | Lin et al. (2026) | §3.4.3, p. 18 |
| One-day CVE exploitation agent | Fang et al. | §3.4.3, p. 18 |
| CVE-Genie | as cited in §3.4.3 | §3.4.3, p. 18 |
| IPIGuard and the other Table 3 defenses | as cited in Table 3 | §5.3.3, p. 37 |
| ASB, AI2 (two different 84.30% results) | as cited in §4.1 | §4.1, pp. 19, 21; §4.4.5, p. 29 |

## This repo (two-cents section)

- assignment2/partA stage 12 (permissions), stage 13 (sandbox), stage 14 (compaction)
- assignment3 agents C and E (McpToolset over stdio, tool_filter)
- assignment4/06_mcp_apps (host allow-list, CSP, sandboxed iframe)
- assignment5/guard and assignment5/01_so_rsi
