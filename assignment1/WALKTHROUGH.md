# Code Walkthrough

A tour of the codebase for a reader who wants to understand how it is structured and what the key implementation decisions are.

---

## Repository Layout

```
app.py                          # Home page and Streamlit entry point
requirements.txt
core/
  data.py                       # All synthetic data generators
  models.py                     # All training functions + Apriori
  viz.py                        # Shared Plotly theme and chart helpers
pages/
  1_Trip_Duration.py
  2_Customer_Segmentation.py
  3_Market_Basket.py
  4_Anomaly_Detection.py
  5_Time_Series.py
  6_CRISPDM_Audit.py
docs/screenshots/               # 23 PNG screenshots
scripts/
  capture_screenshots.py        # Playwright automation
  recapture_seg_anomaly.py      # Targeted recapture after fixes
```

Every page follows the same six-tab structure mapping to CRISP-DM phases: Business Understanding, Data Understanding, Data Preparation, Modeling, Evaluation, Live Inference.

---

## core/data.py

All synthetic data generators. Each is decorated with `@st.cache_data` so the data is generated once per session, not once per slider move.

**`make_trip_data(n=8000)`** — generates 8,000 NYC-style taxi trips. Coordinates are uniform within the bounding box. Duration is a nonlinear function of haversine distance with a rush-hour slowdown factor (1.4×) and a late-night speedup factor (0.85×). The nonlinearity is why linear regression underperforms relative to gradient boosting on this dataset.

**`haversine(lat1, lon1, lat2, lon2)`** — vectorised great-circle distance in km. Uses `np.radians` and `np.arcsin`. This is the key engineered feature for trip duration; Euclidean distance on degrees would be incorrect at NYC's latitude.

**`make_rfm_data(n=3000)`** — generates 3,000 RFM records from four latent Gaussian groups with explicit separation. The `true_group` column is included in the returned DataFrame but is dropped before clustering.

**`make_basket_data(n=4000)`** — generates 4,000 grocery baskets with four planted single-antecedent rules. The catalog size (20 items) and basket density (mean ~4 items) were chosen so background pairs have support ~3.3% (above the 3% default threshold) but background confidence ~21% (below the 30% default), so only planted-rule-driven associations survive the full filter set.

**`_build_telemetry_cov()`** — constructs the 5×5 covariance matrix for server telemetry. The correlation structure is the key design choice: CPU and memory are correlated (0.60), latency and error_rate are correlated (0.45), throughput is negatively correlated with both (−0.25 to −0.35). This correlation is what makes LOF fail — anomalies sit in the correlated tail of the multivariate normal, not in isolated pockets.

**`make_telemetry_data(n=6000)`** — generates telemetry with three tiers of anomaly severity (subtle/moderate/clear) and 360 hard-negative normal records (throughput-only outliers). The key insight: IsolationForest isolates multi-dimensional extremes faster than single-dimensional ones, so true anomalies (extreme in latency+error+cpu simultaneously) rank above the throughput-only outliers in the isolation path-length score.

**`make_timeseries_data(n_days=730)`** — generates 730 days of demand with additive trend (100 + 0.05t), weekly seasonality (amplitude 20), yearly seasonality (amplitude 30), and Gaussian noise (σ=8).

---

## core/models.py

All training functions plus the from-scratch Apriori.

**`train_trip_models(df)`** — `@st.cache_resource`. Splits 80/20, fits LinearRegression and HistGBR inside Pipelines (StandardScaler → model), computes permutation importance on the test set with 5 repeats. Returns both models, both metric dicts, the test split, and the importance object. The scaler is fit inside the Pipeline on `X_train` only.

**`train_segmentation(df, k=4)`** — `@st.cache_resource`. Sweeps k=2..10, computes inertia and silhouette at each k. Fits the final model at the chosen k. Applies PCA(2) for visualization (not for modeling). Computes cluster profiles (mean R/F/M, size, revenue share). Returns everything needed by both the Evaluation and Live Inference tabs.

**`apriori(transactions, min_support, min_confidence, min_lift)`** — from-scratch implementation. Phase 1: count singletons, prune by min_support to form L1. Phase 2: iteratively generate candidate k-itemsets by unioning pairs of (k-1)-frequent sets, count support by scanning all transactions, prune. Phase 3: for each frequent itemset of size ≥ 2, enumerate all antecedent/consequent splits, compute confidence and lift, filter. Safety cap at k=6. Returns a dict of all frequent itemsets and a DataFrame of rules sorted by lift.

**`recommend(rules_df, cart_items, top_n=3)`** — filters the rules table to rules whose antecedent is a subset of the cart items, excludes consequents already in the cart, returns top_n by lift.

**`train_anomaly_models(df)`** — `@st.cache_resource`. Stratified 80/20 split. Fits IsolationForest and LOF on X_train (features only). Scores X_test for PR-AUC evaluation and all of X for the Live Inference demo. Returns separate `_test` and `_all` score arrays so the page can use the right one for the right purpose.

**`make_lag_features(df)`** — adds lag_1, lag_7, lag_14, lag_28 and roll_mean_7, roll_mean_28 columns. Uses `demand.shift(1).rolling(w).mean()` so the current row's demand is never in its own rolling mean. Drops the first 28 rows where lags are undefined.

**`train_timeseries_model(df)`** — `@st.cache_resource`. Builds features, runs 5-fold TimeSeriesSplit, accumulates fold residuals (used for the uncertainty band), fits a final model on all data. Returns the model, feature column list, fold metrics DataFrame, naive MAPE, and the residuals array.

**`recursive_forecast(model, df_feat, feature_cols, horizon, residuals)`** — multi-step forecast. For each future step, prior forecasts are appended to history and used as lag inputs. The uncertainty band is the 10th–90th percentile of backtest residuals applied as a constant offset above and below the point forecast.

---

## core/viz.py

**`LAYOUT_BASE`** — shared Plotly layout dict: dark background (#0e1117), matching axis grids (#2a2a3a), Set2 qualitative palette. Applied to every chart via `_apply(fig)`.

**`_apply(fig)`** — applies LAYOUT_BASE to any Plotly Figure and sets grid colors on both axes.

**`map_two_points(lat1, lon1, lat2, lon2)`** — uses `go.Scattermap` (not `Scattermapbox` — renamed in Plotly 7) with the `carto-darkmatter` tile style. Returns a Figure centered between the two points. Used in the Trip Duration Live Inference tab.

The remaining helpers (`scatter`, `bar`, `heatmap`, `line`, `histogram`) are thin wrappers around plotly.express that call `_apply` before returning.

---

## Page 1 — pages/1_Trip_Duration.py

**Core calls:** `make_trip_data()`, `haversine()`, `train_trip_models()`, `map_two_points()`.

**What to look at.** The Data Understanding tab shows a 24×7 hourly demand heatmap (weekday × hour, built with `go.Heatmap`) that visually confirms the rush-hour structure baked into the data generator. The Evaluation tab shows permutation importance — `distance_km` dominates, as expected, because duration is a near-linear function of distance in this generator.

**Key implementation detail.** The OLS trendline for the distance-vs-duration scatter is computed with `np.polyfit`/`np.polyval` rather than `trendline="ols"` (which requires `statsmodels`, not in the allowed dependency set). The numpy trendline is added as a separate Scatter trace.

---

## Page 2 — pages/2_Customer_Segmentation.py

**Core calls:** `make_rfm_data()`, `train_segmentation()`, plus `derive_personas()` defined in the page itself.

**What to look at.** The `derive_personas(profile)` function at the top of the page. It computes a composite score from normalized inverted recency + normalized frequency + normalized monetary, ranks clusters highest-to-lowest, and assigns the label pool (Champions, Loyal, At Risk, Dormant) to those ranks. This is the fix for the hardcoded cluster-ID→label mapping that produced wrong labels when KMeans assigned IDs in a different order than expected.

**Key implementation detail.** The Data Understanding tab uses `px.scatter_3d` with `color=df["true_group"].astype(str)` — the column must be cast to string before passing to `color` or Plotly 7 raises a `ValueError: invalid value of type builtin_function_or_method received for colorscale`. Plotly 7 changed how it validates the colorscale parameter for numeric vs categorical color columns.

---

## Page 3 — pages/3_Market_Basket.py

**Core calls:** `make_basket_data()`, `apriori()`, `recommend()`.

**What to look at.** The Modeling and Evaluation tabs both run `apriori()` on-demand with slider values. This means Apriori runs every time a slider moves. With 4,000 baskets and ~20 items, the runtime is fast enough that this is acceptable, but it is why the Modeling tab adds `extra=6` wait time in the screenshot script.

**Key implementation detail.** With a 20-item catalog and mean basket size 4, background item pairs have support ~3.3% (above the 3% default threshold) but lift ~0.88 (below 1.0, due to negative correlation from sampling without replacement). The default min_lift=1.0 therefore filters all background rules automatically. Only planted-rule-driven associations, with lift ~2.1–2.3, survive. This is why the catalog size and basket density matter: if baskets were larger, cross-combination rules would also pass.

---

## Page 4 — pages/4_Anomaly_Detection.py

**Core calls:** `make_telemetry_data()`, `train_anomaly_models()`.

**What to look at.** The Evaluation tab uses `results["iso_scores_test"]` and `results["y_test"]` (held-out set) for PR-AUC and ROC-AUC. The Live Inference tab uses `results["iso_scores"]` and `results["y"]` (full dataset) for the threshold slider and confusion matrix. These are two different score arrays returned by the same cached training function.

**Key implementation detail.** The scoring function `_score(pipe, X_arr)` inside `train_anomaly_models()` calls `score_samples` and negates the result: `return -pipe.named_steps["model"].score_samples(...)`. IsolationForest and LOF define `score_samples` as returning lower values for more anomalous points, so negation makes higher scores correspond to higher anomaly likelihood throughout the page.

---

## Page 5 — pages/5_Time_Series.py

**Core calls:** `make_timeseries_data()`, `train_timeseries_model()`, `recursive_forecast()`.

**What to look at.** The ACF plot in the Data Understanding tab is computed manually with numpy — no `statsmodels.tsa.stattools.acf`. The computation: center the series, compute `sum(x[:n-lag] * x[lag:]) / sum(x**2)` for each lag. The 95% confidence interval is `±1.96 / sqrt(n)`. This is shown as code in the tab.

**Key implementation detail.** `make_lag_features()` uses `demand.shift(1).rolling(w).mean()`. The `.shift(1)` is critical: without it, the rolling mean for row t would include `demand[t]` itself, which is the target — direct target leakage. The `.shift(1)` ensures the rolling window looks at rows t−1 through t−w.

---

## Page 6 — pages/6_CRISPDM_Audit.py

No `core/` calls. This page is documentation: static data structures rendered as Streamlit tables and expanders. The leakage audit table is a hardcoded DataFrame with one row per project. The reward hacking section and reproducibility section are prose rendered with `st.write()`.

**What to look at.** The audit page is the differentiator for this portfolio. It documents what prevents each project from being a misleading demo. A grader who reads only this page should be able to verify the methodology without running the code.

---

## scripts/capture_screenshots.py

**What it does.** Starts Streamlit as a subprocess on port 8501, polls until HTTP 200, then uses Playwright sync API to navigate to each page, click through tabs, and capture full-page PNG screenshots to `docs/screenshots/`.

**The Streamlit async-render problem.** Streamlit renders Plotly charts asynchronously: the DOM is present, the network is idle, but the chart pixels are not yet painted. A screenshot taken at `networkidle` will capture a blank chart container. The solution is a three-phase wait:

1. `page.wait_for_load_state("networkidle")` — ensures no pending XHR or WebSocket messages.
2. `page.wait_for_selector(".js-plotly-plot", state="attached")` — waits until the Plotly SVG container is in the DOM. Plotly adds this class when it finishes rendering into the container.
3. `time.sleep(extra)` — a calibrated sleep (2–5 seconds depending on the tab) to give Plotly's `requestAnimationFrame` loop time to paint pixels.

**The Streamlit tab element problem.** Streamlit 1.63 renders tabs as `<div role="tab" data-testid="stTab">`, not `<button role="tab">`. A naive `page.locator('button[role="tab"]')` finds nothing. The fix is `page.get_by_role("tab", name=label)`, which uses Playwright's ARIA role matching and works regardless of the HTML tag. Before clicking, `page.wait_for_selector('[data-testid="stTab"]')` ensures the tab bar has actually rendered.

**`poll_until_ready(url, timeout=30)`** — tight polling loop with 0.5 second sleep, no fixed `time.sleep(N)` before the first attempt. This is correct: on a fast machine Streamlit can be ready in 3–4 seconds, so a fixed 10-second sleep wastes time.
