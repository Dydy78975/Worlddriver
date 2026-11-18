"""Phase 1b: Dukascopy-Dateien entschlüsseln, Tageskerzen 17:00 New York, robuster Abruf (ohne Internet)."""

import lzma
import struct
import urllib.error
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from forex_nexus.ingestion import dukascopy, http
from forex_nexus.ingestion.fx_daily import store_rows


def _bi5(month_start, candles, divisor=1e5):
    """candles: Liste (Stunde ab Monatsbeginn, open, close, low, high, volume)."""
    raw = b"".join(struct.pack(">5if", h * 3600, round(o * divisor), round(c * divisor), round(lo * divisor),
                               round(hi * divisor), v) for h, o, c, lo, hi, v in candles)
    return lzma.compress(raw)


def test_decode_and_drop_zero_volume_hours():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    raw = _bi5(start, [(0, 1.1, 1.1, 1.1, 1.1, 0.0), (1, 1.10, 1.11, 1.09, 1.12, 50.0)])
    df = dukascopy.decode_hour_candles(raw, start, 1e5)
    assert len(df) == 1
    row = df.iloc[0]
    assert df.index[0] == start + timedelta(hours=1)
    assert (row.open, row.high, row.low, row.close) == pytest.approx((1.10, 1.12, 1.09, 1.11))


def test_jpy_divisor():
    assert dukascopy.price_divisor("USDJPY") == 1e3 and dukascopy.price_divisor("EURUSD") == 1e5


def test_impossible_candle_rejected():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    raw = _bi5(start, [(1, 1.10, 1.11, 1.12, 1.13, 5.0)])   # Tief über Eröffnung
    with pytest.raises(ValueError, match="unmöglichen"):
        dukascopy.decode_hour_candles(raw, start, 1e5)


def _hours(utc_start, n, price=1.0):
    idx = pd.date_range(utc_start, periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": price, "high": price + 0.01, "low": price - 0.01, "close": price, "volume": 1.0}, index=idx)


@pytest.mark.parametrize("utc_open, label", [
    ("2024-07-14 21:00", "Sommerzeit: 17:00 New York = 21:00 UTC"),
    ("2024-01-14 22:00", "Winterzeit: 17:00 New York = 22:00 UTC"),
])
def test_ny_close_session_boundaries(utc_open, label):
    # Sonntag 17:00 New York bis Montag 17:00 New York = Handelstag Montag (24 Stunden)
    hourly = _hours(utc_open, 26)
    days = dukascopy.to_ny_close_days(hourly)
    monday = (pd.Timestamp(utc_open) + pd.Timedelta(days=1)).date()
    assert days.loc[monday, "hours"] == 24, label
    assert days.index.max() == monday + timedelta(days=1)   # die letzten 2 Stunden gehören zu Dienstag


def test_ohlc_aggregation_and_weekend_drop():
    hourly = _hours("2024-07-14 21:00", 24)
    hourly["open"] = range(24)
    hourly["close"] = [x + 0.5 for x in range(24)]
    hourly["high"] = hourly["close"] + 1
    hourly["low"] = hourly["open"] - 1
    hourly.iloc[5, hourly.columns.get_loc("high")] = 100
    sat = _hours("2024-07-19 21:00", 3)          # Freitag 17:00 NY danach -> Samstag-Sitzung
    days = dukascopy.to_ny_close_days(pd.concat([hourly, sat]))
    d = days.loc[date(2024, 7, 15)]
    assert (d.open, d.high, d.low, d.close) == (0, 100, -1, 23.5)
    assert all(x.weekday() < 5 for x in days.index)


def test_months_iterator():
    assert [m.month for m in dukascopy.months(date(2024, 11, 5), date(2025, 2, 1))] == [11, 12, 1, 2]


# --- robuster Abruf -------------------------------------------------------------------

class _Resp:
    def __init__(self, data): self.data = data
    def read(self): return self.data
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _err(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_fetch_bytes_retries_on_rate_limit(monkeypatch):
    answers = [_err(429), ConnectionResetError(), _Resp(b"ok")]
    def fake(url, timeout):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(http.urllib.request, "urlopen", fake)
    waits = []
    assert http.fetch_bytes("u", sleep=waits.append) == b"ok"
    assert waits == [5.0, 10.0]


def test_fetch_bytes_not_found(monkeypatch):
    monkeypatch.setattr(http.urllib.request, "urlopen", lambda url, timeout: (_ for _ in ()).throw(_err(404)))
    with pytest.raises(http.NotFound):
        http.fetch_bytes("u", sleep=lambda s: None)


def test_download_uses_cache_and_marks_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(dukascopy, "CACHE_DIR", tmp_path)
    calls = []
    def fake_fetch(url):
        calls.append(url)
        if "/2024/00/" in url:
            raise http.NotFound(url)
        return b"x"
    monkeypatch.setattr(dukascopy, "fetch_bytes", fake_fetch)
    monkeypatch.setattr(dukascopy.time, "sleep", lambda s: None)
    s1 = dukascopy.download(["EURUSD"], date(2024, 1, 1), date(2024, 2, 1), log=lambda m: None)
    assert s1 == {"loaded": 1, "cached": 0, "missing": 1}
    assert (tmp_path / "EURUSD" / "2024-01.bi5").read_bytes() == b""
    s2 = dukascopy.download(["EURUSD"], date(2024, 1, 1), date(2024, 2, 1), log=lambda m: None)
    assert s2 == {"loaded": 0, "cached": 2, "missing": 0} and len(calls) == 2


# --- Speichern mit Hoch/Tief ------------------------------------------------------------

def test_store_ohlc_and_reject_inconsistent(db_url, conn):
    from zoneinfo import ZoneInfo
    at = datetime(2024, 7, 15, 17, tzinfo=ZoneInfo("America/New_York"))
    good = pd.DataFrame([{"symbol": "EURUSD", "trade_date": date(2024, 7, 15), "open": 1.09, "high": 1.095,
                          "low": 1.085, "close": 1.091, "available_at": at}])
    assert store_rows(db_url, "DUKASCOPY_BID", good)["inserted"] == 1
    bad = good.assign(trade_date=date(2024, 7, 16), high=1.08)
    with pytest.raises(Exception, match="fx_daily_ohlc_consistent"):
        store_rows(db_url, "DUKASCOPY_BID", bad)
    status = conn.execute("SELECT status FROM raw.ingestion_run ORDER BY run_id DESC LIMIT 1").fetchone()[0]
    assert status == "failed"
