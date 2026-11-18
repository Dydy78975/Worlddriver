"""Phase 1: Kreuzkurse, Parser, Qualitätsprüfungen, unveränderliches Speichern (ohne Internet)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from forex_nexus.fx.crosses import ALL_PAIRS, all_pairs_from_usd
from forex_nexus.ingestion import fx_daily
from forex_nexus.quality import fx_checks

USD = pd.DataFrame(
    {"EURUSD": [1.10], "GBPUSD": [1.25], "AUDUSD": [0.65], "NZDUSD": [0.60],
     "USDCAD": [1.40], "USDCHF": [0.80], "USDJPY": [150.0]},
    index=[date(2026, 11, 2)],
)


# --- Kreuzkurse -----------------------------------------------------------------

def test_all_28_pairs_computed():
    out = all_pairs_from_usd(USD)
    assert list(out.columns) == ALL_PAIRS and len(ALL_PAIRS) == 28


@pytest.mark.parametrize("pair, expected", [
    ("EURUSD", 1.10),
    ("EURJPY", 1.10 * 150.0),
    ("EURGBP", 1.10 / 1.25),
    ("GBPCAD", 1.25 * 1.40),
    ("AUDNZD", 0.65 / 0.60),
    ("CADJPY", 150.0 / 1.40),
    ("CHFJPY", 150.0 / 0.80),
    ("CADCHF", 0.80 / 1.40),
])
def test_cross_rates(pair, expected):
    assert all_pairs_from_usd(USD)[pair].iloc[0] == pytest.approx(expected)


def test_triangular_consistency():
    out = all_pairs_from_usd(USD).iloc[0]
    assert out["EURGBP"] * out["GBPJPY"] == pytest.approx(out["EURJPY"])


def test_cross_missing_when_component_missing():
    usd = USD.copy()
    usd.loc[date(2026, 11, 3)] = [1.1, 1.25, 0.65, 0.60, 1.40, 0.80, np.nan]
    out = all_pairs_from_usd(usd).loc[date(2026, 11, 3)]
    assert np.isnan(out["EURJPY"]) and not np.isnan(out["EURGBP"])


# --- Parser -----------------------------------------------------------------------

def test_parse_fred_skips_holidays():
    s = fx_daily.parse_fred_csv("observation_date,DEXUSEU\n2026-11-10,1.1\n2026-11-11,\n2026-11-12,1.2\n")
    assert list(s.index) == [date(2026, 11, 10), date(2026, 11, 12)]


def test_parse_fred_rejects_non_positive():
    with pytest.raises(ValueError):
        fx_daily.parse_fred_csv("observation_date,DEXUSEU\n2026-11-10,0\n")


def test_parse_ecb():
    text = ("KEY,CURRENCY,TIME_PERIOD,OBS_VALUE\n"
            "x,USD,2026-11-02,1.12\nx,JPY,2026-11-02,170.1\nx,USD,2026-11-03,1.11\n")
    df = fx_daily.parse_ecb_csv(text)
    assert df.loc[date(2026, 11, 2), "EURJPY"] == 170.1
    assert np.isnan(df.loc[date(2026, 11, 3), "EURJPY"])


# --- Qualitätsprüfungen -------------------------------------------------------------

def _series(n=400, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n).date
    return pd.DataFrame({"EURUSD": 1.1 * np.exp(np.cumsum(rng.normal(0, 0.005, n)))}, index=idx)


def test_gap_detection():
    df = _series()
    single_holiday = df.drop(index=df.index[100])
    assert fx_checks.find_gaps(single_holiday) == []
    long_gap = df.drop(index=df.index[200:205])
    found = fx_checks.find_gaps(long_gap)
    assert len(found) == 1 and found[0].details["business_days"] == 5


def test_outlier_detection_uses_only_past():
    df = _series()
    df.iloc[300:, 0] *= 1.10   # Sprung um 10 % an Tag 300
    found = fx_checks.find_outliers(df)
    assert [(f.day, f.check, f.severity) for f in found] == [(df.index[300], "extreme_move", "info")]
    assert fx_checks.find_outliers(_series()) == []


def test_spike_is_flagged_as_suspected_error():
    df = _series()
    df.iloc[300, 0] *= 1.10    # nur ein einzelner falscher Tageswert
    found = fx_checks.find_outliers(df)
    assert [(f.day, f.check, f.severity) for f in found] == [(df.index[300], "spike", "warning")]


def test_outlier_check_handles_fixed_rates():
    df = _series()
    df.iloc[:200, 0] = 1.0          # feste Kurse: Schwankung 0
    df.iloc[150, 0] = 1.05          # Abwertung im Festkurs-Regime
    for f in fx_checks.find_outliers(df):
        assert np.isfinite(f.details["robust_sigma"])


def test_whipsaw_confirmed_by_control_is_market_event():
    df = _series()
    df.iloc[300, 0] *= 1.10
    control = df.copy()               # zweite Quelle zeigt denselben Sprung -> echt
    found = fx_checks.find_outliers(df, control=control)
    assert [(f.check, f.details["confirmed_by_control"]) for f in found] == [("extreme_move", True)]


def test_ecb_all_pairs_matches_direct_quotes():
    ecb = pd.DataFrame({"EURUSD": [1.1], "EURGBP": [0.88], "EURAUD": [1.69], "EURNZD": [1.83],
                        "EURCAD": [1.54], "EURCHF": [0.88], "EURJPY": [165.0]}, index=[date(2026, 11, 2)])
    out = fx_checks.ecb_all_pairs(ecb).iloc[0]
    for sym in ecb:
        assert out[sym] == pytest.approx(ecb[sym].iloc[0])
    assert out["GBPUSD"] == pytest.approx(1.1 / 0.88)
    assert out["USDJPY"] == pytest.approx(165.0 / 1.1)


def test_source_mismatch():
    a = _series()
    b = a.copy()
    b.iloc[50, 0] *= 1.05
    found, stats = fx_checks.compare_sources(a, b)
    assert [f.day for f in found] == [a.index[50]]
    assert stats.iloc[0]["flagged"] == 1


def test_stale():
    df = _series()
    last = df.index[-1]
    assert fx_checks.find_stale(df, "ECB", last + timedelta(days=3)) == []
    assert len(fx_checks.find_stale(df, "ECB", last + timedelta(days=10))) == 1


# --- Speichern in der Datenbank -----------------------------------------------------------

def test_store_is_append_only_and_reports_revisions(db_url, conn):
    ny = ZoneInfo("America/New_York")
    r1 = fx_daily.store(db_url, "FRED_H10", USD, ny, time(12))
    assert r1["inserted"] == 7 and r1["revisions"] == 0

    again = fx_daily.store(db_url, "FRED_H10", USD, ny, time(12))
    assert again["inserted"] == 0 and again["revisions"] == 0

    changed = USD.copy()
    changed["EURUSD"] = 1.11
    r3 = fx_daily.store(db_url, "FRED_H10", changed, ny, time(12))
    assert r3["inserted"] == 0 and r3["revisions"] == 1

    stored = conn.execute(
        "SELECT close::float8, available_at FROM raw.fx_daily JOIN ref.instrument USING (instrument_id) WHERE symbol='EURUSD'"
    ).fetchone()
    assert stored[0] == 1.10                                        # Originalwert bleibt
    assert stored[1] == datetime(2026, 11, 2, 12, tzinfo=ny)        # Mittag New York
    issue = conn.execute("SELECT check_name, details->>'new' FROM raw.data_quality_issue").fetchone()
    assert issue == ("source_revision", "1.11")
    runs = conn.execute("SELECT count(*) FROM raw.ingestion_run WHERE status='ok'").fetchone()[0]
    assert runs == 3
