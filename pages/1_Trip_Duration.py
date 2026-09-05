import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from core.data import make_trip_data, haversine
from core.models import train_trip_models
from core.viz import _apply, LAYOUT_BASE, PALETTE, BG, GRID, TEXT

st.set_page_config(layout="wide", page_title="Trip Duration Predictor")
st.title("Trip Duration Predictor")
st.caption("NYC-style taxi trips — regression with feature engineering")

df = make_trip_data()
results = train_trip_models(df)

tabs = st.tabs([
    "Business Understanding",
    "Data Understanding",
    "Data Preparation",
    "Modeling",
    "Evaluation",
    "Live Inference",
])

# ── Tab 1: Business Understanding ──────────────────────────────────────────
with tabs[0]:
    st.subheader("Business Understanding")
    st.write(
        "A ride-hailing app needs to quote trip duration before the passenger "
        "books. Quoting too low erodes driver ratings; quoting too high loses "
        "riders to competitors. The target is trip duration in minutes, "
        "predicted from pickup/dropoff coordinates, time of day, and passenger count."
    )
    st.write(
        "Success means RMSE under 5 minutes on held-out data. That's roughly "
        "half the variation caused by rush-hour congestion, so it's useful "
        "without being dishonestly precise."
    )
    st.write(
        "The baseline to beat is a linear regression on the same features. "
        "If the gradient boosted model doesn't outperform it meaningfully, "
        "complexity isn't justified."
    )


# ── Tab 2: Data Understanding ───────────────────────────────────────────────
with tabs[1]:
    st.subheader("Data Understanding")
    st.write(
        f"Synthetic dataset: {len(df):,} trips, 9 columns. Coordinates are "
        "drawn uniformly within NYC's bounding box. Duration is a nonlinear "
        "function of haversine distance, hour, and weekday — with rush-hour "
        "slowdowns baked in."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", f"{len(df):,}")
    col2.metric("Mean duration", f"{df.duration_min.mean():.1f} min")
    col3.metric("Max distance", f"{df.distance_km.max():.1f} km")

    st.dataframe(df.head(10), use_container_width=True)

    # Distance vs duration scatter with manual trendline
    sample = df.sample(1500, random_state=42)
    fig = px.scatter(
        sample, x="distance_km", y="duration_min",
        color="hour", opacity=0.5,
        title="Distance vs Duration (sample 1500, colored by hour)",
        labels={"distance_km": "Haversine Distance (km)", "duration_min": "Duration (min)"},
        color_continuous_scale="Viridis",
    )
    # Manual OLS trendline via numpy
    x_arr = sample["distance_km"].values
    y_arr = sample["duration_min"].values
    coef = np.polyfit(x_arr, y_arr, 1)
    x_line = np.linspace(x_arr.min(), x_arr.max(), 100)
    fig.add_scatter(x=x_line, y=np.polyval(coef, x_line),
                    mode="lines", line=dict(color="red", dash="dash"),
                    name="Trend", showlegend=True)
    _apply(fig)
    st.plotly_chart(fig, use_container_width=True)

    # Hourly demand heatmap (24 hours x 7 weekdays)
    pivot = df.groupby(["weekday", "hour"]).size().unstack(fill_value=0)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hour_labels = [f"{h:02d}:00" for h in range(24)]

    # Ensure all hours and weekdays present
    pivot = pivot.reindex(range(7), fill_value=0)
    pivot = pivot.reindex(columns=range(24), fill_value=0)

    fig2 = go.Figure(go.Heatmap(
        z=pivot.values,
        x=hour_labels,
        y=day_labels,
        colorscale="YlOrRd",
        showscale=True,
    ))
    fig2.update_layout(title="Trip Demand: Weekday × Hour", **LAYOUT_BASE)
    st.plotly_chart(fig2, use_container_width=True)


# ── Tab 3: Data Preparation ─────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Data Preparation")
    st.write(
        "The key engineered feature is haversine distance — straight-line "
        "great-circle distance in km between pickup and dropoff. This matters "
        "because Euclidean distance on lat/lon degrees doesn't map linearly "
        "to km at NYC's latitude (~40°N)."
    )
    st.code(
        """def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))""",
        language="python",
    )
    st.write(
        "All scaling happens inside a sklearn Pipeline, fit only on the "
        "training fold. The test set never touches the scaler's fit step, "
        "which prevents data leakage. An 80/20 random split is appropriate "
        "here because trips are i.i.d. (no temporal ordering in this dataset)."
    )

    split_info = {
        "Training rows": [len(results["X_train"])],
        "Test rows": [len(results["X_test"])],
        "Features": [", ".join(results["features"])],
    }
    st.table(pd.DataFrame(split_info))


# ── Tab 4: Modeling ─────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Modeling")
    st.write(
        "Two models, same features. LinearRegression as a baseline establishes "
        "what raw correlation alone can achieve. HistGradientBoostingRegressor "
        "captures the nonlinear interaction between distance, hour, and "
        "weekday that the data generating process contains."
    )
    st.write(
        "Both live inside sklearn Pipelines: StandardScaler → model. "
        "The scaler is fit on training data only — it never sees test targets."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Baseline — Linear Regression**")
        st.json(results["baseline_metrics"])
    with col2:
        st.markdown("**Main — HistGradientBoostingRegressor**")
        st.json(results["main_metrics"])


# ── Tab 5: Evaluation ───────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Evaluation")

    # Metrics comparison bar chart
    metrics_df = pd.DataFrame({
        "Metric": ["RMSE", "MAE", "R²"],
        "Linear Regression": [
            results["baseline_metrics"]["RMSE"],
            results["baseline_metrics"]["MAE"],
            results["baseline_metrics"]["R2"],
        ],
        "HistGBR": [
            results["main_metrics"]["RMSE"],
            results["main_metrics"]["MAE"],
            results["main_metrics"]["R2"],
        ],
    })
    fig_m = px.bar(
        metrics_df.melt(id_vars="Metric", var_name="Model", value_name="Value"),
        x="Metric", y="Value", color="Model", barmode="group",
        title="Model Comparison",
    )
    _apply(fig_m)
    st.plotly_chart(fig_m, use_container_width=True)

    # Residual plot
    preds = results["main"].predict(results["X_test"])
    residuals = results["y_test"].values - preds
    fig_r = px.scatter(
        x=preds, y=residuals,
        labels={"x": "Predicted (min)", "y": "Residual (min)"},
        title="Residuals vs Predicted — HistGBR",
        opacity=0.4,
    )
    fig_r.add_hline(y=0, line_dash="dash", line_color="red")
    _apply(fig_r)
    st.plotly_chart(fig_r, use_container_width=True)

    # Permutation importance
    perm = results["perm_importance"]
    fi_df = pd.DataFrame({
        "feature": results["features"],
        "importance": perm.importances_mean,
    }).sort_values("importance", ascending=True)
    fig_fi = px.bar(fi_df, x="importance", y="feature", orientation="h",
                    title="Permutation Feature Importance (test set)")
    _apply(fig_fi)
    st.plotly_chart(fig_fi, use_container_width=True)

    r2_main = results["main_metrics"]["R2"]
    st.write(
        f"The HistGBR R² of {r2_main:.3f} is inflated because the model is recovering "
        "a known generating function from clean synthetic data. The data was produced by "
        "a deterministic formula (haversine distance + hour/weekday effects + Gaussian "
        "noise). The model can learn that formula almost exactly given enough trees. "
        "On real NYC taxi data, R² typically lands around 0.80-0.85 because real trips "
        "contain variance the model cannot recover: GPS noise, traffic incidents, driver "
        "routing decisions, weather, and pickup/dropoff micro-location effects that "
        "lat/lon coordinates don't fully capture."
    )


# ── Tab 6: Live Inference ───────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Live Inference")
    st.write("Adjust the trip parameters and get an instant duration prediction.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pickup**")
        p_lat = st.slider("Pickup latitude", 40.63, 40.85, 40.75, 0.001, key="p_lat")
        p_lon = st.slider("Pickup longitude", -74.05, -73.75, -73.99, 0.001, key="p_lon")
    with col2:
        st.markdown("**Dropoff**")
        d_lat = st.slider("Dropoff latitude", 40.63, 40.85, 40.72, 0.001, key="d_lat")
        d_lon = st.slider("Dropoff longitude", -74.05, -73.75, -73.96, 0.001, key="d_lon")

    col3, col4 = st.columns(2)
    with col3:
        hour = st.slider("Hour of day", 0, 23, 8, key="hour_inf")
        weekday = st.selectbox(
            "Weekday",
            options=list(range(7)),
            format_func=lambda x: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][x],
            key="wd_inf",
        )
    with col4:
        passengers = st.slider("Passengers", 1, 6, 2, key="pass_inf")

    dist = haversine(
        np.array([p_lat]), np.array([p_lon]),
        np.array([d_lat]), np.array([d_lon]),
    )[0]

    x_inf = pd.DataFrame([{
        "distance_km": dist,
        "hour": hour,
        "weekday": weekday,
        "passengers": passengers,
        "pickup_lat": p_lat,
        "pickup_lon": p_lon,
        "dropoff_lat": d_lat,
        "dropoff_lon": d_lon,
    }])

    pred_min = results["main"].predict(x_inf)[0]

    col_a, col_b = st.columns(2)
    col_a.metric("Predicted Duration", f"{pred_min:.1f} min")
    col_b.metric("Haversine Distance", f"{dist:.2f} km")

    # Map
    from core.viz import map_two_points
    fig_map = map_two_points(p_lat, p_lon, d_lat, d_lon)
    st.plotly_chart(fig_map, use_container_width=True)
