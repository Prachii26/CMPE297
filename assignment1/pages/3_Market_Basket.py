import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.data import make_basket_data, GROCERY_ITEMS
from core.models import apriori, recommend
from core.viz import _apply, LAYOUT_BASE

st.set_page_config(layout="wide", page_title="Market Basket Analysis")
st.title("Market Basket Analysis")
st.caption("Apriori association rules — implemented from scratch")

baskets = make_basket_data()
ALL_ITEMS = sorted(set(item for basket in baskets for item in basket))

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
        "A grocery retailer wants to know which products are bought together "
        "so they can improve shelf placement, cross-sell promotions, and "
        "recommendation emails. Association rule mining finds these patterns "
        "without needing any labels."
    )
    st.write(
        "Three metrics define a rule. Support is how often the combination "
        "appears at all (a floor on statistical reliability). Confidence is "
        "how often the consequent appears given the antecedent (directional "
        "strength). Lift is the ratio of observed co-occurrence to what you'd "
        "expect under independence — lift above 1 means the association is real."
    )
    st.write(
        "The planted rules in this dataset (e.g. milk+bread → butter) should "
        "surface with high lift. If they don't, the algorithm or thresholds are wrong."
    )


with tabs[1]:
    st.subheader("Data Understanding")
    st.write(
        f"{len(baskets):,} transactions, {len(ALL_ITEMS)} unique items. "
        "Basket size ranges from 2 to ~10 items. Four co-occurrence patterns "
        "were planted at 50-60% conditional probability."
    )

    item_counts = {}
    for basket in baskets:
        for item in basket:
            item_counts[item] = item_counts.get(item, 0) + 1

    freq_df = pd.DataFrame(
        {"item": list(item_counts.keys()), "count": list(item_counts.values())}
    ).sort_values("count", ascending=False)

    fig_freq = px.bar(
        freq_df.head(20), x="item", y="count",
        title="Top 20 Items by Frequency",
        labels={"count": "Basket Appearances"},
    )
    _apply(fig_freq)
    st.plotly_chart(fig_freq, use_container_width=True)

    col1, col2 = st.columns(2)
    col1.metric("Transactions", f"{len(baskets):,}")
    col2.metric("Unique Items", len(ALL_ITEMS))


with tabs[2]:
    st.subheader("Data Preparation")
    st.write(
        "Market basket data needs no scaling. Each transaction is a set of "
        "items. The Apriori algorithm works directly on these sets."
    )
    st.write(
        "The only choices are the three thresholds: min_support prunes rare "
        "itemsets early (cutting the search space dramatically), "
        "min_confidence filters weak rules, and min_lift removes rules that "
        "are just reflections of item popularity."
    )
    st.code(
        """# Candidate generation: union of pairs sharing k-2 items
for i in range(len(prev_keys)):
    for j in range(i+1, len(prev_keys)):
        union = prev_keys[i] | prev_keys[j]
        if len(union) == k:
            cnt = sum(1 for basket in item_sets if union.issubset(basket))
            if cnt / n >= min_support:
                candidates[union] = cnt / n""",
        language="python",
    )


with tabs[3]:
    st.subheader("Modeling")

    col1, col2, col3 = st.columns(3)
    with col1:
        ms = st.slider("min_support", 0.01, 0.15, 0.03, 0.005, key="ms_model")
    with col2:
        mc = st.slider("min_confidence", 0.1, 0.9, 0.3, 0.05, key="mc_model")
    with col3:
        ml = st.slider("min_lift", 1.0, 5.0, 1.0, 0.1, key="ml_model")

    with st.spinner("Running Apriori..."):
        freq_sets, rules_df = apriori(baskets, ms, mc, ml)

    # Itemset size distribution
    size_counts = {}
    for fs in freq_sets:
        sz = len(fs)
        size_counts[sz] = size_counts.get(sz, 0) + 1
    sz_df = pd.DataFrame({"size": list(size_counts.keys()),
                          "count": list(size_counts.values())}).sort_values("size")
    fig_sz = px.bar(sz_df, x="size", y="count",
                    title="Frequent Itemsets by Size",
                    labels={"size": "Itemset size", "count": "# itemsets"})
    _apply(fig_sz)
    st.plotly_chart(fig_sz, use_container_width=True)

    st.write(
        f"Found **{len(freq_sets)}** frequent itemsets and "
        f"**{len(rules_df)}** rules at these thresholds."
    )


with tabs[4]:
    st.subheader("Evaluation")

    # Reuse sliders from modeling tab via session state (default values)
    ms_e = st.slider("min_support", 0.01, 0.15, 0.03, 0.005, key="ms_eval")
    mc_e = st.slider("min_confidence", 0.1, 0.9, 0.3, 0.05, key="mc_eval")
    ml_e = st.slider("min_lift", 1.0, 5.0, 1.0, 0.1, key="ml_eval")

    with st.spinner("Running Apriori..."):
        _, rules_eval = apriori(baskets, ms_e, mc_e, ml_e)

    if rules_eval.empty:
        st.warning("No rules found at these thresholds. Lower min_support or min_confidence.")
    else:
        st.markdown("**Rules Table** (sortable — click column headers)")
        st.dataframe(rules_eval, use_container_width=True)

        # Antecedent vs Consequent scatter, sized by lift
        fig_net = px.scatter(
            rules_eval,
            x="antecedent", y="consequent",
            size="lift", color="confidence",
            title="Rule Map: antecedent → consequent (size = lift)",
            color_continuous_scale="Viridis",
            hover_data=["support", "confidence", "lift"],
        )
        _apply(fig_net)
        st.plotly_chart(fig_net, use_container_width=True)


with tabs[5]:
    st.subheader("Live Inference")
    st.write(
        "Select items already in the cart. The miner will suggest the top-3 "
        "items most likely to be added next."
    )

    cart = st.multiselect("Items in cart", options=ALL_ITEMS,
                          default=["milk", "bread"], key="cart_inf")

    ms_li = st.slider("min_support", 0.01, 0.15, 0.03, 0.005, key="ms_live")
    mc_li = st.slider("min_confidence", 0.1, 0.9, 0.25, 0.05, key="mc_live")
    ml_li = st.slider("min_lift", 1.0, 5.0, 1.0, 0.1, key="ml_live")

    if cart:
        with st.spinner("Mining rules..."):
            _, rules_live = apriori(baskets, ms_li, mc_li, ml_li)

        recs = recommend(rules_live, cart, top_n=3)
        if recs.empty:
            st.info("No recommendations found. Try lowering thresholds or adding more items to the cart.")
        else:
            st.markdown("**Top 3 recommended items:**")
            for _, row in recs.iterrows():
                st.markdown(
                    f"- **{row['consequent']}** "
                    f"(confidence={row['confidence']:.2f}, lift={row['lift']:.2f})"
                )
    else:
        st.info("Add at least one item to the cart.")
