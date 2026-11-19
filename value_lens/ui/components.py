"""HTML building blocks: page styles, header, score, margin-of-safety strip, test cards."""

from __future__ import annotations

from html import escape

from ..analysis.graham import FAIL, INFO, NA, PASS, Analysis, Check, money
from ..analysis.verdict import Verdict
from ..data.models import CompanyData
from . import theme as t

STATUS = {
    PASS: ("✓", "Pass", "pass"),
    FAIL: ("✕", "Fail", "fail"),
    NA: ("–", "Can't judge", "na"),
    INFO: ("i", "For reference", "info"),
}

CSS = f"""
<style>
/* Greys are mixed from the current text colour, so every panel follows the
   light or dark theme automatically. */
:root {{
  --vl-accent: {t.ACCENT};
  --vl-good: {t.GOOD};
  --vl-bad: {t.CRITICAL};
  --vl-fair: {t.FAIR};
  --vl-warn: {t.WARNING};
  --vl-s1: {t.SERIES_1};
  --vl-s2: {t.SERIES_2};
}}
.block-container {{ padding-top: 3.4rem; padding-bottom: 4rem; max-width: 1240px; }}
[data-testid="stHeader"] {{ background: transparent; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
[data-testid="stMain"] {{
  background-image: radial-gradient(900px 380px at 78% -120px, color-mix(in srgb, var(--vl-accent) 13%, transparent), transparent 70%);
  background-repeat: no-repeat;
}}

.gl-muted {{ color: color-mix(in srgb, currentColor 68%, transparent); }}
.gl-hero {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap;
  padding-bottom: 22px; border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent); margin-bottom: 22px; }}
.gl-name {{ font-family: {t.FONT_SERIF}; font-size: clamp(2.3rem, 4.4vw, 3.6rem); line-height: 1.02; margin: 0;
  font-weight: 400; color: inherit; }}
.gl-meta {{ color: color-mix(in srgb, currentColor 68%, transparent); font-size: 0.98rem; margin-top: 10px; }}
.gl-meta b {{ color: var(--text-color, inherit); font-weight: 600; }}
.gl-price {{ text-align: right; }}
.gl-price .num {{ font-family: {t.FONT_SERIF}; font-size: 3rem; line-height: 1; font-variant-numeric: tabular-nums; }}
.gl-price .sub {{ color: color-mix(in srgb, currentColor 62%, transparent); font-size: 0.9rem; margin-top: 6px; }}

.gl-panel, .gl-card, .gl-tile, .gl-loading {{
  background: color-mix(in srgb, currentColor 4%, transparent);
  /* White cards on the light theme, a faint lift on the dark one: the white's
     opacity falls as the text colour gets lighter. */
  background: oklch(from currentColor 1 0 0 / calc(0.94 - 0.96 * l));
  border: 1px solid color-mix(in srgb, currentColor 11%, transparent);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05), 0 8px 24px -12px rgba(15, 23, 42, 0.18);
}}
.gl-panel {{ border-radius: 18px; padding: 22px 24px; height: 100%; }}
.gl-panel h4 {{ font-family: {t.FONT_SANS}; font-size: 0.95rem; font-weight: 600; margin: 0 0 14px 0;
  color: color-mix(in srgb, currentColor 68%, transparent); }}
.gl-panel-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }}

.gl-score {{ display: flex; align-items: baseline; gap: 10px; }}
.gl-score .big {{ font-family: {t.FONT_SERIF}; font-size: 5.2rem; line-height: 0.9; color: var(--vl-accent); }}
.gl-score .of {{ font-family: {t.FONT_SERIF}; font-size: 2rem; color: color-mix(in srgb, currentColor 60%, transparent); }}
.gl-score-caption {{ font-size: 1rem; margin: 8px 0 16px 0; }}
.gl-pips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.gl-pip {{ width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; font-weight: 700;
  font-size: 0.95rem; border: 1.5px solid; cursor: default; }}
.gl-pip.pass {{ color: var(--vl-good); background: color-mix(in srgb, var(--vl-good) 13%, transparent); }}
.gl-pip.fail {{ color: var(--vl-bad); background: color-mix(in srgb, var(--vl-bad) 11%, transparent); }}
.gl-pip.na {{ color: color-mix(in srgb, currentColor 55%, transparent); background: color-mix(in srgb, currentColor 6%, transparent); }}
.gl-pip.warned {{ box-shadow: 0 0 0 3px color-mix(in srgb, var(--vl-warn) 45%, transparent); }}
.gl-key {{ color: color-mix(in srgb, currentColor 52%, transparent); font-size: 0.82rem; margin-top: 12px; }}

.gl-mos-head {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }}
.gl-mos-figure {{ font-family: {t.FONT_SERIF}; font-size: 2.6rem; line-height: 1; }}
.gl-mos-figure.good {{ color: var(--vl-good); }}
.gl-mos-figure.bad {{ color: var(--vl-bad); }}
.gl-mos-text {{ color: color-mix(in srgb, currentColor 68%, transparent); font-size: 0.92rem; max-width: 46ch; }}
.gl-track {{ position: relative; height: 150px; margin-top: 18px; }}
.gl-rail {{ position: absolute; left: 0; right: 0; top: 48px; height: 6px; border-radius: 3px;
  background: color-mix(in srgb, currentColor 13%, transparent); }}
.gl-gap {{ position: absolute; top: 46px; height: 10px; border-radius: 5px; }}
.gl-gap.good {{ background: color-mix(in srgb, var(--vl-good) 60%, transparent); }}
.gl-gap.bad {{ background: color-mix(in srgb, var(--vl-bad) 55%, transparent); }}
.gl-mark {{ position: absolute; top: 36px; width: 2px; height: 30px; transform: translateX(-1px); border-radius: 1px;
  background: currentColor; }}
.gl-mark.accent {{ background: var(--vl-accent); }}
.gl-mark.s2 {{ background: var(--vl-s2); }}
.gl-mark.dim {{ background: color-mix(in srgb, currentColor 45%, transparent); }}
.gl-label {{ position: absolute; transform: translateX(-50%); white-space: nowrap; font-size: 0.82rem; text-align: center;
  line-height: 1.25; color: color-mix(in srgb, currentColor 65%, transparent); }}
.gl-label b {{ display: block; font-weight: 600; font-size: 0.95rem; color: var(--text-color, currentColor);
  font-variant-numeric: tabular-nums; }}
.gl-label.above {{ top: 0; }}
.gl-label.row1 {{ top: 72px; }}
.gl-label.row2 {{ top: 112px; }}
.gl-label.edge-l {{ transform: none; text-align: left; }}
.gl-label.edge-r {{ transform: translateX(-100%); text-align: right; }}

.gl-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 14px; }}
.gl-card {{ border-radius: 16px; padding: 18px 20px; display: flex; flex-direction: column; gap: 9px; }}
.gl-card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
.gl-card-title {{ font-weight: 600; font-size: 1.04rem; }}
.gl-card-src {{ color: color-mix(in srgb, currentColor 50%, transparent); font-size: 0.8rem; margin-top: 2px; }}
.gl-pill, .gl-verdict {{ display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; font-weight: 600;
  white-space: nowrap; border: 1px solid; }}
.gl-pill {{ padding: 3px 10px 3px 8px; font-size: 0.8rem; }}
.gl-pill .ic, .gl-verdict .ic {{ font-weight: 700; }}
.gl-pill.pass, .gl-verdict.undervalued {{ color: var(--vl-good); border-color: color-mix(in srgb, var(--vl-good) 55%, transparent);
  background: color-mix(in srgb, var(--vl-good) 12%, transparent); }}
.gl-pill.fail, .gl-verdict.overvalued {{ color: var(--vl-bad); border-color: color-mix(in srgb, var(--vl-bad) 55%, transparent);
  background: color-mix(in srgb, var(--vl-bad) 10%, transparent); }}
.gl-verdict.fair {{ color: var(--vl-fair); border-color: color-mix(in srgb, var(--vl-fair) 55%, transparent);
  background: color-mix(in srgb, var(--vl-fair) 11%, transparent); }}
.gl-pill.na, .gl-pill.info, .gl-verdict.unknown {{ color: color-mix(in srgb, currentColor 68%, transparent);
  border-color: color-mix(in srgb, currentColor 18%, transparent); background: color-mix(in srgb, currentColor 5%, transparent); }}
.gl-verdict {{ padding: 4px 12px; font-size: 0.9rem; align-items: baseline; gap: 7px; }}
.gl-verdict .by {{ font-weight: 400; font-size: 0.8rem; opacity: 0.8; }}
.gl-card-value {{ font-size: 1rem; font-weight: 500; }}
.gl-card-rule {{ color: color-mix(in srgb, currentColor 52%, transparent); font-size: 0.86rem; }}
.gl-card-meaning {{ color: color-mix(in srgb, currentColor 72%, transparent); font-size: 0.92rem; line-height: 1.45; }}
.gl-years {{ display: flex; align-items: center; gap: 10px; color: color-mix(in srgb, currentColor 52%, transparent); font-size: 0.8rem; }}
.gl-years .bar {{ flex: 1; height: 4px; border-radius: 2px; overflow: hidden; max-width: 140px;
  background: color-mix(in srgb, currentColor 12%, transparent); }}
.gl-years .fill {{ height: 100%; background: var(--vl-s1); }}
.gl-years .fill.short {{ background: var(--vl-warn); }}

.gl-callout {{ display: flex; gap: 10px; align-items: flex-start; border-radius: 12px; padding: 10px 14px;
  font-size: 0.88rem; line-height: 1.45; border: 1px solid; }}
.gl-callout .ic {{ font-weight: 700; flex: none; width: 1.1em; text-align: center; }}
.gl-callout.warn {{ background: color-mix(in srgb, var(--vl-warn) 9%, transparent); border-color: color-mix(in srgb, var(--vl-warn) 40%, transparent); }}
.gl-callout.warn .ic {{ color: var(--vl-warn); }}
.gl-callout.note {{ background: color-mix(in srgb, var(--vl-s1) 8%, transparent); border-color: color-mix(in srgb, var(--vl-s1) 35%, transparent); }}
.gl-callout.note .ic {{ color: var(--vl-s1); }}
.gl-callout.error {{ background: color-mix(in srgb, var(--vl-bad) 8%, transparent); border-color: color-mix(in srgb, var(--vl-bad) 40%, transparent); }}
.gl-callout.error .ic {{ color: var(--vl-bad); }}
.gl-stack {{ display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }}

.gl-section {{ font-family: {t.FONT_SERIF}; font-size: 1.9rem; margin: 8px 0 4px 0; font-weight: 400; }}
.gl-section-sub {{ color: color-mix(in srgb, currentColor 68%, transparent); font-size: 0.95rem; margin-bottom: 16px; max-width: 72ch; }}
.gl-chart-title {{ font-weight: 600; font-size: 1rem; margin: 10px 0 -6px 2px; }}

.gl-tiles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 18px; }}
.gl-tiles.cols-4 {{ grid-template-columns: repeat(4, 1fr); }}
.gl-tile {{ border-radius: 14px; padding: 14px 16px; }}
.gl-tile .k {{ color: color-mix(in srgb, currentColor 68%, transparent); font-size: 0.84rem; }}
.gl-tile .v {{ font-family: {t.FONT_SERIF}; font-size: 2rem; line-height: 1.1; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.gl-tile .s {{ color: color-mix(in srgb, currentColor 52%, transparent); font-size: 0.8rem; margin-top: 2px; }}

.gl-loading {{ border-radius: 18px; padding: 26px 28px; margin: 6px 0 22px 0; }}
.gl-loading .title {{ font-family: {t.FONT_SERIF}; font-size: 1.9rem; line-height: 1.1; }}
.gl-loading .sub {{ color: color-mix(in srgb, currentColor 66%, transparent); margin-top: 6px; font-size: 0.95rem; }}
.gl-loading .bar {{ position: relative; height: 4px; border-radius: 2px; overflow: hidden; margin-top: 18px;
  background: color-mix(in srgb, currentColor 10%, transparent); }}
.gl-loading .bar::after {{ content: ""; position: absolute; top: 0; bottom: 0; width: 35%; border-radius: 2px;
  background: var(--vl-accent); animation: gl-slide 1.3s ease-in-out infinite; }}
.gl-skeleton {{ display: grid; grid-template-columns: 1fr 1.7fr; gap: 14px; margin-top: 18px; }}
.gl-skeleton div {{ height: 120px; border-radius: 14px; background: color-mix(in srgb, currentColor 6%, transparent); }}
@keyframes gl-slide {{ 0% {{ left: -35%; }} 100% {{ left: 100%; }} }}
@media (prefers-reduced-motion: reduce) {{ .gl-loading .bar::after {{ animation: none; left: 0; width: 100%; opacity: 0.5; }} }}

.gl-empty {{ padding: 8vh 0 4vh 0; max-width: 760px; }}
.gl-empty h1 {{ font-family: {t.FONT_SERIF}; font-size: clamp(2.6rem, 5.5vw, 4.4rem); line-height: 1.02;
  font-weight: 400; margin: 0 0 18px 0; }}
.gl-empty p {{ color: color-mix(in srgb, currentColor 70%, transparent); font-size: 1.08rem; line-height: 1.55; max-width: 60ch; }}
.gl-footer {{ color: color-mix(in srgb, currentColor 50%, transparent); font-size: 0.82rem; padding-top: 14px; margin-top: 36px;
  border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent); }}

@media (max-width: 720px) {{
  .block-container {{ padding-top: 4rem; }}
  .gl-tiles, .gl-tiles.cols-4 {{ grid-template-columns: repeat(2, 1fr); }}
  .gl-price {{ text-align: left; }}
  .gl-score .big {{ font-size: 4rem; }}
  .gl-skeleton {{ grid-template-columns: 1fr; }}
}}
</style>
"""


def _e(x) -> str:
    return escape(str(x))


def hero(cd: CompanyData) -> str:
    latest_fy = cd.annual.index.max()
    fy_text = f"fiscal year ending {latest_fy:%b %Y}" if latest_fy is not None else "no annual data"
    price = f"${cd.price:,.2f}" if cd.price is not None else "n/a"
    date = f"Close on {cd.price_date:%d %b %Y}" if cd.price_date is not None else ""
    source = "Fictional demo data" if cd.is_demo else "SEC EDGAR filings and Yahoo Finance prices"
    return f"""
<div class="gl-hero">
  <div>
    <h1 class="gl-name">{_e(cd.name)}</h1>
    <div class="gl-meta"><b>{_e(cd.ticker)}</b>, latest annual report for the {_e(fy_text)}. Source: {_e(source)}.</div>
  </div>
  <div class="gl-price"><div class="num">{_e(price)}</div><div class="sub">{_e(date)}</div></div>
</div>"""


def callouts(messages: list[str], kind: str = "note") -> str:
    if not messages:
        return ""
    icon = {"warn": "!", "note": "i", "error": "✕"}[kind]
    items = "".join(f'<div class="gl-callout {kind}"><span class="ic">{icon}</span><span>{_e(m)}</span></div>'
                    for m in messages)
    return f'<div class="gl-stack">{items}</div>'


def score_panel(a: Analysis) -> str:
    pips = []
    for c in a.checks:
        icon, word, cls = STATUS[c.status]
        warned = " warned" if c.warning else ""
        tip = f"{c.title}: {word}" + (" (limited data)" if c.warning else "")
        pips.append(f'<div class="gl-pip {cls}{warned}" title="{_e(tip)}" aria-label="{_e(tip)}">{icon}</div>')
    short = sum(1 for c in a.checks if c.warning)
    caption = "defensive investor tests passed"
    key = "✓ pass, ✕ fail, – can't judge. Hover a circle for the test name."
    if short:
        key += f" A ring marks the {short} test{'s' if short > 1 else ''} run on less history than Graham asks for."
    return f"""
<div class="gl-panel">
  <h4>Graham scorecard</h4>
  <div class="gl-score"><span class="big">{a.score}</span><span class="of">of {a.scored_total}</span></div>
  <div class="gl-score-caption">{caption}</div>
  <div class="gl-pips">{''.join(pips)}</div>
  <div class="gl-key">{_e(key)}</div>
</div>"""


def margin_panel(a: Analysis, vd: Verdict | None = None) -> str:
    v = a.valuation
    pill = verdict_pill(vd) if vd else ""
    if v.price is None or v.graham_number is None:
        why = ("The Graham Number needs positive average earnings and positive book value."
               if v.price is not None else "No current price found.")
        return f"""
<div class="gl-panel">
  <div class="gl-panel-top"><h4>Margin of safety</h4>{pill}</div>
  <div class="gl-mos-figure bad">Not measurable</div>
  <div class="gl-mos-text" style="margin-top:10px">{_e(why)} Graham would treat a stock without either as speculative.</div>
</div>"""

    mos = (v.graham_number - v.price) / v.graham_number * 100
    good = mos > 0
    cls = "good" if good else "bad"
    limit = "the most Graham's P/E and book-value limits allow"
    multiple = v.price / v.graham_number
    if good:
        figure, text = f"{mos:+.0f}%", f"The price is {mos:.0f}% below the Graham Number, {limit}."
    elif multiple < 2:
        figure, text = f"{mos:+.0f}%", f"The price is {multiple * 100 - 100:.0f}% above the Graham Number, {limit}."
    else:
        figure, text = f"{multiple:.1f}x", f"The price is {multiple:.1f} times the Graham Number, {limit}. No margin of safety."

    marks = [("Graham Number", v.graham_number, "accent")]
    if v.growth_value:
        marks.append(("Growth formula", v.growth_value, "s2"))
    if v.ncav_ps and v.ncav_ps > 0:
        marks.append(("Net-net (⅔ NCAV)", v.ncav_ps * 2 / 3, "dim"))
    # A position strip, not a bar chart, so it needn't start at zero.
    values = [v.price] + [m[1] for m in marks]
    lo, hi = min(values) * 0.75, max(values) * 1.12

    def pos(x: float) -> float:
        return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))

    def edge(p: float) -> str:
        return " edge-l" if p < 9 else (" edge-r" if p > 91 else "")

    p_price, p_gn = pos(v.price), pos(v.graham_number)
    left, width = min(p_price, p_gn), abs(p_price - p_gn)
    parts = [
        '<div class="gl-rail"></div>',
        f'<div class="gl-gap {cls}" style="left:{left:.2f}%;width:{width:.2f}%"></div>',
        f'<div class="gl-mark" style="left:{p_price:.2f}%"></div>',
        f'<div class="gl-label above{edge(p_price)}" style="left:{p_price:.2f}%"><b>${v.price:,.2f}</b>Price</div>',
    ]
    first_row: list[float] = []  # label positions already used on the first row
    for name, val, color in sorted(marks, key=lambda m: m[1]):
        p = pos(val)
        if any(abs(p - q) < 16 for q in first_row):
            row = "row2"
        else:
            row = "row1"
            first_row.append(p)
        parts.append(f'<div class="gl-mark {color}" style="left:{p:.2f}%"></div>')
        parts.append(f'<div class="gl-label {row}{edge(p)}" style="left:{p:.2f}%"><b>${val:,.2f}</b>{_e(name)}</div>')

    return f"""
<div class="gl-panel">
  <div class="gl-panel-top"><h4>Margin of safety</h4>{pill}</div>
  <div class="gl-mos-head">
    <div><div class="gl-mos-figure {cls}">{figure}</div></div>
    <div class="gl-mos-text">{_e(text)}</div>
  </div>
  <div class="gl-track">{''.join(parts)}</div>
</div>"""


def _years_meter(c: Check) -> str:
    if not c.years_needed:
        return ""
    have = c.years_used or 0
    pct = min(100, have / c.years_needed * 100)
    short = " short" if have < c.years_needed else ""
    return (f'<div class="gl-years"><span>{have} of {c.years_needed} years of data</span>'
            f'<span class="bar"><span class="fill{short}" style="display:block;width:{pct:.0f}%"></span></span></div>')


def check_card(c: Check) -> str:
    icon, word, cls = STATUS[c.status]
    warning = (f'<div class="gl-callout warn"><span class="ic">!</span><span>{_e(c.warning)}</span></div>'
               if c.warning else "")
    return f"""
<div class="gl-card">
  <div class="gl-card-top">
    <div><div class="gl-card-title">{_e(c.title)}</div><div class="gl-card-src">{_e(c.source)}</div></div>
    <span class="gl-pill {cls}"><span class="ic">{icon}</span>{word}</span>
  </div>
  <div class="gl-card-value">{_e(c.value)}</div>
  <div class="gl-card-rule">Rule: {_e(c.rule)}</div>
  <div class="gl-card-meaning">{_e(c.meaning)}</div>
  {_years_meter(c)}
  {warning}
</div>"""


def card_grid(checks: list[Check]) -> str:
    return f'<div class="gl-grid">{"".join(check_card(c) for c in checks)}</div>'


def loading(title: str, sub: str) -> str:
    return (f'<div class="gl-loading" role="status" aria-live="polite"><div class="title">{_e(title)}</div>'
            f'<div class="sub">{_e(sub)}</div><div class="bar"></div>'
            f'<div class="gl-skeleton"><div></div><div></div></div></div>')


def chart_title(title: str) -> str:
    return f'<div class="gl-chart-title">{_e(title)}</div>'


def section(title: str, sub: str = "") -> str:
    sub_html = f'<div class="gl-section-sub">{_e(sub)}</div>' if sub else ""
    return f'<div class="gl-section">{_e(title)}</div>{sub_html}'


def page_header(title: str, sub: str) -> str:
    return (f'<div class="gl-hero"><div><h1 class="gl-name">{_e(title)}</h1>'
            f'<div class="gl-meta">{_e(sub)}</div></div></div>')


def tiles(items: list[tuple[str, str, str]], columns: int = 3) -> str:
    cells = "".join(f'<div class="gl-tile"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div>'
                    f'<div class="s">{_e(s)}</div></div>' for k, v, s in items)
    return f'<div class="gl-tiles cols-{columns}">{cells}</div>'


def verdict_pill(vd: Verdict) -> str:
    icon = {"undervalued": "✓", "fair": "≈", "overvalued": "▲", "unknown": "–"}[vd.code]
    return (f'<span class="gl-verdict {vd.code}"><span class="ic">{icon}</span>{_e(vd.label)}'
            f'<span class="by">by Graham\u2019s standard</span></span>')


def fmt_x(x: float | None, digits: int = 1, suffix: str = "") -> str:
    return "n/a" if x is None else f"{x:.{digits}f}{suffix}"


def fmt_usd(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.2f}"


EMPTY_STATE = """
<div class="gl-empty">
  <h1>Would Benjamin Graham buy this stock?</h1>
  <p>Enter a US ticker in the sidebar. Value Lens runs the seven tests from Chapter 14 of
  <i>The Intelligent Investor</i> on the company's SEC filings, shows how far the price sits from
  Graham's limits, and tells you when there isn't enough history to be sure.</p>
  <p>No connection or no SEC contact set up yet? Turn on demo mode to explore with two fictional companies.</p>
</div>"""

PORTFOLIO_EMPTY = """
<div class="gl-empty">
  <h1>See your whole portfolio through Graham's eyes.</h1>
  <p>Point Value Lens at the Consolidated_Portfolio_Positions.csv file from your other project: add its full path
  as PORTFOLIO_CSV in this project's .env file and restart the app. The file is only read, never copied.</p>
  <p>Or open a CSV from the sidebar, or switch on the demo portfolio to see how it works.</p>
</div>"""

FOOTER = """
<div class="gl-footer">For learning only. This is not financial advice, and the figures come with no warranty:
check anything important against the company's own filings. Fundamentals from SEC EDGAR; prices and dividends
from Yahoo Finance via yfinance, for personal use.</div>"""

__all__ = ["CSS", "hero", "callouts", "score_panel", "margin_panel", "card_grid", "section", "tiles",
           "fmt_x", "fmt_usd", "money", "EMPTY_STATE", "PORTFOLIO_EMPTY", "FOOTER", "page_header", "verdict_pill"]
