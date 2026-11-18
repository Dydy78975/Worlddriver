"""COT-Positionierung und Wirtschaftskalender: Abruf, Veröffentlichungszeitpunkt, Index (ohne Internet)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from forex_nexus.ingestion import calendar, cot
from forex_nexus.signals.data import as_of, cot_indices, decision_times

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
    idx = cot_indices(_cot_frame(nets))
    assert idx["comm_idx"].iloc[99] == pytest.approx(100)          # Höchststand im Fenster
    assert idx["comm_idx"].iloc[100] == pytest.approx(50 / 99 * 100, rel=1e-6)
    assert idx["spec_idx"].iloc[99] == pytest.approx(0)            # Spekulanten spiegelbildlich
    assert idx["comm_idx"].iloc[:51].isna().all()                   # erst ab 52 Wochen


def test_cot_counts_only_after_publication():
    idx = cot_indices(_cot_frame(list(range(60))))
    tuesday = idx["report_date"].iloc[-1]
    g = idx.set_index(pd.to_datetime(idx["report_date"]))
    when = decision_times(pd.bdate_range(tuesday, periods=6))     # Di, Mi, Do, Fr, Mo, Di
    s = as_of(g["comm_idx"], g["available_at"], when, "W")
    prev = idx["comm_idx"].iloc[-2]
    assert list(s.iloc[:4]) == [prev] * 4                          # Fr 12:00 New York: Bericht kommt erst 15:30
    assert s.iloc[4] == idx["comm_idx"].iloc[-1]                   # ab Montag bekannt


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
