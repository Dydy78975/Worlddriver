"""Modelle je Währung: keine Zukunftsdaten, richtige Richtung, Kosten, Mehrfachtest-Korrektur,
Kombi-Modell, Abstimmung und die Parser der Datenquellen."""

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import MAJORS, all_pairs_from_usd
from forex_nexus.ingestion import yields
from forex_nexus.signals import validate
from forex_nexus.signals.data import Inputs, as_of, currency_strength, decision_times
from forex_nexus.signals.library import Model, relative, sign

USD_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"]


def _inputs(n=6000, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("1999-01-04", periods=n)
    usd = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.006, (n, 7)), axis=0)), index=dates, columns=USD_PAIRS)
    closes = all_pairs_from_usd(usd)
    closes.index = pd.to_datetime(closes.index)
    return Inputs(closes, decision_times(dates), {}, {}, pd.Series(dtype=float), currency_strength(closes), {})


def test_as_of_respects_release_time_and_staleness():
    when = decision_times(pd.bdate_range("2024-01-01", "2024-08-30"))
    values = pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-02-01"]))
    avail = pd.Series(pd.to_datetime(["2024-02-15 23:00", "2024-03-15 23:00"], utc=True), index=values.index)
    s = as_of(values, avail, when, "M")
    assert s[when < pd.Timestamp("2024-02-16", tz="UTC")].isna().all()         # vor Veröffentlichung unbekannt
    assert s[(when > pd.Timestamp("2024-02-16", tz="UTC")) & (when < pd.Timestamp("2024-03-15", tz="UTC"))].eq(1.0).all()
    assert s[(when > pd.Timestamp("2024-03-16", tz="UTC")) & (when < pd.Timestamp("2024-05-29", tz="UTC"))].eq(2.0).all()
    assert s[when > pd.Timestamp("2024-06-01", tz="UTC")].isna().all()         # nächster Wert überfällig -> verworfen


def test_relative_factor_points_the_right_way():
    f = pd.DataFrame([{c: 1.0 for c in MAJORS} | {"EUR": 4.0, "JPY": np.nan}])
    assert sign(relative(f, "EUR"), 0.25).iloc[0] == 1          # höher als der Schnitt der anderen -> stärker
    assert sign(relative(f, "USD"), 0.25).iloc[0] == 0 or relative(f, "USD").iloc[0] < 0
    assert sign(relative(f, "JPY"), 0.25).iloc[0] == 0          # keine Daten -> keine Aussage


def test_currency_strength_sums_to_zero_and_follows_the_pair():
    inp = _inputs(n=50)
    st = inp.strength
    assert np.allclose(st.sum(axis=1), 0)
    up = inp.closes["EURUSD"].diff() > 0
    assert ((st["EUR"] - st["USD"]).diff()[up] > 0).all()


def test_grids_use_period_ends():
    st = pd.DataFrame({c: np.arange(80, dtype=float) for c in MAJORS}, index=pd.bdate_range("2024-01-01", periods=80))
    days, fwd = validate.grid(st, "1W")
    assert list(days.day_name().unique()) == ["Friday"] and fwd["EUR"].iloc[0] == 5
    days, fwd = validate.grid(st, "1M")
    assert days[0] == pd.Timestamp("2024-01-31") and days[1] == pd.Timestamp("2024-02-29")


def test_costs_only_when_signal_changes():
    days = pd.bdate_range("2024-01-01", periods=4)
    fwd = pd.Series([0.01] * 4, index=days)
    net, _ = validate.evaluate(pd.Series([1, 1, -1, -1], index=days), fwd, days)
    assert np.allclose(net.values, [0.01 - validate.COST, 0.01, -0.01 - validate.COST, -0.01])


def test_benjamini_hochberg():
    p = {"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5}
    assert validate.benjamini_hochberg(p, q=0.10) == {"a", "b", "c"}
    assert validate.benjamini_hochberg(p, q=0.01) == {"a"}


def test_planted_model_is_found_and_combo_learns_it(monkeypatch):
    inp = _inputs()
    fwd = inp.strength.shift(-1) - inp.strength
    rng = np.random.default_rng(3)

    def good(i):                                    # kennt mit 58 % Trefferquote die Richtung des Euro
        right = np.sign(fwd["EUR"]).fillna(0).astype(int)
        return pd.Series(np.where(rng.random(len(right)) < 0.42, -right, right), index=right.index)

    def noise(i):
        return pd.Series(rng.choice([-1, 0, 1], len(i.closes)), index=i.closes.index)

    models = [Model("EUR:good", "EUR", "Test", "gut", "", good)] + [Model(f"{c}:noise", c, "Test", "Zufall", "", noise) for c in MAJORS]
    monkeypatch.setattr(validate, "MODELS", models)
    res = validate.run(inp)
    d = res["horizons"]["1D"]
    assert "EUR:good" in d["valid"] and not any(k.endswith(":noise") for k in d["valid"])
    eur = d["currencies"]["EUR"]
    assert eur["combo"]["confirmed"] and eur["combo"]["test"][0]["hit"] > 0.54
    assert eur["checked"]["total"] == 1
    assert 0 <= d["pairs"]["EURUSD"]["p_up"] <= 1


def test_tally_and_labels():
    t = validate.tally({"a": 1, "b": 1, "c": -1, "d": 0})
    assert (t["bull"], t["bear"], t["neutral"], t["total"]) == (2, 1, 1, 4)
    assert np.isclose(t["share_bull"], 2 / 3) and t["label"] == "eher long"
    assert validate.label(None) == "kein Signal" and validate.label(0.8) == "klar long" and validate.label(0.1) == "klar short"


def test_hit_table_counts_only_confident_cases():
    prob = pd.Series([0.9, 0.55, 0.45, 0.2])
    y = pd.Series([1.0, -1.0, -1.0, -1.0])
    tab = validate.hit_table(prob, y)
    assert tab[0]["n"] == 4 and np.isclose(tab[0]["hit"], 0.75)
    assert tab[-1]["n"] == 2 and tab[-1]["hit"] == 1.0          # nur die sicheren Fälle (|p − 50 %| ≥ 20 Punkte)


def test_bis_csv_and_calendar_yoy():
    from forex_nexus.ingestion.fred_series import parse_ecb_series
    from forex_nexus.signals.data import _yoy
    text = ("FREQ,REF_AREA,TITLE,TIME_PERIOD,OBS_VALUE\n"
            'D,GB,"From 3 Aug 2006, official bank rate",2026-11-06,4\nD,GB,"x",2026-11-09,3.75\n')
    s = parse_ecb_series(text)
    assert list(s.values) == [4.0, 3.75] and str(s.index[0]) == "2026-11-06"
    idx = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    v = pd.Series([100.0] * 12 + [103.0] * 12, index=idx)
    assert np.isclose(_yoy(v, "Q").iloc[-1], 3.0)


def test_yield_parsers():
    boc = '"TERMS"\n\n"OBSERVATIONS"\n"date","BD.CDN.2YR.DQ.YLD"\n"2026-11-16","3.30"\n"2026-11-17","3.30"\n'
    assert list(yields.parse_boc(boc).values) == [3.3, 3.3]
    rba = "F2\nTitle,2 year\nSeries ID,FCMYGBAG2\n20-May-2013,2.5,1\n05-Aug-2013\n03-Jun-2013,2.6,1\n11-Nov-2026,4.808,1\n"
    s = yields.parse_rba_csv(rba)
    assert [str(d) for d in s.index] == ["2013-05-20", "2013-06-03", "2026-11-11"]      # Mai darf Juni nicht verdrängen
    mof = "Interest Rate (November 2026),,,\nDate,1Y,2Y,3Y\n2026/11/2,1.671,1.88,1.98\n2026/11/4,1.676,1.891,1.99\n"
    assert list(yields.parse_mof(mof).values) == [1.88, 1.891]
    assert list(yields.parse_boe("DATE,IUDSNPY\n13 Nov 2026,4.9526\n16 Nov 2026,4.9734\n").values) == [4.9526, 4.9734]


def test_boe_waits_and_retries_when_blocked(monkeypatch):
    answers = iter(["<!DOCTYPE html>", "DATE,IUDSNPY\n02 Jan 1995,8.1\n", "DATE,IUDSNPY\n02 Jan 2015,1.1\n"])
    monkeypatch.setattr(yields, "fetch_text", lambda url, user_agent=None: next(answers))
    waits = []
    s = yields.fetch("BOE_5Y", sleep=waits.append)
    assert list(s.values) == [8.1, 1.1] and waits == [yields.BOE_PAUSE, yields.BOE_PAUSE]
