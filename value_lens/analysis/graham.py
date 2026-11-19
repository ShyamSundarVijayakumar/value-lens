"""Benjamin Graham's tests from The Intelligent Investor (revised 1973 edition).

The seven scored tests are the defensive investor's criteria from Chapter 14.
Everything else (Chapter 5 P/E limits, Graham Number, net-net value, the
Chapter 11 growth formula, listing age) is shown for context but not scored.

When a test needs more years than the data covers, it is still calculated on
what exists and carries a warning, so you can judge how much to trust it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .. import config
from ..data.models import CompanyData

PASS, FAIL, NA, INFO = "pass", "fail", "na", "info"


@dataclass
class Check:
    key: str
    title: str
    source: str  # where in the book the rule comes from
    rule: str  # the threshold, in words
    value: str  # what this company actually shows
    status: str  # PASS / FAIL / NA
    meaning: str  # what the result implies
    years_used: int | None = None
    years_needed: int | None = None
    warning: str | None = None
    scored: bool = True


@dataclass
class Valuation:
    price: float | None = None
    market_cap: float | None = None
    eps_latest: float | None = None
    eps_avg3: float | None = None
    eps_avg7: float | None = None
    bvps: float | None = None
    tangible_bvps: float | None = None
    pe_latest: float | None = None
    pe_avg3: float | None = None
    pe_avg7: float | None = None
    pb: float | None = None
    graham_number: float | None = None
    ncav_ps: float | None = None
    growth_rate: float | None = None  # % per year, from past EPS
    growth_value: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    shareholder_yield: float | None = None


@dataclass
class Analysis:
    checks: list[Check]
    context: list[Check]
    valuation: Valuation
    pe_history: pd.DataFrame
    dividends_by_year: pd.Series
    years_available: int
    listing_years: float | None
    notes: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(c.status == PASS for c in self.checks)

    @property
    def scored_total(self) -> int:
        return len(self.checks)


# ---------------------------------------------------------------- helpers

def money(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e12:
        return f"{sign}${x / 1e12:.2f} T"
    if x >= 1e9:
        return f"{sign}${x / 1e9:.2f} B"
    if x >= 1e6:
        return f"{sign}${x / 1e6:.0f} M"
    return f"{sign}${x:,.2f}"


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def coverage_warning(have: int, need: int) -> str | None:
    if have >= need:
        return None
    return (
        f"Only {have} of the {need} years Graham asks for are available. "
        "The result uses the years that exist, so treat it as less reliable."
    )


def _latest_row(annual: pd.DataFrame) -> pd.Series:
    return annual.iloc[-1] if len(annual) else pd.Series(dtype="float64")


# ---------------------------------------------------------------- main

def analyze(cd: CompanyData, min_revenue: float = config.DEFAULT_MIN_REVENUE_USD) -> Analysis:
    annual = cd.annual.sort_index()
    eps = annual["eps"].dropna()
    latest = _latest_row(annual)
    fy = annual.index[-1].year if len(annual) else None
    price = cd.price
    today = cd.price_date or pd.Timestamp.today()

    v = Valuation(price=price)
    shares_now = _num(cd.shares_outstanding) or _num(latest.get("shares"))
    if price and shares_now:
        v.market_cap = price * shares_now

    v.eps_latest = _num(eps.iloc[-1]) if len(eps) else None
    v.eps_avg3 = _num(eps.tail(3).mean()) if len(eps) else None
    v.eps_avg7 = _num(eps.tail(7).mean()) if len(eps) else None
    equity = _num(latest.get("equity"))
    if equity is not None and shares_now:
        v.bvps = equity / shares_now
        intangible = (_num(latest.get("goodwill")) or 0.0) + (_num(latest.get("intangibles")) or 0.0)
        v.tangible_bvps = (equity - intangible) / shares_now
    if price:
        if v.eps_latest and v.eps_latest > 0:
            v.pe_latest = price / v.eps_latest
        if v.eps_avg3 and v.eps_avg3 > 0:
            v.pe_avg3 = price / v.eps_avg3
        if v.eps_avg7 and v.eps_avg7 > 0:
            v.pe_avg7 = price / v.eps_avg7
        if v.bvps and v.bvps > 0:
            v.pb = price / v.bvps
    if v.eps_avg3 and v.eps_avg3 > 0 and v.bvps and v.bvps > 0:
        # Graham Number: the highest price that still passes both the P/E 15
        # and P/B 1.5 limits combined (15 x 1.5 = 22.5).
        v.graham_number = math.sqrt(22.5 * v.eps_avg3 * v.bvps)

    checks = [
        _check_size(latest, fy, min_revenue),
        _check_financial_condition(latest, fy),
        _check_earnings_stability(eps),
        _check_dividend_record(cd, today),
        _check_earnings_growth(eps, v),
        _check_moderate_pe(v, len(eps)),
        _check_price_to_assets(v),
    ]

    listing_years = None
    if cd.first_trade is not None:
        listing_years = (today - cd.first_trade).days / 365.25

    context = [
        _check_chapter5_pe(v, len(eps)),
        _check_listing_age(listing_years, cd.first_trade),
        _check_net_net(latest, shares_now, price, v),
        _check_growth_formula(v),
        _check_shareholder_yield(latest, v, cd, today),
    ]

    pe_hist = _pe_history(annual, cd.prices)
    div_by_year = cd.dividends.groupby(cd.dividends.index.year).sum() if len(cd.dividends) else pd.Series(dtype="float64")

    return Analysis(
        checks=checks,
        context=context,
        valuation=v,
        pe_history=pe_hist,
        dividends_by_year=div_by_year,
        years_available=len(eps),
        listing_years=listing_years,
        notes=list(cd.notes),
    )


# ---------------------------------------------------------------- the seven tests (Ch. 14)

def _check_size(latest: pd.Series, fy: int | None, min_revenue: float) -> Check:
    rev = _num(latest.get("revenue"))
    rule = f"Annual sales of at least {money(min_revenue)} (Graham's $100 M in 1971 dollars, adjusted)"
    if rev is None:
        return Check("size", "Adequate size", "Ch. 14", rule, "Revenue not found in the filings", NA,
                     "Can't judge size without revenue. Check the income statement in the latest 10-K.")
    ok = rev >= min_revenue
    return Check(
        "size", "Adequate size", "Ch. 14", rule, f"{money(rev)} revenue in FY{fy}", PASS if ok else FAIL,
        "Big enough to absorb a bad year or two." if ok
        else "Smaller than Graham's cut-off. Small companies tend to swing harder in downturns.",
    )


def _check_financial_condition(latest: pd.Series, fy: int | None) -> Check:
    title, src = "Strong financial condition", "Ch. 14"
    rule = "Current assets at least 2x current liabilities, and long-term debt no more than net current assets"
    ca, cl, debt = _num(latest.get("current_assets")), _num(latest.get("current_liabilities")), _num(latest.get("lt_debt"))
    if ca is None or cl is None or cl <= 0:
        return Check("condition", title, src, rule, "No current assets or liabilities reported", NA,
                     "Usual for banks, insurers and some utilities. Graham judged those with different tests.")
    ratio = ca / cl
    nca = ca - cl
    warning = None
    if debt is None:
        debt_ok = True
        warning = "No long-term debt figure found in the filings, so only the current ratio was checked. Look at the balance sheet to confirm."
        debt_text = "debt not found"
    else:
        debt_ok = debt <= nca
        debt_text = f"long-term debt {money(debt)} vs net current assets {money(nca)}"
    ok = ratio >= 2 and debt_ok
    if ok:
        meaning = "Plenty of short-term assets to cover bills, and debt that working capital alone could repay."
    elif ratio < 2 and not debt_ok:
        meaning = "Thin cushion for short-term bills, and more long-term debt than working capital could repay."
    elif ratio < 2:
        meaning = "Short-term assets cover bills by less than Graham's 2-to-1 cushion."
    else:
        meaning = "Long-term debt is larger than working capital could repay."
    return Check("condition", title, src, rule, f"Current ratio {ratio:.2f}; {debt_text} (FY{fy})",
                 PASS if ok else FAIL, meaning, warning=warning)


def _check_earnings_stability(eps: pd.Series) -> Check:
    need = config.YEARS_EARNINGS_STABILITY
    window = eps.tail(need)
    n = len(window)
    rule = f"Positive earnings in each of the past {need} years"
    if n == 0:
        return Check("stability", "Earnings stability", "Ch. 14", rule, "No earnings history found", NA,
                     "Without earnings history this can't be judged.", 0, need)
    losses = [d.year for d, x in window.items() if x <= 0]
    ok = not losses
    value = f"Positive in {n - len(losses)} of {n} years"
    if losses:
        value += f"; losses in {', '.join(map(str, losses))}"
    meaning = ("Profitable through every year shown, good times and bad." if ok
               else "Losses in the period. Graham saw that as a sign the business is not yet dependable enough for a defensive investor.")
    return Check("stability", "Earnings stability", "Ch. 14", rule, value, PASS if ok else FAIL, meaning,
                 n, need, coverage_warning(n, need))


def dividend_streak(dividends: pd.Series, today: pd.Timestamp) -> int:
    """Consecutive calendar years with a dividend, counting back from now."""
    if dividends is None or dividends.empty:
        return 0
    years = set(dividends.index.year)
    y = today.year if today.year in years else today.year - 1
    streak = 0
    while y in years:
        streak += 1
        y -= 1
    return streak


def _check_dividend_record(cd: CompanyData, today: pd.Timestamp) -> Check:
    need = config.YEARS_DIVIDEND_RECORD
    rule = f"Dividends paid without a break for at least {need} years"
    streak = dividend_streak(cd.dividends, today)
    data_years = None
    if cd.first_trade is not None:
        data_years = today.year - cd.first_trade.year
    warning = None
    if streak and data_years is not None and streak >= data_years - 1 and data_years < need:
        warning = (f"Price and dividend data only start in {cd.first_trade.year}. The record may be longer; "
                   "check the company's investor-relations page.")
    if streak == 0:
        value = "No dividend in the last year" if len(cd.dividends) else "No dividends on record"
        meaning = ("No current dividend. Many younger or growth companies reinvest instead; Graham's defensive "
                   "investor would pass on them.")
        return Check("dividends", "Dividend record", "Ch. 14", rule, value, FAIL, meaning, 0, need, warning)
    ok = streak >= need
    paid_years = set(cd.dividends.index.year)
    latest_year = today.year if today.year in paid_years else today.year - 1
    value = f"Paid every year for {streak} years (since {latest_year - streak + 1})"
    meaning = ("A long unbroken record suggests real, cash-backed profits and steady management." if ok
               else "Shorter than Graham's 20-year record. The company may still be sound, but it hasn't proven it through as many cycles.")
    return Check("dividends", "Dividend record", "Ch. 14", rule, value, PASS if ok else FAIL, meaning,
                 min(streak, need), need, warning)


def _check_earnings_growth(eps: pd.Series, v: Valuation) -> Check:
    need = config.YEARS_EARNINGS_GROWTH
    window = eps.tail(need)
    n = len(window)
    rule = "EPS up at least one-third over 10 years, comparing 3-year averages at each end"
    if n < 4:
        return Check("growth", "Earnings growth", "Ch. 14", rule, f"Only {n} years of EPS", NA,
                     "Needs at least 4 years to compare two 3-year averages.", n, need, coverage_warning(n, need))
    start, end = float(window.head(3).mean()), float(window.tail(3).mean())
    span = n - 3  # years between the middles of the two 3-year windows
    if start > 0 and end > 0:
        v.growth_rate = ((end / start) ** (1 / span) - 1) * 100
    warning = coverage_warning(n, need)
    if n < 6:
        overlap = "The two 3-year windows overlap because there are fewer than 6 years."
        warning = f"{warning} {overlap}" if warning else overlap
    if start <= 0:
        value = f"Average EPS went from {start:.2f} to {end:.2f}"
        return Check("growth", "Earnings growth", "Ch. 14", rule, value, FAIL,
                     "The starting average was a loss, so growth can't be measured the way Graham intended.",
                     n, need, warning)
    change = end / start - 1
    ok = change >= 1 / 3
    value = f"{change * 100:+.0f}% (average EPS {start:.2f} to {end:.2f})"
    meaning = ("Earnings per share have grown enough to keep ahead of inflation and justify paying for the future." if ok
               else "Earnings per share have barely grown. Graham wanted at least a third more over a decade.")
    return Check("growth", "Earnings growth", "Ch. 14", rule, value, PASS if ok else FAIL, meaning, n, need, warning)


def _check_moderate_pe(v: Valuation, years: int) -> Check:
    rule = "Price no more than 15x average earnings of the past 3 years"
    warning = coverage_warning(years, 3)
    if v.eps_avg3 is None or v.price is None:
        return Check("pe", "Moderate P/E", "Ch. 14", rule, "Price or earnings missing", NA, "Can't be calculated.",
                     years, 3, warning)
    if v.eps_avg3 <= 0:
        return Check("pe", "Moderate P/E", "Ch. 14", rule, f"Average EPS is {v.eps_avg3:.2f} (a loss)", FAIL,
                     "With losses there are no earnings to pay a multiple of.", min(years, 3), 3, warning)
    ok = v.pe_avg3 <= 15
    meaning = ("You are paying a modest price for proven earnings." if ok
               else "The price assumes strong future growth. Graham warned that paying up for growth leaves little margin of safety.")
    return Check("pe", "Moderate P/E", "Ch. 14", rule, f"P/E {v.pe_avg3:.1f} on 3-year average EPS {v.eps_avg3:.2f}",
                 PASS if ok else FAIL, meaning, min(years, 3), 3, warning)


def _check_price_to_assets(v: Valuation) -> Check:
    rule = "Price no more than 1.5x book value, or P/E x P/B no more than 22.5"
    if v.bvps is None or v.price is None:
        return Check("pb", "Moderate price to assets", "Ch. 14", rule, "Book value missing", NA, "Can't be calculated.")
    if v.bvps <= 0:
        return Check("pb", "Moderate price to assets", "Ch. 14", rule, f"Book value per share {v.bvps:.2f} (negative)", FAIL,
                     "Liabilities exceed assets on the books, often after big buybacks. Graham's asset test can't be met.")
    product = v.pb * v.pe_avg3 if v.pe_avg3 else None
    ok = v.pb <= 1.5 or (product is not None and product <= 22.5)
    value = f"P/B {v.pb:.2f}"
    if product is not None:
        value += f"; P/E x P/B {product:.1f}"
    meaning = ("The price is backed by a reasonable amount of assets." if ok
               else "Most of the price rests on future earnings rather than assets you could point to today.")
    return Check("pb", "Moderate price to assets", "Ch. 14", rule, value, PASS if ok else FAIL, meaning)


# ---------------------------------------------------------------- context (not scored)

def _check_chapter5_pe(v: Valuation, years: int) -> Check:
    rule = "No more than 25x average earnings of the past 7 years, and no more than 20x the latest year"
    warning = coverage_warning(years, 7)
    if v.pe_avg7 is None or v.pe_latest is None:
        return Check("pe5", "Chapter 5 price limit", "Ch. 5", rule, "Needs positive earnings", NA,
                     "Losses in the period mean no P/E can be calculated.", min(years, 7), 7, warning, scored=False)
    ok = v.pe_avg7 <= 25 and v.pe_latest <= 20
    value = f"{v.pe_avg7:.1f}x the 7-year average; {v.pe_latest:.1f}x the latest year"
    if warning is None:
        warning = "Uses the latest fiscal year as a stand-in for the last twelve months."
    return Check("pe5", "Chapter 5 price limit", "Ch. 5", rule, value, PASS if ok else FAIL,
                 "Graham's looser limit for a defensive investor's stock list." if ok
                 else "Above even Graham's looser Chapter 5 limit.",
                 min(years, 7), 7, warning, scored=False)


def _check_listing_age(listing_years: float | None, first_trade: pd.Timestamp | None) -> Check:
    rule = f"Graham advised defensive investors to avoid new issues (listed under ~{config.RECENT_IPO_YEARS} years here)"
    if listing_years is None:
        return Check("ipo", "Listing age", "Ch. 6", rule, "Listing date unknown", NA, "No price history found.", scored=False)
    recent = listing_years < config.RECENT_IPO_YEARS
    return Check(
        "ipo", "Listing age", "Ch. 6", rule,
        f"Trading since {first_trade:%b %Y} ({listing_years:.1f} years)", FAIL if recent else PASS,
        "Recent listing. New issues tend to come to market when prices favour the sellers, and there's little public record to judge."
        if recent else "Long enough on the market to have a public track record.",
        scored=False,
    )


def _check_net_net(latest: pd.Series, shares: float | None, price: float | None, v: Valuation) -> Check:
    rule = "Bargain if the price is below two-thirds of net current asset value (current assets minus all liabilities)"
    ca, tl = _num(latest.get("current_assets")), _num(latest.get("total_liabilities"))
    if tl is None:
        ta, eq = _num(latest.get("total_assets")), _num(latest.get("equity"))
        tl = ta - eq if ta is not None and eq is not None else None
    if ca is None or tl is None or not shares or not price:
        return Check("netnet", "Net-net value", "Ch. 15", rule, "Not enough balance-sheet data", NA,
                     "Can't be calculated.", scored=False)
    v.ncav_ps = (ca - tl) / shares
    ok = v.ncav_ps > 0 and price < v.ncav_ps * 2 / 3
    value = f"Net current asset value {v.ncav_ps:.2f} per share; price {price:.2f}"
    return Check("netnet", "Net-net value", "Ch. 15", rule, value, PASS if ok else FAIL,
                 "A rare deep-value bargain by Graham's strictest test." if ok
                 else "Not a net-net. Few large companies are; this test mostly finds small, unloved firms.",
                 scored=False)


def _check_growth_formula(v: Valuation) -> Check:
    rule = "Value = normal EPS x (8.5 + 2 x expected growth %). Here past EPS growth stands in for expected growth"
    if v.growth_rate is None or v.eps_avg3 is None or v.eps_avg3 <= 0:
        return Check("growthval", "Growth-stock formula", "Ch. 11", rule, "Needs positive earnings and growth history", NA,
                     "Can't be calculated.", scored=False)
    g = max(v.growth_rate, 0.0)
    v.growth_value = v.eps_avg3 * (8.5 + 2 * g)
    ok = v.price is not None and v.price <= v.growth_value
    warning = None
    if g > 15:
        warning = "Past growth above 15% a year rarely lasts. The formula gets very sensitive here; treat the value with caution."
    return Check("growthval", "Growth-stock formula", "Ch. 11", rule,
                 f"Value {v.growth_value:.2f} using {g:.1f}% growth; price {v.price:.2f}", PASS if ok else FAIL,
                 "The price is below what the formula gives." if ok else "The price is above what the formula gives.",
                 warning=warning, scored=False)


def _check_shareholder_yield(latest: pd.Series, v: Valuation, cd: CompanyData, today: pd.Timestamp) -> Check:
    rule = "Not one of Graham's tests. Dividends plus buybacks as a share of market value, for companies that return cash by buying back shares"
    last12 = cd.dividends[cd.dividends.index > today - pd.DateOffset(years=1)].sum() if len(cd.dividends) else 0.0
    if v.price:
        v.dividend_yield = last12 / v.price * 100
    if v.eps_latest and v.eps_latest > 0 and len(cd.dividends):
        v.payout_ratio = last12 / v.eps_latest * 100
    paid, bought = _num(latest.get("dividends_paid")) or 0.0, _num(latest.get("buybacks")) or 0.0
    if not v.market_cap:
        return Check("shy", "Shareholder yield", "Modern", rule, "Market value unknown", NA, "Can't be calculated.", scored=False)
    v.shareholder_yield = (paid + bought) / v.market_cap * 100
    value = f"{v.shareholder_yield:.1f}% (dividend yield {v.dividend_yield or 0:.1f}%)"
    return Check("shy", "Shareholder yield", "Modern", rule, value, INFO,
                 "Shown for comparison with the dividend test. Buybacks only help owners when done below fair value.",
                 scored=False)


# ---------------------------------------------------------------- history for charts

def _pe_history(annual: pd.DataFrame, prices: pd.Series) -> pd.DataFrame:
    rows = []
    if prices is None or prices.empty:
        return pd.DataFrame(columns=["price", "eps", "pe", "bvps", "pb"])
    for end, r in annual.iterrows():
        if end < prices.index[0]:
            continue
        p = float(prices.asof(end))
        eps = _num(r.get("eps"))
        shares = _num(r.get("shares"))
        eq = _num(r.get("equity"))
        bvps = eq / shares if eq is not None and shares else None
        rows.append({
            "date": end,
            "price": p,
            "eps": eps,
            "pe": p / eps if eps and eps > 0 else None,
            "bvps": bvps,
            "pb": p / bvps if bvps and bvps > 0 else None,
        })
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=["price", "eps", "pe", "bvps", "pb"])
