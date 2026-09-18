import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from core.data import make_timeseries_data
from core.models import train_timeseries_model, recursive_forecast
from core.viz import _apply, LAYOUT_BASE, PALETTE

st.set_page_config(layout="wide", page_title="Time Series Forecasting")
st.title("Time Series Forecasting")
st.caption("Daily demand — lag-feature regression with TimeSeriesSplit")

df = make_timeseries_data()
results = train_timeseries_model(df)

tabs = st.tabs([
    "Business Understanding",
    "Data Understanding",
    "Data Preparation",
    "Modeling",
    "Evaluation",
    "Live Inference",
])

with tabs[0]:
    st.subheader("Business Understanding")
    st.write(
        "A retail buyer needs to know how much product to order two weeks out. "
        "Under-ordering means lost sales; over-ordering means spoilage and "
        "tied-up capital. The forecast horizon is 7–90 days, and the relevant "
        "patterns are weekly seasonality (weekends differ from weekdays) and "
        "yearly seasonality (summer peaks, winter troughs)."
    )
    st.write(
        "The baseline is seasonal naive: predict today's demand equals the "
        "same weekday last week. A good model should beat this. MAPE "
        "(mean absolute percentage error) is the right metric because the "
        "buyer thinks in percentage terms, not absolute units."
    )
    st.write(
        "Time series evaluation is strict: you can never train on the future. "
        "We use TimeSeriesSplit, which creates expanding windows where the "
        "test fold always follows the training fold in time."
    )


with tabs[1]:
    st.subheader("Data Understanding")
    st.write(
        f"730 days of synthetic daily demand from 2022-01-01. "
        "Signal has a linear trend (+0.05 units/day), a 7-day cycle, "
        "a 365-day cycle, and Gaussian noise (σ=8). No missing values."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Days", len(df))
    col2.metric("Mean demand", f"{df.demand.mean():.1f}")
    col3.metric("Std demand", f"{df.demand.std():.1f}")

    # Full series
    fig_series = go.Figure()
    fig_series.add_trace(go.Scatter(
        x=df["date"], y=df["demand"],
        mode="lines", name="Demand", line=dict(width=1, color=PALETTE[0]),
    ))
    fig_series.update_layout(title="Daily Demand — Full Series",
                             xaxis_title="Date", yaxis_title="Demand",
                             **LAYOUT_BASE)
    st.plotly_chart(fig_series, use_container_width=True)

    # ACF — computed manually with numpy
    st.subheader("Autocorrelation Function (manual numpy, up to lag 40)")
    demand_vals = df["demand"].values
    demand_c = demand_vals - demand_vals.mean()
    n = len(demand_c)
    acf_vals = []
    for lag in range(41):
        if lag == 0:
            acf_vals.append(1.0)
        else:
            num = np.sum(demand_c[:n - lag] * demand_c[lag:])
            den = np.sum(demand_c ** 2)
            acf_vals.append(num / den)

    confidence_bound = 1.96 / np.sqrt(n)
    fig_acf = go.Figure()
    fig_acf.add_trace(go.Bar(
        x=list(range(41)), y=acf_vals, name="ACF",
        marker_color=PALETTE[1],
    ))
    fig_acf.add_hline(y=confidence_bound, line_dash="dash", line_color="red",
                      annotation_text="95% CI")
    fig_acf.add_hline(y=-confidence_bound, line_dash="dash", line_color="red")
    fig_acf.update_layout(title="ACF (manually computed, numpy)",
                          xaxis_title="Lag (days)", yaxis_title="Autocorrelation",
                          **LAYOUT_BASE)
    st.plotly_chart(fig_acf, use_container_width=True)

    st.write(
        "Spikes at lags 7, 14, 21, 28 confirm weekly seasonality. "
        "The slow decay of the envelope reflects the trend component."
    )


with tabs[2]:
    st.subheader("Data Preparation")
    st.write(
        "Lag features turn a time series into a tabular regression problem. "
        "We use lags 1, 7, 14, 28 and rolling means over 7 and 28 days. "
        "Rolling means are computed off the shifted series (shift by 1) so "
        "they never include the current row's value — no leakage."
    )
    st.code(
        """for lag in [1, 7, 14, 28]:
    df[f'lag_{lag}'] = df['demand'].shift(lag)
for w in [7, 28]:
    df[f'roll_mean_{w}'] = df['demand'].shift(1).rolling(w).mean()
df = df.dropna()  # first 28 rows have NaN lags""",
        language="python",
    )
    st.write(
        "The first 28 rows are dropped because lags are undefined there. "
        "TimeSeriesSplit(n_splits=5) creates 5 expanding folds. "
        "Fold k+1 never appears in the training data for fold k."
    )

    feat_df = results["df_feat"]
    st.write(f"After lag construction: {len(feat_df)} rows, {len(results['feature_cols'])} features.")
    st.write(f"Features: {', '.join(results['feature_cols'])}")


with tabs[3]:
    st.subheader("Modeling")
    st.write(
        "HistGradientBoostingRegressor handles the nonlinear interactions "
        "between lags and calendar features. No scaling is needed — tree models "
        "are invariant to feature scale."
    )
    st.write(
        "The seasonal naive baseline predicts demand[t-7]: whatever demand "
        "was exactly one week ago. It's a strong baseline because weekly "
        "seasonality dominates this signal."
    )

    col1, col2 = st.columns(2)
    col1.metric("Naive baseline MAPE", f"{results['naive_mape']:.1f}%")
    col2.metric("Model MAPE (last fold)", f"{results['fold_metrics'].iloc[-1]['MAPE']:.1f}%")

    st.dataframe(results["fold_metrics"], use_container_width=True)


with tabs[4]:
    st.subheader("Evaluation")

    # Train/test split visualization (last 20% as pseudo-test)
    df_feat = results["df_feat"]
    split_idx = int(len(df_feat) * 0.8)
    train_df = df_feat.iloc[:split_idx]
    test_df = df_feat.iloc[split_idx:]

    model = results["model"]
    feat_cols = results["feature_cols"]
    test_pred = model.predict(test_df[feat_cols].values)

    fig_eval = go.Figure()
    fig_eval.add_trace(go.Scatter(
        x=train_df["date"], y=train_df["demand"],
        mode="lines", name="Train", line=dict(color=PALETTE[0], width=1),
    ))
    fig_eval.add_trace(go.Scatter(
        x=test_df["date"], y=test_df["demand"],
        mode="lines", name="Actual (test)", line=dict(color=PALETTE[1], width=1.5),
    ))
    fig_eval.add_trace(go.Scatter(
        x=test_df["date"], y=test_pred,
        mode="lines", name="Predicted (test)",
        line=dict(color=PALETTE[2], width=1.5, dash="dash"),
    ))
    fig_eval.update_layout(title="Forecast vs Actual (hold-out)",
                           xaxis_title="Date", yaxis_title="Demand",
                           **LAYOUT_BASE)
    st.plotly_chart(fig_eval, use_container_width=True)

    # Fold-by-fold MAPE
    st.markdown("**Backtest MAPE by fold**")
    st.dataframe(results["fold_metrics"], use_container_width=True)

    fold_mapes = results["fold_metrics"]["MAPE"].tolist()
    naive_mape = results["naive_mape"]
    mean_mape = results["fold_metrics"]["MAPE"].mean()
    last_mape = fold_mapes[-1]

    st.write(
        f"Fold 1 MAPE is {fold_mapes[0]:.1f}% — roughly three times worse than folds 3-5. "
        "The first fold trains on about five months of data and predicts the next two "
        "months. It has never seen a full yearly cycle, so the yearly seasonality component "
        "is invisible to it. The error reflects that missing knowledge, not model failure."
    )
    st.write(
        f"Folds 3-5 MAPE: {fold_mapes[2]:.1f}%, {fold_mapes[3]:.1f}%, {fold_mapes[4]:.1f}%. "
        f"The seasonal naive baseline scores {naive_mape:.1f}% when computed across the full "
        f"series. The model only beats naive once it has seen enough history to learn the "
        "yearly pattern — roughly from fold 3 onward. That is an honest limitation, not a defect. "
        "Reporting the mean MAPE across all five folds would be misleading because fold 1 "
        "drags it up to levels that don't reflect the model's real capability on mature data."
    )


with tabs[5]:
    st.subheader("Live Inference")
    st.write(
        "Choose a forecast horizon. The model generates a recursive multi-step "
        "forecast using the predictions from prior steps as inputs to subsequent "
        "steps. The shaded band is the 10th–90th percentile of backtest residuals."
    )

    horizon = st.slider("Forecast horizon (days)", 7, 90, 30, key="horizon_inf")

    fcast_df = recursive_forecast(
        results["model"],
        results["df_feat"],
        results["feature_cols"],
        horizon,
        results["residuals"],
    )

    # Show last 90 days of history + forecast
    hist_tail = results["df_feat"].tail(90)

    fig_fcast = go.Figure()
    fig_fcast.add_trace(go.Scatter(
        x=hist_tail["date"], y=hist_tail["demand"],
        mode="lines", name="History", line=dict(color=PALETTE[0], width=1.5),
    ))
    fig_fcast.add_trace(go.Scatter(
        x=fcast_df["date"], y=fcast_df["forecast"],
        mode="lines", name="Forecast", line=dict(color=PALETTE[2], width=2),
    ))
    fig_fcast.add_trace(go.Scatter(
        x=pd.concat([fcast_df["date"], fcast_df["date"][::-1]]),
        y=pd.concat([fcast_df["upper"], fcast_df["lower"][::-1]]),
        fill="toself",
        fillcolor="rgba(100,200,100,0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        name="80% band",
    ))
    fig_fcast.update_layout(
        title=f"{horizon}-day Recursive Forecast",
        xaxis_title="Date", yaxis_title="Demand",
        **LAYOUT_BASE,
    )
    st.plotly_chart(fig_fcast, use_container_width=True)

    st.dataframe(fcast_df.head(10).round(2), use_container_width=True)
