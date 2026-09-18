# CRISP-DM & Leakage Audit Report

Standalone export of the audit content in `pages/6_CRISPDM_Audit.py`. That page is the live, interactive version; this document is the fixed record for grading.

---

## CRISP-DM Phases — What They Meant in This Repo

**1. Business Understanding.** Each project started with a declared success metric before any data or model was created. Trip duration: RMSE < 5 minutes on held-out data. Segmentation: silhouette > 0.3 with interpretable cluster personas. Market basket: recover the four planted rules at default thresholds. Anomaly detection: held-out PR-AUC > 0.5 (majority-class accuracy baseline is 98%, so accuracy is not used). Time series: MAPE below the seasonal naive baseline on folds 3–5, once the model has seen a full yearly cycle.

**2. Data Understanding.** All datasets are synthetic. Data understanding meant verifying the generators produced the intended structure: RFM group separation visible in 3D scatter, planted association rules appearing in basket co-occurrences at the expected support levels, anomaly patterns visible as a tail in the telemetry score histograms. Every Data Understanding tab shows summary statistics, raw distributions, and at least one exploratory chart.

**3. Data Preparation.** Feature engineering is documented and shown as runnable code in each page's Data Preparation tab. Haversine distance for trips, lag and rolling-mean features for time series. All transformations live inside sklearn Pipelines. Scalers are fit on training data only. The rolling means in the time series use `.shift(1)` before `.rolling()` so the current row's value never leaks into its own feature.

**4. Modeling.** Every project uses two models to make comparison possible: LinearRegression vs HistGradientBoostingRegressor for trips, KMeans at k=2–10 for segmentation, from-scratch Apriori vs threshold tuning for baskets, IsolationForest vs LOF for anomalies, lag regression vs seasonal naive for time series. Seeds are fixed to 42 everywhere.

**5. Evaluation.** Metrics match the problem type. Regression: RMSE, MAE, R². Clustering: silhouette and inertia (no accuracy — there is no target). Association rules: support, confidence, lift. Anomaly detection: PR-AUC and ROC-AUC on a held-out test set, not accuracy. Time series: MAPE with TimeSeriesSplit, no shuffled folds.

**6. Deployment.** The Live Inference tab on each page is the deployment artifact. A user can move sliders and get an immediate prediction from the full inference pipeline including all preprocessing steps. Models are cached with `@st.cache_resource` so training happens once per session.

---

## Leakage Audit Table

One row per project. Each column is a specific avenue for data leakage, and the entry states what the code actually does.

| Project | Preprocessing fit scope | Train-test split method | Target leakage check | Seed pinned | Metric appropriate for class balance | Code reference |
|---|---|---|---|---|---|---|
| Trip Duration | StandardScaler fit on X_train only (inside Pipeline) | 80/20 random split; trips are i.i.d. | `duration_min` excluded from feature list | `np.random.default_rng(42)`, `random_state=42` | RMSE/MAE/R² — regression, no class imbalance | `core/models.py :: train_trip_models()` |
| Customer Segmentation | StandardScaler fit on full X — justified: unsupervised, no target to leak | No split — intrinsic evaluation (silhouette, inertia) | No target; `true_group` column dropped before clustering | `np.random.default_rng(42)`, `random_state=42` | Silhouette + inertia — clustering metrics | `core/models.py :: train_segmentation()` |
| Market Basket | No scaling needed (set operations on transaction lists) | No split — unsupervised; thresholds are tunable by user | No target in association mining | `np.random.default_rng(42)` | Support/confidence/lift — frequency-based | `core/models.py :: apriori()` |
| Anomaly Detection | StandardScaler fit on X_train only (80% stratified split, labels never seen during training) | Stratified 80/20 split (`random_state=42`); PR-AUC on held-out test set | `is_anomaly` excluded from feature list; used only for evaluation | `np.random.default_rng(42)`, `random_state=42` | PR-AUC, ROC-AUC — not accuracy; 2% anomaly rate stated explicitly | `core/models.py :: train_anomaly_models()` |
| Time Series | No scaling; rolling/lag features computed with `.shift(1)` before any split | TimeSeriesSplit(n_splits=5), shuffle=False | Lag features use `.shift(1)` — no look-ahead into the current row's demand | `np.random.default_rng(42)`, `random_state=42` | MAPE — percentage error, robust to demand scale shifts | `core/models.py :: train_timeseries_model()` |

---

## Reward Hacking: Three Failure Modes and What Prevents Each

**1. Reporting accuracy on the anomaly dataset.**

How it inflates the metric: the dataset has a 2% anomaly rate. A model that fires zero alerts achieves 98% accuracy while catching nothing. This metric looks impressive and is completely useless for the stated goal of catching incidents before users notice.

What the code does: accuracy is never computed or displayed for this project. The Business Understanding tab shows the 2.0% anomaly rate and 98.0% majority-class accuracy as metric cards specifically to make the trap visible. All evaluation uses PR-AUC and ROC-AUC, which are not inflated by class imbalance.

**2. Shuffling the time series train-test split.**

How it inflates the metric: if future observations appear in the training set, the model can effectively "memorize" the future when predicting the past. A model trained with shuffle=True on time series data will show near-zero MAPE and is cheating.

What the code does: `TimeSeriesSplit(n_splits=5)` is used with no shuffle. The test fold in every split is strictly later in time than the training fold. The lag features use `.shift(1)` before rolling calculations so the current row's demand value is never an input feature. This is enforced in `core/models.py :: make_lag_features()`.

**3. Tuning hyperparameters against the test set.**

How it inflates the metric: if you run train → evaluate on test → adjust model → repeat, the test set becomes effective training data. The final reported metrics are optimistic because the model was chosen to perform well on that specific sample.

What the code does: model configuration (`max_iter=200`, `max_depth=6`, `n_estimators=100`) was set once before any evaluation run and was never changed in response to test metrics. No hyperparameter search is performed against any test fold.

---

## Reproducibility

**Random seeds.** Every random source uses seed 42. Data generators use `np.random.default_rng(42)`. All sklearn estimators that accept `random_state` use `random_state=42`. The market basket generator uses the same `rng` object throughout so the sequence is deterministic. Streamlit caching (`@st.cache_data`, `@st.cache_resource`) ensures generators and models execute once per session, not once per widget interaction.

**Package versions.**

```
streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.26.0
scikit-learn>=1.4.0
plotly>=5.20.0
playwright>=1.40.0
```

**One-command run.**

```bash
pip install -r requirements.txt
streamlit run app.py
```

No internet access is required at runtime. No external API calls. No database connections. No file downloads. All data is generated in-process from fixed seeds.

**What varies between runs.** Nothing in the model outputs. UI widget states start at their declared defaults every session. The only runtime variation is Plotly rendering (hover states, font rasterization), which does not affect the results.

---

## Honest Limitations

**Synthetic data.** All five datasets are generated in code, not collected from real systems. This means the data generation process is fully known to the models — the model for trip duration is literally recovering the formula used to generate `duration_min`. Real-world data has unmeasured confounders (weather, driver behavior, GPS noise, traffic incidents) that would degrade all metrics substantially. The portfolio demonstrates correct methodology, not real-world prediction performance.

**Trip duration R² = 0.988.** This is inflated by synthetic data. On real NYC taxi data, published benchmarks land around 0.80–0.85. The inflated value is acknowledged in the Evaluation tab of page 1 and should not be interpreted as evidence of a production-ready model. The nonlinear demand factor (base speed 20 mph, 1.4× rush-hour slowdown, 0.85× late-night speedup, Gaussian noise σ=2 min) is simple enough for gradient boosting to recover almost exactly.

**Anomaly detection in-sample scoring vs held-out.** IsolationForest and LOF are unsupervised. Both models are fit on the 80% training split using features only (labels are never used during training). PR-AUC is evaluated on the 20% held-out test set. The held-out IsolationForest PR-AUC (0.756) is nearly identical to the in-sample value because unsupervised models do not memorize labels; the difference would be larger for a supervised classifier.

**Association rules with planted signals.** The four planted rules (milk→butter, coffee→chocolate, pasta→cheese, chicken→vegetables) were designed to be recoverable at the default thresholds. In real grocery data, the "interesting" rules are rarely this clean. The demo shows the algorithm works correctly; it does not claim the specific rules have business value.

**Time series MAPE on early folds.** Fold 1 MAPE is 21.88% because the model trains on roughly five months of data and cannot see a full yearly cycle. Reporting mean MAPE across all five folds (11.17%) would misrepresent the model's mature performance. Folds 3–5 land at 7.2–7.6%, which is comparable to the seasonal naive baseline (7.94%) and represents what the model achieves once it has enough history.
