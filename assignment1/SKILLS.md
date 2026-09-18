# Skills Catalog

Data science techniques demonstrated in this portfolio, grouped by category. Each entry names where it is implemented — file and function — and what specifically it does. Nothing is listed unless it is actually in the code.

---

## Regression

**HistGradientBoostingRegressor** — gradient boosted trees for trip duration prediction. `max_iter=200`, `max_depth=6`, `random_state=42`. Captures the nonlinear interaction between distance, hour, and weekday.
- `core/models.py :: train_trip_models()`
- `pages/1_Trip_Duration.py` (calls `train_trip_models`, renders results)

**LinearRegression** — baseline for trip duration. Same feature set as the HistGBR model; used to quantify how much the nonlinear model adds over raw correlation.
- `core/models.py :: train_trip_models()`

**sklearn Pipeline** — wraps StandardScaler → model so the scaler is fit on training data only and transformation is applied consistently at inference time. Used for both regression models.
- `core/models.py :: train_trip_models()`

**Permutation feature importance** — computed on the test set with 5 repeats using `sklearn.inspection.permutation_importance`. Shows which features most affect prediction quality by measuring the RMSE increase when each feature is randomly shuffled.
- `core/models.py :: train_trip_models()`
- `pages/1_Trip_Duration.py` (Evaluation tab, horizontal bar chart)

**Haversine distance** — great-circle distance in km between pickup and dropoff coordinates. Replaces Euclidean lat/lon distance, which is incorrect at NYC's latitude. Vectorised with `np.radians` and `np.arcsin`.
- `core/data.py :: haversine()`

---

## Clustering

**KMeans** — k-means clustering of RFM data inside a Pipeline with StandardScaler. Sweep over k=2..10. `n_init=10`, `random_state=42`.
- `core/models.py :: train_segmentation()`

**Elbow method (inertia)** — within-cluster sum of squares across k=2..10, plotted to find the inflection point where adding clusters yields diminishing returns.
- `core/models.py :: train_segmentation()` (computes inertias list)
- `pages/2_Customer_Segmentation.py` (Modeling tab, line chart)

**Silhouette score** — computed for each k using `sklearn.metrics.silhouette_score`. Measures how similar each point is to its own cluster vs the nearest neighbouring cluster. Values above 0.3 indicate meaningful structure.
- `core/models.py :: train_segmentation()` (computes silhouettes list)
- `pages/2_Customer_Segmentation.py` (Modeling tab, line chart)

**PCA 2D projection** — `PCA(n_components=2, random_state=42)` applied to the StandardScaler-transformed features for cluster visualization. Not used in the model itself.
- `core/models.py :: train_segmentation()`
- `pages/2_Customer_Segmentation.py` (Evaluation tab, scatter plot)

**Runtime persona derivation** — composite score ranking of cluster centroids (inverted normalized recency + normalized frequency + normalized monetary). Assigns personas (Champions, Loyal, At Risk, Dormant) by centroid rank rather than by cluster ID, so the label is always correct regardless of KMeans initialization order.
- `pages/2_Customer_Segmentation.py :: derive_personas()`

---

## Association Rules

**Apriori — from scratch** — full from-scratch implementation: singleton counting → L1 pruning → candidate generation by set union → support counting → rule generation with confidence and lift filtering. Safety cap at itemset size 6.
- `core/models.py :: apriori()`

**Support** — fraction of transactions containing a given itemset. Used as the first filter in Apriori.
- `core/models.py :: apriori()`

**Confidence** — conditional probability P(consequent | antecedent) = support(antecedent ∪ consequent) / support(antecedent).
- `core/models.py :: apriori()`

**Lift** — ratio of observed confidence to expected confidence under independence: confidence / support(consequent). Lift > 1.0 means the association is stronger than chance. Background rules in this dataset have lift < 1.0 due to sampling without replacement, so min_lift=1.0 filters them automatically.
- `core/models.py :: apriori()`

**Cart recommendation** — filters the rules table to rules whose antecedent is a subset of the current cart, excludes items already in the cart, returns top-n by lift.
- `core/models.py :: recommend()`
- `pages/3_Market_Basket.py` (Live Inference tab)

---

## Anomaly Detection

**IsolationForest** — `n_estimators=100`, `contamination=0.02`, `random_state=42`. Builds random trees and measures path length to isolation. Anomalies are isolated in fewer splits. Fit on training data only; scored on held-out test set for evaluation.
- `core/models.py :: train_anomaly_models()`

**LocalOutlierFactor** — `n_neighbors=20`, `contamination=0.02`, `novelty=True`. Computes local density ratio relative to neighbours. `novelty=True` enables inductive scoring on unseen records (required because we score the test set separately from the training set).
- `core/models.py :: train_anomaly_models()`

**Stratified train/test split for unsupervised models** — 80/20 split stratified by `is_anomaly` to preserve the 2% anomaly rate in both halves. Models are fit on X_train (features only, no labels), then scored on X_test for held-out PR-AUC.
- `core/models.py :: train_anomaly_models()`

**Anomaly score negation** — both models define `score_samples()` as returning lower values for more anomalous points. Negation (`-score_samples(...)`) converts this to a score where higher = more anomalous, consistent with PR-AUC convention.
- `core/models.py :: train_anomaly_models() :: _score()`

**PR-AUC (Precision-Recall Area Under Curve)** — primary evaluation metric for imbalanced anomaly detection. Insensitive to class imbalance in a way that accuracy and ROC-AUC are not. Computed on the held-out test set.
- `pages/4_Anomaly_Detection.py` (Evaluation tab, using `sklearn.metrics.precision_recall_curve`, `auc`)

**ROC-AUC** — secondary evaluation metric. Shown alongside PR-AUC to demonstrate that the two metrics can diverge substantially (IsoForest ROC-AUC 0.955 vs PR-AUC 0.756; LOF ROC-AUC 0.515 vs PR-AUC 0.115).
- `pages/4_Anomaly_Detection.py` (Evaluation tab)

**Threshold-dependent confusion matrix** — live slider moves the anomaly score threshold, recomputing precision, recall, F1, and the 2×2 confusion matrix in real time.
- `pages/4_Anomaly_Detection.py` (Live Inference tab)

**Multivariate correlated normal for data generation** — `numpy.random.Generator.multivariate_normal` with a correlation matrix encoding realistic server metric relationships (latency-error correlation 0.45, CPU-memory correlation 0.60).
- `core/data.py :: _build_telemetry_cov()`, `make_telemetry_data()`

---

## Time Series

**Lag features** — demand at t−1, t−7, t−14, t−28, created with `pd.Series.shift()`. Converts the time series forecasting problem to tabular regression.
- `core/models.py :: make_lag_features()`

**Rolling mean features** — 7-day and 28-day rolling means, computed as `demand.shift(1).rolling(w).mean()`. The `.shift(1)` prevents the current row's demand from appearing in its own rolling mean (target leakage).
- `core/models.py :: make_lag_features()`

**HistGradientBoostingRegressor for time series** — same estimator as the regression project but applied to lag-feature matrices. No scaling required (tree models are scale-invariant).
- `core/models.py :: train_timeseries_model()`

**TimeSeriesSplit** — `n_splits=5`, no shuffle. Each fold's test set is strictly later in time than its training set. Prevents future data from appearing in training.
- `core/models.py :: train_timeseries_model()`

**Seasonal naive baseline** — predicts demand[t] = demand[t−7]. Strong baseline for a weekly-seasonal series. Computed directly from `lag_7` without a separate model.
- `core/models.py :: train_timeseries_model()`

**MAPE (Mean Absolute Percentage Error)** — `mean(|actual - predicted| / |actual + ε|) × 100`. Primary metric for the time series project. Percentage-based, robust to the trend-driven scale shifts in the demand signal.
- `core/models.py :: train_timeseries_model()`

**Recursive multi-step forecast** — for each future step, previous forecasts are appended to the history and used as lag inputs for the next step. Error accumulates with horizon.
- `core/models.py :: recursive_forecast()`

**Empirical uncertainty band** — 10th and 90th percentile of backtest residuals accumulated across all TimeSeriesSplit folds. Applied as a constant offset above and below the point forecast.
- `core/models.py :: recursive_forecast()`

**Manual ACF computation** — autocorrelation function computed from scratch with numpy: `sum(x[:n-lag] * x[lag:]) / sum(x**2)`. No statsmodels dependency. 95% confidence band as `±1.96 / sqrt(n)`.
- `pages/5_Time_Series.py` (Data Understanding tab)

---

## Evaluation Methodology

**80/20 random train/test split** — used for trip duration. Appropriate because trips are i.i.d. (no temporal ordering).
- `core/models.py :: train_trip_models()`

**Stratified train/test split** — used for anomaly detection to preserve the 2% anomaly rate in both halves.
- `core/models.py :: train_anomaly_models()`

**Intrinsic evaluation (no split)** — used for clustering (silhouette, inertia) and association rules (support/confidence/lift). No target variable means no train/test split is needed or appropriate.
- `core/models.py :: train_segmentation()`, `apriori()`

**Permutation importance** — feature importance computed by measuring RMSE increase when each feature is shuffled on the test set. More reliable than impurity-based importance for correlated features.
- `core/models.py :: train_trip_models()`

**PR curve and PR-AUC** — used for imbalanced anomaly detection. Computed with `sklearn.metrics.precision_recall_curve` and `auc`.
- `pages/4_Anomaly_Detection.py`

**Fold-by-fold MAPE table** — all five fold MAPEs shown individually rather than just the mean, to make visible the fold-1 inflation from insufficient training history.
- `pages/5_Time_Series.py` (Modeling and Evaluation tabs)

---

## Leakage Prevention

**StandardScaler inside Pipeline** — scaler is fit on `X_train` only, then transforms both train and test sets. The test set never influences the scaling parameters.
- `core/models.py :: train_trip_models()`, `train_anomaly_models()`

**Unsupervised fit on features only** — IsolationForest and LOF are fit on X_train with no reference to `y_train`. Labels are used only for computing held-out metrics.
- `core/models.py :: train_anomaly_models()`

**Rolling features with shift** — `demand.shift(1).rolling(w).mean()` prevents the current row from appearing in its own rolling mean.
- `core/models.py :: make_lag_features()`

**TimeSeriesSplit with no shuffle** — ensures the test fold is always later in time than the training fold. Shuffling would allow future observations into training.
- `core/models.py :: train_timeseries_model()`

**`true_group` dropped before clustering** — the data generator label is not passed to KMeans or used in any model. It exists only in the raw DataFrame and is dropped for display.
- `pages/2_Customer_Segmentation.py` (Data Understanding tab uses `df.drop(columns=["true_group"])`)

**`is_anomaly` excluded from feature list** — the label column is never in the feature matrix. It is only accessed from the returned DataFrame for evaluation.
- `core/models.py :: train_anomaly_models()` (features list does not include `is_anomaly`)

**Fixed seeds everywhere** — `np.random.default_rng(42)` for all data generators, `random_state=42` for all sklearn estimators that accept it. Ensures reproducibility across runs.
- `core/data.py` (all generators), `core/models.py` (all training functions)

**`@st.cache_data` / `@st.cache_resource`** — data generators are cached by `@st.cache_data`, training functions by `@st.cache_resource`. This prevents re-running training on every slider interaction, which could appear to cause leakage (the model appearing to "know" the slider value) if the model were retrained after seeing the widget state.
- `core/data.py` (all generators), `core/models.py` (all `train_*` functions)
