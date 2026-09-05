"""Synthetic data generators for all five projects. All use fixed seed 42."""

import numpy as np
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# 1. Trip Duration
# ---------------------------------------------------------------------------

@st.cache_data
def make_trip_data(n: int = 8000) -> pd.DataFrame:
    rng = np.random.default_rng(42)

    # NYC bounding box
    lat_min, lat_max = 40.63, 40.85
    lon_min, lon_max = -74.05, -73.75

    pickup_lat = rng.uniform(lat_min, lat_max, n)
    pickup_lon = rng.uniform(lon_min, lon_max, n)
    dropoff_lat = rng.uniform(lat_min, lat_max, n)
    dropoff_lon = rng.uniform(lon_min, lon_max, n)

    hour = rng.integers(0, 24, n)
    weekday = rng.integers(0, 7, n)
    passengers = rng.integers(1, 7, n)

    dist = haversine(pickup_lat, pickup_lon, dropoff_lat, dropoff_lon)

    # Rush hours: 7-9am, 5-7pm on weekdays
    rush_factor = np.where(
        (weekday < 5) & (((hour >= 7) & (hour <= 9)) | ((hour >= 17) & (hour <= 19))),
        1.4, 1.0
    )
    night_factor = np.where((hour >= 0) & (hour <= 5), 0.85, 1.0)

    base_speed = 20.0  # mph average
    duration_h = dist / (base_speed * rush_factor * night_factor)
    duration_min = duration_h * 60 + rng.normal(0, 2, n)
    duration_min = np.clip(duration_min, 2, 90)

    df = pd.DataFrame({
        "pickup_lat": pickup_lat,
        "pickup_lon": pickup_lon,
        "dropoff_lat": dropoff_lat,
        "dropoff_lon": dropoff_lon,
        "hour": hour,
        "weekday": weekday,
        "passengers": passengers,
        "distance_km": dist,
        "duration_min": duration_min,
    })
    return df


def haversine(lat1, lon1, lat2, lon2):
    """Vectorised haversine distance in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# 2. Customer Segmentation (RFM)
# ---------------------------------------------------------------------------

@st.cache_data
def make_rfm_data(n: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(42)

    # 4 latent groups with real separation
    group_sizes = [600, 900, 900, 600]
    groups = []

    params = [
        # (recency_mean, recency_std, freq_mean, freq_std, monetary_mean, monetary_std)
        (10,  5,  20, 4,  800, 150),   # Champions: recent, frequent, high spend
        (60,  20, 8,  2,  300, 80),    # At risk: less recent, moderate freq
        (120, 30, 3,  1,  150, 50),    # Dormant: old, infrequent, low spend
        (20,  8,  12, 3,  500, 120),   # Loyal: recent, moderate freq, good spend
    ]

    for i, (sz, (rm, rs, fm, fs, mm, ms)) in enumerate(zip(group_sizes, params)):
        r = np.clip(rng.normal(rm, rs, sz), 1, 365)
        f = np.clip(rng.normal(fm, fs, sz), 1, 50).astype(int)
        m = np.clip(rng.normal(mm, ms, sz), 10, 5000)
        groups.append(pd.DataFrame({"recency": r, "frequency": f, "monetary": m, "true_group": i}))

    df = pd.concat(groups, ignore_index=True).sample(frac=1, random_state=42).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 3. Market Basket
# ---------------------------------------------------------------------------

GROCERY_ITEMS = [
    "milk", "bread", "eggs", "butter", "cheese",
    "apples", "bananas", "chicken", "pasta", "rice",
    "yogurt", "coffee", "tea", "juice", "chips",
    "cookies", "chocolate", "vegetables", "beef", "cereal",
]

# 4 planted rules: single antecedent → consequent, each in a distinct thematic domain.
# With 4 rules, cross-combination triple support ≈ 1.3% (below 3% threshold), so
# Apriori finds only the 4 direct rules + their reverses (≈ 8-12 total at defaults).
# Each rule lifts conditional confidence from ~25% background to ~68%, giving
# lift ≈ 2.3 — clearly separable from background associations filtered by lift>1.0.
_PLANTED_RULES = [
    ("milk",    "butter",      0.55),   # dairy: morning staple
    ("coffee",  "chocolate",   0.55),   # indulgence: often bought together
    ("pasta",   "cheese",      0.55),   # Italian: go-to pairing
    ("chicken", "vegetables",  0.55),   # dinner: protein + produce
]


@st.cache_data
def make_basket_data(n: int = 4000) -> list:
    rng = np.random.default_rng(42)
    baskets = []

    for _ in range(n):
        basket = set()
        # Background: 3-5 items without replacement from 20-item catalog (mean ~4).
        # At mean 4 / catalog 20: P(two specific antecedents co-occur) ≈ 3.3%.
        # Cross-planted triple support ≈ 3.3% × 0.65 × 0.65 ≈ 1.4% → filtered at 3%.
        n_bg = rng.integers(3, 6)
        bg = rng.choice(GROCERY_ITEMS, size=n_bg, replace=False).tolist()
        basket.update(bg)

        # Apply planted single-antecedent rules
        for antecedent, consequent, prob in _PLANTED_RULES:
            if antecedent in basket and consequent not in basket:
                if rng.random() < prob:
                    basket.add(consequent)

        baskets.append(sorted(basket))

    return baskets


# ---------------------------------------------------------------------------
# 4. Anomaly Detection (Server Telemetry)
# ---------------------------------------------------------------------------

def _build_telemetry_cov():
    """Covariance matrix encoding realistic correlations between server metrics."""
    # latency, error_rate, throughput, cpu, memory
    stds = np.array([15.0, 2.5, 150.0, 15.0, 12.0])
    # CPU and memory are positively correlated (same load driver).
    # Latency and error_rate are positively correlated (overload symptoms).
    # Throughput is negatively correlated with latency/error (inverse capacity effect).
    corr = np.array([
        [1.00,  0.45, -0.35,  0.25,  0.10],
        [0.45,  1.00, -0.25,  0.20,  0.10],
        [-0.35, -0.25,  1.00, -0.30, -0.20],
        [0.25,  0.20, -0.30,  1.00,  0.60],
        [0.10,  0.10, -0.20,  0.60,  1.00],
    ])
    return np.diag(stds) @ corr @ np.diag(stds)


@st.cache_data
def make_telemetry_data(n: int = 6000) -> pd.DataFrame:
    """
    Hard anomaly detection dataset. Anomalies overlap substantially with the
    tail of the normal distribution. ~30% are single-feature subtle deviations.
    Normal-but-unusual records (traffic bursts, maintenance, DB pressure) provide
    realistic false-positive candidates. Target IsolationForest PR-AUC ~0.75-0.90.
    """
    rng = np.random.default_rng(42)
    cov = _build_telemetry_cov()

    n_anomaly = int(n * 0.02)          # 120 true anomalies
    # Normal-but-unusual: 3 per anomaly — legitimate spikes that look suspicious.
    # Crucially, these are extreme in THROUGHPUT only, not in latency/error.
    # IsolationForest isolates multi-dimensional extremes faster than
    # single-dimensional ones, so true anomalies (latency+error+cpu) will
    # still rank above these throughput-only outliers.
    n_unusual = n_anomaly * 3          # 360 hard-negative normals
    n_plain = n - n_anomaly - n_unusual

    # Feature order: latency_ms, error_rate_pct, throughput_rps, cpu_pct, memory_pct
    mu_normal = np.array([50.0, 3.0, 1000.0, 40.0, 60.0])

    # ── Plain normal traffic ──────────────────────────────────────────────
    X_plain = rng.multivariate_normal(mu_normal, cov, size=n_plain)

    # ── Normal-but-unusual (labeled 0) — extreme ONLY in throughput ───────
    n_burst = n_unusual // 2
    n_maint = n_unusual - n_burst

    # Traffic burst: throughput 2.5σ high — still unusual but ranks below the
    # clear+moderate anomalies whose extremity spans latency+error simultaneously.
    X_burst = rng.multivariate_normal(
        [52.0, 3.2, 1375.0, 44.0, 63.0], cov, size=n_burst
    )
    # Maintenance: throughput 2.5σ low — same reasoning; single-feature isolation
    # scores lower than multi-feature anomalies.
    X_maint = rng.multivariate_normal(
        [47.0, 2.8, 625.0, 36.0, 57.0], cov, size=n_maint
    )

    X_normal = np.vstack([X_plain, X_burst, X_maint])
    y_normal = np.zeros(len(X_normal))

    # ── True anomalies — extreme in {latency, error_rate, cpu, memory} ───
    n_subtle   = int(n_anomaly * 0.30)  # 1 feature barely off, very hard
    n_moderate = int(n_anomaly * 0.40)  # 2-3 features at 3-5 sigma
    n_clear    = n_anomaly - n_subtle - n_moderate  # 3-4 features at 6-9 sigma

    # Subtle: latency at 2.5σ (87.5ms) only — sits in the upper tail of the
    # normal distribution (99th pct), so there are real normal records here too.
    X_subtle = rng.multivariate_normal(
        [87.5, 3.3, 975.0, 41.0, 61.0], cov, size=n_subtle
    )
    # Moderate: latency at 6.5σ (147ms) + error at 6.4σ (19%). Two-feature
    # extremity in the {latency,error} subspace decisively outranks the
    # throughput-only unusual normals in IsolationForest path-length scoring.
    X_moderate = rng.multivariate_normal(
        [147.0, 19.0, 840.0, 70.0, 76.0], cov, size=n_moderate
    )
    # Clear: latency at 10σ + error at 8.8σ + cpu at 3.2σ. Unmistakable.
    X_clear = rng.multivariate_normal(
        [200.0, 25.0, 720.0, 88.0, 88.0], cov, size=n_clear
    )

    X_anomaly = np.vstack([X_subtle, X_moderate, X_clear])
    y_anomaly = np.ones(len(X_anomaly))

    X_all = np.vstack([X_normal, X_anomaly])
    y_all = np.concatenate([y_normal, y_anomaly]).astype(int)

    col_clips = [(1.0, 500.0), (0.0, 100.0), (50.0, 3000.0), (0.0, 100.0), (0.0, 100.0)]
    for i, (lo, hi) in enumerate(col_clips):
        X_all[:, i] = np.clip(X_all[:, i], lo, hi)

    df = pd.DataFrame(X_all, columns=[
        "latency_ms", "error_rate_pct", "throughput_rps", "cpu_pct", "memory_pct"
    ])
    df["is_anomaly"] = y_all

    return df.sample(frac=1, random_state=42).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. Time Series (Daily Demand)
# ---------------------------------------------------------------------------

@st.cache_data
def make_timeseries_data(n_days: int = 730) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2022-01-01", periods=n_days, freq="D")

    t = np.arange(n_days)
    trend = 100 + 0.05 * t
    weekly = 20 * np.sin(2 * np.pi * t / 7 + 0.5)
    yearly = 30 * np.sin(2 * np.pi * t / 365.25)
    noise = rng.normal(0, 8, n_days)
    demand = trend + weekly + yearly + noise
    demand = np.clip(demand, 10, None)

    df = pd.DataFrame({"date": dates, "demand": demand})
    df["dayofweek"] = df["date"].dt.dayofweek
    df["dayofyear"] = df["date"].dt.dayofyear
    df["month"] = df["date"].dt.month
    return df
