# Build Prompts

## Initial Build Prompt

> You are building a data science portfolio app for a graduate assignment. Work fast and precisely. Do not ask me clarifying questions — make reasonable choices and keep going.
>
> ## Context
> This replicates (and improvises on) a professor's 14-project data science repo. I have limited time, so we build ONE Streamlit multipage app containing 5 real data science projects plus a CRISP-DM audit page. Depth over breadth is a deliberate scoping decision.
>
> ## Hard constraints
> - Python + Streamlit ONLY. No React, no npm, no FastAPI, no separate ports.
> - Dependencies limited to: streamlit, pandas, numpy, scikit-learn, plotly. Nothing else.
> - All datasets generated synthetically in code with fixed seeds (np.random.default_rng(42)). No downloads, no Kaggle, no network calls at runtime. The repo must run offline with two commands.
> - Every model must train in under 5 seconds. Cap sample sizes accordingly.
> - Use @st.cache_data on all data generators and @st.cache_resource on all trained models. The UI must feel instant when sliders move.
> - NO DATA LEAKAGE. All scaling/encoding goes inside a sklearn Pipeline fit on train folds only. Time series uses TimeSeriesSplit with shuffle=False. This is graded — be strict.
>
> ## File layout
> Assignment1/
>   app.py
>   requirements.txt
>   README.md
>   PROMPTS.md
>   .gitignore
>   core/__init__.py
>   core/data.py          # all synthetic data generators
>   core/viz.py           # shared plotly theme + helper chart functions
>   core/models.py        # training functions, all seeded
>   pages/1_Trip_Duration.py
>   pages/2_Customer_Segmentation.py
>   pages/3_Market_Basket.py
>   pages/4_Anomaly_Detection.py
>   pages/5_Time_Series.py
>   pages/6_CRISPDM_Audit.py
>   docs/screenshots/.gitkeep
>
> ## app.py — portfolio home
> Title, one-paragraph intro, a table listing all 6 pages with what each demonstrates, a "How this was built" section naming Claude Code as the agent used, and a Quick Start block. Set st.set_page_config(layout="wide") in every page file.
>
> ## Every project page follows the SAME 6-tab structure
> tabs = st.tabs(["Business Understanding", "Data Understanding", "Data Preparation", "Modeling", "Evaluation", "Live Inference"])
> This maps 1:1 to CRISP-DM. In each tab write 2-4 sentences of real explanation (plain, direct prose — no corporate filler) plus the actual code output/chart. The Live Inference tab must have interactive widgets that produce a prediction immediately.
>
> ## The 5 projects
>
> 1. TRIP DURATION PREDICTOR (pages/1_Trip_Duration.py)
> Synthetic NYC-style taxi trips, 8000 rows: pickup/dropoff lat-lon within NYC bounds, hour, weekday, passenger count, haversine distance, duration as a nonlinear function of distance/hour/weekday plus noise.
> Model: HistGradientBoostingRegressor inside a Pipeline. Compare against a LinearRegression baseline.
> Show: haversine feature engineering explained, distance vs duration scatter with trendline, 24x7 hourly demand heatmap, residual plot, RMSE/MAE/R2 for both models side by side, permutation feature importance.
> Live Inference: sliders for pickup/dropoff coords, hour, weekday, passengers -> predicted minutes + a plotly map showing the two points.
>
> 2. CUSTOMER SEGMENTATION (pages/2_Customer_Segmentation.py)
> Synthetic RFM data, 3000 customers, 4 latent groups with real separation.
> Model: KMeans inside a Pipeline with StandardScaler. Sweep k=2..10, plot elbow (inertia) AND silhouette score. Add PCA 2D projection colored by cluster.
> Show: per-cluster profile table (mean recency/frequency/monetary, size, % of revenue), plus a plain-English persona label per cluster derived from the centroids.
> Live Inference: user enters their own R/F/M -> assign to a cluster, show which one and why.
>
> 3. MARKET BASKET MINING (pages/3_Market_Basket.py)
> Synthetic grocery transactions, 4000 baskets, ~25 items, with 4 planted co-occurrence rules so the algorithm finds something real.
> Implement Apriori FROM SCRATCH in core/models.py — do not use mlxtend. Candidate generation, support pruning, then rule generation with support/confidence/lift.
> Show: item frequency bar chart, the itemset lattice size at each level, a rules table sortable by lift, and a network-style scatter of antecedent vs consequent sized by lift.
> Live Inference: min_support / min_confidence / min_lift sliders that re-run the miner and update the rules table. Also a "customer has X in cart" selector that recommends the top-3 next items.
>
> 4. ANOMALY DETECTION (pages/4_Anomaly_Detection.py)
> Synthetic server telemetry, 6000 rows, ~2% labeled anomalies (latency spikes, error bursts, throughput collapse).
> Models: IsolationForest and LocalOutlierFactor(novelty=True). Compare.
> Show: WHY accuracy is the wrong metric here (state the class balance and what a majority-class predictor would score), then precision-recall curve, PR-AUC, ROC-AUC, confusion matrix at the chosen threshold.
> Live Inference: threshold slider that moves the confusion matrix live and shows the precision/recall tradeoff in real numbers, plus a table of the top-20 flagged records.
>
> 5. TIME SERIES FORECASTING (pages/5_Time_Series.py)
> Synthetic daily demand, 730 days: trend + weekly seasonality + yearly seasonality + noise.
> Model: lag-feature regression (lags 1,7,14,28 + rolling means) with HistGradientBoostingRegressor, evaluated with TimeSeriesSplit(n_splits=5). Baseline: seasonal naive (t-7).
> Show: the series with train/test split marked, ACF plot computed manually with numpy up to 40 lags, backtest fold-by-fold MAPE table, forecast vs actual overlay.
> Live Inference: horizon slider (7-90 days) producing a recursive forecast with the fan/uncertainty band from backtest residual quantiles.
>
> 6. CRISP-DM & LEAKAGE AUDIT (pages/6_CRISPDM_Audit.py)
> This page is the differentiator. Include:
> - A walkthrough of all 6 CRISP-DM phases with what each meant concretely in THIS repo
> - A leakage audit table: one row per project, columns = Preprocessing fit scope / Train-test split method / Target leakage check / Seed pinned / Metric appropriate for class balance — with the actual answer for each project, and a code reference (filename + function name)
> - A short section on reward hacking: name 3 ways these specific models could be gamed into looking good (e.g. reporting accuracy on the 2%-anomaly dataset, shuffling a time series split, tuning on the test fold) and state what the code does to prevent each
> - A reproducibility section: seeds, versions, one-command run
>
> ## Writing style for ALL prose in the app and docs
> Direct, plain, human. Written like a grad student who understands the material. No "delve", "leverage", "it's worth noting", "in today's fast-paced world", no em-dash-heavy rhetorical flourishes, no bullet lists of adjectives. Short sentences. Say the thing.
>
> ## README.md
> - Title + one-paragraph what-this-is
> - Table of the 6 pages with a one-line description each
> - Quick start: pip install -r requirements.txt && streamlit run app.py
> - "Built with Claude Code" section: which agent, how the workflow went, what you'd do differently
> - Screenshots section with markdown image links pointing to docs/screenshots/ — leave placeholders named 01_home.png through 07_audit.png
> - A "YOUTUBE_VIDEO_LINK_HERE" placeholder near the top for the walkthrough video
> - A "Scope decisions" section stating honestly that this trades breadth for depth and why
>
> ## PROMPTS.md
> Record this build prompt verbatim under a heading, and leave a clearly marked section "Follow-up prompts" where I will add subsequent ones.
>
> ## Execution order
> 1. Create all files with requirements.txt and .gitignore first
> 2. core/data.py, core/viz.py, core/models.py
> 3. The 5 project pages
> 4. The audit page
> 5. app.py, README.md, PROMPTS.md
> 6. Run `streamlit run app.py` yourself, catch import/runtime errors, fix them, and confirm every page renders without exception before telling me you're done.
>
> Start now. Tell me only when it runs clean.

---

## Follow-up Prompts

<!-- Add subsequent prompts here as the project evolves -->

---

## Reproduction Prompts — Build This From Scratch

> This section is a reproduction guide, not a record of the actual session.
> Use this sequence with a coding agent (Claude Code or equivalent) to rebuild
> the project from an empty directory. Each prompt is self-contained and assumes
> the previous one completed successfully. Adjust metric values if your
> synthetic seeds produce different numbers.

---

### Prompt R1 — Initial Build

```
You are building a data science portfolio app for a graduate assignment (CMPE 297).
Work fast and precisely. Do not ask clarifying questions — make reasonable choices
and keep going.

## Hard constraints
- Python + Streamlit ONLY. No React, no npm, no FastAPI, no separate ports.
- Dependencies: streamlit, pandas, numpy, scikit-learn, plotly. Nothing else.
- All datasets generated synthetically in code with fixed seeds (np.random.default_rng(42)).
  No downloads, no Kaggle, no network calls at runtime. Runs offline with two commands.
- Every model trains in under 5 seconds.
- Use @st.cache_data on all data generators, @st.cache_resource on all trained models.
- NO DATA LEAKAGE. All scaling goes inside a sklearn Pipeline fit on train folds only.
  Time series uses TimeSeriesSplit with shuffle=False.

## File layout
Assignment1/
  app.py
  requirements.txt
  README.md
  PROMPTS.md
  .gitignore
  core/__init__.py
  core/data.py       # all synthetic data generators
  core/viz.py        # shared plotly theme + chart helpers
  core/models.py     # training functions, all seeded
  pages/1_Trip_Duration.py
  pages/2_Customer_Segmentation.py
  pages/3_Market_Basket.py
  pages/4_Anomaly_Detection.py
  pages/5_Time_Series.py
  pages/6_CRISPDM_Audit.py
  docs/screenshots/.gitkeep

## Every project page uses this tab structure
tabs = st.tabs(["Business Understanding", "Data Understanding", "Data Preparation",
                "Modeling", "Evaluation", "Live Inference"])
Write 2-4 sentences of real explanation per tab plus the actual chart or output.
The Live Inference tab must have interactive widgets that produce a prediction immediately.

## The 5 projects

1. TRIP DURATION (pages/1_Trip_Duration.py)
Synthetic NYC taxi trips, 8000 rows: pickup/dropoff lat-lon, hour, weekday,
passengers, haversine distance, duration as nonlinear function of distance/hour/weekday.
Model: HistGradientBoostingRegressor in a Pipeline. Baseline: LinearRegression.
Show: haversine explanation, distance-vs-duration scatter with numpy trendline,
24x7 heatmap, residuals, RMSE/MAE/R² for both models, permutation importance.
Live Inference: sliders for coords/hour/weekday/passengers → predicted minutes + map.
Note: do NOT use trendline="ols" in plotly — statsmodels is not in the dependency list.
Compute the trendline manually with np.polyfit.

2. CUSTOMER SEGMENTATION (pages/2_Customer_Segmentation.py)
Synthetic RFM data, 3000 customers, 4 latent groups.
Model: KMeans in a Pipeline with StandardScaler. Sweep k=2..10, plot elbow + silhouette.
Add PCA 2D projection. Show cluster profile table.
Persona labels MUST be derived from centroid values at runtime — do NOT hardcode
cluster-ID→label. Write a derive_personas(profile) function that ranks clusters by
composite score (inverted recency + frequency + monetary) and assigns
Champions/Loyal/At Risk/Dormant to those ranks.
Live Inference: R/F/M sliders → cluster assignment + persona.

3. MARKET BASKET (pages/3_Market_Basket.py)
Synthetic grocery transactions, 4000 baskets, 20 items.
Implement Apriori FROM SCRATCH in core/models.py — no mlxtend.
Planted rules: single antecedent → consequent (e.g. milk→butter at 55% probability).
Use 4 rules. Catalog size and basket density must be chosen so background pair lift < 1.0
(filtered by min_lift=1.0 default), leaving only planted-rule associations in the output.
Target: 8-16 rules at default settings (support=0.03, confidence=0.30, lift=1.0).
Live Inference: cart multiselect → top-3 recommendations.

4. ANOMALY DETECTION (pages/4_Anomaly_Detection.py)
Synthetic server telemetry, 6000 rows, 2% anomaly rate.
Models: IsolationForest and LocalOutlierFactor(novelty=True).
IMPORTANT: fit both models on an 80% training split (features only, no labels).
Evaluate PR-AUC on the 20% held-out test set. Score all 6000 records for the
Live Inference threshold demo. Return separate _test and _all score arrays.
Show why accuracy is wrong here (state the 98% majority-class baseline explicitly).
Live Inference: threshold slider → live confusion matrix + precision/recall/F1.

5. TIME SERIES (pages/5_Time_Series.py)
Synthetic daily demand, 730 days: trend + weekly + yearly seasonality + noise.
Model: lag features (lags 1,7,14,28 + rolling means) with HistGBR.
Evaluate with TimeSeriesSplit(n_splits=5), shuffle=False.
Baseline: seasonal naive (lag_7). Show fold-by-fold MAPE table — do not just report mean.
Compute ACF manually with numpy (no statsmodels).
Live Inference: horizon slider (7-90 days) → recursive forecast with uncertainty band
from backtest residual quantiles.

6. CRISP-DM AUDIT (pages/6_CRISPDM_Audit.py)
Static documentation page. Include:
- All 6 CRISP-DM phases with concrete description of what each meant in this repo
- Leakage audit table: one row per project, columns = preprocessing fit scope,
  train-test split method, target leakage check, seed pinned, metric appropriateness,
  code reference (filename + function name)
- 3 reward-hacking failure modes and what the code does to prevent each
- Reproducibility section

## app.py
Title, intro paragraph, pages table with key techniques, "How this was built" section
crediting Claude Code, Quick Start block. st.set_page_config(layout="wide") everywhere.

## Writing style
Direct, plain, human. No "delve", "leverage", "it's worth noting". Short sentences.

## Execution order
1. requirements.txt and .gitignore first (exclude docs/screenshots/*.png from git)
2. core/data.py, core/viz.py, core/models.py
3. The 5 project pages
4. The audit page
5. app.py, README.md, PROMPTS.md
6. Run the app, catch import/runtime errors, fix them, confirm every page renders.

Tell me only when it runs clean.
```

---

### Prompt R2 — Metric Audit and Data Quality Fixes

```
Run a metric audit across all 5 project pages and report back before changing anything.

For each page, print the key evaluation metrics from the actual trained models
(RMSE/R² for regression, silhouette for clustering, rules found at default thresholds
for basket, PR-AUC for anomaly, fold MAPEs for time series).

For each metric, give a one-line judgment:
- Is this suspiciously perfect (R² > 0.98, PR-AUC = 1.0, 0 rules found)?
- Is it realistic?
- Does the app page state the right metric for the problem type?

Do not change any code yet. Just report.
```

After reviewing the report, issue targeted fix prompts as needed. Common issues found in
this build:

```
The anomaly detection PR-AUC is 1.0 — the synthetic anomalies are trivially separable.
Rewrite make_telemetry_data in core/data.py so the task is genuinely hard:
- Draw all features from a correlated multivariate normal with realistic server metric
  correlations (latency-error positively correlated, CPU-memory positively correlated,
  throughput negatively correlated with both).
- 30% of anomalies should be subtle (single feature at 2.5σ).
- 40% moderate (two features at 3-6σ).
- 30% clear (three features at 6-10σ).
- Add 3x as many normal-but-unusual records (traffic bursts, maintenance windows)
  that are extreme in throughput only, to create realistic false-positive pressure.
- Target IsolationForest held-out PR-AUC between 0.75 and 0.90.
  Print the actual PR-AUC after each attempt. Up to 3 attempts, then stop and report.

Do not change the anomaly page or any other file — only core/data.py.
```

```
The market basket page shows 0 rules at default settings.
This means the planted rules do not produce sufficient support at the 3% threshold.
Fix the data, not the thresholds.
Restructure the planted rules to use single-item antecedents.
Choose catalog size and basket density so:
(a) background pair confidence < 0.30 (filtered by min_confidence default)
(b) background pair lift < 1.0 (filtered by min_lift=1.0 default)
(c) planted rule pairs have support > 3% and lift > 2.0

After fixing, confirm: apriori(baskets, 0.03, 0.30, 1.0) returns 8-16 rules,
and each of the planted rules appears in the output.
Only change core/data.py.
```

```
The segmentation persona labels are wrong. A customer with R=30, F=10, M=$400 is
labeled Dormant when they are clearly a high-value active customer.
The root cause is that PERSONA_LABELS is hardcoded by cluster ID, but KMeans does not
guarantee a fixed ID→centroid mapping.
Fix: replace the hardcoded dict with a derive_personas(profile) function that
computes a composite score per centroid (inverted recency + frequency + monetary,
each normalized to [0,1]), ranks clusters highest-to-lowest, and assigns
Champions/Loyal/At Risk/Dormant to those ranks.
Print each cluster's centroid and its assigned label so I can verify before I recapture.
```

---

### Prompt R3 — Screenshot Automation

```
Add automated screenshot capture using Playwright.

Create scripts/capture_screenshots.py that:
1. Starts the Streamlit app as a subprocess on port 8501, headless, no auto-browser.
2. Polls http://localhost:8501 until HTTP 200 (max 30s) — tight loop, no fixed sleep.
3. Uses Playwright sync API, chromium, viewport 1600x1000.
4. Captures the home page, then each of the 6 pages.
5. For EACH page: wait for networkidle, wait for .js-plotly-plot to exist in DOM,
   then sleep 2-3 more seconds for chart paint. Streamlit renders async — screenshots
   taken too early come out blank.
6. On the 5 project pages, click through the Modeling, Evaluation, and Live Inference
   tabs and capture each. On the audit page, capture the Leakage Audit Table tab.
7. Saves full-page PNGs to docs/screenshots/ with filenames matching README.md references.
8. Shuts the subprocess down cleanly in a finally block.
9. Prints each filename and KB size as it saves.
10. After all captures, prints a summary table and exits non-zero if any file is under 50 KB.

Add playwright to requirements.txt.
Run: playwright install chromium
Run: python scripts/capture_screenshots.py
Then verify every PNG exists and is over 50 KB. Report which ones fail if any.

IMPORTANT: In Streamlit 1.63, tabs are rendered as <div role="tab" data-testid="stTab">,
not <button role="tab">. Use page.get_by_role("tab", name=label) for clicking.
Use page.wait_for_selector('[data-testid="stTab"]') before any tab click.
The first page navigated to after a cold start may need 10-12 seconds extra wait
because model training runs on first render.
```

---

### Prompt R4 — Documentation

```
Add four root-level documentation files. Markdown only — do not change any code.

1. AUDIT_REPORT.md — export the full content of the CRISP-DM & Leakage Audit page
   into a standalone report. Include the per-project leakage table with actual file
   and function references, the three reward-hacking failure modes and what prevents
   each, the reproducibility section (seeds, versions, one-command run), and an honest
   limitations section covering synthetic data and the inflated R² on trip duration.

2. IMPLEMENTATION_PLANS.md — one section per project: business problem, data generation
   approach with the actual distributions used, feature engineering, model choice and why,
   evaluation protocol, and the final metric. State the real numbers.
   Add a short section on the overall architecture decision (single Streamlit app vs
   separate frontends) and why.

3. WALKTHROUGH.md — a code tour. For each of the 6 pages: which file, which functions
   in core/ it calls, what the reader should look at, and the key implementation detail
   worth understanding. Include a section on scripts/capture_screenshots.py explaining
   the Playwright approach and the Streamlit async-render problem it solves.

4. SKILLS.md — catalog the data science techniques demonstrated across the portfolio,
   grouped by category (regression, clustering, association rules, anomaly detection,
   time series, evaluation methodology, leakage prevention). For each, name where it's
   implemented — file and function. Be accurate; do not list anything not actually in
   the code.

Update README.md to link all four near the top in a Documentation section.

Write in plain direct prose. No filler. Then commit and push.
```

---

### Prompt R5 — Final Push

```
Run a final staleness check:
1. Search all .py and .md files for any metric values, course codes, or protocol
   descriptions that contradict the current code or screenshot content.
   Report anything stale before fixing.
2. Boot Streamlit, confirm HTTP 200, confirm no errors in stderr.
3. Commit all changes with a descriptive message.
4. Push to the remote.

Tell me the commit hash and confirm the push completed.
```
