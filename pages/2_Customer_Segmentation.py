import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.data import make_rfm_data
from core.models import train_segmentation
from core.viz import _apply, LAYOUT_BASE, PALETTE

st.set_page_config(layout="wide", page_title="Customer Segmentation")
st.title("Customer Segmentation")
st.caption("RFM clustering with KMeans — who are your customers?")

df = make_rfm_data()


def derive_personas(profile: pd.DataFrame) -> dict:
    """
    Assign RFM persona labels from cluster centroids at runtime.

    Ranks clusters by a composite score: inverted recency (lower = more recent =
    better) + normalised frequency + normalised monetary.  The ranking determines
    the label — no hardcoded cluster-ID→label mapping.

    Returns {cluster_id: (name, description)}.
    """
    p = profile[["recency", "frequency", "monetary"]].copy().astype(float)

    r_range = p["recency"].max() - p["recency"].min()
    f_range = p["frequency"].max() - p["frequency"].min()
    m_range = p["monetary"].max() - p["monetary"].min()

    p["score"] = (
        (p["recency"].max() - p["recency"]) / (r_range if r_range else 1)
        + (p["frequency"] - p["frequency"].min()) / (f_range if f_range else 1)
        + (p["monetary"] - p["monetary"].min()) / (m_range if m_range else 1)
    )

    # Highest composite score → Champions; lowest → Dormant
    ordered = p["score"].sort_values(ascending=False).index.tolist()

    _label_pool = [
        ("Champions",     "Bought recently, buy often, and spend the most. Reward them."),
        ("Loyal",         "Buy regularly with solid spend. Nurture toward Champions."),
        ("At Risk",       "Higher spenders who haven't bought lately. Send a win-back offer."),
        ("Dormant",       "Long lapsed, infrequent, low spend. Hard to reactivate."),
        ("Occasional",    "Infrequent buyers with low spend."),
        ("High Potential","Frequent but lower spend — could convert upward."),
    ]

    return {cid: _label_pool[i] for i, cid in enumerate(ordered)}

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
        "Marketing budgets are finite. Sending the same email to everyone "
        "wastes money on customers who've already churned and annoys the ones "
        "who'd buy anyway. Segmentation lets you spend where it has impact."
    )
    st.write(
        "Recency, Frequency, and Monetary (RFM) are the three levers. "
        "A customer who bought yesterday, ten times, for $500 is worth "
        "treating differently from one who bought three years ago, once, for $20."
    )
    st.write(
        "Success looks like: clusters that are internally coherent (low "
        "intra-cluster variance) and have interpretable business meaning. "
        "The silhouette score formalises the first criterion."
    )


with tabs[1]:
    st.subheader("Data Understanding")
    st.write(
        f"Synthetic RFM dataset: {len(df):,} customers, 4 planted groups with "
        "real separation in the feature space. Recency is days since last "
        "purchase; Frequency is total purchases; Monetary is total spend."
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Customers", f"{len(df):,}")
    col2.metric("Median Recency", f"{df.recency.median():.0f} days")
    col3.metric("Median Monetary", f"${df.monetary.median():.0f}")

    st.dataframe(df.drop(columns=["true_group"]).describe().round(1), use_container_width=True)

    sample_3d = df.sample(800, random_state=42).copy()
    sample_3d["group"] = sample_3d["true_group"].astype(str)
    fig = px.scatter_3d(
        sample_3d,
        x="recency", y="frequency", z="monetary",
        color="group", opacity=0.6,
        title="3D RFM view (true latent groups, sample 800)",
        labels={"group": "Latent group"},
        category_orders={"group": ["0", "1", "2", "3"]},
    )
    fig.update_layout(**LAYOUT_BASE)
    st.plotly_chart(fig, use_container_width=True)


with tabs[2]:
    st.subheader("Data Preparation")
    st.write(
        "KMeans is distance-based, so features on different scales dominate "
        "the objective. StandardScaler is applied inside a Pipeline, fit "
        "exclusively on training data. There is no test/train split here "
        "because clustering is unsupervised — the whole dataset is used to "
        "fit the model, and evaluation is intrinsic (inertia, silhouette)."
    )
    st.write(
        "No feature engineering is needed beyond scaling. Recency, frequency, "
        "and monetary are already directly meaningful."
    )
    st.code(
        """pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('kmeans', KMeans(n_clusters=k, random_state=42, n_init=10)),
])
labels = pipe.fit_predict(X)""",
        language="python",
    )


with tabs[3]:
    st.subheader("Modeling")
    k_select = st.slider("Choose k for full analysis", 2, 10, 4, key="k_model")
    results = train_segmentation(df, k=k_select)

    col1, col2 = st.columns(2)

    sweep_df = pd.DataFrame({
        "k": results["k_range"],
        "Inertia": results["inertias"],
        "Silhouette": results["silhouettes"],
    })

    with col1:
        fig_elbow = px.line(sweep_df, x="k", y="Inertia",
                            title="Elbow Curve (Inertia vs k)", markers=True)
        _apply(fig_elbow)
        st.plotly_chart(fig_elbow, use_container_width=True)

    with col2:
        fig_sil = px.line(sweep_df, x="k", y="Silhouette",
                          title="Silhouette Score vs k", markers=True)
        _apply(fig_sil)
        st.plotly_chart(fig_sil, use_container_width=True)

    st.write(
        f"At k={k_select}, silhouette = "
        f"{results['silhouettes'][results['k_range'].index(k_select)]:.3f}. "
        "Values above 0.3 indicate meaningful structure."
    )


with tabs[4]:
    st.subheader("Evaluation")
    k_eval = st.slider("k for evaluation view", 2, 10, 4, key="k_eval")
    results = train_segmentation(df, k=k_eval)

    # PCA scatter
    fig_pca = px.scatter(
        results["df"], x="pca_1", y="pca_2",
        color=results["df"]["cluster"].astype(str),
        title=f"PCA 2D Projection — k={k_eval}",
        opacity=0.5,
        labels={"color": "Cluster"},
    )
    _apply(fig_pca)
    st.plotly_chart(fig_pca, use_container_width=True)

    # Cluster profile table
    st.markdown("**Cluster Profile**")
    profile = results["profile"].copy()
    profile.index.name = "Cluster"
    st.dataframe(profile, use_container_width=True)

    # Persona labels derived from centroids — not hardcoded by cluster ID
    personas = derive_personas(results["profile"])
    st.markdown("**Plain-English Personas** (derived from centroid values)")
    for c_id, (name, desc) in sorted(personas.items()):
        r = results["profile"].loc[c_id, "recency"]
        f = results["profile"].loc[c_id, "frequency"]
        m = results["profile"].loc[c_id, "monetary"]
        st.markdown(
            f"- **Cluster {c_id} — {name}** "
            f"(recency {r:.0f}d, freq {f:.1f}, monetary ${m:.0f}): {desc}"
        )


with tabs[5]:
    st.subheader("Live Inference")
    st.write("Enter your own RFM values to see which cluster you'd land in.")

    results4 = train_segmentation(df, k=4)

    col1, col2, col3 = st.columns(3)
    with col1:
        r_in = st.slider("Recency (days)", 1, 365, 30, key="r_inf")
    with col2:
        f_in = st.slider("Frequency (purchases)", 1, 50, 10, key="f_inf")
    with col3:
        m_in = st.slider("Monetary ($)", 10, 5000, 400, key="m_inf")

    X_user = np.array([[r_in, f_in, m_in]])
    cluster_id = results4["pipe"].predict(X_user)[0]

    personas4 = derive_personas(results4["profile"])
    persona_name, persona_desc = personas4[cluster_id]

    st.success(f"You belong to **Cluster {cluster_id} — {persona_name}**")
    st.write(persona_desc)

    # Show where user falls in profile
    profile4 = results4["profile"].copy()
    profile4.index.name = "Cluster"
    profile4["← You"] = ""
    profile4.loc[cluster_id, "← You"] = "★"
    st.dataframe(profile4, use_container_width=True)

    st.caption(
        "Why: the StandardScaler transforms your values using the mean/std "
        "learned from the training data, then KMeans assigns you to the nearest "
        "centroid in that scaled space."
    )
