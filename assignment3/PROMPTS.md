# Prompts

Every prompt sent for Assignment 3, verbatim, in order.

At the time of writing there has been exactly one prompt: the full assignment
brief below, reproduced word for word with no edits, reordering, or
summarising. (It arrived duplicated in the session — the same text twice in one
message — and is recorded once here, as the single prompt that was sent.)

---

## Prompt 1

````text
Assignment 3: build five Google ADK agents end to end.

## Location
Create the Assignment3 folder at the root of the CMPE297 repo, next to the existing Assignment1 and assignment2 folders. Do not nest it inside assignment2.

Step 1: list the repo root and check the exact names of the existing assignment folders (assignment2 is lowercase on disk). Match that naming style. If the existing folders use lowercase, create assignment3. Otherwise use Assignment3.

Step 2: create this structure:
  Assignment3/
    _reference/              (gitignored, not submitted)
    a_deep_research_agent/
    b_gemini_cli_agent/
    c_bug_assistant_agent/
    d_code_review_agent/
    e_ecommerce_agent/
    README.md
    PROMPTS.md
    DECISIONS.md

Step 3: add `_reference/` and `.venv/` to the repo-root .gitignore if they are not already there. Do not add a second .gitignore inside Assignment3 unless an agent folder needs one.

Step 4: confirm the tree with a directory listing, then continue. Every agent path below is relative to Assignment3/.

I am on Windows PowerShell. Write every run command in PowerShell syntax, and use paths like `cd Assignment3\c_bug_assistant_agent`.

## Ground rules
- Python 3.11. One .venv per agent folder. Pin google-adk and record the exact version in each README.
- Model: gemini-2.5-flash. Local runs use AI Studio: GOOGLE_GENAI_USE_VERTEXAI=FALSE and GOOGLE_API_KEY, mapped from the GEMINI_API_KEY already in my environment. Put keys only in .env (gitignored), never in any tracked file.
- Clone the five reference repos into Assignment3/_reference/ with gh. Read the references before you write anything. Do not copy files from them. Write our own code, change the domain, and change at least two behaviours per agent. Cite each source in that agent's README.
- Do not ask me questions. Make a reasonable call and log it as one line in Assignment3/DECISIONS.md.
- Commit and push after each agent is verified.
- Cloud deployment is out of scope until everything else is done. Do not create any GCP resources without asking me.

## Definition of done, per agent
Each agent folder contains:
- The agent code, organised as an ADK package that `adk web` can load.
- README.md: what it does, a mermaid architecture diagram, setup, run, env vars, known limits, sources.
- requirements.txt and .env.example.
- tests/ with at least 3 pytest tests that run without a live API (stub the model or the tools).
- docs/demo.md with one real transcript from a live run, and a screenshot in docs/.

"Verified" means: adk web starts, one real Gemini call succeeds, the tool calls show in the trace, and the tests pass. If an agent is still failing after 45 minutes, stop, mark it PARTIAL in its README with the exact error, and move on. Do not fake a pass.

## Agents, in build order

c_bug_assistant_agent (MCP first, no cloud)
Build a small MCP server (FastMCP) over a SQLite bug tracker seeded with 30 synthetic bugs. Tools: search_bugs, get_bug, add_comment, set_status. The ADK agent connects with McpToolset and StdioConnectionParams. Reference: google/adk-samples software-bug-assistant and the zero-to-assistant codelab. Our change: triage by severity and component, and set_status requires a reason.

a_deep_research_agent (lead generation)
Input is an ideal customer profile: industry, region, company size. Use SequentialAgent, ParallelAgent, and LoopAgent. A planner splits the search, parallel researchers run, a critic loop checks the evidence, and a report writer outputs a markdown lead table with company, fit reason, and source URLs. Pass state between agents with output_key. If the built-in google_search tool conflicts with other tools on the same agent, wrap the search agent in AgentTool. Verify this against the installed ADK version. Reference: MagnIeeT/leadGenerationAgentADK and the Google blog post "Build a deep research agent with Google ADK". Our change: each lead gets a 1–5 fit score.

d_code_review_agent
Root agent takes a Python file path. Tools: ast parse, pycodestyle, and a complexity count, all as FunctionTools. A reviewer LlmAgent writes findings with severity. A LoopAgent fixer proposes a patch, re-runs the checks, and exits through an exit_loop tool when they pass, capped at 3 iterations. Include samples/buggy_module.py with planted bugs. Reference: ayoisio/adk-code-review-assistant. Our change: the fixer must also emit a unified diff.

b_gemini_cli_agent
An LlmAgent that calls Gemini CLI as a function tool: gemini_cli(prompt, cwd). It runs `gemini -p` non-interactively through subprocess with a 120-second timeout and returns stdout capped at a fixed size. Errors come back as strings, not exceptions. Use shutil.which to find the executable, because on Windows it is gemini.cmd. Never pass auto-approve flags, and pin cwd to a sandbox folder. Install the CLI with npm if it is missing, and record the install step. Reference: derrickchwong/gemini-cli-on-adk. Our change: the agent answers questions about a code folder and returns a structured summary.

e_ecommerce_agent
Tools: search_products, get_product, add_to_cart, place_order, order_status. All are served through a local SQLite MCP server with seeded synthetic data. Every tool takes user_id and checks ownership before reading or writing. Reference: mtoscano84/sports-agent-adk-mcp-alloydb. Document the AlloyDB-to-SQLite swap in the README with the reason: AlloyDB needs a paid cluster. Our change: out-of-stock items return alternatives.

## Final deliverables
- Assignment3/README.md: a table of the five agents with status (WORKING or PARTIAL), one line each, run commands, and links to each agent README.
- Assignment3/PROMPTS.md: every prompt I sent for this assignment, verbatim, in order. Pull them from session history. Do not invent or reword any.
- Run all test suites and report pass counts per agent.
- Grep the whole Assignment3/ tree for AIza and sk- and confirm there are no hits.
- Confirm _reference/ and .venv/ are gitignored.

End with: each agent's status, the one real demo query and a one-line summary of its output, and any partial agent with the reason.
````
