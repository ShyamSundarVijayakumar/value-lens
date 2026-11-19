"""My portfolio: every holding with its Graham score and verdict. Select a row to open it."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from .. import config
from ..data.demo import DEMO_TICKERS
from ..data.models import DataError
from ..portfolio import positions as pos
from ..portfolio.resolve import Resolver, read_overrides, write_overrides
from . import charts
from . import components as ui
from .shared import _keep, html, settings_panel, show_chart, summarize

VERDICT_TEXT = {
    "undervalued": "✓ Undervalued",
    "fair": "≈ Fairly valued",
    "overvalued": "▲ Overvalued",
    "unknown": "– Can't value",
}
VERDICT_CHART_LABEL = {
    "undervalued": "Undervalued",
    "fair": "Fairly valued",
    "overvalued": "Overvalued",
    "unknown": "Can't value",
}
VERDICT_COLOR = {  # mid-tones that read on light and dark tables
    "✓ Undervalued": "#16a34a",
    "≈ Fairly valued": "#3b82f6",
    "▲ Overvalued": "#dc2626",
}


def _source() -> tuple[bytes | None, str, bool]:
    """Return (file bytes, description, is_demo)."""
    ss = st.session_state
    env_path = os.getenv(config.PORTFOLIO_CSV_ENV, "").strip().strip('"')
    ss.setdefault("pf_demo", not env_path)
    ss.setdefault("_w_pf_demo", ss["pf_demo"])
    with st.sidebar:
        st.caption("Your holdings, each checked against Graham's tests.")
        demo = st.toggle("Demo portfolio", key="_w_pf_demo", on_change=_keep, args=("pf_demo",),
                         help="Six fictional holdings, including real estate, a bond and a fund.")
        upload = None
        if not demo:
            if env_path:
                st.caption(f"Reading {Path(env_path).name} from the path in your .env file.")
            upload = st.file_uploader("Open a different CSV", type=["csv"],
                                      help="The file stays on your computer; it isn't saved anywhere.")
    if demo:
        return (config.SAMPLES_DIR / "demo_portfolio.csv").read_bytes(), "the demo portfolio", True
    if upload is not None:
        return upload.getvalue(), upload.name, False
    if env_path:
        p = Path(env_path).expanduser()
        if not p.exists():
            raise DataError(f"PORTFOLIO_CSV in your .env points to {p}, but there's no file there.")
        return p.read_bytes(), p.name, False
    return None, "", False


def _build(df: pd.DataFrame, demo: bool, settings) -> pd.DataFrame:
    resolver = Resolver()
    demo_set = set(DEMO_TICKERS)
    rows = []
    box = st.empty()
    progress = st.empty()
    if not demo:
        box.html(ui.loading(
            f"Checking {len(df)} holdings",
            "Finding each ISIN's ticker, then reading SEC filings and Yahoo prices for every US stock. "
            "The first run can take a minute; after that it comes from the local cache."))
    for i, r in df.iterrows():
        if not demo:
            progress.progress(i / max(len(df), 1), text=f"{i + 1} of {len(df)}: {r['Security Name']}")
        res = None
        if pos.ISIN_RE.match(r["ISIN"]) and r["Sector"].strip().lower() not in pos.NOT_STOCK_SECTORS:
            res = resolver.resolve(r["ISIN"], demo=demo)
        kind, reason = pos.classify(r, res, demo_set)
        summary = None
        if kind == pos.STOCK_US:
            summary = summarize(res.ticker, demo, settings.user_agent, settings.min_revenue)
            if summary.get("error"):
                kind, reason = pos.UNRESOLVED, summary["error"]
        rows.append({
            "kind": kind,
            "reason": reason,
            "ticker": res.ticker if res else None,
            "ticker_source": res.source if res else "",
            "score": f"{summary['score']} of {summary['total']}" if summary and not summary.get("error") else "",
            "short_history": bool(summary and not summary.get("error") and summary["short_history"]),
            "verdict": summary["verdict"] if summary and not summary.get("error") else None,
            "ratio": summary["ratio"] if summary and not summary.get("error") else None,
        })
    box.empty()
    progress.empty()
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def render() -> None:
    from .pages import ANALYSIS  # imported here to avoid a circular import

    ss = st.session_state
    try:
        data, label, demo = _source()
    except DataError as exc:
        with st.sidebar:
            settings_panel()
        html(ui.callouts([str(exc)], "error"))
        return
    with st.sidebar:
        settings = settings_panel()
        if st.button("Refresh analysis", help="Fetch the latest filings and prices for every holding."):
            summarize.clear()
        st.caption("For learning only. Not financial advice.")

    if data is None:
        html(ui.PORTFOLIO_EMPTY)
        return

    try:
        df = pos.add_money_columns(pos.read_positions(data))
    except DataError as exc:
        html(ui.callouts([str(exc)], "error"))
        return
    if df.empty:
        html(ui.callouts(["The CSV has no rows with a security name."], "warn"))
        return

    html(ui.page_header("My portfolio", f"{len(df)} holdings from {label}, valued with the prices in the file."))
    table = _build(df, demo, settings).sort_values("Value (EUR)", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------ header and totals
    total = table["Value (EUR)"].sum()
    pnl = table["Unrealized PnL (EUR)"].sum()
    cost = total - pnl
    analysed = table[table["verdict"].notna()]
    analysed_value = analysed["Value (EUR)"].sum()
    under_value = analysed.loc[analysed["verdict"] == "undervalued", "Value (EUR)"].sum()

    html(ui.tiles([
        ("Portfolio value", f"€{total:,.0f}", "Quantity times current price"),
        ("Unrealized gain", f"{'+' if pnl >= 0 else '-'}€{abs(pnl):,.0f}", f"{pnl / cost * 100:+.1f}% on cost" if cost > 0 else ""),
        ("Analysed with Graham's tests", f"{len(analysed)} of {len(table)}",
         f"{analysed_value / total * 100:.0f}% of the value" if total else ""),
        ("Undervalued by Graham's standard", f"{under_value / analysed_value * 100:.0f}%" if analysed_value else "n/a",
         "Share of the analysed value"),
    ], columns=4))

    by_verdict: dict[str, float] = {}
    for _, r in table.iterrows():
        key = VERDICT_CHART_LABEL[r["verdict"]] if pd.notna(r["verdict"]) else "Not analysed"
        by_verdict[key] = by_verdict.get(key, 0.0) + (r["Value (EUR)"] or 0.0)
    sectors = table["Sector"].map(lambda x: (x.replace("_", " ").strip()[:1].upper() + x.replace("_", " ").strip()[1:])
                                  if x else "Unknown")
    by_sector = table.assign(Sector=sectors).groupby("Sector")["Value (EUR)"].sum()

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        show_chart(charts.verdict_value_chart(by_verdict))
    with c2:
        show_chart(charts.sector_value_chart(by_sector.to_dict()))

    # ------------------------------------------------------------ holdings table
    html(ui.section("Holdings", "Select a row to open the full analysis. Verdicts compare today's price with "
                                   "the Graham Number: within 15% either side counts as fairly valued."))
    view = pd.DataFrame({
        "Security": table["Security Name"],
        "Verdict": [VERDICT_TEXT[v] if pd.notna(v) else "○ Not analysed" for v in table["verdict"]],
        "Graham score": table["score"],
        "Price vs Graham Number": table["ratio"].map(lambda x: f"{x:.2f}x" if pd.notna(x) else ""),
        "Value": table["Value (EUR)"],
        "Weight": table["Weight"],
        "Gain": table["Unrealized PnL (EUR)"],
        "Gain %": table["PnL %"] * 100,
        "Ticker": table["ticker"].fillna("").astype(str),
        "Notes": [r if r else ("Fewer years of data than Graham asks for" if short else "")
                  for r, short in zip(table["reason"], table["short_history"])],
    })
    styled = view.style.map(lambda v: f"color: {VERDICT_COLOR.get(v, '#8a95a8')}; font-weight: 600",
                            subset=["Verdict"])
    styled = styled.map(lambda v: "" if pd.isna(v) else ("color: #16a34a" if v > 0 else "color: #dc2626" if v < 0 else ""),
                        subset=["Gain", "Gain %"])
    ss.setdefault("pf_nonce", 0)
    event = st.dataframe(
        styled,
        key=f"pf_table_{ss['pf_nonce']}",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
        height=min(35 * (len(view) + 1) + 3, 640),
        column_config={
            "Security": st.column_config.TextColumn(width="large", pinned=True),
            "Value": st.column_config.NumberColumn("Value (EUR)", format="€ %,.0f"),
            "Weight": st.column_config.ProgressColumn("Weight", format="%.1f%%", min_value=0,
                                                      max_value=float(max(view["Weight"].max(), 1))),
            "Gain": st.column_config.NumberColumn("Gain (EUR)", format="€ %+,.0f"),
            "Gain %": st.column_config.NumberColumn(format="%+.1f%%"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )
    picked = event.selection.rows if event and event.selection else []
    if picked:
        row = table.iloc[picked[0]]
        if row["kind"] == pos.STOCK_US and row["ticker"]:
            ss["open_ticker"] = (row["ticker"], demo)
            ss["from_portfolio"] = True
            ss["pf_nonce"] += 1  # a fresh table next time, with nothing selected
            st.switch_page(ANALYSIS)
        else:
            html(ui.callouts([f"{row['Security Name']}: {row['reason']}."], "note"))

    _fix_tickers(table, demo)
    html(ui.FOOTER)


def _fix_tickers(table: pd.DataFrame, demo: bool) -> None:
    if demo:
        return
    candidates = table[table["ISIN"].map(lambda s: bool(pos.ISIN_RE.match(s)))
                       & ~table["kind"].isin([pos.NOT_STOCK])]
    if candidates.empty:
        return
    with st.expander("Fix tickers"):
        st.caption("Tickers are found by searching Yahoo Finance for each ISIN. If one is wrong or missing, type the "
                   "right symbol here (US stocks without a suffix, e.g. KO). Saved to data/isin_tickers.csv, which "
                   "stays out of Git.")
        current = read_overrides()
        editor_df = pd.DataFrame({
            "ISIN": candidates["ISIN"],
            "Security": candidates["Security Name"],
            "Found": candidates["ticker"].fillna(""),
            "Your ticker": [current.get(i, "") for i in candidates["ISIN"]],
        })
        edited = st.data_editor(editor_df, hide_index=True, width="stretch", disabled=["ISIN", "Security", "Found"],
                                key="pf_fix")
        if st.button("Save tickers"):
            mapping = dict(current)
            for _, r in edited.iterrows():
                t = str(r["Your ticker"]).strip().upper()
                if t:
                    mapping[r["ISIN"]] = t
                else:
                    mapping.pop(r["ISIN"], None)
            write_overrides(mapping)
            summarize.clear()
            st.rerun()
