"""The shape of the data every other part of the app works with."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

# Columns of CompanyData.annual. Money is in the reporting currency (USD for
# US filers); per-share figures and share counts are adjusted for later
# stock splits so they line up with today's share price.
ANNUAL_COLUMNS = [
    "revenue",
    "net_income",
    "eps",
    "shares",
    "op_cash_flow",
    "capex",
    "dividends_paid",
    "buybacks",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "total_liabilities",
    "lt_debt",
    "equity",
    "goodwill",
    "intangibles",
]


def fiscal_year(end) -> int:
    """The year a fiscal period belongs to.

    Companies on 52/53-week years (Johnson & Johnson, for example) end their
    year on the Sunday nearest 31 December, which is sometimes 1-3 January.
    Those periods count for the year before, so FY2022 ends on 1 Jan 2023.
    """
    return (pd.Timestamp(end) - pd.Timedelta(days=15)).year


def fiscal_labels(index) -> list[str]:
    """One unique label per fiscal period, e.g. "2024". If a company changed
    its year-end and two periods fall in the same year, the month is added."""
    years = [str(fiscal_year(d)) for d in index]
    counts = Counter(years)
    return [f"{y} ({pd.Timestamp(d):%b})" if counts[y] > 1 else y for y, d in zip(years, index)]


class DataError(Exception):
    """A problem the user can act on (bad ticker, missing contact email, ...)."""


@dataclass
class CompanyData:
    ticker: str
    name: str
    currency: str
    annual: pd.DataFrame  # index: fiscal year-end dates, columns: ANNUAL_COLUMNS
    prices: pd.Series  # daily close, split-adjusted
    dividends: pd.Series  # cash dividend per share on each pay date, split-adjusted
    splits: pd.Series  # split ratio on each split date (4.0 means 4-for-1)
    first_trade: pd.Timestamp | None
    shares_outstanding: float | None = None  # latest count, split-adjusted
    sources: dict[str, str] = field(default_factory=dict)  # column -> XBRL tag used
    notes: list[str] = field(default_factory=list)
    is_demo: bool = False

    @property
    def price(self) -> float | None:
        return float(self.prices.iloc[-1]) if len(self.prices) else None

    @property
    def price_date(self) -> pd.Timestamp | None:
        return self.prices.index[-1] if len(self.prices) else None
