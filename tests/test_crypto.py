"""Krypto-Analysen: keine Zukunftsdaten, faire Zählung, korrekte Spannen (ohne Netz, synthetische Daten)."""

import time
from datetime import date

import numpy as np
import pandas as pd

from forex_nexus.crypto import analysis as A
from forex_nexus.crypto.data import parse_fng, parse_klines


def _walk(n=1500, seed=1, vol=0.03, start="2019-01-01"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="D").date
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0, vol, n))), index=idx)


def test_unfinished_candle_dropped():
    now = int(time.time() * 1000)
    day = 86_400_000
    rows = [[now - 2 * day, "1", "2", "0.5", "1.5", "0", now - day - 1, "10", 0, 0, 0, 0],
            [now - day, "1.5", "2", "1", "1.8", "0", now + day, "10", 0, 0, 0, 0]]
    df = parse_klines(rows)
    assert len(df) == 1 and df["close"].iloc[0] == 1.5


def test_parse_fng_sorted():
    s = parse_fng({"data": [{"timestamp": "1700092800", "value": "40"}, {"timestamp": "1700006400", "value": "12"}]})
    assert list(s.values) == [12, 40] and s.index[0] < s.index[1]


def test_ranges_cover_about_80_percent_on_random_walk():
    r = A.ranges(pd.DataFrame({"X": _walk(2000)}))["X"]
    for k in ("1T", "1W"):
        assert 0.74 <= r[k]["coverage"] <= 0.86
        assert r[k]["low"] < 0 < r[k]["high"]


def test_trend_rule_cannot_catch_the_signal_day_jump():
    p = pd.Series(100.0, index=pd.date_range("2020-01-01", periods=600, freq="D").date)
    p.iloc[400:] = 200.0                       # Sprung genau an dem Tag, an dem das Signal dreht
    t = A.trend_backtest(pd.DataFrame({"X": p}))["X"]
    assert t["hold"]["total"] > 0.9            # Halten erwischt den Sprung
    assert t["sma200"]["total"] < 0            # Regel steigt erst am Folgetag ein (nur Gebühr)


def test_fng_cases_do_not_overlap():
    btc = _walk(800)
    fng = pd.Series(10, index=btc.index)       # jeden Tag extreme Angst
    out = A.fng_study(fng, btc, days=30)
    assert out["fear"]["n"] <= 800 // 30 + 1
    assert out["greed"]["n"] == 0


def test_seasonality_skips_running_month():
    p = _walk(400, start="2024-01-01")         # endet mitten im Monat
    s = A.seasonality(pd.DataFrame({"BTC": p}))
    last = pd.Timestamp(p.index[-1])
    assert last.year not in s["months"][last.month]["years"]


def test_cot_backtest_measures_from_release_friday():
    prices = pd.DataFrame({"BTC": _walk(1500, start="2019-01-01")})
    tuesdays = pd.date_range("2019-01-01", "2022-12-31", freq="W-TUE")
    cot = pd.DataFrame({"coin": "BTC", "report_date": [d.date() for d in tuesdays],
                        "spec_net": np.sin(np.arange(len(tuesdays)) / 8) * 1000,
                        "comm_net": 0.0, "small_net": 0.0, "open_interest": 1.0})
    out = A.cot_backtest(cot, prices)["BTC"]
    assert out["high"]["n"] > 0 and out["low"]["n"] > 0
    assert out["all"]["n"] <= len(tuesdays)


def test_robustness_counts_consistent():
    r = A.robustness(pd.DataFrame({"X": _walk(1200), "Y": _walk(1200, seed=2)}))
    assert r["tests"] == 2 * 10
    assert 0 <= r["better_sharpe"] <= r["tests"] and 0 <= r["smaller_dd"] <= r["tests"]
    assert date.fromisoformat(r["coins"]["X"]["halves"]["1"]["to"]) == date.fromisoformat(r["coins"]["X"]["halves"]["2"]["from"])
