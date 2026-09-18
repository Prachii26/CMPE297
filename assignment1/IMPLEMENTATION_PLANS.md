# Implementation Plans

Per-project implementation notes: business problem, data, features, model choice, evaluation, and final metrics. All numbers are from the actual run with seed 42.

---

## Overall Architecture Decision

The portfolio is a single Streamlit multipage app (`app.py` + `pages/`), not separate services or a React frontend. The reason is constraint: the assignment requires two-command deployment (`pip install -r requirements.txt && streamlit run app.py`) with no external ports, no network calls, and no database. Streamlit multipage apps satisfy this while providing per-page URL routing, a sidebar navigation bar, and a tab API that maps cleanly onto the six CRISP-DM phases.

The cost is that every page reloads the entire Python module on each render, which is why `@st.cache_data` and `@st.cache_resource` are used on all data generators and training functions. Without caching, moving a slider would retrain the model on every interaction.

All shared logic lives in three modules under `core/`: `data.py` (synthetic data generators), `models.py` (training functions and Apriori), and `viz.py` (shared Plotly theme and helper chart functions). Pages import from `core/` and contain only Streamlit UI code.

---

## Project 1 — Trip Duration Predictor

**Business problem.** A ride-hailing app needs to quote trip duration before the passenger books. The goal is to minimize RMSE on held-out trips without being so imprecise that the estimate is useless. Target: RMSE < 5 minutes.

**Data generation.** `core/data.py :: make_trip_data(n=8000)`. Pickup and dropoff coordinates are drawn uniformly within the NYC bounding box (lat 40.63–40.85, lon −74.05 to −73.75). Hour is uniform over 0–23, weekday over 0–6, passengers over 1–6. Duration is derived as a nonlinear function of haversine distance: `duration = (distance / (base_speed × rush_factor × night_factor)) × 60 + N(0, 2)`. Base speed is 20 mph. Rush factor is 1.4× on weekday hours 7–9 and 17–19. Night factor is 0.85× on hours 0–5. Gaussian noise has σ=2 minutes. Duration is clipped to [2, 90] minutes.

**Feature engineering.** The key engineered feature is haversine distance: great-circle distance in km between pickup and dropoff coordinates. Euclidean distance on lat/lon degrees does not map linearly to km at NYC's latitude (~40°N), so the conversion matters. Implemented in `core/data.py :: haversine()`. Features passed to the model: `distance_km`, `hour`, `weekday`, `passengers`, `pickup_lat`, `pickup_lon`, `dropoff_lat`, `dropoff_lon`.

**Model choice.** Two models, same feature set. `LinearRegression` establishes what raw correlation achieves. `HistGradientBoostingRegressor(max_iter=200, max_depth=6, random_state=42)` captures the nonlinear interaction between distance, hour, and weekday that the data generating process contains. Both live inside sklearn Pipelines with a `StandardScaler` fit on training data only. The scaler is not strictly necessary for HistGBR (tree models are scale-invariant) but is included so both models have identical pipeline structure.

**Evaluation protocol.** 80/20 random split (`random_state=42`). Trips are i.i.d. — no temporal ordering — so a random split is appropriate. Permutation importance computed on the test set with 5 repeats. Implemented in `core/models.py :: train_trip_models()`.

**Final metrics.**
- Linear Regression: RMSE 5.935 min, MAE 4.360 min, R² 0.908
- HistGBR: RMSE 2.156 min, MAE 1.689 min, R² 0.988

The R² of 0.988 is inflated by synthetic data — the model is recovering a known formula. Real NYC taxi data typically yields R² ≈ 0.80–0.85 due to unmeasured variance from weather, routing, and driver behavior.

---

## Project 2 — Customer Segmentation

**Business problem.** A retailer wants to segment customers for targeted marketing. Sending the same campaign to all customers wastes budget on churned users and annoys active ones. Recency, Frequency, and Monetary (RFM) are the three signals. Success: clusters are internally coherent (silhouette > 0.3) and have interpretable business personas.

**Data generation.** `core/data.py :: make_rfm_data(n=3000)`. Four latent groups with genuine separation, sizes 600/900/900/600:
- Group 0 (Champions): recency N(10, 5), frequency N(20, 4), monetary N(800, 150)
- Group 1 (At Risk): recency N(60, 20), frequency N(8, 2), monetary N(300, 80)
- Group 2 (Dormant): recency N(120, 30), frequency N(3, 1), monetary N(150, 50)
- Group 3 (Loyal): recency N(20, 8), frequency N(12, 3), monetary N(500, 120)

All values are clipped (recency: [1, 365], frequency: [1, 50], monetary: [10, 5000]). The dataset is shuffled so cluster IDs in KMeans output do not correspond to the generation order.

**Feature engineering.** No derived features. Recency, frequency, and monetary are already directly meaningful. `StandardScaler` normalizes the three features so each contributes equally to the KMeans distance objective.

**Model choice.** KMeans inside a Pipeline with StandardScaler. KMeans is distance-based, so scaling is mandatory. The k sweep (k=2..10) uses both inertia (elbow method) and silhouette score, providing two independent views on cluster quality. PCA(n_components=2) is used for 2D visualization only — not for modeling. Implemented in `core/models.py :: train_segmentation()`.

**Persona assignment.** Personas are not hardcoded by cluster ID. `derive_personas()` in `pages/2_Customer_Segmentation.py` computes a composite score per centroid — inverted normalized recency + normalized frequency + normalized monetary — ranks clusters highest to lowest, and assigns Champions → Loyal → At Risk → Dormant to those ranks. This is robust to any permutation of cluster IDs across random seeds or k values.

**Evaluation protocol.** No train/test split — clustering is unsupervised with no target to leak. Evaluation is intrinsic: silhouette score and inertia across k=2..10. Labels from the data generator (`true_group`) are never used during modeling.

**Final metrics at k=4.**
- Silhouette: 0.346 (values above 0.3 indicate meaningful structure)
- Cluster 0: recency 58.6, freq 7.2, monetary $287.3 → At Risk
- Cluster 1: recency 124.5, freq 2.6, monetary $151.7 → Dormant
- Cluster 2: recency 18.6, freq 11.9, monetary $521.9 → Loyal
- Cluster 3: recency 9.9, freq 20.2, monetary $811.0 → Champions

---

## Project 3 — Market Basket Analysis

**Business problem.** A grocery retailer wants to find which products are bought together to improve shelf placement and cross-sell promotions. Association rule mining finds these patterns without labels.

**Data generation.** `core/data.py :: make_basket_data(n=4000)`. Catalog of 20 grocery items. Each basket samples 3–5 items without replacement (mean ~4). Four planted rules with 55% trigger probability each:
- milk → butter (dairy pairing)
- coffee → chocolate (indulgence)
- pasta → cheese (Italian cooking)
- chicken → vegetables (dinner staple)

The catalog size and basket density were chosen so that: (a) background pair support is ~3.3%, just above the 3% default threshold; (b) background confidence is ~21%, below the 30% default, so background rules are filtered; (c) cross-combination triple support is ~1.4%, below 3%, so Apriori finds only the direct planted rules and their reverses. Each planted rule lifts conditional confidence from ~25% background to ~68%, giving lift ≈ 2.3.

**Feature engineering.** Not applicable. Market basket analysis works directly on sets of items with no numerical features.

**Model choice.** Apriori implemented from scratch in `core/models.py :: apriori()`. No external library (not mlxtend). The implementation: (1) count singleton support, prune by min_support; (2) generate k-item candidate sets by unioning (k-1)-item frequent sets, count support, prune; (3) generate rules from all frequent itemsets with size ≥ 2, compute confidence and lift, filter. Safety cap at itemset size 6. `core/models.py :: recommend()` finds rules whose antecedent is a subset of a given cart and returns the top-n consequents.

**Evaluation protocol.** No train/test split — association mining is unsupervised. Evaluation is whether the planted rules appear in the output at default thresholds (support=0.03, confidence=0.30, lift=1.0).

**Final results at defaults.** 203 frequent itemsets, 16 rules. All four planted rules recovered. Planted rule confidence: 0.61–0.63. Planted rule lift: 2.11–2.19. Background rules are excluded by lift < 1.0 (negative correlation from sampling without replacement means background pairs have lift ≈ 0.88).

---

## Project 4 — Anomaly Detection

**Business problem.** An SRE team wants to flag server incidents automatically. Anomalies are 2% of all observations, so a model that predicts "normal" for everything achieves 98% accuracy while missing every incident. The right metric is PR-AUC. Models must be unsupervised (labels are not available at training time in practice).

**Data generation.** `core/data.py :: make_telemetry_data(n=6000)`. Five features: latency_ms, error_rate_pct, throughput_rps, cpu_pct, memory_pct. Drawn from a multivariate normal with a correlation structure that reflects real server behavior: latency and error_rate positively correlated (0.45), CPU and memory positively correlated (0.60), throughput negatively correlated with both (−0.25 to −0.35).

Normal records: 5,520 plain traffic records at μ=[50, 3, 1000, 40, 60].

Hard-negative normals (360 records, labeled 0 but look suspicious): 180 traffic bursts (throughput at 2.5σ high) and 180 maintenance windows (throughput at 2.5σ low). These are extreme in throughput only — not in latency/error — which is the key design choice: IsolationForest isolates multi-dimensional extremes faster than single-dimensional ones.

True anomalies (120 records, 2%):
- Subtle (36, 30%): latency at 2.5σ (87.5ms) only
- Moderate (48, 40%): latency at 6.5σ (147ms) + error at 6.4σ (19%)
- Clear (36, 30%): latency at 10σ (200ms) + error at 8.8σ (25%) + cpu at 3.2σ (88%)

**Model choice.** Two unsupervised models:
- `IsolationForest(contamination=0.02, n_estimators=100, random_state=42)`: builds random trees and measures how quickly each point is isolated. Points in sparse regions (anomalies) need fewer splits.
- `LocalOutlierFactor(n_neighbors=20, contamination=0.02, novelty=True)`: computes local density ratio. `novelty=True` enables inductive scoring on unseen data.

Both live inside Pipelines with StandardScaler. Implemented in `core/models.py :: train_anomaly_models()`.

**Evaluation protocol.** Stratified 80/20 split (stratify=y, random_state=42) keeps the 2% anomaly rate in both halves. Both models are fit on X_train using features only — labels are never seen during training. PR-AUC and ROC-AUC are computed on the 20% held-out test set. All 6,000 records are scored for the Live Inference threshold demo.

**Final held-out metrics.**
- IsolationForest: PR-AUC 0.756, ROC-AUC 0.955
- LOF: PR-AUC 0.115, ROC-AUC 0.515

LOF underperforms because its local-density assumption breaks down when anomalies are correlated across features and sit in the tails of a multivariate correlated normal, rather than being individually isolated. This is a finding, not an implementation defect.

---

## Project 5 — Time Series Forecasting

**Business problem.** A retail buyer needs to forecast daily demand 7–90 days out. Under-ordering means lost sales; over-ordering means spoilage. The signal has a linear trend plus weekly and yearly seasonality. MAPE is the right metric because buyers think in percentage terms. The baseline is seasonal naive: predict today's demand equals the same weekday last week.

**Data generation.** `core/data.py :: make_timeseries_data(n_days=730)`. 730 days starting 2022-01-01. Signal components:
- Trend: `100 + 0.05 × t`
- Weekly seasonality: `20 × sin(2π × t / 7 + 0.5)`
- Yearly seasonality: `30 × sin(2π × t / 365.25)`
- Noise: N(0, 8)

All components summed and clipped at a minimum of 10.

**Feature engineering.** `core/models.py :: make_lag_features()`. Lag features: demand at t−1, t−7, t−14, t−28. Rolling mean features: 7-day and 28-day rolling means, computed from `demand.shift(1).rolling(w).mean()`. The `.shift(1)` ensures the current row's demand is never an input to its own prediction. Calendar features: day of week, day of year, month. The first 28 rows are dropped after lag construction (NaN lags).

**Model choice.** `HistGradientBoostingRegressor(max_iter=200, random_state=42)`. Tree models are invariant to feature scale, so no StandardScaler is used. The lag and rolling features turn the time series problem into tabular regression. The seasonal naive baseline (`lag_7`) is compared directly.

**Evaluation protocol.** `TimeSeriesSplit(n_splits=5)` with shuffle=False. Each fold's test set is strictly later in time than its training set. The backtest accumulates residuals from all folds for the uncertainty band computation. A final model is fit on all available data for the live recursive forecast. Implemented in `core/models.py :: train_timeseries_model()`.

**Recursive forecast.** `core/models.py :: recursive_forecast()`. For each future step, prior forecasts are used as lag inputs. The uncertainty band is the 10th–90th percentile of the accumulated backtest residuals, applied as a constant offset above and below the point forecast.

**Final metrics.**
- Fold MAPEs: 21.88% / 11.55% / 7.59% / 7.21% / 7.62%
- Naive baseline MAPE (full series): 7.94%
- Model beats naive from fold 3 onward; fold 1 is inflated because the model trains on ~5 months and cannot learn yearly seasonality.
