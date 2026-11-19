import pandas as pd

from value_lens.analysis import analyze
from value_lens.analysis.graham import FAIL, NA, PASS, coverage_warning, dividend_streak
from value_lens.data.demo import load_demo
from value_lens.data.models import ANNUAL_COLUMNS, CompanyData


def company(eps, start_year=2016, price=50.0, dividends=None, **latest):
    idx = pd.DatetimeIndex([pd.Timestamp(f"{start_year + i}-12-31") for i in range(len(eps))])
    annual = pd.DataFrame(index=idx, columns=ANNUAL_COLUMNS, dtype="float64")
    annual["eps"] = eps
    annual["shares"] = 100.0
    annual["revenue"] = 2e9
    for k, v in latest.items():
        annual.loc[idx[-1], k] = v
    prices = pd.Series([price, price], index=pd.to_datetime(["2005-01-03", "2026-11-13"]))
    return CompanyData(
        ticker="TEST", name="Test", currency="USD", annual=annual, prices=prices,
        dividends=dividends if dividends is not None else pd.Series(dtype="float64"),
        splits=pd.Series(dtype="float64"), first_trade=prices.index[0], shares_outstanding=100.0,
    )


def by_key(a):
    return {c.key: c for c in a.checks + a.context}


def test_coverage_warning_only_when_short():
    assert coverage_warning(10, 10) is None
    assert "5 of the 10" in coverage_warning(5, 10)


def test_short_history_still_calculates_with_warning():
    a = analyze(company([1, 1.1, 1.2, 1.3, 1.5]))
    stab = by_key(a)["stability"]
    assert stab.status == PASS
    assert stab.years_used == 5 and stab.warning


def test_loss_year_fails_stability():
    a = analyze(company([1, 1.1, -0.2, 1.3, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]))
    stab = by_key(a)["stability"]
    assert stab.status == FAIL and "2018" in stab.value
    assert stab.warning is None


def test_growth_one_third_rule():
    # 3-year averages: start 1.0, end 1.4 -> +40%
    a = analyze(company([1, 1, 1, 1.1, 1.2, 1.2, 1.3, 1.4, 1.4, 1.4]))
    assert by_key(a)["growth"].status == PASS
    # start 1.0, end 1.2 -> +20%
    a = analyze(company([1, 1, 1, 1, 1, 1, 1.1, 1.2, 1.2, 1.2]))
    assert by_key(a)["growth"].status == FAIL


def test_moderate_pe_uses_three_year_average():
    a = analyze(company([1, 1, 1, 1, 1, 1, 1, 3, 3, 3], price=44.0))  # 44 / 3 = 14.7
    assert by_key(a)["pe"].status == PASS
    a = analyze(company([1, 1, 1, 1, 1, 1, 1, 3, 3, 3], price=46.0))  # 15.3
    assert by_key(a)["pe"].status == FAIL


def test_price_to_assets_either_rule():
    # P/B 2.0 but P/E 10 -> product 20 <= 22.5 -> pass
    a = analyze(company([5] * 10, price=50.0, equity=2500.0))
    assert by_key(a)["pb"].status == PASS
    assert abs(a.valuation.graham_number - (22.5 * 5 * 25) ** 0.5) < 1e-9


def test_financial_condition_na_for_banks():
    a = analyze(company([2] * 10))
    assert by_key(a)["condition"].status == NA


def test_financial_condition_debt_rule():
    a = analyze(company([2] * 10, current_assets=300.0, current_liabilities=100.0, lt_debt=250.0))
    assert by_key(a)["condition"].status == FAIL  # ratio 3 but debt 250 > 200
    a = analyze(company([2] * 10, current_assets=300.0, current_liabilities=100.0, lt_debt=150.0))
    assert by_key(a)["condition"].status == PASS


def test_dividend_streak_counts_back_from_last_paid_year():
    d = pd.Series(1.0, index=pd.to_datetime([f"{y}-06-01" for y in range(2000, 2026)]))
    assert dividend_streak(d, pd.Timestamp("2026-03-01")) == 26  # 2026 not paid yet
    gap = d.drop(pd.Timestamp("2010-06-01"))
    assert dividend_streak(gap, pd.Timestamp("2026-03-01")) == 15


def test_demo_companies_run():
    for t in ("DEMO", "NEWCO"):
        a = analyze(load_demo(t))
        assert a.scored_total == 7
    newco = by_key(analyze(load_demo("NEWCO")))
    assert newco["ipo"].status == FAIL
    assert newco["stability"].warning


def test_verdict_bands():
    from value_lens.analysis.graham import Valuation
    from value_lens.analysis.verdict import verdict

    assert verdict(Valuation(price=80, graham_number=100)).code == "undervalued"
    assert verdict(Valuation(price=110, graham_number=100)).code == "fair"
    assert verdict(Valuation(price=120, graham_number=100)).code == "overvalued"
    assert verdict(Valuation(price=120, graham_number=None)).code == "unknown"
