"""Signal-Prüfung: keine Zukunftsdaten, richtige Richtung, Kosten, Mehrfachtest-Korrektur, Abstimmung."""

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS
from forex_nexus.signals import validate
from forex_nexus.signals.data import Inputs, as_of, decision_times
from forex_nexus.signals.library import Signal, pair_diff, sign


def _inputs(n=6000, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("1999-01-04", periods=n)
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.006, (n, len(ALL_PAIRS))), axis=0)),
                          index=dates, columns=ALL_PAIRS)
    return Inputs(closes, decision_times(dates), {}, {}, pd.Series(dtype=float), {})


def test_as_of_respects_release_time_and_staleness():
    when = decision_times(pd.bdate_range("2024-01-01", "2024-08-30"))
    values = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    avail = pd.Series(pd.to_datetime(["2024-02-15 23:00", "2024-03-15 23:00"], utc=True), index=values.index)
    s = as_of(values, avail, when, "M")
    assert s[when < pd.Timestamp("2024-02-16", tz="UTC")].isna().all()         # vor Veröffentlichung unbekannt
    assert s[(when > pd.Timestamp("2024-02-16", tz="UTC")) & (when < pd.Timestamp("2024-03-15", tz="UTC"))].eq(1.0).all()
    assert s[(when > pd.Timestamp("2024-03-16", tz="UTC")) & (when < pd.Timestamp("2024-05-29", tz="UTC"))].eq(2.0).all()
    assert s[when > pd.Timestamp("2024-06-01", tz="UTC")].isna().all()         # nächster Wert überfällig -> verworfen


def test_currency_factor_points_the_right_way():
    f = pd.DataFrame([{c: 0.0 for c in MAJORS} | {"EUR": 4.0, "USD": 2.0}])
    s = sign(pair_diff(f), 0.25)
    assert s.at[0, "EURUSD"] == 1          # höherer Zins in der Basiswährung -> long
    assert s.at[0, "USDJPY"] == 1
    assert s.at[0, "GBPUSD"] == -1         # höherer Zins in der Kurswährung -> short
    assert s.at[0, "GBPJPY"] == 0          # kein Unterschied -> keine Aussage


def test_weekly_grid_uses_week_end_to_next_week_end():
    dates = pd.bdate_range("2024-01-01", periods=15)
    closes = pd.DataFrame({"EURUSD": np.arange(1, 16, dtype=float)}, index=dates)
    days, fwd = validate.grid(closes, "1W")
    assert list(days.day_name().unique()) == ["Friday"]
    assert np.isclose(fwd.loc[days[0], "EURUSD"], np.log(10 / 5))


def test_costs_only_when_signal_changes():
    days = pd.bdate_range("2024-01-01", periods=4)
    fwd = pd.DataFrame({"EURUSD": [0.01, 0.01, 0.01, 0.01]}, index=days)
    sig = pd.DataFrame({"EURUSD": [1, 1, -1, -1]}, index=days)
    daily, _, _ = validate.evaluate(sig, fwd, days)
    expected = [0.01 - validate.COST, 0.01, -0.01 - validate.COST, -0.01]
    assert np.allclose(daily.values, expected)


def test_benjamini_hochberg():
    p = {"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}
    assert validate.benjamini_hochberg(p, q=0.10) == {"a", "b", "c"}
    assert validate.benjamini_hochberg(p, q=0.01) == {"a"}


def test_planted_signal_is_found_and_noise_is_not(monkeypatch):
    inp = _inputs()
    fwd1 = np.log(inp.closes).shift(-1) - np.log(inp.closes)
    eur = [p for p in ALL_PAIRS if "EUR" in p]
    rng = np.random.default_rng(3)

    def good(i):                                    # kennt mit 56 % Trefferquote die Richtung der EUR-Paare
        s = pd.DataFrame(0, index=i.closes.index, columns=ALL_PAIRS)
        right = np.sign(fwd1[eur]).fillna(0).astype(int)
        flip = rng.random(right.shape) < 0.44
        s[eur] = np.where(flip, -right, right)
        return s

    def noise(i):
        return pd.DataFrame(rng.choice([-1, 0, 1], (len(i.closes), len(ALL_PAIRS))), index=i.closes.index, columns=ALL_PAIRS)

    monkeypatch.setattr(validate, "SIGNALS", [Signal("good", "Test", "gut", "", good),
                                              Signal("noise", "Test", "Zufall", "", noise)])
    monkeypatch.setattr(validate, "FUNDAMENTAL_VOTE", ["good", "noise"])
    res = validate.run(inp)
    valid = set(res["horizons"]["1D"]["valid"])
    assert ("good", "EUR") in valid
    assert not any(k == "noise" for k, _ in valid)
    assert "good" in res["horizons"]["1D"]["members"]["EURUSD"]
    test = res["horizons"]["1D"]["checked"]["test"]["all"]
    assert test["hit"] > 0.53                        # Schlusstest bestätigt das gepflanzte Signal


def test_vote_labels_and_counts():
    assert validate.label(None) == "kein Signal"
    assert validate.label(0.8) == "klar long"
    assert validate.label(0.6) == "eher long"
    assert validate.label(0.5) == "unentschieden"
    assert validate.label(0.4) == "eher short"
    assert validate.label(0.1) == "klar short"
    days = pd.bdate_range("2024-01-01", periods=2)
    sigs = {k: pd.DataFrame(v, index=days, columns=ALL_PAIRS) for k, v in (("a", 1), ("b", 1), ("c", -1), ("d", 0))}
    vote = validate.votes(sigs, {p: ["a", "b", "c", "d"] for p in ALL_PAIRS})
    cur = validate.current_vote(vote, sigs, days[-1])["pairs"]["EURUSD"]
    assert (cur["bull"], cur["bear"], cur["neutral"]) == (2, 1, 1)
    assert np.isclose(cur["share_bull"], 2 / 3) and cur["label"] == "eher long"


def test_bis_csv_and_calendar_yoy():
    from forex_nexus.ingestion.fred_series import parse_ecb_series
    from forex_nexus.signals.data import _yoy
    text = ("FREQ,REF_AREA,TITLE,TIME_PERIOD,OBS_VALUE\n"
            'D,GB,"From 3 Aug 2006, official bank rate",2026-11-06,4\nD,GB,"x",2026-11-09,3.75\n')
    s = parse_ecb_series(text)
    assert list(s.values) == [4.0, 3.75] and str(s.index[0]) == "2026-11-06"
    # Quartalspreise als Monatsreihe (Wert wiederholt): Vorjahresvergleich nach Kalender, nicht nach Zeilen
    idx = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    v = pd.Series([100.0] * 12 + [103.0] * 12, index=idx)
    assert np.isclose(_yoy(v, "Q").iloc[-1], 3.0)
