import pandas as pd

from value_lens.data import edgar


def fy(start, end, val, filed, form="10-K"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def inst(end, val, filed, form="10-K"):
    return {"end": end, "val": val, "filed": filed, "form": form}


FACTS = {
    "facts": {
        "us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [
                fy("2018-01-01", "2018-12-31", 100.0, "2019-02-10"),
                fy("2019-01-01", "2019-12-31", 120.0, "2020-02-10"),
                fy("2019-01-01", "2019-12-31", 121.0, "2021-02-10"),  # restated later: keep this
                fy("2020-01-01", "2020-12-31", 90.0, "2021-02-10"),
                fy("2020-10-01", "2020-12-31", 30.0, "2021-02-10"),  # a quarter: ignore
                fy("2021-01-01", "2021-12-31", 50.0, "2021-11-01", form="10-Q"),  # not annual: ignore
            ]}},
            "Revenues": {"units": {"USD": [
                fy("2018-01-01", "2018-12-31", 1000.0, "2019-02-10"),
            ]}},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                fy("2019-01-01", "2019-12-31", 1100.0, "2020-02-10"),
                fy("2020-01-01", "2020-12-31", 1050.0, "2021-02-10"),
            ]}},
            "EarningsPerShareDiluted": {"units": {"USD/shares": [
                fy("2018-01-01", "2018-12-31", 7.0, "2019-02-10"),
                fy("2019-01-01", "2019-12-31", 8.0, "2020-02-10"),
                fy("2019-01-01", "2019-12-31", 2.0, "2021-02-10"),  # restated after 4:1 split
                fy("2020-01-01", "2020-12-31", 1.5, "2021-02-10"),
            ]}},
            "AssetsCurrent": {"units": {"USD": [
                inst("2019-12-31", 500.0, "2020-02-10"),
                inst("2020-12-31", 520.0, "2021-02-10"),
                inst("2020-06-30", 999.0, "2020-08-01", form="10-Q"),
            ]}},
        },
        "dei": {
            "EntityCommonStockSharesOutstanding": {"units": {"shares": [
                {"end": "2021-01-31", "val": 60.0, "filed": "2021-02-10", "form": "10-K"},
                {"end": "2021-01-31", "val": 40.0, "filed": "2021-02-10", "form": "10-K"},
                {"end": "2020-01-31", "val": 25.0, "filed": "2020-02-10", "form": "10-K"},
            ]}},
        },
    }
}


def test_parse_keeps_full_years_and_latest_restatement():
    values, filed, tags = edgar.parse_company_facts(FACTS)
    assert list(values.index.year) == [2018, 2019, 2020]
    assert values.loc["2019-12-31", "net_income"] == 121.0
    assert values.loc["2020-12-31", "net_income"] == 90.0


def test_revenue_falls_back_across_tags():
    values, _, tags = edgar.parse_company_facts(FACTS)
    assert values.loc["2018-12-31", "revenue"] == 1000.0
    assert values.loc["2019-12-31", "revenue"] == 1100.0
    assert tags["revenue"] == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_instants_only_at_year_end():
    values, _, _ = edgar.parse_company_facts(FACTS)
    assert values.loc["2020-12-31", "current_assets"] == 520.0
    assert pd.isna(values.loc["2018-12-31", "current_assets"])


def test_split_adjustment_uses_filing_date():
    values, filed, _ = edgar.parse_company_facts(FACTS)
    splits = pd.Series([4.0], index=[pd.Timestamp("2020-08-31")])
    adj = edgar.adjust_for_splits(values, filed, splits)
    assert adj.loc["2018-12-31", "eps"] == 7.0 / 4  # filed before the split
    assert adj.loc["2019-12-31", "eps"] == 2.0  # restated after the split already
    assert adj.loc["2020-12-31", "eps"] == 1.5


def test_share_classes_are_added():
    shares, filed_on = edgar.latest_shares_outstanding(FACTS)
    assert shares == 100.0
    assert filed_on == "2021-02-10"


def test_ticker_normalization():
    assert edgar.normalize_ticker(" brk.b ") == "BRK-B"
