"""Two fictional companies for trying the app offline.

These numbers are invented. They exist so the app can be explored, tested and
screenshotted without an internet connection. They describe no real company.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .models import ANNUAL_COLUMNS, CompanyData

DEMO_TICKERS = {
    "DEMO": "Harbor Mill Industries (fictional)",
    "NEWCO": "Lumen Grid Robotics (fictional)",
}

# Fictional ISINs used by samples/demo_portfolio.csv. "ZZ" is not a real country code.
DEMO_ISINS = {
    "ZZDEMO000001": ("DEMO", "EQUITY"),
    "ZZNEWCO00002": ("NEWCO", "EQUITY"),
    "ZZEURO000003": ("NWM.DE", "EQUITY"),
    "ZZETF0000006": ("WEQ.DE", "ETF"),
}

TODAY = pd.Timestamp("2026-11-13")


def _price_path(start: str, end: pd.Timestamp, p0: float, p1: float, vol: float, seed: int) -> pd.Series:
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, vol, len(dates))
    walk = np.cumsum(steps)
    walk -= np.linspace(0, walk[-1], len(dates))  # pin the end point
    trend = np.linspace(np.log(p0), np.log(p1), len(dates))
    return pd.Series(np.round(np.exp(trend + walk), 2), index=dates)


def _annual(rows: dict[int, dict[str, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(f"{y}-12-31") for y in rows])
    df = pd.DataFrame(list(rows.values()), index=idx)
    return df.reindex(columns=ANNUAL_COLUMNS).astype("float64")


def _harbor_mill() -> CompanyData:
    years = range(2012, 2026)
    eps = [2.05, 2.18, 2.31, 2.40, 2.52, 2.71, 2.88, 3.02, 2.41, 2.95, 3.30, 3.58, 3.81, 4.02]
    revenue = [3.21, 3.36, 3.52, 3.60, 3.77, 4.02, 4.30, 4.46, 3.95, 4.61, 5.12, 5.48, 5.77, 6.04]
    shares = [412, 409, 405, 401, 398, 395, 391, 388, 386, 384, 381, 377, 374, 371]
    rows = {}
    for i, y in enumerate(years):
        sh = shares[i] * 1e6
        ni = eps[i] * sh
        rev = revenue[i] * 1e9
        ca = rev * 0.46
        cl = ca / (2.25 + 0.01 * i)
        equity = sh * (17.5 + 0.95 * i)
        rows[y] = {
            "revenue": rev,
            "net_income": ni,
            "eps": eps[i],
            "shares": sh,
            "op_cash_flow": ni * 1.32,
            "capex": rev * 0.045,
            "dividends_paid": ni * 0.42,
            "buybacks": ni * 0.18,
            "current_assets": ca,
            "current_liabilities": cl,
            "total_assets": equity * 1.9,
            "total_liabilities": equity * 0.9,
            "lt_debt": (ca - cl) * 0.62,
            "equity": equity,
            "goodwill": equity * 0.12,
            "intangibles": equity * 0.05,
        }
    annual = _annual(rows)

    prices = _price_path("2001-03-01", TODAY, 9.5, 57.8, 0.011, seed=7)
    pay_dates = pd.date_range("2001-03-15", TODAY, freq="QS-MAR") + pd.Timedelta(days=14)
    dps = np.round(np.linspace(0.07, 0.43, len(pay_dates)), 3)
    dividends = pd.Series(dps, index=pay_dates)
    splits = pd.Series([2.0], index=[pd.Timestamp("2015-06-01")])

    return CompanyData(
        ticker="DEMO",
        name=DEMO_TICKERS["DEMO"],
        currency="USD",
        annual=annual,
        prices=prices,
        dividends=dividends,
        splits=splits,
        first_trade=prices.index[0],
        shares_outstanding=368e6,
        sources={c: "demo data" for c in ANNUAL_COLUMNS},
        notes=["Fictional sample data for trying the app. It describes no real company."],
        is_demo=True,
    )


def _lumen_grid() -> CompanyData:
    rows = {
        2021: {"revenue": 0.21e9, "eps": -1.42},
        2022: {"revenue": 0.38e9, "eps": -0.96},
        2023: {"revenue": 0.71e9, "eps": -0.31},
        2024: {"revenue": 1.12e9, "eps": 0.44},
        2025: {"revenue": 1.69e9, "eps": 0.97},
    }
    for i, (y, r) in enumerate(rows.items()):
        sh = (180 + 12 * i) * 1e6
        r.update(
            shares=sh,
            net_income=r["eps"] * sh,
            op_cash_flow=r["revenue"] * (-0.12 + 0.07 * i),
            capex=r["revenue"] * 0.14,
            dividends_paid=0.0,
            buybacks=0.0,
            current_assets=r["revenue"] * 1.6,
            current_liabilities=r["revenue"] * 0.7,
            total_assets=r["revenue"] * 2.8,
            total_liabilities=r["revenue"] * 1.3,
            lt_debt=r["revenue"] * 0.35,
            equity=r["revenue"] * 1.5,
            goodwill=0.0,
            intangibles=r["revenue"] * 0.1,
        )
    annual = _annual(rows)
    prices = _price_path("2023-06-14", TODAY, 31.0, 88.4, 0.028, seed=11)
    return CompanyData(
        ticker="NEWCO",
        name=DEMO_TICKERS["NEWCO"],
        currency="USD",
        annual=annual,
        prices=prices,
        dividends=pd.Series(dtype="float64"),
        splits=pd.Series(dtype="float64"),
        first_trade=prices.index[0],
        shares_outstanding=231e6,
        sources={c: "demo data" for c in ANNUAL_COLUMNS},
        notes=["Fictional sample data for trying the app. It describes no real company."],
        is_demo=True,
    )


def load_demo(ticker: str) -> CompanyData:
    return _lumen_grid() if ticker.upper() == "NEWCO" else _harbor_mill()
