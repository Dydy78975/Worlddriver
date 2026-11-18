"""Fundamentale Wochenanalyse: COT, Saisonalität, Konfluenz, Kalender (ohne Internet)."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from forex_nexus.fundamentals import analysis as A
from forex_nexus.ingestion import calendar, cot

NY = ZoneInfo("America/New_York")


def test_cot_release_is_friday_after_tuesday():
    assert cot.release_time(date(2026, 11, 10)) == datetime(2026, 11, 13, 15, 30, tzinfo=NY)


def test_cot_parse_maps_contracts():
    rows = [{"report_date_as_yyyy_mm_dd": "2026-11-10T00:00:00.000", "cftc_contract_market_code": "099741",
             "open_interest_all": "854705", "comm_positions_long_all": "488832", "comm_positions_short_all": "384210",
             "noncomm_positions_long_all": "227478", "noncomm_positions_short_all": "363874",
             "nonrept_positions_long_all": "86805", "nonrept_positions_short_all": "55031"},
            {"report_date_as_yyyy_mm_dd": "2026-11-10T00:00:00.000", "cftc_contract_market_code": "999999"}]
    out = cot.parse(rows)
    assert len(out) == 1 and out[0][1] == "EUR" and out[0][5] == 488832


def _cot_frame(net_values, ccy="EUR"):
    d = pd.date_range("2020-01-07", periods=len(net_values), freq="W-TUE").date
    return pd.DataFrame({"currency": ccy, "report_date": d,
                         "available_at": [cot.release_time(x) for x in d], "open_interest": 1000,
                         "comm_long": [1000 + v for v in net_values], "comm_short": 1000,
                         "noncomm_long": 500, "noncomm_short": [500 + v for v in net_values]})


def test_cot_index_scale_and_window():
    nets = list(range(0, 100)) + [50]
    idx = A.cot_indices(_cot_frame(nets))
    assert idx["comm_idx"].iloc[99] == pytest.approx(100)          # Höchststand im Fenster
    assert idx["comm_idx"].iloc[100] == pytest.approx(50 / 99 * 100, rel=1e-6)
    assert idx["spec_idx"].iloc[99] == pytest.approx(0)            # Spekulanten spiegelbildlich
    assert idx["comm_idx"].iloc[:51].isna().all()                   # erst ab 52 Wochen


def test_cot_as_of_respects_publication():
    idx = A.cot_indices(_cot_frame(list(range(60))))
    last_tuesday = idx["report_date"].iloc[-1]
    before = datetime.combine(last_tuesday, time(12), NY)            # Dienstag: Bericht noch nicht veröffentlicht
    assert A.cot_as_of(idx, before).loc["EUR", "report_date"] < last_tuesday
    after = datetime.combine(last_tuesday, time(12), NY) + pd.Timedelta(days=4)
    assert A.cot_as_of(idx, after).loc["EUR", "report_date"] == last_tuesday


def test_season_signal_rules():
    assert A.season_signal({"hit": 0.7, "n": 20, "mean": 0.01}) == 1
    assert A.season_signal({"hit": 0.3, "n": 20, "mean": -0.01}) == -1
    assert A.season_signal({"hit": 0.55, "n": 20, "mean": 0.01}) == 0
    assert A.season_signal({"hit": 0.9, "n": 3, "mean": 0.01}) == 0            # zu wenige Jahre


def test_season_stats_only_uses_prior_years():
    idx = pd.date_range("2000-01-31", "2010-12-31", freq="ME")
    m = pd.DataFrame({"EURUSD": np.where(idx.year < 2010, 0.01, -0.05)}, index=idx)
    st = A.season_stats(m, before_year=2010)
    assert st["EURUSD"][3]["mean"] == pytest.approx(0.01)
    assert st["EURUSD"][3]["n"] == 10


def test_pair_view_confluence_and_against():
    cot_now = pd.DataFrame({"comm_idx": {"EUR": 90.0, "USD": 20.0}})
    trend = pd.Series({"EUR": 1.0, "USD": -0.2})
    season = {"EURUSD": {11: {"mean": -0.01, "hit": 0.2, "n": 20, "t": -2.0}}}
    v = A.pair_view("EURUSD", cot_now, trend, season, 11)
    assert v.direction == 1 and v.confluence == 2 and v.against == ["season"]
    v0 = A.pair_view("EURUSD", pd.DataFrame(), pd.Series(dtype=float), {}, 11)
    assert v0.direction == 0 and v0.confluence == 0


def test_wilson_interval():
    lo, hi = A._wilson(60, 100)
    assert 0.5 < lo < 0.6 < hi < 0.7
    assert A._wilson(0, 0) is None


def test_pips():
    assert A.pips("EURUSD", 1.1, np.log(1.001)) == pytest.approx(11.0)
    assert A.pips("USDJPY", 150.0, np.log(1.001)) == pytest.approx(15.0)


def test_calendar_parse_filters_and_keys():
    items = [{"title": "CPI y/y", "country": "GBP", "date": "2026-11-18T02:00:00-05:00", "impact": "High",
              "forecast": "3.6%", "previous": "3.5%"},
             {"title": "Bank Holiday", "country": "CNY", "date": "2026-11-18T00:00:00-05:00", "impact": "Holiday"},
             {"title": "Speech", "country": "USD", "date": "2026-11-18T10:00:00-05:00", "impact": "Non-Economic"}]
    out = calendar.parse(items)
    assert len(out) == 1 and out[0]["currency"] == "GBP" and out[0]["impact"] == "High"
    assert out[0]["source_key"] == "FF|GBP|2026-11-18T07:00|CPI y/y"


def test_calendar_and_cot_store(db_url, conn, monkeypatch):
    monkeypatch.setattr(calendar, "fetch_text", lambda *a, **k: '[{"title":"CPI","country":"EUR","date":"2026-11-18T05:00:00-05:00","impact":"High","forecast":"2%","previous":"2.1%"}]')
    assert calendar.ingest(db_url) == {"events": 1, "high": 1}
    monkeypatch.setattr(calendar, "fetch_text", lambda *a, **k: '[{"title":"CPI","country":"EUR","date":"2026-11-18T05:00:00-05:00","impact":"High","forecast":"2%","previous":"2.1%","actual":"2.3%"}]')
    calendar.ingest(db_url)
    assert conn.execute("SELECT count(*), max(actual) FROM ref.event").fetchone() == (1, "2.3%")
    monkeypatch.setattr(cot, "fetch", lambda since="": [{"report_date_as_yyyy_mm_dd": "2026-11-10T00:00:00.000",
                                                        "cftc_contract_market_code": "232741", "open_interest_all": "10",
                                                        "comm_positions_long_all": "5", "comm_positions_short_all": "1",
                                                        "noncomm_positions_long_all": "1", "noncomm_positions_short_all": "5",
                                                        "nonrept_positions_long_all": "1", "nonrept_positions_short_all": "1"}])
    assert cot.ingest(db_url)["rows"] == 1
    assert cot.ingest(db_url)["rows"] == 1
    assert conn.execute("SELECT count(*), max(currency) FROM raw.cot_position").fetchone() == (1, "AUD")
