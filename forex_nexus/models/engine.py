"""Prognose-Engine: drei unabhängige Horizonte (Tag, Woche, Monat), Walk-Forward-Validierung.

Modelle je Horizont (jedes Modell wird NUR auf Daten seines Horizonts trainiert):
  * climatology – historische Klassenhäufigkeit je Paar (Referenz)
  * volref      – Schwankungs-Referenz: logistische Regression NUR auf Schwankungsmerkmalen. Sie fängt den
                  Effekt ein, dass „seitwärts“ über eine geschätzte (ungenaue) Volatilität definiert ist.
Zusätzlich je Horizont:
  * Intervall: empirische Quantile der standardisierten Rendite (Skalierung mit aktueller Volatilität)
  * Spanne: empirische Quantile der standardisierten Kursspanne (Schlusskurse)

Entfernt am 18.11.2026 (Beleg: Walk-Forward 2006–2021 und Hold-out ab 2022, docs/12_signal_abstimmung.md):
logistische Regression und LightGBM schlugen die Schwankungs-Referenz in keinem Horizont, das Ridge-
Renditemodell hatte überall ein negatives Out-of-Sample-R². Richtungssignale prüft jetzt forex_nexus.signals.

Walk-Forward: Für jedes Testjahr wird nur mit Beobachtungen trainiert, deren Zielzeitraum mindestens
einen Horizont (Embargo) vor Beginn des Testjahres endet.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from forex_nexus.models.features import FEATURES, HORIZONS, vix_regime

MODELS = ("climatology", "volref")
QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
VALIDATION_END_YEAR = 2021          # 2006–2021: Modellauswahl; ab 2022: Hold-out (nur Bericht)
FIRST_TEST_YEAR = 2006
CLASSES = np.array([-1, 0, 1])      # bärisch, neutral, bullisch

# Schwellen für „Wahrscheinlichkeiten dürfen angezeigt werden“ (versioniert)
DISPLAY_RULES = {"min_effective_n": 300, "max_ece": 0.05, "bss_ci_lower_gt": 0.0}


# --------------------------------------------------------------------------- Modelle

def _fit_predict_proba(model: str, train: pd.DataFrame, test: pd.DataFrame, horizon: str) -> np.ndarray:
    y = train[f"cls_{horizon}"].astype(int).values
    if model == "climatology":
        freq = (train.groupby("pair")[f"cls_{horizon}"].value_counts(normalize=True)
                .unstack(fill_value=0).reindex(columns=CLASSES, fill_value=0))
        overall = pd.Series(y).value_counts(normalize=True).reindex(CLASSES, fill_value=0).values
        out = np.tile(overall, (len(test), 1)).astype(float)
        known = test["pair"].isin(freq.index).values
        out[known] = freq.loc[test.loc[known, "pair"]].values
        return out
    if model != "volref":
        raise ValueError(model)
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=1000))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf.fit(train[FEATURES].values, y)
        proba = clf.predict_proba(test[FEATURES].values)
    return pd.DataFrame(proba, columns=clf[-1].classes_).reindex(columns=CLASSES, fill_value=0).values


def _dist_params(train: pd.DataFrame, horizon: str) -> dict:
    h = HORIZONS[horizon]
    scale = train["sigma"] * np.sqrt(h)
    z = train[f"y_{horizon}"] / scale
    hi = train[f"hi_{horizon}"] / scale
    lo = train[f"lo_{horizon}"] / scale
    return {"z_q": {q: float(z.quantile(q)) for q in QUANTILES},
            "hi_med": float(hi.median()), "lo_med": float(lo.median())}


def usable(df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    return df.dropna(subset=FEATURES + ["sigma", f"y_{horizon}", f"cls_{horizon}"])


# --------------------------------------------------------------------------- Walk-Forward

def walk_forward(panel: pd.DataFrame, horizon: str, models=MODELS, log=print) -> pd.DataFrame:
    h = HORIZONS[horizon]
    data = usable(panel, horizon).sort_values("date")
    dates = np.sort(data["date"].unique())
    out = []
    for year in range(FIRST_TEST_YEAR, pd.Timestamp(dates[-1]).year + 1):
        start = pd.Timestamp(f"{year}-01-01")
        test = data[(data["date"] >= start) & (data["date"] < pd.Timestamp(f"{year + 1}-01-01"))]
        if test.empty:
            continue
        # Purging + Embargo: Zielzeitraum muss mindestens h Handelstage vor Teststart enden
        first_pos = np.searchsorted(dates, np.datetime64(start))
        cutoff = dates[max(0, first_pos - 2 * h)]
        train = data[data["target_date_" + horizon] < cutoff]
        res = test[["date", "pair", "sigma", f"y_{horizon}", f"cls_{horizon}", f"hi_{horizon}", f"lo_{horizon}",
                    "vix_level"]].copy()
        res.columns = ["date", "pair", "sigma", "y", "cls", "hi", "lo", "vix_level"]
        for m in models:
            p = _fit_predict_proba(m, train, test, horizon)
            res[f"{m}_p_bear"], res[f"{m}_p_neutral"], res[f"{m}_p_bull"] = p[:, 0], p[:, 1], p[:, 2]
        params = _dist_params(train, horizon)
        scale = res["sigma"] * np.sqrt(h)
        for q, zq in params["z_q"].items():
            res[f"q{int(q * 100):02d}"] = zq * scale
        res["hi_pred"], res["lo_pred"] = params["hi_med"] * scale, params["lo_med"] * scale
        res["year"] = year
        out.append(res)
        log(f"  {horizon} {year}: Training {len(train):,} / Test {len(test):,}".replace(",", "."))
    result = pd.concat(out, ignore_index=True)
    result["regime"] = vix_regime(result["vix_level"]).values
    return result


# --------------------------------------------------------------------------- Kennzahlen

def _probs(df, m):
    return df[[f"{m}_p_bear", f"{m}_p_neutral", f"{m}_p_bull"]].values


def _onehot(cls):
    return (cls.values[:, None] == CLASSES[None, :]).astype(float)


def brier(df, m):
    return ((_probs(df, m) - _onehot(df["cls"])) ** 2).sum(axis=1)


def logloss(df, m):
    p = np.clip(_probs(df, m), 1e-6, 1)
    return -np.log((p * _onehot(df["cls"])).sum(axis=1))


def ece(df, m, bins: int = 10) -> float:
    p, o = _probs(df, m).ravel(), _onehot(df["cls"]).ravel()
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - o[mask].mean())
    return float(total)


def block_bootstrap_ci(daily_diff: pd.Series, block: int, reps: int = 400, seed: int = 7) -> tuple[float, float]:
    """95-%-Intervall des Mittelwerts mit Block-Bootstrap über Tage (berücksichtigt Überlappung und
    Abhängigkeit zwischen den Paaren desselben Tages)."""
    x = daily_diff.values
    n = len(x)
    if n < block * 3:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    nblocks = int(np.ceil(n / block))
    means = []
    for _ in range(reps):
        starts = rng.integers(0, n - block, nblocks)
        sample = np.concatenate([x[s:s + block] for s in starts])[:n]
        means.append(sample.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def metrics(df: pd.DataFrame, model: str, horizon: str) -> dict:
    h = HORIZONS[horizon]
    b, b0 = brier(df, model), brier(df, "climatology")
    ll = logloss(df, model)
    score = df[f"{model}_p_bull"] - df[f"{model}_p_bear"]
    decided = (score != 0) & (df["y"] != 0)
    hits = (np.sign(score[decided]) == np.sign(df["y"][decided]))
    daily = pd.DataFrame({"date": df["date"], "d": b0 - b}).groupby("date")["d"].mean()
    lo, hi = block_bootstrap_ci(daily, block=max(20, 4 * h))
    bss = 1 - b.mean() / b0.mean()
    denom = b0.mean()
    n_dates = df["date"].nunique()
    y = df["y"]
    return {
        "n": int(len(df)), "n_dates": int(n_dates),
        "effective_n": int(n_dates / h * 7),     # 7 unabhängige Währungsbewegungen, nicht überlappend
        "brier": float(b.mean()), "brier_climatology": float(denom), "bss": float(bss),
        "bss_ci_low": float(lo / denom) if lo == lo else None, "bss_ci_high": float(hi / denom) if hi == hi else None,
        "log_loss": float(ll.mean()), "hit_rate": float(hits.mean()) if len(hits) else None,
        "hit_n": int(len(hits)), "ece": ece(df, model),
        "coverage_80": float(((y >= df["q10"]) & (y <= df["q90"])).mean()),
        "coverage_90": float(((y >= df["q05"]) & (y <= df["q95"])).mean()),
    }


def display_allowed(m: dict) -> bool:
    return (m["effective_n"] >= DISPLAY_RULES["min_effective_n"] and m["ece"] <= DISPLAY_RULES["max_ece"]
            and m["bss_ci_low"] is not None and m["bss_ci_low"] > DISPLAY_RULES["bss_ci_lower_gt"])


@dataclass
class HorizonReport:
    horizon: str
    validation: dict = field(default_factory=dict)     # Modell -> Kennzahlen 2006–2021
    holdout: dict = field(default_factory=dict)        # Modell -> Kennzahlen ab 2022
    by_segment: list = field(default_factory=list)     # Zeilen für ml.evaluation
    champion: str = "climatology"
    display_calibrated: bool = False
    yearly: list = field(default_factory=list)         # Verlauf: Jahr, Modell, BSS


def evaluate(oos: pd.DataFrame, horizon: str, models=MODELS) -> HorizonReport:
    rep = HorizonReport(horizon)
    val = oos[oos["year"] <= VALIDATION_END_YEAR]
    hold = oos[oos["year"] > VALIDATION_END_YEAR]
    for m in models:
        rep.validation[m] = metrics(val, m, horizon)
        if not hold.empty:
            rep.holdout[m] = metrics(hold, m, horizon)
    # Champion: die Schwankungs-Referenz, wenn sie die reine Häufigkeit belastbar schlägt
    if "volref" in models and (rep.validation["volref"]["bss_ci_low"] or -1) > 0:
        rep.champion = "volref"
    rep.display_calibrated = rep.champion != "climatology" and display_allowed(rep.validation[rep.champion])
    for m in models:
        for seg_type, col in (("pair", "pair"), ("regime", "regime")):
            for seg, part in oos.groupby(col):
                if len(part) < 200:
                    continue
                k = metrics(part, m, horizon)
                rep.by_segment.append({"model": m, "segment_type": seg_type, "segment_value": seg, **k})
        for ccy in ("USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"):
            part = oos[oos["pair"].str.contains(ccy)]
            rep.by_segment.append({"model": m, "segment_type": "currency", "segment_value": ccy,
                                   **metrics(part, m, horizon)})
        for year, part in oos.groupby("year"):
            b = brier(part, m).mean()
            rep.yearly.append({"year": int(year), "model": m, "brier": float(b),
                               "bss": float(1 - b / brier(part, "climatology").mean())})
    return rep


# --------------------------------------------------------------------------- Live-Prognose

def live_forecast(panel: pd.DataFrame, horizon: str, champion: str, models=MODELS) -> pd.DataFrame:
    """Trainiert auf allen Daten, deren Ergebnis bereits bekannt ist, und prognostiziert ab dem letzten Tag."""
    h = HORIZONS[horizon]
    last_date = panel["date"].max()
    today = panel[(panel["date"] == last_date)].dropna(subset=FEATURES + ["sigma"]).copy()
    train = usable(panel, horizon)
    train = train[train[f"target_date_{horizon}"] <= last_date]
    for m in models:
        p = _fit_predict_proba(m, train, today, horizon)
        today[f"{m}_p_bear"], today[f"{m}_p_neutral"], today[f"{m}_p_bull"] = p[:, 0], p[:, 1], p[:, 2]
    params = _dist_params(train, horizon)
    scale = today["sigma"] * np.sqrt(h)
    for q, zq in params["z_q"].items():
        today[f"q{int(q * 100):02d}"] = zq * scale
    today["hi_pred"], today["lo_pred"] = params["hi_med"] * scale, params["lo_med"] * scale
    today["horizon"] = horizon
    today["champion"] = champion
    return today

