"""The single-stock page: scorecard, verdict, margin of safety and charts."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config
from ..analysis import analyze
from ..analysis.verdict import verdict
from ..data import DataError
from ..data.demo import DEMO_TICKERS
from ..data.models import fiscal_labels
from . import charts
from . import components as ui
from .shared import _keep, html, load, settings_panel, show_chart


def _apply_open_request() -> None:
    """The portfolio page asks to open a holding by leaving a note in session state."""
    ss = st.session_state
    req = ss.pop("open_ticker", None)
    if not req:
        return
    ticker, demo = req
    ss["demo_on"] = ss["_w_demo_on"] = demo
    if demo:
        ss["demo_ticker"] = ss["_w_demo_ticker"] = ticker
    else:
        ss["active"] = ss["_w_typed"] = ticker


def render() -> None:
    from .pages import PORTFOLIO  # imported here to avoid a circular import

    ss = st.session_state
    params = st.query_params
    # Plain keys (not widget keys) so choices survive switching pages.
    ss.setdefault("demo_on", params.get("demo") == "1")
    ss.setdefault("demo_ticker", params.get("t", "").upper() if params.get("t", "").upper() in DEMO_TICKERS else "DEMO")
    ss.setdefault("active", "" if ss["demo_on"] else params.get("t", ""))
    _apply_open_request()
    # Widgets read their starting value from these keys. Streamlit forgets
    # widget values when you change page, so they're refilled from the plain keys.
    ss.setdefault("_w_demo_on", ss["demo_on"])
    ss.setdefault("_w_demo_ticker", ss["demo_ticker"])
    ss.setdefault("_w_typed", ss["active"])

    with st.sidebar:
        st.caption("Benjamin Graham's tests and a plain verdict on value, using today's numbers.")
        demo = st.toggle("Demo mode", key="_w_demo_on", on_change=_keep, args=("demo_on",),
                         help="Two fictional companies so you can explore without an internet connection.")
        if demo:
            options = list(DEMO_TICKERS)
            active = st.selectbox("Sample company", options, key="_w_demo_ticker", on_change=_keep,
                                  args=("demo_ticker",),
                                  format_func=lambda k: DEMO_TICKERS[k])
        else:
            with st.form("lookup", border=False):
                # A fixed key keeps this the same box between searches. Without it,
                # Streamlit rebuilt the box after each search and lost the next entry.
                typed = st.text_input("US ticker", key="_w_typed", placeholder="For example KO, JNJ or MSFT")
                if st.form_submit_button("Analyze", type="primary", width="stretch"):
                    ss["active"] = typed.strip()
                    ss["from_portfolio"] = False
            active = ss["active"]
        settings = settings_panel()
        st.caption("For learning only. Not financial advice.")

    if ss.get("from_portfolio"):
        st.page_link(PORTFOLIO, label="Back to My portfolio")

    if not active:
        html(ui.EMPTY_STATE)
        return

    holder = st.empty()
    if not demo:
        holder.html(ui.loading(
            f"Fetching {active.upper()}",
            "Reading annual reports from SEC EDGAR and prices from Yahoo Finance. The first look at a company takes "
            "a few seconds; after that it comes from the local cache."))
    try:
        cd = load(active, demo, settings.user_agent)
    except DataError as exc:
        holder.empty()
        html(ui.callouts([str(exc)], "error"))
        return
    except Exception as exc:  # keep the app usable and the message readable
        holder.empty()
        html(ui.callouts([f"Something went wrong while loading {active.upper()}: {exc}"], "error"))
        return
    holder.empty()

    a = analyze(cd, min_revenue=settings.min_revenue)
    v = a.valuation
    vd = verdict(v)
    today = cd.price_date or pd.Timestamp.today()

    html(ui.hero(cd))
    html(ui.callouts(a.notes, "note"))
    if a.years_available < config.YEARS_EARNINGS_STABILITY:
        html(ui.callouts([
            f"Only {a.years_available} years of annual figures are available. Graham's tests want 10 (20 for dividends). "
            "Every test still runs on the years that exist; each card shows how many it used."], "warn"))

    left, right = st.columns([1, 1.7], gap="medium")
    with left:
        html(ui.score_panel(a))
    with right:
        html(ui.margin_panel(a, vd))

    st.write("")
    tab_score, tab_value, tab_earn, tab_bal, tab_div, tab_data = st.tabs(
        ["Scorecard", "Valuation", "Earnings", "Balance sheet", "Dividends and price", "Data"])

    with tab_score:
        html(ui.section("The defensive investor's seven tests",
                           "From Chapter 14. A stock that passes all seven is, in Graham's view, safe enough for an "
                           "investor who doesn't want to spend much time on research."))
        html(ui.card_grid(a.checks))
        html(ui.section("Other checks from the book", "Shown for context. They don't count toward the score."))
        html(ui.card_grid(a.context))

    with tab_value:
        html(ui.section("What the price implies"))
        html(ui.tiles([
            ("P/E on 3-year average EPS", ui.fmt_x(v.pe_avg3), "Graham's limit: 15"),
            ("P/E on latest annual EPS", ui.fmt_x(v.pe_latest), "Chapter 5 limit: 20"),
            ("Price to book", ui.fmt_x(v.pb, 2), "Graham's limit: 1.5"),
            ("Graham Number", ui.fmt_usd(v.graham_number), "Highest price passing both limits"),
            ("Growth-formula value", ui.fmt_usd(v.growth_value),
             f"At {v.growth_rate:.1f}% past growth" if v.growth_rate is not None else "Needs growth history"),
            ("Dividend yield", ui.fmt_x(v.dividend_yield, 1, "%"), "Last 12 months"),
        ]))
        show_chart(charts.pe_chart(a.pe_history, v.pe_latest, cd.price_date))
        st.caption("P/E here uses each year's price at fiscal year end divided by that year's EPS. "
                   "The median shows what has been normal for this stock.")

    with tab_earn:
        show_chart(charts.eps_chart(cd.annual))
        show_chart(charts.revenue_fcf_chart(cd.annual))

    with tab_bal:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            show_chart(charts.debt_chart(cd.annual))
        with c2:
            show_chart(charts.current_ratio_chart(cd.annual))
        st.caption("Graham wanted long-term debt below net current assets, and current assets at least twice "
                   "current liabilities.")

    with tab_div:
        show_chart(charts.dividends_chart(a.dividends_by_year, today))
        show_chart(charts.price_chart(cd.prices, settings.log_price))

    with tab_data:
        _data_tab(cd)

    html(ui.FOOTER)


LABELS = {
    "revenue": "Revenue", "net_income": "Net income", "eps": "EPS (diluted, USD)",
    "shares": "Diluted shares (millions)", "op_cash_flow": "Operating cash flow", "capex": "Capital spending",
    "dividends_paid": "Dividends paid", "buybacks": "Share buybacks", "current_assets": "Current assets",
    "current_liabilities": "Current liabilities", "total_assets": "Total assets",
    "total_liabilities": "Total liabilities", "lt_debt": "Long-term debt", "equity": "Shareholders' equity",
    "goodwill": "Goodwill", "intangibles": "Other intangibles",
}


def _data_tab(cd) -> None:
    html(ui.section("Annual figures", "Money in USD millions. EPS in USD per share, adjusted for later splits."))
    table = cd.annual.sort_index(ascending=False).copy()
    scale = [c for c in table.columns if c != "eps"]
    table[scale] = table[scale] / 1e6
    table.index = [f"FY{label}" for label in fiscal_labels(table.index)]
    table = table.rename(columns=LABELS).T
    st.dataframe(table.style.format("{:,.2f}", na_rep="n/a"), width="stretch", height=(len(table) + 1) * 35 + 3)
    st.download_button("Download as CSV", data=cd.annual.to_csv().encode("utf-8"),
                       file_name=f"{cd.ticker}_annual.csv", mime="text/csv")
    if cd.sources and not cd.is_demo:
        html(ui.section("Where each figure comes from", "The XBRL tag used for the latest year."))
        st.dataframe(pd.DataFrame(sorted(cd.sources.items()), columns=["Field", "XBRL tag"]),
                     hide_index=True, width="stretch")
