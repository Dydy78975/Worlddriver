"""Prüfung der Einzelsignale und Abstimmung je Paar.

Regeln (festgelegt vor dem Blick auf den Schlusstest, nicht nachträglich anpassen):
  1. Drei Zeiträume: Entdeckung 1999–2012, Bestätigung 2013–2019, Schlusstest ab 2020.
  2. Ergebnis = Kursänderung in Signalrichtung bis zum Horizont, abzüglich 0,03 % Kosten bei jedem neuen
     oder gedrehten Signal.
  3. Geprüft wird jede Kombination Signal × Währung: Ergebnis je Entscheidungstag = Mittel über die
     7 Paare dieser Währung. „Gültig“ für eine Währung ist ein Signal, wenn es
       a) in der Entdeckung nach Benjamini-Hochberg-Korrektur (10 %) über ALLE Kombinationen des Horizonts
          signifikant positiv ist, und
       b) in der Bestätigung für dieselbe Währung positiv bleibt (t-Wert > 1).
     Ein gültiges Signal stimmt bei allen 7 Paaren dieser Währung mit (bei einem Paar höchstens einmal).
  4. Der Schlusstest ab 2020 wird für keine Entscheidung genutzt. Er zeigt ehrlich, wie gut die gültigen
     Signale und die Abstimmung danach tatsächlich waren.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS
from forex_nexus.signals.data import Inputs
from forex_nexus.signals.library import FUNDAMENTAL_VOTE, SIGNALS

PERIODS = {"entdeckung": (1999, 2012), "bestaetigung": (2013, 2019), "schlusstest": (2020, 2100)}
HORIZONS = {"1D": "Tag", "1W": "Woche"}
COST = 0.0003
FDR = 0.10
CONFIRM_T = 1.0
PERIODS_PER_YEAR = {"1D": 252, "1W": 52}
VOTE_BUCKETS = [("klar long", 0.70, 1.01), ("eher long", 0.55, 0.70), ("unentschieden", 0.45, 0.55),
                ("eher short", 0.30, 0.45), ("klar short", -0.01, 0.30)]


def grid(closes: pd.DataFrame, horizon: str) -> tuple[pd.DatetimeIndex, pd.DataFrame]:
    """Entscheidungstage und Kursänderung bis zum Horizont (Log). Woche = letzter Handelstag der Woche
    bis zum letzten Handelstag der Folgewoche."""
    lp = np.log(closes)
    if horizon == "1D":
        return closes.index, lp.shift(-1) - lp
    wk = closes.index.to_period("W-FRI")
    last = pd.Series(wk, index=closes.index) != pd.Series(wk, index=closes.index).shift(-1)
    days = closes.index[last.values]
    w = lp.loc[days]
    return days, w.shift(-1) - w


def evaluate(sig: pd.DataFrame, fwd: pd.DataFrame, days: pd.DatetimeIndex) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """Liefert (Ergebnis je Entscheidungstag, Signal, Nettoergebnis je Paar)."""
    s = sig.reindex(days).fillna(0)
    r = fwd.reindex(days)
    s = s.where(r.notna(), 0)
    new = (s != s.shift(1)) & (s != 0)
    net = (s * r.fillna(0) - COST * new).where(s != 0)
    return net.mean(axis=1).dropna(), s, net


def stats(daily: pd.Series, s: pd.DataFrame, net: pd.DataFrame, horizon: str, years: tuple[int, int]) -> dict:
    m = (daily.index.year >= years[0]) & (daily.index.year <= years[1])
    d = daily[m]
    n = len(d)
    if n < 20:
        return {"n": n, "mean": None, "t": None, "annual": None, "hit": None, "trades": 0, "years_pos": None}
    sd = d.std(ddof=1)
    t = float(d.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0
    sel = s.index.year >= years[0]
    sel &= s.index.year <= years[1]
    nn = net[sel].stack()
    yearly = d.groupby(d.index.year).mean()
    return {"n": n, "mean": float(d.mean()), "t": t, "annual": float(d.mean() * PERIODS_PER_YEAR[horizon]),
            "hit": float((nn > 0).mean()) if len(nn) else None, "trades": int(len(nn)),
            "years_pos": float((yearly > 0).mean()), "yearly": {int(y): float(v) for y, v in yearly.items()}}


def benjamini_hochberg(p: dict, q: float = FDR) -> set:
    items = sorted((v, k) for k, v in p.items() if v is not None)
    m = len(items)
    passed = 0
    for i, (pv, _) in enumerate(items, start=1):
        if pv <= q * i / m:
            passed = i
    return {k for _, k in items[:passed]}


def run(inputs: Inputs) -> dict:
    sigs = {s.key: s.rule(inputs).reindex(columns=ALL_PAIRS).fillna(0).astype(int) for s in SIGNALS}
    out = {"rules": {"periods": PERIODS, "cost": COST, "fdr": FDR, "confirm_t": CONFIRM_T,
                     "tests_per_horizon": len(sigs) * len(MAJORS)}, "horizons": {}}
    for h in HORIZONS:
        days, fwd = grid(inputs.closes, h)
        res, pvals = {}, {}
        for key, sig in sigs.items():
            panel, s, net = evaluate(sig, fwd, days)
            per_ccy = {}
            for c in MAJORS:
                cols = [p for p in ALL_PAIRS if c in (p[:3], p[3:])]
                st = {name: stats(net[cols].mean(axis=1).dropna(), s[cols], net[cols], h, yrs) for name, yrs in PERIODS.items()}
                per_ccy[c] = st
                t = st["entdeckung"]["t"]
                pvals[(key, c)] = None if t is None else float(1 - norm.cdf(t))
            res[key] = {"panel": {name: stats(panel, s, net, h, yrs) for name, yrs in PERIODS.items()}, "currencies": per_ccy}
        disc = benjamini_hochberg(pvals)
        valid = {u for u in disc if (res[u[0]]["currencies"][u[1]]["bestaetigung"]["t"] or 0) > CONFIRM_T}
        members = {p: sorted({k for k, c in valid if c in (p[:3], p[3:])}) for p in ALL_PAIRS}
        for k, v in res.items():
            for c, st in v["currencies"].items():
                st["entdeckt"], st["gueltig"] = (k, c) in disc, (k, c) in valid
        last = inputs.closes.index[-1]
        vote = votes(sigs, members)
        fund_members = {p: FUNDAMENTAL_VOTE for p in ALL_PAIRS}
        fund = votes(sigs, fund_members)
        out["horizons"][h] = {"signals": res, "valid": sorted(valid), "members": members,
                              "checked": {"test": vote_backtest(vote, fwd, days, h), "current": current_vote(vote, sigs, last)},
                              "fundamental": {"test": vote_backtest(fund, fwd, days, h), "current": current_vote(fund, sigs, last)}}
    return out


def votes(sigs: dict, members: dict) -> dict:
    """Je Paar: Anzahl long- und short-Stimmen der für dieses Paar gültigen Signale an jedem Tag."""
    bull, bear = {}, {}
    members = {p: list(members[p]) for p in ALL_PAIRS}
    for p in ALL_PAIRS:
        keys = members[p]
        if not keys:
            continue
        m = pd.concat([sigs[k][p] for k in keys], axis=1)
        bull[p], bear[p] = (m > 0).sum(axis=1), (m < 0).sum(axis=1)
    return {"bull": pd.DataFrame(bull), "bear": pd.DataFrame(bear), "members": members}


def label(share: float | None) -> str:
    if share is None:
        return "kein Signal"
    return next(name for name, lo, hi in VOTE_BUCKETS if lo <= share < hi)


def vote_backtest(vote: dict, fwd: pd.DataFrame, days: pd.DatetimeIndex, horizon: str) -> dict:
    """Wie gut war die Abstimmung im Schlusstest (ab 2020)? Je Stufe: Anzahl, Trefferquote, Ø Ergebnis."""
    if vote["bull"].empty:
        return {"n": 0, "from": None, "buckets": {}, "all": _hit_summary(pd.DataFrame()), "horizon": horizon,
                "before_costs": True}
    start = pd.Timestamp(f"{PERIODS['schlusstest'][0]}-01-01")
    d = days[days >= start]
    bull, bear = vote["bull"].reindex(d).fillna(0), vote["bear"].reindex(d).fillna(0)
    r = fwd.reindex(d)[bull.columns]
    tot = bull + bear
    share = (bull / tot.replace(0, np.nan))
    direction = np.sign(bull - bear)
    rows = []
    for p in bull.columns:
        for day in d:
            sh, rr, di = share.at[day, p], r.at[day, p], direction.at[day, p]
            if np.isnan(sh) or np.isnan(rr):
                continue
            rows.append((day, label(sh), di, rr * di if di else 0.0, (np.sign(rr) == di) if di and rr else None))
    df = pd.DataFrame(rows, columns=["day", "label", "dir", "ret", "hit"])
    out = {}
    for name, _, _ in VOTE_BUCKETS:
        g = df[df["label"] == name]
        out[name] = _hit_summary(g[g["dir"] != 0])
        out[name]["n"] = int(len(g))
    return {"n": int(len(df)), "from": str(d[0].date()) if len(d) else None, "buckets": out,
            "all": _hit_summary(df[df["dir"] != 0]), "horizon": horizon, "before_costs": True}


def _hit_summary(g: pd.DataFrame) -> dict:
    """Trefferquote mit 95-%-Intervall. Paare desselben Tages hängen zusammen, deshalb zählt für das
    Intervall jeder Entscheidungstag nur einmal (vorsichtig)."""
    if g.empty:
        return {"hit": None, "avg_return": None, "ci": None, "days": 0}
    hit = float(g["hit"].astype(float).mean())
    days = int(g["day"].nunique())
    return {"hit": hit, "avg_return": float(g["ret"].mean()), "days": days, "ci": wilson(hit, days)}


def wilson(p: float, n: int, z: float = 1.96):
    if n == 0:
        return None
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(c - h), float(c + h)]


def current_vote(vote: dict, sigs: dict, day: pd.Timestamp) -> dict:
    out = {}
    for p in ALL_PAIRS:
        keys = vote["members"][p]
        detail = [{"signal": k, "vote": int(sigs[k].at[day, p])} for k in keys]
        bull = sum(1 for x in detail if x["vote"] > 0)
        bear = sum(1 for x in detail if x["vote"] < 0)
        share = bull / (bull + bear) if bull + bear else None
        out[p] = {"bull": bull, "bear": bear, "neutral": len(keys) - bull - bear, "total": len(keys),
                  "share_bull": share, "label": label(share), "signals": detail}
    return {"date": str(day.date()), "pairs": out}
