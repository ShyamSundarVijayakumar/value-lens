import pandas as pd
import pytest

from value_lens import config
from value_lens.cache import DiskCache
from value_lens.data.models import DataError
from value_lens.portfolio import positions as pos
from value_lens.portfolio.positions import Resolution
from value_lens.portfolio.resolve import Resolver


@pytest.mark.parametrize("raw,expected", [
    ("1234.5", 1234.5), ("1,234.50", 1234.5), ("1.234,50", 1234.5), ("1234,5", 1234.5),
    ("12,345", 12345.0), ("€ 99,90", 99.9), ("-255.00", -255.0), ("", None), (None, None),
])
def test_parse_number(raw, expected):
    assert pos.parse_number(raw) == expected


HEADER = ";".join(pos.COLUMNS)


def test_read_positions_semicolons_and_decimal_commas():
    csv = HEADER + "\nUS1912161007;Coca-Cola Co;2024-01-02;10;55,10;61,25;USD;Consumer Staples;Beverages;United States;61,50\n"
    df = pos.read_positions(csv.encode("utf-8"))
    assert df.loc[0, "Current Price (EUR)"] == 61.25
    assert df.loc[0, "ISIN"] == "US1912161007"


def test_read_positions_reports_missing_columns():
    with pytest.raises(DataError, match="missing"):
        pos.read_positions(b"ISIN,Name\nUS1,Foo\n")


def row(**kw):
    base = {c: "" for c in pos.COLUMNS}
    base.update(kw)
    return pd.Series(base)


def test_classify():
    us = Resolution("KO", "EQUITY", "Yahoo search")
    assert pos.classify(row(ISIN="US1912161007"), us, set())[0] == pos.STOCK_US
    de = Resolution("SAP.DE", "EQUITY", "Yahoo search")
    assert pos.classify(row(ISIN="DE0007164600"), de, set())[0] == pos.STOCK_OTHER
    etf = Resolution("IWDA.AS", "ETF", "Yahoo search")
    assert pos.classify(row(ISIN="IE00B4L5Y983"), etf, set())[0] == pos.FUND
    assert pos.classify(row(ISIN="", Sector="real_estate"), None, set())[0] == pos.NOT_STOCK
    assert pos.classify(row(ISIN="DE0001102580", Sector="Bonds"), None, set())[0] == pos.NOT_STOCK
    # A REIT labelled with the usual sector name is still a stock.
    reit = Resolution("O", "EQUITY", "Yahoo search")
    assert pos.classify(row(ISIN="US7561091049", Sector="Real Estate"), reit, set())[0] == pos.STOCK_US
    assert pos.classify(row(ISIN="US0000000001"), Resolution(None, None, "not found"), set())[0] == pos.UNRESOLVED


def test_money_columns():
    df = pd.DataFrame({"Current Quantity": [10.0, 5.0], "Current Price (EUR)": [20.0, 40.0],
                       "Average Buy Price (EUR)": [10.0, 50.0], "Unrealized PnL (EUR)": [None, -50.0]})
    out = pos.add_money_columns(df)
    assert list(out["Value (EUR)"]) == [200.0, 200.0]
    assert out.loc[0, "Unrealized PnL (EUR)"] == 100.0  # filled in from cost when missing
    assert list(out["Weight"]) == [50.0, 50.0]


def test_resolver_prefers_plain_us_symbol_and_caches(tmp_path):
    calls = []

    def search(isin):
        calls.append(isin)
        return [{"symbol": "APC.DE", "quoteType": "EQUITY"}, {"symbol": "AAPL", "quoteType": "EQUITY"}]

    r = Resolver(DiskCache(tmp_path), overrides={}, search=search)
    assert r.resolve("US0378331005").ticker == "AAPL"
    assert r.resolve("US0378331005").ticker == "AAPL"
    assert len(calls) == 1


def test_resolver_overrides_win_and_failures_are_not_cached(tmp_path):
    def broken(isin):
        raise ConnectionError("offline")

    r = Resolver(DiskCache(tmp_path), overrides={"US0378331005": "AAPL"}, search=broken)
    assert r.resolve("US0378331005").ticker == "AAPL"
    res = r.resolve("US1912161007")
    assert res.ticker is None and res.source == "search failed"
    assert DiskCache(tmp_path).get("isin:US1912161007", 1e9) is None


def test_demo_portfolio_file_reads():
    df = pos.read_positions((config.SAMPLES_DIR / "demo_portfolio.csv").read_bytes())
    assert len(df) == 6
