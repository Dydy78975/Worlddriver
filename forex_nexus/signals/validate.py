"""Prüfung der Modelle je Währung, Abstimmung und Kombi-Modell.

Regeln (festgelegt vor dem Blick auf den Schlusstest, nicht nachträglich anpassen):
  1. Drei Zeiträume: Entdeckung 1999–2012, Bestätigung 2013–2019, Schlusstest ab 2020.
  2. Gemessen wird die Stärke der Währung gegen den Durchschnitt der anderen 7 bis zum Horizont
     (Tag: nächster Handelstag; Woche/Monat: Periodenende bis Periodenende), nach 0,03 % Kosten je neuem Signal.
  3. Einzelmodelle: „gültig“, wenn a) in der Entdeckung nach Benjamini-Hochberg (10 %) über ALLE Modelle des
     Horizonts signifikant positiv und b) in der Bestätigung positiv (t-Wert > 1).
  4. Kombi-Modell je Währung: logistische Regression über alle Modelle der Währung (Gewichte gelernt).
     Bestätigung: Training bis 2012, Prüfung 2013–2019. Schlusstest: Training bis 2019 (eingefroren),
     Prüfung ab 2020 – dieses eingefrorene Modell liefert auch die aktuelle Einschätzung.
     Berichtet wird die Trefferquote insgesamt und je Sicherheitsstufe (wie weit die Wahrscheinlichkeit
     von 50 % entfernt ist), jeweils mit 95-%-Bereich. „Bestätigt“ ist ein Kombi-Modell, wenn die untere
     Grenze des 95-%-Bereichs seiner Trefferquote in der Bestätigung (alle Fälle) über 50 % liegt.
  5. Der Schlusstest wird für keine Entscheidung genutzt.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS
from forex_nexus.signals.data import Inputs
from forex_nexus.signals.library import MODELS

PERIODS = {"entdeckung": (1999, 2012), "bestaetigung": (2013, 2019), "schlusstest": (2020, 2100)}
HORIZONS = {"1D": "Tag", "1W": "Woche", "1M": "Monat"}
COST = 0.0003
FDR = 0.10
CONFIRM_T = 1.0
PERIODS_PER_YEAR = {"1D": 252, "1W": 52, "1M": 12}
COMBO_C = 0.05                   # starke Regularisierung: viele schwache, ähnliche Signale
CONFIDENCE = (0.0, 0.05, 0.10, 0.15, 0.20)     # Abstand der Wahrscheinlichkeit von 50 %
VOTE_BUCKETS = [("klar long", 0.70, 1.01), ("eher long", 0.55, 0.70), ("unentschieden", 0.45, 0.55),
                ("eher short", 0.30, 0.45), ("klar short", -0.01, 0.30)]


def grid(strength: pd.DataFrame, horizon: str) -> tuple[pd.DatetimeIndex, pd.DataFrame]:
    """Entscheidungstage und Änderung der Währungsstärke bis zum Horizont (Woche/Monat: letzter Handelstag
    der Periode bis zum letzten Handelstag der Folgeperiode)."""
    if horizon == "1D":
        return strength.index, strength.shift(-1) - strength
    wk = strength.index.to_period("W-FRI" if horizon == "1W" else "M")
    last = pd.Series(wk, index=strength.index) != pd.Series(wk, index=strength.index).shift(-1)
    days = strength.index[last.values]
    w = strength.loc[days]
    return days, w.shift(-1) - w


def evaluate(sig: pd.Series, fwd: pd.Series, days: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """Nettoergebnis je Entscheidungstag mit Signal (Kosten bei jedem neuen oder gedrehten Signal)."""
    s = sig.reindex(days).fillna(0)
    r = fwd.reindex(days)
    s = s.where(r.notna(), 0)
    new = (s != s.shift(1)) & (s != 0)
    net = (s * r.fillna(0) - COST * new).where(s != 0)
    return net.dropna(), s


def _in(index, years):
    return (index.year >= years[0]) & (index.year <= years[1])


def stats(net: pd.Series, horizon: str, years: tuple[int, int]) -> dict:
    d = net[_in(net.index, years)]
    n = len(d)
    if n < 20:
        return {"n": n, "mean": None, "t": None, "annual": None, "hit": None}
    sd = d.std(ddof=1)
    return {"n": n, "mean": float(d.mean()), "t": float(d.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0,
            "annual": float(d.mean() * PERIODS_PER_YEAR[horizon]), "hit": float((d > 0).mean())}


def benjamini_hochberg(p: dict, q: float = FDR) -> set:
    items = sorted((v, k) for k, v in p.items() if v is not None)
    passed = 0
    for i, (pv, _) in enumerate(items, start=1):
        if pv <= q * i / len(items):
            passed = i
    return {k for _, k in items[:passed]}


def wilson(p: float, n: int, z: float = 1.96):
    if not n:
        return None
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(c - h), float(c + h)]


def hit_table(prob: pd.Series, y: pd.Series) -> list[dict]:
    """Trefferquote je Sicherheitsstufe: nur Fälle, in denen |p − 50 %| mindestens die Stufe erreicht."""
    out = []
    for c in CONFIDENCE:
        m = (prob - 0.5).abs() >= c
        if c == 0:
            m &= prob != 0.5
        hits = (np.sign(prob[m] - 0.5) == np.sign(y[m]))
        n = int(m.sum())
        out.append({"min_conf": c, "n": n, "share": float(n / len(prob)) if len(prob) else None,
                    "hit": float(hits.mean()) if n else None, "ci": wilson(float(hits.mean()), n) if n else None})
    return out


def _fit(X: pd.DataFrame, y: pd.Series):
    clf = LogisticRegression(C=COMBO_C, max_iter=2000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf.fit(X.values, (y > 0).astype(int).values)
    return clf


def combo(X: pd.DataFrame, y: pd.Series) -> dict:
    """Kombi-Modell einer Währung: Bestätigung (Training ≤ 2012) und Schlusstest (Training ≤ 2019)."""
    ok = y.notna() & (y != 0)
    X, y = X[ok], y[ok]
    out = {"weights": {}, "confirm": [], "test": [], "model": None, "confirmed": False}
    tr1, te1 = _in(X.index, (1999, 2012)), _in(X.index, PERIODS["bestaetigung"])
    tr2, te2 = _in(X.index, (1999, 2019)), _in(X.index, PERIODS["schlusstest"])
    if tr1.sum() < 100 or te1.sum() < 50:
        return out
    m1 = _fit(X[tr1], y[tr1])
    out["confirm"] = hit_table(pd.Series(m1.predict_proba(X[te1].values)[:, 1], index=X[te1].index), y[te1])
    m2 = _fit(X[tr2], y[tr2])
    if te2.sum():
        out["test"] = hit_table(pd.Series(m2.predict_proba(X[te2].values)[:, 1], index=X[te2].index), y[te2])
    out["weights"] = dict(zip(X.columns, m2.coef_[0].round(4)))
    ci = out["confirm"][0]["ci"]
    out["confirmed"] = bool(ci and ci[0] > 0.5)
    out["model"] = m2
    return out


def label(share: float | None) -> str:
    if share is None:
        return "kein Signal"
    return next(name for name, lo, hi in VOTE_BUCKETS if lo <= share < hi)


def tally(votes: dict) -> dict:
    bull = sum(1 for v in votes.values() if v > 0)
    bear = sum(1 for v in votes.values() if v < 0)
    share = bull / (bull + bear) if bull + bear else None
    return {"bull": bull, "bear": bear, "neutral": len(votes) - bull - bear, "total": len(votes),
            "share_bull": share, "label": label(share), "votes": votes}


def vote_test(S: pd.DataFrame, y: pd.Series) -> list[dict]:
    """Abstimmung (Anteil long unter allen Stimmen) im Schlusstest: Trefferquote je Stufe."""
    t = _in(S.index, PERIODS["schlusstest"]) & y.notna() & (y != 0)
    bull, bear = (S[t] > 0).sum(axis=1), (S[t] < 0).sum(axis=1)
    share = bull / (bull + bear).replace(0, np.nan)
    out = []
    for name, lo, hi in VOTE_BUCKETS:
        m = (share >= lo) & (share < hi) & (bull != bear)
        hits = np.sign(bull[m] - bear[m]) == np.sign(y[t][m])
        n = int(m.sum())
        out.append({"label": name, "n": n, "hit": float(hits.mean()) if n else None,
                    "ci": wilson(float(hits.mean()), n) if n else None})
    return out


def run(inputs: Inputs) -> dict:
    sig = {m.key: m.rule(inputs).reindex(inputs.closes.index).fillna(0).astype(int) for m in MODELS}
    out = {"rules": {"periods": PERIODS, "cost": COST, "fdr": FDR, "confirm_t": CONFIRM_T, "combo_c": COMBO_C,
                     "models": len(MODELS)}, "horizons": {}}
    last = inputs.closes.index[-1]
    for h in HORIZONS:
        days, fwd = grid(inputs.strength, h)
        res, pvals = {}, {}
        for m in MODELS:
            net, _ = evaluate(sig[m.key], fwd[m.currency], days)
            res[m.key] = {p: stats(net, h, yrs) for p, yrs in PERIODS.items()}
            t = res[m.key]["entdeckung"]["t"]
            pvals[m.key] = None if t is None else float(1 - norm.cdf(t))
        disc = benjamini_hochberg(pvals)
        valid = sorted(k for k in disc if (res[k]["bestaetigung"]["t"] or 0) > CONFIRM_T)
        for k, v in res.items():
            v["entdeckt"], v["gueltig"] = k in disc, k in valid
        cur, p_up = {}, {}
        for c in MAJORS:
            keys = [m.key for m in MODELS if m.currency == c]
            S = pd.DataFrame({k: sig[k] for k in keys})
            X, y = S.reindex(days), fwd[c].reindex(days)
            cb = combo(X, y)
            p_up[c] = float(cb["model"].predict_proba(S.loc[[last]].values)[:, 1][0]) if cb["model"] else None
            cur[c] = {"all": tally({k: int(S.at[last, k]) for k in keys}),
                      "checked": tally({k: int(S.at[last, k]) for k in keys if k in valid}),
                      "vote_test": vote_test(X, y),
                      "combo": {"p_up": p_up[c], "confirm": cb["confirm"], "test": cb["test"], "weights": cb["weights"],
                                "confirmed": cb["confirmed"]}}
        pairs = {}
        for p in ALL_PAIRS:
            b, q = p[:3], p[3:]
            votes = {**cur[b]["all"]["votes"], **{k: -v for k, v in cur[q]["all"]["votes"].items()}}
            pb, pq = p_up[b], p_up[q]
            pairs[p] = {"all": tally(votes),
                        "p_up": None if pb is None or pq is None else float(pb * (1 - pq) / (pb * (1 - pq) + pq * (1 - pb)))}
        out["horizons"][h] = {"models": res, "valid": valid, "currencies": cur, "pairs": pairs, "date": str(last.date())}
    return out
