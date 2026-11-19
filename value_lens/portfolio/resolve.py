"""Turn ISINs into ticker symbols.

Order of preference:
1. Your own list in data/isin_tickers.csv (columns ISIN,Ticker). Always wins.
2. Yahoo Finance search, the same service that already supplies prices.
   Results are cached for 30 days in .cache/.
The data/ folder is in .gitignore, so your list never reaches GitHub.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import config
from ..cache import DiskCache
from ..data.demo import DEMO_ISINS
from .positions import Resolution

OVERRIDES_FILE = config.DATA_DIR / "isin_tickers.csv"
SEARCH_MAX_AGE = 30 * 24 * 3600


def read_overrides(path: Path = OVERRIDES_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    return {r["ISIN"].strip().upper(): r["Ticker"].strip().upper() for _, r in df.iterrows() if r["Ticker"].strip()}


def write_overrides(mapping: dict[str, str], path: Path = OVERRIDES_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted((k, v) for k, v in mapping.items() if v)
    pd.DataFrame(rows, columns=["ISIN", "Ticker"]).to_csv(path, index=False)


def _pick(quotes: list[dict], isin: str) -> dict | None:
    if not quotes:
        return None
    if isin.startswith("US"):
        # Yahoo may list a US company on several exchanges (AAPL, APC.DE, ...).
        # The SEC lookup needs the plain US symbol, which has no suffix.
        for q in quotes:
            if "." not in q.get("symbol", ""):
                return q
    return quotes[0]


def yahoo_search(isin: str) -> list[dict]:
    import yfinance as yf

    search = yf.Search(isin, max_results=8, news_count=0, lists_count=0, recommended=0)
    return [{"symbol": q.get("symbol", ""), "quoteType": q.get("quoteType", ""), "exchange": q.get("exchange", "")}
            for q in (search.quotes or [])]


class Resolver:
    def __init__(self, cache: DiskCache | None = None, overrides: dict[str, str] | None = None, search=yahoo_search):
        self.cache = cache or DiskCache(config.CACHE_DIR)
        self.overrides = read_overrides() if overrides is None else overrides
        self.search = search

    def resolve(self, isin: str, demo: bool = False) -> Resolution:
        isin = isin.strip().upper()
        if demo:
            ticker, qt = DEMO_ISINS.get(isin, (None, None))
            return Resolution(ticker, qt, "demo" if ticker else "not found")
        if isin in self.overrides:
            cached = self.cache.get(f"isin:{isin}", SEARCH_MAX_AGE) or {}
            return Resolution(self.overrides[isin], cached.get("quoteType") or "EQUITY", "your ticker list")
        key = f"isin:{isin}"
        hit = self.cache.get(key, SEARCH_MAX_AGE)
        if hit is None:
            try:
                quote = _pick(self.search(isin), isin)
            except Exception:
                return Resolution(None, None, "search failed")  # not cached: try again next time
            hit = {"symbol": quote["symbol"] if quote else None, "quoteType": quote.get("quoteType") if quote else None}
            self.cache.set(key, hit)
        if not hit.get("symbol"):
            return Resolution(None, None, "not found")
        return Resolution(hit["symbol"], hit.get("quoteType"), "Yahoo search")
