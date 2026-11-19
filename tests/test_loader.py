"""The live-data path, with SEC and Yahoo replaced by fakes (no network needed)."""

import pytest

from value_lens import config
from value_lens.analysis import analyze
from value_lens.data import DataError, edgar, loader, market

from .test_edgar import FACTS

TICKERS = {"0": {"cik_str": 1234, "ticker": "TEST", "title": "Test Corp"}}


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.urls = []

    def get(self, url, timeout=30):
        self.urls.append(url)
        if url == edgar.TICKERS_URL:
            return FakeResponse(TICKERS)
        if url == edgar.FACTS_URL.format(cik=1234):
            return FakeResponse(FACTS)
        return FakeResponse({}, 404)


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    session = FakeSession()
    real_init = edgar.EdgarClient.__init__

    def init(self, user_agent, cache, session_arg=None):
        real_init(self, user_agent, cache, session)

    monkeypatch.setattr(edgar.EdgarClient, "__init__", init)
    monkeypatch.setattr(market, "_download", lambda t: {
        "prices": {"2019-01-02": 40.0, "2021-02-01": 12.0, "2026-11-13": 15.0},
        "dividends": {"2025-06-01": 0.1, "2026-06-01": 0.1},
        "splits": {"2020-08-31": 4.0},
        "name": "Test Corporation",
        "currency": "USD",
    })
    return session


def test_load_company_end_to_end(offline):
    cd = loader.load_company("test", "Jane Doe jane@example.com")
    assert cd.name == "Test Corporation"
    assert cd.annual.loc["2018-12-31", "eps"] == 1.75  # split-adjusted
    assert cd.shares_outstanding == 100.0  # cover-page count filed after the split
    a = analyze(cd)
    assert a.scored_total == 7
    stability = next(c for c in a.checks if c.key == "stability")
    assert stability.warning  # only 3 years in the fake filings


def test_second_load_uses_cache(offline):
    loader.load_company("TEST", "Jane Doe jane@example.com")
    first = len(offline.urls)
    loader.load_company("TEST", "Jane Doe jane@example.com")
    assert len(offline.urls) == first


def test_missing_contact_email_is_explained(offline):
    with pytest.raises(DataError, match="SEC needs a contact"):
        loader.load_company("TEST", "")


def test_unknown_ticker_is_explained(offline):
    with pytest.raises(DataError, match="isn't in SEC's list"):
        loader.load_company("NOPE", "Jane Doe jane@example.com")
