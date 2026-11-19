"""Combine SEC fundamentals and Yahoo prices into one CompanyData."""

from __future__ import annotations

import pandas as pd

from .. import config
from ..cache import DiskCache
from . import edgar, market
from .models import CompanyData, DataError


def load_company(ticker: str, user_agent: str, max_years: int = 20) -> CompanyData:
    ticker = edgar.normalize_ticker(ticker)
    if not ticker:
        raise DataError("Enter a ticker symbol, for example KO or JNJ.")

    cache = DiskCache(config.CACHE_DIR)
    client = edgar.EdgarClient(user_agent, cache)
    cik, sec_name = client.lookup(ticker)
    facts = client.company_facts(cik)
    values, filed, tags = edgar.parse_company_facts(facts)

    mkt = market.fetch_market(ticker, cache)
    annual = edgar.adjust_for_splits(values, filed, mkt.splits).tail(max_years)

    shares_out = None
    latest = edgar.latest_shares_outstanding(facts)
    if latest:
        shares_out = latest[0] * edgar.split_factor_after(latest[1], mkt.splits)

    notes: list[str] = []
    if annual.index.max() < pd.Timestamp.today() - pd.DateOffset(months=18):
        notes.append(
            f"The latest annual report found ends {annual.index.max():%b %Y}. "
            "The company may have stopped filing or changed form type."
        )
    if (mkt.currency or "USD") != "USD":
        notes.append(f"Prices are quoted in {mkt.currency} but the filings are in USD. Ratios may be off.")

    return CompanyData(
        ticker=ticker,
        name=mkt.name or sec_name,
        currency=mkt.currency or "USD",
        annual=annual,
        prices=mkt.prices,
        dividends=mkt.dividends,
        splits=mkt.splits,
        first_trade=mkt.prices.index[0] if len(mkt.prices) else None,
        shares_outstanding=shares_out,
        sources=tags,
        notes=notes,
    )
