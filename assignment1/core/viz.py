"""Shared Plotly theme and helper chart functions."""

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

PALETTE = px.colors.qualitative.Set2
BG = "#0e1117"
GRID = "#2a2a3a"
TEXT = "#fafafa"

LAYOUT_BASE = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG,
    font=dict(color=TEXT, family="Inter, sans-serif", size=13),
    margin=dict(l=50, r=30, t=50, b=50),
    colorway=PALETTE,
)


def _apply(fig: go.Figure) -> go.Figure:
    fig.update_layout(**LAYOUT_BASE)
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def scatter(df, x, y, color=None, title="", trendline=False, labels=None):
    kwargs = dict(data_frame=df, x=x, y=y, title=title, opacity=0.6,
                  labels=labels or {})
    if color:
        kwargs["color"] = color
    if trendline:
        kwargs["trendline"] = "ols"
    fig = px.scatter(**kwargs)
    return _apply(fig)


def bar(df, x, y, title="", labels=None):
    fig = px.bar(df, x=x, y=y, title=title, labels=labels or {})
    return _apply(fig)


def heatmap(z, x_labels, y_labels, title="", colorscale="Viridis"):
    fig = go.Figure(go.Heatmap(
        z=z, x=x_labels, y=y_labels,
        colorscale=colorscale, showscale=True,
    ))
    fig.update_layout(title=title, **LAYOUT_BASE)
    return fig


def line(df, x, y, color=None, title="", labels=None):
    kwargs = dict(data_frame=df, x=x, y=y, title=title, labels=labels or {})
    if color:
        kwargs["color"] = color
    fig = px.line(**kwargs)
    return _apply(fig)


def histogram(series, title="", xaxis_title=""):
    fig = px.histogram(series, title=title, nbins=40)
    fig.update_layout(xaxis_title=xaxis_title, **LAYOUT_BASE)
    return _apply(fig)


def map_two_points(lat1, lon1, lat2, lon2):
    fig = go.Figure()
    fig.add_trace(go.Scattermap(
        lat=[lat1, lat2], lon=[lon1, lon2],
        mode="markers+lines",
        marker=dict(size=[14, 14], color=["#2ecc71", "#e74c3c"]),
        text=["Pickup", "Dropoff"],
    ))
    fig.update_layout(
        map=dict(
            style="carto-darkmatter",
            center=dict(lat=(lat1 + lat2) / 2, lon=(lon1 + lon2) / 2),
            zoom=11,
        ),
        height=400,
        margin=dict(l=0, r=0, t=30, b=0),
        **{k: v for k, v in LAYOUT_BASE.items() if k != "margin"},
    )
    return fig
