"""Things both pages need: settings that survive page switches, and cached loaders."""

from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st

from .. import config
from ..analysis import analyze
from ..analysis.verdict import verdict
from ..data import DataError
from ..data.demo import DEMO_TICKERS, load_demo
from ..data.loader import load_company


@dataclass
class Settings:
    user_agent: str
    min_revenue: float  # USD
    log_price: bool


def html(markup: str) -> None:
    """st.html, but skip empty strings (Streamlit raises an error for them)."""
    if markup and markup.strip():
        st.html(markup)


def show_chart(fig) -> None:
    """A Plotly chart with its title drawn in HTML, so the title follows the theme."""
    from . import charts, components

    meta = fig.layout.meta
    title = meta.get("title") if isinstance(meta, dict) else None
    if title:
        st.html(components.chart_title(title))
    st.plotly_chart(fig, width="stretch", config=charts.PLOTLY_CONFIG)


def _keep(name: str) -> None:
    # Widget values are dropped when you change page; copy them to plain keys.
    st.session_state[name] = st.session_state[f"_w_{name}"]


def settings_panel() -> Settings:
    ss = st.session_state
    ss.setdefault("user_agent", os.getenv("SEC_USER_AGENT", ""))
    ss.setdefault("min_rev_m", config.DEFAULT_MIN_REVENUE_USD // 1_000_000)
    ss.setdefault("log_price", True)
    for name in ("user_agent", "min_rev_m", "log_price"):
        ss.setdefault(f"_w_{name}", ss[name])  # refill after a page change
    with st.expander("Settings"):
        st.text_input("SEC contact (name and email)", key="_w_user_agent",
                      on_change=_keep, args=("user_agent",),
                      help="SEC asks every user of its free API to identify themselves. Set it once in your .env file.")
        st.number_input("Size test: smallest company to accept (yearly sales, USD millions)", min_value=0, step=50,
                        key="_w_min_rev_m", on_change=_keep, args=("min_rev_m",),
                        help="Graham's first test only accepts companies with enough yearly sales (revenue). "
                             "He used $100 million in 1971, which is about $800 million today. Lower it to "
                             "include smaller companies.")
        st.toggle("Price chart: show percentage moves evenly (log scale)", key="_w_log_price",
                  on_change=_keep, args=("log_price",),
                  help="On a log scale a rise from $10 to $20 looks as big as $100 to $200, since both are +100%. "
                       "Best for long histories. Turn off to see plain dollar amounts.")
    st.caption("Light or dark look: open the ⋮ menu at the top right.")
    return Settings(ss["user_agent"], ss["min_rev_m"] * 1_000_000, ss["log_price"])


@st.cache_data(ttl=3600, show_spinner=False)
def get_company(ticker: str, user_agent: str):
    return load_company(ticker, user_agent)


def load(ticker: str, demo: bool, user_agent: str):
    return load_demo(ticker) if demo else get_company(ticker, user_agent)


@st.cache_data(ttl=3600, show_spinner=False)
def summarize(ticker: str, demo: bool, user_agent: str, min_revenue: float) -> dict:
    """Score and verdict for one ticker, for the portfolio table."""
    try:
        cd = load(ticker, demo, user_agent)
    except DataError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # one bad holding mustn't break the whole table
        return {"error": f"{exc.__class__.__name__}: {exc}"}
    a = analyze(cd, min_revenue=min_revenue)
    vd = verdict(a.valuation)
    return {
        "error": None,
        "name": cd.name,
        "score": a.score,
        "total": a.scored_total,
        "short_history": sum(1 for c in a.checks if c.warning),
        "verdict": vd.code,
        "verdict_label": vd.label,
        "ratio": vd.ratio,
        "currency": cd.currency,
    }


def is_demo_ticker(ticker: str) -> bool:
    return ticker.upper() in DEMO_TICKERS
