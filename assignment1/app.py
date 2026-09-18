import streamlit as st

st.set_page_config(
    page_title="Data Science Portfolio",
    layout="wide",
    page_icon="📊",
)

st.title("Data Science Portfolio")
st.caption("Five real projects, one Streamlit app — built for CMPE 297")

st.markdown(
    """
This app replicates and extends a 14-project data science curriculum. Five projects were chosen
for depth: regression, clustering, association mining, anomaly detection, and time series. Each
follows the full CRISP-DM lifecycle, from business framing through live interactive inference.
All data is generated synthetically in code with fixed seeds — no downloads, no network calls.
Models train in under 5 seconds. Every preprocessing step lives inside a sklearn Pipeline fit
only on training data, so there is no data leakage.
"""
)

st.divider()

st.subheader("Pages")

import pandas as pd

pages_table = pd.DataFrame({
    "Page": [
        "1 — Trip Duration Predictor",
        "2 — Customer Segmentation",
        "3 — Market Basket Analysis",
        "4 — Anomaly Detection",
        "5 — Time Series Forecasting",
        "6 — CRISP-DM & Leakage Audit",
    ],
    "What it demonstrates": [
        "Regression with haversine feature engineering; HistGBR vs linear baseline; permutation importance",
        "KMeans clustering with elbow + silhouette sweep; PCA 2D projection; RFM personas",
        "Apriori association rules implemented from scratch; support/confidence/lift; cart recommendations",
        "IsolationForest + LOF on imbalanced data; why accuracy is wrong; PR-AUC; threshold tuning",
        "Lag-feature regression; TimeSeriesSplit; ACF computed in numpy; recursive forecast with bands",
        "CRISP-DM phase walkthrough; data leakage audit table; reward hacking and how it is prevented",
    ],
    "Key technique": [
        "HistGradientBoostingRegressor, Pipeline, permutation_importance",
        "KMeans, StandardScaler, PCA, silhouette_score",
        "Apriori from scratch — no mlxtend",
        "IsolationForest, LocalOutlierFactor, PR curves",
        "TimeSeriesSplit, lag features, recursive forecasting",
        "Audit documentation — no model",
    ],
})

st.dataframe(pages_table, use_container_width=True, hide_index=True)

st.divider()

st.subheader("How this was built")
st.write(
    "This portfolio was built using **Claude Code** (Anthropic's CLI agent, model: claude-sonnet-4-6). "
    "The entire codebase — data generators, models, five project pages, the audit page, and this home "
    "screen — was produced in a single prompt session. The workflow was: write a detailed build prompt "
    "specifying every constraint (no external data, no mlxtend, no leakage, CRISP-DM tabs), then let "
    "the agent generate all files and verify they run. Follow-up prompts fixed any import or rendering "
    "errors caught during the verification step."
)

st.divider()

st.subheader("Quick Start")
st.code(
    """pip install -r requirements.txt
streamlit run app.py""",
    language="bash",
)
st.write("Runs offline. No API keys. No database. No downloads.")
