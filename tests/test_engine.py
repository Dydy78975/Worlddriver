"""Prognose-Engine: Point-in-Time-Merkmale, Leakage-Schutz im Walk-Forward, Kennzahlen, Dependency-Tests."""

import numpy as np
import pandas as pd
import pytest

from forex_nexus.dependencies import validation
from forex_nexus.fx.crosses import all_pairs_from_usd
from forex_nexus.models import engine
from forex_nexus.models.features import FEATURES, build_panel

USD_PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY"]


def synthetic_closes(start="2004-01-01", end="2007-12-31", seed=3):
    """Reine Zufallspfade: Es gibt nichts vorherzusagen."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, end)
    start_px = [1.2, 1.5, 0.7, 0.6, 1.3, 1.1, 110.0]
    usd = pd.DataFrame({p: s * np.exp(np.cumsum(rng.normal(0, 0.006, len(idx))))
                        for p, s in zip(USD_PAIRS, start_px)}, index=idx.date)
    return all_pairs_from_usd(usd)


def synthetic_vix(index, seed=4):
    rng = np.random.default_rng(seed)
    return pd.Series(np.exp(np.log(18) + np.cumsum(rng.normal(0, 0.03, len(index))) * 0.3), index=index)


@pytest.fixture(scope="module")
def panel():
    closes = synthetic_closes()
    return build_panel(closes, synthetic_vix(closes.index))


# --- Merkmale ---------------------------------------------------------------------------

def test_targets_are_future_returns(panel):
    p = panel[panel.pair == "EURUSD"].reset_index(drop=True)
    t = 300
    assert p.loc[t, "y_1D"] == pytest.approx(np.log(p.loc[t + 1, "price"] / p.loc[t, "price"]))
    assert p.loc[t, "y_1W"] == pytest.approx(np.log(p.loc[t + 5, "price"] / p.loc[t, "price"]))
    assert p.loc[t, "y_1M"] == pytest.approx(np.log(p.loc[t + 20, "price"] / p.loc[t, "price"]))
    band = 0.5 * p.loc[t, "sigma"] * np.sqrt(5)
    expected = 1 if p.loc[t, "y_1W"] > band else -1 if p.loc[t, "y_1W"] < -band else 0
    assert p.loc[t, "cls_1W"] == expected


def test_features_do_not_change_when_future_prices_change():
    closes = synthetic_closes()
    vix = synthetic_vix(closes.index)
    base = build_panel(closes, vix)
    cut = closes.index[700]
    changed = closes.copy()
    changed.loc[changed.index > cut] *= 1.25            # Zukunft massiv verändern
    vix2 = vix.copy()
    vix2[vix2.index > cut] *= 3
    alt = build_panel(changed, vix2)
    a = base[base.date <= pd.Timestamp(cut)].set_index(["date", "pair"])[FEATURES + ["sigma"]]
    b = alt[alt.date <= pd.Timestamp(cut)].set_index(["date", "pair"])[FEATURES + ["sigma"]]
    pd.testing.assert_frame_equal(a, b)


def test_vix_is_taken_from_previous_day():
    closes = synthetic_closes()
    vix = pd.Series(20.0, index=closes.index)
    jump_day = closes.index[400]
    vix[jump_day:] = 40.0
    p = build_panel(closes, vix)
    e = p[p.pair == "EURUSD"].set_index("date")
    pos = e.index.get_loc(pd.Timestamp(jump_day))
    assert np.exp(e["vix_level"].iloc[pos]) == pytest.approx(20.0)       # am Sprungtag noch alter Wert
    assert np.exp(e["vix_level"].iloc[pos + 1]) == pytest.approx(40.0)


# --- Walk-Forward ----------------------------------------------------------------------------

@pytest.mark.parametrize("horizon", ["1D", "1M"])
def test_walk_forward_never_trains_on_overlapping_targets(panel, horizon, monkeypatch):
    seen = []
    real = engine._fit_predict_proba

    def spy(model, train, test, h):
        seen.append((train[f"target_date_{h}"].max(), test["date"].min()))
        return real(model, train, test, h)

    monkeypatch.setattr(engine, "_fit_predict_proba", spy)
    engine.walk_forward(panel, horizon, models=("climatology", "logreg"), log=lambda m: None)
    assert seen
    for last_target, test_start in seen:
        assert last_target < test_start, "Trainingsziel reicht in den Testzeitraum (Leakage)"


def test_random_walk_produces_no_false_champion(panel):
    oos = engine.walk_forward(panel, "1W", log=lambda m: None)
    rep = engine.evaluate(oos, "1W")
    assert 0.45 < rep.validation["logreg"]["hit_rate"] < 0.55
    # Bei reinem Zufall darf kein Richtungsmodell gewinnen. Die Schwankungs-Referenz darf die reine
    # Häufigkeit schlagen (sie korrigiert nur die ungenaue Volatilitätsschätzung).
    assert rep.champion in ("climatology", "volref")
    for m in engine.DIRECTIONAL:
        assert (rep.validation[m]["bss_vs_volref_ci_low"] or -1) <= 0 or rep.validation[m]["bss_ci_low"] <= 0
    assert not rep.use_return_model
    cov = rep.validation["climatology"]["coverage_80"]
    assert 0.7 < cov < 0.9                       # Intervalle sind auch bei Zufall ehrlich


def test_metrics_basics():
    df = pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=4), "cls": [1, 0, -1, 1],
                       "y": [0.01, 0.0, -0.01, 0.02], "ret_pred": 0.0, "q05": -1, "q10": -1, "q90": 1, "q95": 1})
    for m in ("climatology", "perfect"):
        df[f"{m}_p_bear"] = [0, 0, 1, 0] if m == "perfect" else 1 / 3
        df[f"{m}_p_neutral"] = [0, 1, 0, 0] if m == "perfect" else 1 / 3
        df[f"{m}_p_bull"] = [1, 0, 0, 1] if m == "perfect" else 1 / 3
    assert engine.brier(df, "perfect").sum() == 0
    assert engine.brier(df, "climatology").mean() == pytest.approx(2 / 3)
    m = engine.metrics(df, "perfect", "1D")
    assert m["bss"] == pytest.approx(1.0) and m["hit_rate"] == 1.0 and m["coverage_80"] == 1.0


def test_display_rules():
    ok = {"effective_n": 1000, "ece": 0.01, "bss_ci_low": 0.001}
    assert engine.display_allowed(ok)
    assert not engine.display_allowed({**ok, "bss_ci_low": -0.001})
    assert not engine.display_allowed({**ok, "ece": 0.08})
    assert not engine.display_allowed({**ok, "effective_n": 100})


# --- Dependency Engine: statistische Prüfung -------------------------------------------------------

def _strength_and_driver(kind, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", "2024-12-31")
    months = pd.period_range("2000-01", "2024-12", freq="M")
    shocks = pd.Series(rng.normal(0, 0.05, len(months)), index=months)
    driver_m = np.exp(np.cumsum(shocks))
    noise = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx).cumsum()
    per = idx.to_period("M")
    if kind == "contemporaneous":
        level = 0.4 * np.log(driver_m.reindex(per).values)
    elif kind == "leading":
        level = 0.4 * np.log(driver_m.shift(3).reindex(per).fillna(1.0).values)
    else:
        level = np.zeros(len(idx))
    strength = pd.DataFrame({"AUD": level + noise.values * 0.2}, index=idx)
    driver = pd.Series(driver_m.values, index=months.to_timestamp())
    return strength, driver


@pytest.mark.parametrize("kind, verdicts", [
    ("contemporaneous", {"erklärend", "schwächer werdend"}),
    ("leading", {"vorauslaufend"}),
    ("none", {"nicht belegt", "instabil"}),
])
def test_dependency_verdicts(kind, verdicts):
    strength, driver = _strength_and_driver(kind)
    r = validation.analyse(strength, driver, "AUD", "M", 45, 1)
    assert r["verdict"] in verdicts, r["verdict"]


def test_dependency_wrong_sign_is_flagged():
    strength, driver = _strength_and_driver("contemporaneous")
    r = validation.analyse(strength, driver, "AUD", "M", 45, -1)
    assert r["verdict"] == "gegenteilig"


def test_target_lead_respects_publication_lag():
    assert validation._target_lead("M", 45) == 3      # Monat m bekannt Mitte m+2 -> Ziel m+3
    assert validation._target_lead("D", 7) == 2
    assert validation._target_lead("D", 0) == 1
