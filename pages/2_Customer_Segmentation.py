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

PERSONA_LABELS = {
    0: ("Champions", "Bought recently, buy often, spend the most. Reward them."),
    1: ("At Risk", "Used to buy regularly but haven't lately. Send a win-back offer."),
    2: ("Dormant", "Haven't bought in a long time, low frequency, low spend. Hard to reactivate."),
    3: ("Loyal", "Buy regularly at decent spend. Nurture toward Champions."),
}

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

    # Persona labels (only for k=4 which matches our planted groups)
    if k_eval == 4:
        st.markdown("**Plain-English Personas**")
        for c_id, (name, desc) in PERSONA_LABELS.items():
            if c_id < k_eval:
                st.markdown(f"- **Cluster {c_id} — {name}**: {desc}")


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

    persona_name, persona_desc = PERSONA_LABELS.get(cluster_id, (f"Cluster {cluster_id}", ""))

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
