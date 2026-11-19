"""Annual fundamentals from SEC EDGAR (free, official, US-listed companies).

SEC asks every client to send a User-Agent with a name and email address and
to stay under 10 requests per second. We make two requests per company and
cache both, so normal use is far below that limit.
API docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from .. import config
from ..cache import DiskCache
from .models import ANNUAL_COLUMNS, DataError

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A"}

# XBRL tags tried in order for each field. Companies switch tags over the
# years (e.g. revenue moved to RevenueFromContractWithCustomer... in 2018),
# so each fiscal year takes the first tag that has a value for it.
FLOW_TAGS: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "SalesRevenueServicesNet",
    ],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
    "shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "op_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends_paid": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
}

INSTANT_TAGS: dict[str, list[str]] = {
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    # Non-current debt first; LongTermDebt can include the current portion,
    # which overstates debt slightly (the conservative direction).
    "lt_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebt",
        "LongTermNotesPayable",
        "SeniorLongTermNotes",
    ],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "goodwill": ["Goodwill"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
}

UNITS = {"eps": "USD/shares", "shares": "shares"}  # everything else: "USD"


def normalize_ticker(ticker: str) -> str:
    """SEC and Yahoo both write share classes with a dash: BRK.B -> BRK-B."""
    return ticker.strip().upper().replace(".", "-")


class EdgarClient:
    def __init__(self, user_agent: str, cache: DiskCache, session: requests.Session | None = None):
        if not user_agent or "@" not in user_agent:
            raise DataError(
                "SEC needs a contact name and email. Add SEC_USER_AGENT to your .env file "
                "or fill in the SEC contact field in Settings."
            )
        self.cache = cache
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})

    def _get_json(self, url: str, max_age_s: float) -> Any:
        cached = self.cache.get(url, max_age_s)
        if cached is not None:
            return cached
        try:
            resp = self.session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise DataError(f"Couldn't reach SEC EDGAR ({exc.__class__.__name__}). Check your internet connection.") from exc
        if resp.status_code == 404:
            raise DataError("SEC EDGAR has no XBRL financial data for this company.")
        if resp.status_code == 403:
            raise DataError(
                "SEC EDGAR refused the request. Make sure SEC_USER_AGENT contains your name and a real email."
            )
        resp.raise_for_status()
        data = resp.json()
        self.cache.set(url, data)
        return data

    def lookup(self, ticker: str) -> tuple[int, str]:
        """Return (CIK, company name) for a ticker."""
        wanted = normalize_ticker(ticker)
        table = self._get_json(TICKERS_URL, config.TICKER_LIST_MAX_AGE)
        for row in table.values():
            if str(row.get("ticker", "")).upper() == wanted:
                return int(row["cik_str"]), str(row["title"])
        raise DataError(
            f"{wanted} isn't in SEC's list of US-listed companies. "
            "Check the ticker. This version covers companies that file with the SEC."
        )

    def company_facts(self, cik: int) -> dict:
        return self._get_json(FACTS_URL.format(cik=cik), config.FACTS_MAX_AGE)


# --------------------------------------------------------------------------
# Turning the raw "companyfacts" JSON into one row per fiscal year
# --------------------------------------------------------------------------

def _rows(facts: dict, tag: str, unit: str) -> list[dict]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return []
    return node.get("units", {}).get(unit, [])


def _annual_flows(rows: list[dict]) -> dict[pd.Timestamp, dict]:
    """Full-year values from annual reports, keyed by period end.

    A 10-K repeats earlier years for comparison; when the same period appears
    in several filings we keep the most recently filed (restated) number.
    """
    out: dict[pd.Timestamp, dict] = {}
    for r in rows:
        if r.get("form") not in ANNUAL_FORMS or "start" not in r:
            continue
        start, end = pd.Timestamp(r["start"]), pd.Timestamp(r["end"])
        if not 350 <= (end - start).days <= 380:  # 52/53-week years included
            continue
        prev = out.get(end)
        if prev is None or r["filed"] > prev["filed"]:
            out[end] = r
    return out


def _instants(rows: list[dict], year_ends: set[pd.Timestamp]) -> dict[pd.Timestamp, dict]:
    """Balance-sheet values at fiscal year ends."""
    out: dict[pd.Timestamp, dict] = {}
    for r in rows:
        if r.get("form") not in ANNUAL_FORMS or "start" in r:
            continue
        end = pd.Timestamp(r["end"])
        if end not in year_ends:
            continue
        prev = out.get(end)
        if prev is None or r["filed"] > prev["filed"]:
            out[end] = r
    return out


def parse_company_facts(facts: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Return (values, filed_dates, tags_used).

    values: one row per fiscal year end, columns = ANNUAL_COLUMNS.
    filed_dates: same shape, the filing date of each value (needed to adjust
                 per-share numbers for splits that happened later).
    tags_used: the XBRL tag used for each column in the latest year.
    """
    flows: dict[str, dict[pd.Timestamp, tuple[float, str, str]]] = {}
    for col, tags in FLOW_TAGS.items():
        unit = UNITS.get(col, "USD")
        merged: dict[pd.Timestamp, tuple[float, str, str]] = {}
        for tag in tags:
            for end, r in _annual_flows(_rows(facts, tag, unit)).items():
                merged.setdefault(end, (float(r["val"]), r["filed"], tag))
        flows[col] = merged

    year_ends = set(flows["net_income"]) | set(flows["revenue"]) | set(flows["eps"])
    if not year_ends:
        raise DataError("No annual (10-K) figures found for this company in SEC EDGAR.")

    instants: dict[str, dict[pd.Timestamp, tuple[float, str, str]]] = {}
    for col, tags in INSTANT_TAGS.items():
        merged = {}
        for tag in tags:
            for end, r in _instants(_rows(facts, tag, "USD"), year_ends).items():
                merged.setdefault(end, (float(r["val"]), r["filed"], tag))
        instants[col] = merged

    index = pd.DatetimeIndex(sorted(year_ends))
    values = pd.DataFrame(index=index, columns=ANNUAL_COLUMNS, dtype="float64")
    filed = pd.DataFrame(index=index, columns=ANNUAL_COLUMNS, dtype="object")
    tags_used: dict[str, str] = {}
    for col, data in {**flows, **instants}.items():
        for end, (val, filed_on, tag) in data.items():
            if end in values.index:
                values.loc[end, col] = val
                filed.loc[end, col] = filed_on
        if data:
            tags_used[col] = data[max(data)][2]

    # Drop fiscal years where we have neither earnings nor revenue.
    keep = values[["eps", "net_income", "revenue"]].notna().any(axis=1)
    return values[keep], filed[keep], tags_used


def latest_shares_outstanding(facts: dict) -> tuple[float, str] | None:
    """Most recent share count from a filing cover page: (shares, filed date)."""
    node = facts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding")
    if not node:
        return None
    rows = node.get("units", {}).get("shares", [])
    if not rows:
        return None
    latest_end = max(r["end"] for r in rows)
    # Companies with several share classes report one row per class; add them.
    same_date = [r for r in rows if r["end"] == latest_end]
    newest_filing = max(r["filed"] for r in same_date)
    total = sum(float(r["val"]) for r in same_date if r["filed"] == newest_filing)
    return total, newest_filing


def adjust_for_splits(values: pd.DataFrame, filed: pd.DataFrame, splits: pd.Series) -> pd.DataFrame:
    """Put EPS and share counts on today's share basis.

    A figure reported in a filing already reflects splits that happened before
    that filing. Splits after it are applied here: EPS is divided by the split
    ratio, share counts multiplied.
    """
    out = values.copy()
    if splits is None or splits.empty:
        return out
    for end in out.index:
        for col, op in (("eps", "div"), ("shares", "mul")):
            f = filed.loc[end, col]
            if pd.isna(out.loc[end, col]) or not isinstance(f, str):
                continue
            later = splits[splits.index > pd.Timestamp(f)]
            factor = float(later.prod()) if len(later) else 1.0
            out.loc[end, col] = out.loc[end, col] / factor if op == "div" else out.loc[end, col] * factor
    return out


def split_factor_after(date: str, splits: pd.Series) -> float:
    if splits is None or splits.empty:
        return 1.0
    later = splits[splits.index > pd.Timestamp(date)]
    return float(later.prod()) if len(later) else 1.0
