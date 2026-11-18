"""Saisonaler Verlauf, Saison-Screener (Mehrfachtest-Korrektur), Stärke-Fenster, Marktstimmung."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from forex_nexus.fundamentals import extras


def _closes(seed=5, start="2005-01-03", end="2025-12-31"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    return pd.DataFrame({"EURUSD": 1.2 * np.exp(np.cumsum(rng.normal(0, 0.005, len(idx)))),
                         "AUDJPY": 80 * np.exp(np.cumsum(rng.normal(0, 0.007, len(idx))))}, index=idx.date)


def test_binomial_test():
    assert extras._binom_p(5, 10) == pytest.approx(1.0)
    assert extras._binom_p(10, 10) == pytest.approx(2 / 1024)
    assert extras._binom_p(0, 10) == pytest.approx(2 / 1024)


def test_seasonal_paths_start_at_100_and_use_completed_years():
    p = extras.seasonal_paths(_closes(), this_year=2026)["EURUSD"]
    assert set(p) == {"5", "10", "15", "20", "max"}
    assert p["10"]["years"] == [2016, 2025] and p["10"]["n"] == 10
    assert p["5"]["path"][0] == pytest.approx(100, abs=0.5)
    assert len(p["max"]["path"]) == 365


def test_screener_finds_no_pattern_in_random_data():
    rows = extras.season_screener(_closes(), date(2026, 11, 18))
    assert len(rows) == 2
    assert not any(r["pattern"] for r in rows)                  # Zufall besteht die Korrektur nicht
    for r in rows:
        assert r["p_adj"] >= r["p"] and r["tests"] == extras.SCREEN_AHEAD * len(extras.SCREEN_LENGTHS)


def test_screener_detects_real_pattern():
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2005-01-03", "2025-12-31")
    r = rng.normal(0, 0.004, len(idx)) + np.where((idx.month == 12) & (idx.day <= 21), 0.003, 0.0)
    c = pd.DataFrame({"EURUSD": 1.2 * np.exp(np.cumsum(r))}, index=idx.date)
    row = extras.season_screener(c, date(2026, 11, 30))[0]
    assert row["pattern"] and row["direction"] == 1 and row["hits"] >= 14


def test_strength_windows_and_mood():
    idx = pd.bdate_range("2024-01-01", periods=300)
    strength = pd.DataFrame({"USD": np.linspace(0, 0.03, 300), "EUR": np.linspace(0, -0.03, 300)}, index=idx)
    w = extras.strength_windows(strength)
    assert w["1W"]["USD"] > 0 > w["1W"]["EUR"] and set(w) == {"1T", "1W", "1M"}
    vix = pd.Series(np.r_[np.full(299, 15.0), 30.0], index=idx)
    closes = pd.DataFrame({"AUDJPY": np.linspace(100, 90, 300)}, index=idx)
    m = extras.market_mood(vix, closes, strength)
    assert m["label"] == "Risk-off" and m["audjpy_20d"] < 0
