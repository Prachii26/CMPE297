"""Training functions and the from-scratch Apriori implementation."""

import numpy as np
import pandas as pd
import streamlit as st
from itertools import combinations

from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    silhouette_score,
)
from sklearn.inspection import permutation_importance


# ---------------------------------------------------------------------------
# 1. Trip Duration
# ---------------------------------------------------------------------------

@st.cache_resource
def train_trip_models(df: pd.DataFrame):
    features = ["distance_km", "hour", "weekday", "passengers",
                 "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon"]
    X = df[features]
    y = df["duration_min"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Baseline: linear regression inside pipeline with scaler
    baseline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LinearRegression()),
    ])
    baseline.fit(X_train, y_train)

    # Main model: HistGBR — handles mixed types, no explicit scaling needed
    main = Pipeline([
        ("scaler", StandardScaler()),
        ("model", HistGradientBoostingRegressor(
            max_iter=200, random_state=42, max_depth=6,
        )),
    ])
    main.fit(X_train, y_train)

    # Permutation importance (on test set, 5 repeats)
    perm = permutation_importance(
        main, X_test, y_test, n_repeats=5, random_state=42
    )

    def metrics(model):
        pred = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, pred))
        mae = mean_absolute_error(y_test, pred)
        r2 = r2_score(y_test, pred)
        return {"RMSE": round(rmse, 3), "MAE": round(mae, 3), "R2": round(r2, 4)}

    return {
        "baseline": baseline,
        "main": main,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "features": features,
        "baseline_metrics": metrics(baseline),
        "main_metrics": metrics(main),
        "perm_importance": perm,
    }


# ---------------------------------------------------------------------------
# 2. Customer Segmentation
# ---------------------------------------------------------------------------

@st.cache_resource
def train_segmentation(df: pd.DataFrame, k: int = 4):
    features = ["recency", "frequency", "monetary"]
    X = df[features].values

    # Elbow / silhouette sweep
    k_range = list(range(2, 11))
    inertias, silhouettes = [], []
    for ki in k_range:
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=ki, random_state=42, n_init=10)),
        ])
        labels = pipe.fit_predict(X)
        inertias.append(pipe.named_steps["kmeans"].inertia_)
        silhouettes.append(silhouette_score(X, labels))

    # Final model at chosen k
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("kmeans", KMeans(n_clusters=k, random_state=42, n_init=10)),
    ])
    labels = pipe.fit_predict(X)

    # PCA for 2-D projection
    pca = PCA(n_components=2, random_state=42)
    X_scaled = pipe.named_steps["scaler"].transform(X)
    X_pca = pca.fit_transform(X_scaled)

    df2 = df.copy()
    df2["cluster"] = labels
    df2["pca_1"] = X_pca[:, 0]
    df2["pca_2"] = X_pca[:, 1]

    # Cluster profiles
    profile = df2.groupby("cluster").agg(
        recency=("recency", "mean"),
        frequency=("frequency", "mean"),
        monetary=("monetary", "mean"),
        size=("recency", "count"),
    ).round(1)
    profile["pct_revenue"] = (
        profile["monetary"] * profile["size"] /
        (profile["monetary"] * profile["size"]).sum() * 100
    ).round(1)

    return {
        "pipe": pipe,
        "labels": labels,
        "df": df2,
        "k_range": k_range,
        "inertias": inertias,
        "silhouettes": silhouettes,
        "profile": profile,
        "pca": pca,
    }


# ---------------------------------------------------------------------------
# 3. Market Basket — Apriori from scratch
# ---------------------------------------------------------------------------

def apriori(transactions: list, min_support: float = 0.02,
            min_confidence: float = 0.3, min_lift: float = 1.0):
    """
    From-scratch Apriori.
    Returns (frequent_itemsets dict, rules list of dicts).
    """
    n = len(transactions)
    item_sets = [frozenset(t) for t in transactions]

    # Count singletons
    item_counts: dict = {}
    for basket in item_sets:
        for item in basket:
            item_counts[item] = item_counts.get(item, 0) + 1

    # L1
    L = {}
    for item, cnt in item_counts.items():
        sup = cnt / n
        if sup >= min_support:
            L[frozenset([item])] = sup

    all_frequent = dict(L)
    k = 2

    while L:
        # Candidate generation: union of pairs sharing k-2 items
        prev_keys = list(L.keys())
        candidates: dict = {}
        for i in range(len(prev_keys)):
            for j in range(i + 1, len(prev_keys)):
                union = prev_keys[i] | prev_keys[j]
                if len(union) == k and union not in candidates:
                    # Count support
                    cnt = sum(1 for basket in item_sets if union.issubset(basket))
                    sup = cnt / n
                    if sup >= min_support:
                        candidates[union] = sup

        all_frequent.update(candidates)
        L = candidates
        k += 1
        if k > 6:  # safety cap
            break

    # Rule generation
    rules = []
    for itemset, sup_itemset in all_frequent.items():
        if len(itemset) < 2:
            continue
        for size in range(1, len(itemset)):
            for antecedent in combinations(sorted(itemset), size):
                ant = frozenset(antecedent)
                con = itemset - ant
                if not con:
                    continue
                sup_ant = all_frequent.get(ant, 0)
                if sup_ant == 0:
                    continue
                conf = sup_itemset / sup_ant
                sup_con = all_frequent.get(con, 0)
                lift = conf / sup_con if sup_con > 0 else 0
                if conf >= min_confidence and lift >= min_lift:
                    rules.append({
                        "antecedent": ", ".join(sorted(ant)),
                        "consequent": ", ".join(sorted(con)),
                        "support": round(sup_itemset, 4),
                        "confidence": round(conf, 4),
                        "lift": round(lift, 4),
                    })

    rules_df = pd.DataFrame(rules).sort_values("lift", ascending=False) if rules else pd.DataFrame()
    return all_frequent, rules_df


def recommend(rules_df: pd.DataFrame, cart_items: list, top_n: int = 3) -> pd.DataFrame:
    """Given items in cart, find rules whose antecedent is a subset of cart."""
    if rules_df.empty:
        return pd.DataFrame()
    cart_set = set(cart_items)
    mask = rules_df["antecedent"].apply(
        lambda a: set(a.split(", ")).issubset(cart_set)
    )
    recs = rules_df[mask].copy()
    # Filter out consequents already in cart
    recs = recs[~recs["consequent"].apply(lambda c: c in cart_set)]
    return recs.head(top_n)


# ---------------------------------------------------------------------------
# 4. Anomaly Detection
# ---------------------------------------------------------------------------

@st.cache_resource
def train_anomaly_models(df: pd.DataFrame):
    """
    Proper unsupervised anomaly detection protocol:
      - Both models are fit on the 80% training split using features only
        (labels are never seen during training).
      - PR-AUC and ROC-AUC are reported on the 20% held-out test set.
      - All records are scored for the Live Inference threshold demo so the
        confusion matrix has enough positive and negative examples to move.
    """
    features = ["latency_ms", "error_rate_pct", "throughput_rps", "cpu_pct", "memory_pct"]
    X = df[features].values
    y = df["is_anomaly"].values

    # Stratified 80/20 split — keeps the 2% anomaly rate in both halves
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # IsolationForest — fit on unlabeled training data only
    iso_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", IsolationForest(contamination=0.02, random_state=42, n_estimators=100)),
    ])
    iso_pipe.fit(X_train)

    def _score(pipe, X_arr):
        return -pipe.named_steps["model"].score_samples(
            pipe.named_steps["scaler"].transform(X_arr)
        )

    iso_scores_test = _score(iso_pipe, X_test)
    iso_scores_all  = _score(iso_pipe, X)

    # LOF (novelty=True for inductive scoring on unseen data)
    lof_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LocalOutlierFactor(n_neighbors=20, contamination=0.02, novelty=True)),
    ])
    lof_pipe.fit(X_train)

    lof_scores_test = _score(lof_pipe, X_test)
    lof_scores_all  = _score(lof_pipe, X)

    return {
        "iso_pipe": iso_pipe,
        "lof_pipe": lof_pipe,
        # Held-out test set — used for PR-AUC / ROC-AUC
        "iso_scores_test": iso_scores_test,
        "lof_scores_test": lof_scores_test,
        "y_test": y_test,
        # Full-dataset scores — used for Live Inference threshold demo
        "iso_scores": iso_scores_all,
        "lof_scores": lof_scores_all,
        "y": y,
        "X": X,
        "features": features,
        "df": df,
    }


# ---------------------------------------------------------------------------
# 5. Time Series
# ---------------------------------------------------------------------------

def make_lag_features(df: pd.DataFrame, lags=(1, 7, 14, 28), roll_windows=(7, 28)):
    out = df.copy()
    for lag in lags:
        out[f"lag_{lag}"] = out["demand"].shift(lag)
    for w in roll_windows:
        out[f"roll_mean_{w}"] = out["demand"].shift(1).rolling(w).mean()
    out = out.dropna()
    return out


@st.cache_resource
def train_timeseries_model(df: pd.DataFrame):
    df_feat = make_lag_features(df)
    feature_cols = [c for c in df_feat.columns
                    if c.startswith("lag_") or c.startswith("roll_") or
                    c in ("dayofweek", "dayofyear", "month")]

    X = df_feat[feature_cols].values
    y = df_feat["demand"].values
    dates = df_feat["date"].values

    # TimeSeriesSplit — no shuffle, no leakage
    tscv = TimeSeriesSplit(n_splits=5)
    fold_metrics = []
    residuals_all = []

    model = None
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        m = HistGradientBoostingRegressor(max_iter=200, random_state=42)
        m.fit(X_tr, y_tr)
        pred = m.predict(X_te)
        mape = np.mean(np.abs((y_te - pred) / (y_te + 1e-8))) * 100
        fold_metrics.append({"fold": fold + 1, "MAPE": round(mape, 2),
                              "n_test": len(y_te)})
        residuals_all.extend((y_te - pred).tolist())
        model = m  # keep last fold model for demo

    # Fit final model on all data
    final_model = HistGradientBoostingRegressor(max_iter=200, random_state=42)
    final_model.fit(X, y)

    # Seasonal naive baseline: predict demand[t-7]
    naive_preds = df_feat["lag_7"].values
    naive_mape = np.mean(np.abs((y - naive_preds) / (y + 1e-8))) * 100

    return {
        "model": final_model,
        "df_feat": df_feat,
        "feature_cols": feature_cols,
        "fold_metrics": pd.DataFrame(fold_metrics),
        "naive_mape": round(naive_mape, 2),
        "residuals": np.array(residuals_all),
        "y": y,
        "dates": dates,
        "X": X,
    }


def recursive_forecast(model, df_feat: pd.DataFrame, feature_cols: list,
                        horizon: int, residuals: np.ndarray):
    """
    Recursive multi-step forecast.
    Returns dates, point forecast, lower/upper quantile bands.
    """
    last_row = df_feat.iloc[-1].copy()
    history = df_feat["demand"].tolist()
    last_date = pd.Timestamp(df_feat["date"].iloc[-1])

    future_dates = [last_date + pd.Timedelta(days=i + 1) for i in range(horizon)]
    forecasts = []

    q_lo = np.percentile(residuals, 10)
    q_hi = np.percentile(residuals, 90)

    lags = [1, 7, 14, 28]
    roll_windows = [7, 28]

    for i, fd in enumerate(future_dates):
        row = {}
        row["dayofweek"] = fd.dayofweek
        row["dayofyear"] = fd.dayofyear
        row["month"] = fd.month

        full_history = history + forecasts

        for lag in lags:
            idx = -(lag)
            row[f"lag_{lag}"] = full_history[idx] if len(full_history) >= lag else np.nan

        for w in roll_windows:
            recent = full_history[-w:] if len(full_history) >= w else full_history
            row[f"roll_mean_{w}"] = float(np.mean(recent))

        x_vec = np.array([[row.get(c, 0) for c in feature_cols]])
        pred = model.predict(x_vec)[0]
        forecasts.append(pred)

    forecasts = np.array(forecasts)
    lower = forecasts + q_lo
    upper = forecasts + q_hi

    return pd.DataFrame({
        "date": future_dates,
        "forecast": forecasts,
        "lower": lower,
        "upper": upper,
    })
