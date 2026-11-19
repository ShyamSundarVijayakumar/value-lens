"""Prices, dividends and splits from Yahoo Finance via the yfinance library.

yfinance is an unofficial client. Yahoo's data is for personal use only, so
this app downloads it on each user's own machine and never ships it in the repo.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .. import config
from ..cache import DiskCache
from .models import DataError


@dataclass
class MarketData:
    prices: pd.Series
    dividends: pd.Series
    splits: pd.Series
    name: str | None
    currency: str | None


def _series_to_json(s: pd.Series) -> dict[str, float]:
    return {d.strftime("%Y-%m-%d"): float(v) for d, v in s.items()}


def _series_from_json(d: dict[str, float]) -> pd.Series:
    if not d:
        return pd.Series(dtype="float64")
    s = pd.Series(d, dtype="float64")
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def fetch_market(ticker: str, cache: DiskCache) -> MarketData:
    key = f"yahoo:{ticker}"
    cached = cache.get(key, config.MARKET_MAX_AGE)
    if cached is None:
        cached = _download(ticker)
        cache.set(key, cached)
    return MarketData(
        prices=_series_from_json(cached["prices"]),
        dividends=_series_from_json(cached["dividends"]),
        splits=_series_from_json(cached["splits"]),
        name=cached.get("name"),
        currency=cached.get("currency"),
    )


def _download(ticker: str) -> dict:
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise DataError("yfinance isn't installed. Run: pip install -r requirements.txt") from exc

    t = yf.Ticker(ticker)
    try:
        hist = t.history(period="max", auto_adjust=False, actions=True)
    except Exception as exc:  # yfinance raises many different errors
        raise DataError(f"Couldn't download prices from Yahoo Finance ({exc.__class__.__name__}).") from exc
    if hist is None or hist.empty:
        raise DataError(f"Yahoo Finance returned no price history for {ticker}.")

    idx = hist.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    hist.index = idx.normalize()

    # "Close" is adjusted for splits but not for dividends: the price you'd
    # compare with split-adjusted EPS.
    prices = hist["Close"].dropna()
    dividends = hist["Dividends"] if "Dividends" in hist else pd.Series(dtype="float64")
    splits = hist["Stock Splits"] if "Stock Splits" in hist else pd.Series(dtype="float64")

    name = currency = None
    try:
        info = t.get_info()
        name = info.get("longName") or info.get("shortName")
        currency = info.get("currency")
    except Exception:
        pass  # name and currency are nice-to-have

    return {
        "prices": _series_to_json(prices),
        "dividends": _series_to_json(dividends[dividends > 0]),
        "splits": _series_to_json(splits[splits > 0]),
        "name": name,
        "currency": currency,
    }
