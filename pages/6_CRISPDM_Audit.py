import pandas as pd
import streamlit as st

st.set_page_config(layout="wide", page_title="CRISP-DM Audit")
st.title("CRISP-DM & Leakage Audit")
st.caption("How this project was built and what prevents it from lying to you")

tabs = st.tabs([
    "CRISP-DM Walkthrough",
    "Leakage Audit Table",
    "Reward Hacking",
    "Reproducibility",
])

# ── Tab 1 ───────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("CRISP-DM in This Repo — Concretely")

    phases = {
        "1. Business Understanding": (
            "Each project started with a stated goal and a declared success metric before "
            "any data was created. Trip duration: RMSE < 5 min. Segmentation: "
            "interpretable clusters with silhouette > 0.3. Market basket: surface the planted "
            "rules. Anomaly: PR-AUC > 0.5. Time series: MAPE below seasonal naive. "
            "These are written into the first tab of every page."
        ),
        "2. Data Understanding": (
            "All datasets are synthetic, so data understanding meant verifying that the "
            "generators produced the intended structure: RFM group separation in 3D, "
            "planted association rules appearing in basket co-occurrences, anomaly "
            "patterns in server telemetry distributions. Every Data Understanding tab "
            "shows the raw distribution, summary stats, and at least one exploratory chart."
        ),
        "3. Data Preparation": (
            "Feature engineering (haversine distance for trips, lag construction for "
            "time series) is explained and shown as code in each page's third tab. "
            "All transformations are inside sklearn Pipelines. Scalers are fit on "
            "training data only — never on test or full data."
        ),
        "4. Modeling": (
            "Each project uses two models so comparison is possible: linear vs gradient "
            "boosting for trips, KMeans at different k for segmentation, from-scratch "
            "Apriori vs threshold tuning for baskets, IsolationForest vs LOF for anomalies, "
            "lag-regression vs seasonal naive for time series. Seeds are fixed to 42 everywhere."
        ),
        "5. Evaluation": (
            "Metrics are chosen to match the problem type. Regression uses RMSE/MAE/R2. "
            "Clustering uses silhouette + inertia (no accuracy — there's no target). "
            "Anomaly detection uses PR-AUC and ROC-AUC, not accuracy, because of class "
            "imbalance. Time series uses MAPE with TimeSeriesSplit, not shuffled folds."
        ),
        "6. Deployment": (
            "Deployment here means the Live Inference tab on each page. A real user can "
            "move sliders and get an immediate prediction. All models are cached with "
            "@st.cache_resource so training happens once. The Live Inference tab demonstrates "
            "the full inference pipeline, including preprocessing transformations."
        ),
    }

    for phase, description in phases.items():
        with st.expander(phase, expanded=True):
            st.write(description)


# ── Tab 2 ───────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Leakage Audit Table")
    st.write(
        "One row per project. Each column is a specific way data leakage could "
        "occur, and the entry states what the code actually does."
    )

    audit_data = {
        "Project": [
            "Trip Duration",
            "Customer Segmentation",
            "Market Basket",
            "Anomaly Detection",
            "Time Series",
        ],
        "Preprocessing fit scope": [
            "StandardScaler fit on X_train only (Pipeline)",
            "StandardScaler fit on full X — justified: unsupervised, no target to leak",
            "No scaling needed (set operations only)",
            "StandardScaler fit on full X — unsupervised, labels never used in fit",
            "No scaling; rolling/lag features computed before any split",
        ],
        "Train-test split method": [
            "80/20 random split (trips are i.i.d.)",
            "No split — intrinsic evaluation (silhouette, inertia)",
            "No split — unsupervised; threshold is tunable by user",
            "No split — anomaly scores evaluated against held-out labels post-hoc",
            "TimeSeriesSplit(n_splits=5), shuffle=False",
        ],
        "Target leakage check": [
            "duration_min excluded from feature list",
            "No target; true_group column dropped before clustering",
            "No target in association mining",
            "is_anomaly excluded from feature list; used only for evaluation",
            "Lag features use .shift(1) — no look-ahead into future demand",
        ],
        "Seed pinned": [
            "np.random.default_rng(42), random_state=42",
            "np.random.default_rng(42), random_state=42",
            "np.random.default_rng(42)",
            "np.random.default_rng(42), random_state=42",
            "np.random.default_rng(42), random_state=42",
        ],
        "Metric appropriate for class balance": [
            "RMSE/MAE/R2 — regression, no class balance issue",
            "Silhouette + inertia — clustering metrics",
            "Support/confidence/lift — frequency-based, appropriate",
            "PR-AUC, ROC-AUC, F1 — not accuracy; 2% anomaly rate noted explicitly",
            "MAPE — percentage error, robust to scale shifts",
        ],
        "Code reference": [
            "core/models.py :: train_trip_models()",
            "core/models.py :: train_segmentation()",
            "core/models.py :: apriori()",
            "core/models.py :: train_anomaly_models()",
            "core/models.py :: train_timeseries_model()",
        ],
    }

    audit_df = pd.DataFrame(audit_data)
    st.dataframe(audit_df, use_container_width=True)


# ── Tab 3 ───────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Reward Hacking: How These Models Could Be Made to Look Better Than They Are")

    st.write(
        "Reward hacking means optimising a measurable proxy (the reported metric) "
        "rather than the actual goal (useful predictions). Here are three specific "
        "ways this could happen in this repo, and what prevents each."
    )

    hacks = [
        {
            "hack": "Report accuracy on the anomaly dataset",
            "how_it_inflates": (
                "2% anomaly rate means predicting 'normal' always gives 98% accuracy. "
                "A model that fires zero alerts looks great by this metric."
            ),
            "what_prevents_it": (
                "This repo explicitly states the majority-class accuracy in the Business "
                "Understanding tab and uses PR-AUC, ROC-AUC, and F1 instead. "
                "Accuracy is never reported for this project."
            ),
        },
        {
            "hack": "Shuffle the time series train-test split",
            "how_it_inflates": (
                "Shuffling means future data leaks into training. A model that sees "
                "next week's demand while predicting last week's will appear to "
                "forecast near-perfectly — it's just memorising the future."
            ),
            "what_prevents_it": (
                "TimeSeriesSplit(n_splits=5, shuffle=False) is enforced. Test folds "
                "always come after training folds in time. The lag features use "
                ".shift(1) so the current row's demand is never an input."
            ),
        },
        {
            "hack": "Tune hyperparameters on the test fold",
            "how_it_inflates": (
                "If you iterate: train → evaluate on test → adjust model → repeat, "
                "the test set effectively becomes training data. Reported metrics "
                "are optimistic because the model was chosen to perform well on them."
            ),
            "what_prevents_it": (
                "No hyperparameter search is run against the test fold. The model "
                "configuration (max_iter=200, max_depth=6) was set once before "
                "any evaluation and never changed in response to test metrics."
            ),
        },
    ]

    for i, h in enumerate(hacks, 1):
        st.markdown(f"### {i}. {h['hack']}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**How it inflates the metric**")
            st.write(h["how_it_inflates"])
        with col2:
            st.markdown("**What the code does to prevent it**")
            st.write(h["what_prevents_it"])
        st.divider()


# ── Tab 4 ───────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Reproducibility")

    st.markdown("### Seeds")
    st.write(
        "Every random source uses seed 42. Data generators use "
        "`np.random.default_rng(42)`. All sklearn estimators use "
        "`random_state=42`. Streamlit's `@st.cache_data` and "
        "`@st.cache_resource` ensure generators and models run once per session."
    )

    st.markdown("### Package versions (requirements.txt)")
    st.code(
        """streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.26.0
scikit-learn>=1.4.0
plotly>=5.20.0""",
        language="text",
    )

    st.markdown("### One-command run")
    st.code(
        """pip install -r requirements.txt
streamlit run app.py""",
        language="bash",
    )

    st.write(
        "No internet access is required at runtime. All data is generated "
        "in-process. No external API calls, no database connections, no file downloads."
    )

    st.markdown("### What varies between runs")
    st.write(
        "Nothing in the model outputs varies between runs on the same machine. "
        "UI widget states (slider positions) start at their declared defaults. "
        "The only runtime variation is Plotly rendering (fonts, hover states) "
        "which doesn't affect the results."
    )
