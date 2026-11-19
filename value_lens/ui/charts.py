"""Plotly charts, all sharing one quiet style so the numbers stay in front."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from . import theme as t

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def _style(fig: go.Figure, title: str, height: int = 330, y_title: str | None = None, legend: bool = True) -> go.Figure:
    # The title is drawn by the page in HTML (it follows the light/dark theme);
    # it travels with the figure in layout.meta.
    fig.update_layout(
        meta={"title": title},
        height=height,
        margin=dict(l=8, r=12, t=40 if legend else 16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=t.FONT_SANS, size=12.5, color=t.AXIS),
        showlegend=legend,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom",
                    font=dict(color=t.LABEL, size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=t.HOVER_BG, bordercolor=t.HOVER_BG, font=dict(family=t.FONT_SANS, color=t.HOVER_INK, size=13)),
        bargap=0.38,
        bargroupgap=0.12,
        barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, linecolor=t.LINE, tickcolor=t.LINE, ticks="outside",
                     tickfont=dict(color=t.AXIS), fixedrange=True)
    fig.update_yaxes(gridcolor=t.GRID, zeroline=True, zerolinecolor=t.LINE, zerolinewidth=1,
                     tickfont=dict(color=t.AXIS), title=dict(text=y_title, font=dict(color=t.AXIS, size=12)),
                     fixedrange=True)
    return fig


def _empty(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=t.AXIS, size=13), x=0.5, y=0.5,
                       xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, title, height=220, legend=False)


def _hline(fig: go.Figure, y: float, label: str, dash: str = "dash", color: str = t.AXIS) -> None:
    fig.add_hline(y=y, line=dict(color=color, width=1.25, dash=dash),
                  annotation=dict(text=label, font=dict(color=t.LABEL, size=11.5), xanchor="left", x=0,
                                  yanchor="bottom"),
                  annotation_position="top left")


def eps_chart(annual: pd.DataFrame) -> go.Figure:
    eps = annual["eps"].dropna()
    title = "Earnings per share by fiscal year"
    if eps.empty:
        return _empty(title, "No earnings history found")
    years = [str(d.year) for d in eps.index]
    fig = go.Figure()
    pos = eps.where(eps > 0)
    neg = eps.where(eps <= 0)
    fig.add_bar(x=years, y=pos, name="Profit year", marker_color=t.SERIES_1,
                hovertemplate="FY%{x}: $%{y:.2f} per share<extra></extra>")
    if neg.notna().any():
        fig.add_bar(x=years, y=neg, name="Loss year", marker_color=t.CRITICAL,
                    hovertemplate="FY%{x}: loss of $%{y:.2f} per share<extra></extra>")
    if len(eps) >= 3:
        avg = eps.rolling(3).mean()
        fig.add_scatter(x=years, y=avg, name="3-year average", mode="lines", line=dict(color=t.SERIES_2, width=2),
                        hovertemplate="3-year average to FY%{x}: $%{y:.2f}<extra></extra>")
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(type="category")
    return _style(fig, title, y_title="USD per share")


def pe_chart(history: pd.DataFrame, current_pe: float | None, price_date: pd.Timestamp | None) -> go.Figure:
    title = "P/E at each fiscal year end"
    h = history.dropna(subset=["pe"]) if not history.empty else history
    if h.empty:
        return _empty(title, "Needs profitable years to show a P/E")
    x = [d.strftime("%Y-%m-%d") for d in h.index]
    fig = go.Figure()
    fig.add_scatter(x=x, y=h["pe"], mode="lines+markers", name="P/E", line=dict(color=t.SERIES_1, width=2),
                    marker=dict(size=8, color=t.SERIES_1, line=dict(width=0)),
                    customdata=h[["price", "eps"]].values,
                    hovertemplate="%{x|%b %Y}: P/E %{y:.1f}<br>Price $%{customdata[0]:.2f} / EPS $%{customdata[1]:.2f}<extra></extra>")
    if current_pe and price_date is not None:
        fig.add_scatter(x=[price_date.strftime("%Y-%m-%d")], y=[current_pe], mode="markers+text", name="Today",
                        marker=dict(size=12, color=t.ACCENT, line=dict(width=0)),
                        text=[f"Today {current_pe:.1f}"], textposition="bottom center",
                        textfont=dict(color=t.ACCENT, size=12.5),
                        hovertemplate="Today: P/E %{y:.1f} on latest annual EPS<extra></extra>")
    _hline(fig, 15, "Graham's limit: 15")
    median = float(h["pe"].median())
    _hline(fig, median, f"Median {median:.1f}", dash="dot", color=t.LINE)
    fig.update_xaxes(type="date")
    return _style(fig, title, y_title="Price / earnings", legend=False)


def revenue_fcf_chart(annual: pd.DataFrame) -> go.Figure:
    title = "Revenue and free cash flow"
    rev = annual["revenue"]
    fcf = annual["op_cash_flow"] - annual["capex"].fillna(0)
    if rev.dropna().empty and fcf.dropna().empty:
        return _empty(title, "No revenue or cash-flow data found")
    years = [str(d.year) for d in annual.index]
    fig = go.Figure()
    fig.add_bar(x=years, y=rev / 1e9, name="Revenue", marker_color=t.SERIES_1,
                hovertemplate="FY%{x} revenue: $%{y:.2f} B<extra></extra>")
    fig.add_bar(x=years, y=fcf / 1e9, name="Free cash flow (operating cash flow minus capex)", marker_color=t.SERIES_2,
                hovertemplate="FY%{x} free cash flow: $%{y:.2f} B<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category")
    return _style(fig, title, y_title="USD billions")


def debt_chart(annual: pd.DataFrame) -> go.Figure:
    title = "Long-term debt against net current assets"
    nca = annual["current_assets"] - annual["current_liabilities"]
    debt = annual["lt_debt"]
    if nca.dropna().empty:
        return _empty(title, "No current assets or liabilities reported (common for banks and insurers)")
    years = [str(d.year) for d in annual.index]
    fig = go.Figure()
    fig.add_bar(x=years, y=nca / 1e9, name="Net current assets", marker_color=t.SERIES_1,
                hovertemplate="FY%{x} net current assets: $%{y:.2f} B<extra></extra>")
    fig.add_bar(x=years, y=debt / 1e9, name="Long-term debt", marker_color=t.SERIES_2,
                hovertemplate="FY%{x} long-term debt: $%{y:.2f} B<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category")
    return _style(fig, title, y_title="USD billions")


def current_ratio_chart(annual: pd.DataFrame) -> go.Figure:
    title = "Current ratio (current assets / current liabilities)"
    ratio = (annual["current_assets"] / annual["current_liabilities"]).dropna()
    if ratio.empty:
        return _empty(title, "No current assets or liabilities reported")
    years = [str(d.year) for d in ratio.index]
    fig = go.Figure()
    fig.add_scatter(x=years, y=ratio, mode="lines+markers", name="Current ratio", line=dict(color=t.SERIES_1, width=2),
                    marker=dict(size=8, color=t.SERIES_1, line=dict(width=0)),
                    hovertemplate="FY%{x}: %{y:.2f}<extra></extra>")
    _hline(fig, 2.0, "Graham's minimum: 2.0")
    fig.update_yaxes(rangemode="tozero")
    fig.update_xaxes(type="category")
    return _style(fig, title, legend=False)


def dividends_chart(by_year: pd.Series, today: pd.Timestamp) -> go.Figure:
    title = "Dividends per share by calendar year"
    if by_year is None or by_year.empty:
        return _empty(title, "No dividends on record")
    years = [str(y) for y in by_year.index]
    partial = [y == today.year for y in by_year.index]
    fig = go.Figure()
    fig.add_bar(x=years, y=by_year.values, name="Dividends per share",
                marker=dict(color=t.SERIES_1, opacity=[0.45 if p else 1.0 for p in partial]),
                customdata=["so far this year" if p else "full year" for p in partial],
                hovertemplate="%{x}: $%{y:.2f} per share (%{customdata})<extra></extra>")
    return _style(fig, title, y_title="USD per share", legend=False)


def _log_ticks(lo: float, hi: float) -> list[float]:
    """1-2-5 ticks across the range, so a log axis reads in plain dollar amounts."""
    ticks, k = [], math.floor(math.log10(max(lo, 0.01)))
    while 10 ** k <= hi * 1.5:
        for m in (1, 2, 5):
            x = m * 10 ** k
            if lo * 0.8 <= x <= hi * 1.25:
                ticks.append(x)
        k += 1
    return ticks or [lo, hi]


def price_chart(prices: pd.Series, log_scale: bool) -> go.Figure:
    title = "Share price (adjusted for splits)"
    if prices is None or prices.empty:
        return _empty(title, "No price history found")
    # Weekly closes keep the chart light without losing the shape.
    weekly = prices.resample("W-FRI").last().dropna()
    fig = go.Figure()
    fig.add_scatter(x=weekly.index, y=weekly.values, mode="lines", name="Price", line=dict(color=t.SERIES_1, width=2),
                    fill="tozeroy" if not log_scale else None, fillcolor="rgba(57,135,229,0.08)",
                    hovertemplate="%{x|%d %b %Y}: $%{y:.2f}<extra></extra>")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(showspikes=True, spikecolor=t.AXIS, spikethickness=1, spikedash="dot", spikemode="across")
    if log_scale:
        fig.update_yaxes(type="log", tickvals=_log_ticks(float(weekly.min()), float(weekly.max())),
                         tickprefix="$", tickformat=",.0f")
    return _style(fig, title, y_title="USD", legend=False)


def _hbar(labels: list[str], values: list[float], colors: list[str], title: str, total: float) -> go.Figure:
    fig = go.Figure()
    text = [f"€{v:,.0f}  ({v / total * 100:.0f}%)" if total else f"€{v:,.0f}" for v in values]
    fig.add_bar(y=labels, x=values, orientation="h", marker_color=colors, text=text, textposition="outside",
                textfont=dict(color=t.LABEL, size=12.5), cliponaxis=False,
                hovertemplate="%{y}: €%{x:,.0f}<extra></extra>")
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)", tickfont=dict(color=t.LABEL, size=13),
                     zeroline=False)
    fig.update_xaxes(visible=False, range=[0, max(values) * 1.45 if values else 1])
    fig = _style(fig, title, height=30 + 46 * len(labels), legend=False)
    fig.update_layout(bargap=0.32, margin=dict(l=8, r=8, t=8, b=8))
    return fig


VERDICT_COLORS = {
    "Undervalued": t.GOOD,
    "Fairly valued": t.FAIR,
    "Overvalued": t.CRITICAL,
    "Can't value": t.NEUTRAL,
    "Not analysed": "rgba(138,149,168,0.45)",
}


def verdict_value_chart(by_verdict: dict[str, float]) -> go.Figure:
    title = "Portfolio value by verdict (Graham Number)"
    items = [(k, by_verdict[k]) for k in VERDICT_COLORS if by_verdict.get(k)]
    if not items:
        return _empty(title, "Nothing to show yet")
    total = sum(by_verdict.values())
    return _hbar([k for k, _ in items], [v for _, v in items], [VERDICT_COLORS[k] for k, _ in items], title, total)


def sector_value_chart(by_sector: dict[str, float], top: int = 8) -> go.Figure:
    title = "Portfolio value by sector"
    items = sorted(by_sector.items(), key=lambda kv: kv[1], reverse=True)
    if not items:
        return _empty(title, "No sectors in the file")
    if len(items) > top:
        rest = sum(v for _, v in items[top - 1:])
        items = items[: top - 1] + [("Other", rest)]
    total = sum(by_sector.values())
    return _hbar([k for k, _ in items], [v for _, v in items], [t.SERIES_1] * len(items), title, total)
