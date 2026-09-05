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

