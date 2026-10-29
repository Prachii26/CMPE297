# Demo transcript — B2B lead research pipeline

**Status: PARTIAL.** Five of the pipeline's seven stages complete against real
models with real web evidence: the planner, all three parallel researchers, and
the lead scorer. The critic loop and the report writer did not finish inside
the timebox, so there is no final lead table.

Best run: **2026-10-29**, session `d91c0a0c`. Server `adk web --port 8741`, app
`lead_research`.

| Agent | Model |
|---|---|
| `IcpPlanner`, `LeadScorer`, `EvidenceCritic`, `ReportWriter` | `gemini-3.5-flash` |
| `MarketResearcher` | `gemini-3.5-flash-lite` |
| `FirmographicResearcher` | `gemini-3.1-flash-lite` |
| `SignalResearcher` | `gemini-flash-lite-latest` |
| `CriticSearchAgent` | `gemini-3.1-flash-lite` |

> **Why five models.** Free-tier quota is 20 requests/day **per model**. The
> three researchers run simultaneously, so sharing one model is an immediate
> 429. Set with `LEAD_RESEARCH_RESEARCHER_MODELS`.

---

## The query

> ICP: industrial IoT and sensor manufacturers, Nordics, 200-1000 employees.

## What completed

```
stages written: research_plan, research_market, research_firmographic,
                research_signals, scored_leads
event authors:  IcpPlanner 1, MarketResearcher 13, FirmographicResearcher 13,
                SignalResearcher 11, LeadScorer 5, EvidenceCritic 1
```

### Stage 1 — planner

Restated the ICP and produced three briefs with concrete queries, then wrote
`research_plan` to state:

```
ICP
Industry: Industrial IoT and sensor manufacturing
Region: Nordics (Sweden, Norway, Denmark, Finland, Iceland)
Company Size: 200–1,000 employees

MARKET  Queries:
 1. "industrial IoT" OR "sensor manufacturers" list Sweden Norway Denmark Finland company directory
 2. "industrial sensors" OR "smart manufacturing" OR "connected devices" manufacturers directory Nordics
FIRMOGRAPHIC  Queries:
 1. "industrial IoT" OR "sensor manufacturer" "200..1000 employees" Sweden OR Finland site:linkedin.com/company
 2. site:proff.se OR site:finder.fi OR site:virk.dk "sensor" OR "industrial IoT" "200".."1000" employees
SIGNALS  Queries:
 1. "industrial IoT" OR "sensor manufacturer" Nordics "hiring" "VP" OR "Director" OR "Head of"
 2. "industrial sensor" OR "IIoT" Nordics "funding" OR "acquired" OR "digital transformation"
```

### Stage 2 — three parallel researchers, real web search

All three ran inside the `ParallelAgent`, each calling the `web_search`
FunctionTool. Searches per researcher: **6 / 6 / 5**, within the 6-search
budget. Sample result shape:

```json
{"ok": true, "query": "...", "result_count": 5,
 "results": [{"title": "...", "url": "https://...", "snippet": "..."}],
 "note": "Cite the `url` values exactly; do not invent URLs."}
```

Market researcher output (excerpt), with sources attached to every claim:

> - **Safran Sensing Technologies Norway AS**: A Norwegian manufacturer and
>   developer of high-precision MEMS gyros, inertial measurement units (IMUs),
>   and semiconductor wafer foundry services
>   (https://en.wikipedia.org/wiki/Safran_Sensing_Technologies_Norway).
> - **Smart Sensor Devices**: A developer of IoT sensors, air quality
>   monitoring hardware, and smart HVAC controllers...

### Stage 3 — the scorer, with the fit-score tool

`LeadScorer` called `score_lead_fit` **five times**, once per company, passing
what the research actually established:

```json
{"company": "Safran Sensing Technologies Norway AS",
 "industry_match": "exact", "region_match": "exact", "size_match": "exact",
 "buying_signals": 1,
 "evidence_urls": ["https://en.wikipedia.org/wiki/Safran_Sensing_Technologies_Norway", ...]}
```

and wrote `scored_leads`:

```
COMPANY: Safran Sensing Technologies Norway AS
FIT_SCORE: 5
WHY: Develops and manufactures high-precision MEMS gyros and inertial
     measurement units (IMUs) with an in-house wafer fab in Norway.
SIGNALS: Active recruitment for production support roles at its Norwegian
     manufacturing operations.
SOURCES: https://en.wikipedia.org/wiki/Safran_Sensing_Technologies_Norway,
     https://newluxjob.com/en/jobs/norway/customer-support/3015347-production-support

COMPANY: Smart Sensor Devices
FIT_SCORE: 4
WHY: Sweden-headquartered manufacturer of IoT sensors, air quality monitoring
     hardware, and connected smart HVAC controllers.
SIGNALS: none found
SOURCES: https://smartsensordevices.com/

COMPANY: JonDeTech
FIT_SCORE: 4
WHY: Swedish developer and manufacturer of ultra-thin infrared (IR) thermal
     sensors for smart devices and industrial applications.
SIGNALS: none found
SOURCES: https://jondetech.com/

COMPANY: ELSYS
FIT_SCORE: 4
WHY: Swedish manufacturer of wireless LoRaWAN environmental sensors built
     specifically for industrial and extreme outdoor environments.
SIGNALS: none found
SOURCES: https://www.elsys.se/en/sensors/

COMPANY: Crosser
FIT_SCORE: 3
WHY: Stockholm-based industrial edge software and streaming analytics provider
     serving the industrial IoT integration ecosystem in Sweden.
SOURCES: https://www.folotop.com/top-5-industrial-iot-solutions-providers-in-sweden/
```

These are real companies with real URLs, and the scores discriminate sensibly:
Safran takes 5 on an exact match across all three ICP dimensions plus a hiring
signal; Crosser drops to 3 because it is edge *software* rather than sensor
manufacturing, and its only source is an aggregator listicle. "SIGNALS: none
found" is reported honestly rather than padded.

### Stage 4 — the critic started

`EvidenceCritic` ran and called `CriticSearchAgent`, the `AgentTool`-wrapped
search agent, to verify a source — the composition behaving exactly as
designed. It did not return before the run was cut off.

## Where it stops, and why

The critic's verification round trip plus the writer need four more model calls
on top of the ~32 already spent. By that point in the day every model bucket
was at or near its 20-request cap, and the final attempt produced
`8 × HTTP 429` without the planner even completing.

```
stages: []    authors: {'user': 1}
```

This is a quota ceiling, not a defect in the loop: the critic is reached, it
calls its tool, and `max_iterations` bounds it. The loop's termination is
covered offline by `tests/test_offline_run.py`, which runs all four stages
against a scripted model and asserts the cap holds when the critic never calls
`exit_loop`.

## Three attempts, and what each one taught

| # | Change | Result |
|---|---|---|
| 1 | `google_search` on `gemini-2.5-flash`, then `gemini-flash-latest` | 429 at the parallel stage both times |
| 2 | One model per researcher | Still 429 — which **ruled out the per-model quota** |
| 3 | Replace `google_search` with DDG-backed `web_search` | Parallel stage completes; reached the scorer |

The decisive test for attempt 2 → 3, one model and one minute:

```
plain (no tools)       200 OK
grounded (search)      429  You exceeded your current quota...
```

**Search grounding is metered separately from the model.** The error shape is
the tell: per-model 429s carry a `QuotaFailure` naming
`GenerateRequestsPerDayPerProjectPerModel`; the grounding one carries only a
help link.

Two further faults were found and fixed along the way, both mine:

- **The search tool held its rate-limit lock across the network call.** One
  researcher's request blocked the other two, and a run sat for 1500 seconds
  with *zero API errors* before timing out. The lock now only reserves a time
  slot; the wait and the request happen outside it. A stall with no errors at
  all points at your own concurrency, not at the provider.
- **Researchers had no search budget.** The market researcher ran **33**
  searches in one run, searching per candidate company rather than per brief,
  and exhausted its model's daily quota before the pipeline could finish. The
  budget is now 6.

DDG throttling was also measured and fixed: it answers a three-way burst with
HTTP 202 and an empty body rather than an error. At a 1.5 s inter-call gap,
**4 usable responses against 15 throttled**; at 6 s, **4 against 0**.

## The screenshot

![ADK dev UI showing the pipeline and the planner output](adk-web-leads.png)

The dev UI with the `lead_research` pipeline loaded, the ICP query accepted,
and the planner's three briefs rendered, with `State: research_plan` recorded.
The later stages shown above are evidenced by the session state dump rather
than this view, because the screenshot of the full run was overwritten by the
final quota-exhausted attempt.

## What is verified without the API

34 tests, none touching the network, including a full end-to-end run of all
four stages against a scripted model:

- every stage writes its `output_key`, in order;
- all three researchers execute inside the `ParallelAgent`;
- the critic loop is capped and terminates when the critic never exits;
- no agent uses the built-in `google_search`;
- the 1–5 fit score is deterministic, capped at 2 without a source URL, and in
  range for every combination of inputs;
- `web_search` normalises results, drops results with no URL, clamps
  `max_results`, truncates snippets, retries transport failures, and reports
  failure as a value rather than raising.
