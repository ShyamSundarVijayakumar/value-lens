"""Read the Consolidated_Portfolio_Positions.csv file and sort each row into a kind.

The file is only read, never copied into this project. It can come from a path
in .env (PORTFOLIO_CSV) or from the upload box on the portfolio page.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

from ..data.models import DataError

COLUMNS = [
    "ISIN", "Security Name", "Last Bought Date", "Current Quantity", "Average Buy Price (EUR)",
    "Current Price (EUR)", "Native Currency", "Sector", "Industry", "Country", "Unrealized PnL (EUR)",
]
REQUIRED = ["Security Name", "Current Quantity", "Current Price (EUR)"]
NUMERIC = ["Current Quantity", "Average Buy Price (EUR)", "Current Price (EUR)", "Unrealized PnL (EUR)"]

# Rows whose Sector is one of these are not company shares, so Graham's tests
# don't apply. Matching ignores upper/lower case but is otherwise exact, so a
# REIT labelled "Real Estate" (with a space) is still treated as a stock.
NOT_STOCK_SECTORS = {
    "real_estate": "Real estate",
    "bonds": "Bond",
    "bond": "Bond",
    "fixed_income": "Bond",
    "cash": "Cash",
    "commodities": "Commodity",
    "commodity": "Commodity",
    "crypto": "Crypto",
}

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# Kinds of row
STOCK_US = "stock_us"  # analysed with SEC data
STOCK_OTHER = "stock_other"  # needs Europe support (planned)
FUND = "fund"
NOT_STOCK = "not_stock"
UNRESOLVED = "unresolved"


def parse_number(x) -> float | None:
    """Handles 1234.5, 1,234.50, 1.234,50, 1234,5 and a stray euro sign."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("€", "").replace(" ", "").replace(" ", "")
    if s in ("", "-", "nan", "None"):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,50
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.50
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def read_positions(data: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    except Exception as exc:
        raise DataError(f"Couldn't read the CSV file ({exc.__class__.__name__}: {exc}).") from exc
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise DataError(f"The CSV is missing these columns: {', '.join(missing)}. Expected: {', '.join(COLUMNS)}.")
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
    for c in NUMERIC:
        df[c] = df[c].map(parse_number)
    df["ISIN"] = df["ISIN"].fillna("").astype(str).str.strip().str.upper()
    for c in ("Security Name", "Sector", "Industry", "Country", "Native Currency"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df = df[df["Security Name"] != ""].reset_index(drop=True)
    return df


@dataclass
class Resolution:
    ticker: str | None
    quote_type: str | None  # EQUITY, ETF, MUTUALFUND, ...
    source: str  # "your ticker list", "Yahoo search", "demo", "not found"


def classify(row: pd.Series, res: Resolution | None, demo_tickers: set[str]) -> tuple[str, str]:
    """Return (kind, reason shown to the user)."""
    sector_key = row.get("Sector", "").strip().lower()
    if sector_key in NOT_STOCK_SECTORS:
        return NOT_STOCK, f"{NOT_STOCK_SECTORS[sector_key]}: Graham's stock tests don't apply"
    isin = row.get("ISIN", "")
    if not ISIN_RE.match(isin):
        return NOT_STOCK, "No ISIN, so not a listed security"
    if res is None or not res.ticker:
        return UNRESOLVED, "No ticker found for this ISIN. Add it under Fix tickers"
    qt = (res.quote_type or "").upper()
    if qt in ("ETF", "MUTUALFUND", "INDEX"):
        return FUND, "Fund: holds many companies, so company tests don't apply"
    if qt and qt != "EQUITY":
        return NOT_STOCK, f"{qt.title()}: Graham's stock tests don't apply"
    if res.ticker.upper() in demo_tickers or isin.startswith("US"):
        return STOCK_US, ""
    return STOCK_OTHER, "Non-US company: analysis comes with Europe support (next version)"


def add_money_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Value (EUR)"] = out["Current Quantity"] * out["Current Price (EUR)"]
    cost = out["Current Quantity"] * out["Average Buy Price (EUR)"]
    pnl = out["Unrealized PnL (EUR)"]
    out["Unrealized PnL (EUR)"] = pnl.where(pnl.notna(), out["Value (EUR)"] - cost)
    out["PnL %"] = out["Unrealized PnL (EUR)"] / cost.where(cost > 0)
    total = out["Value (EUR)"].sum()
    out["Weight"] = out["Value (EUR)"] / total * 100 if total else 0.0
    return out
