"""Zusätzliche Auswertungen für die Website: saisonaler Jahresverlauf, Saison-Screener mit
Mehrfachtest-Korrektur, Währungsstärke über Tag/Woche/Monat und eine beschreibende Marktstimmung."""

from __future__ import annotations

from datetime import date, timedelta
from math import comb

import numpy as np
import pandas as pd

LOOKBACKS = {"5": 5, "10": 10, "15": 15, "20": 20, "max": None}
SCREEN_YEARS = 15
SCREEN_LENGTHS = (10, 20, 30)       # Kalendertage
SCREEN_AHEAD = 28                   # Starttage in den nächsten 4 Wochen


def seasonal_paths(closes: pd.DataFrame, this_year: int) -> dict:
    """Durchschnittlicher Jahresverlauf je Paar (Basis 100 am Jahresanfang), nur abgeschlossene Jahre."""
    c = closes.copy()
    c.index = pd.to_datetime(c.index)
    out = {}
    years_all = sorted(y for y in c.index.year.unique() if y < this_year)
    for pair in c.columns:
        s = c[pair].dropna()
        yearly = {}
        for y in years_all:
            ys = s[s.index.year == y]
            if len(ys) < 200:
                continue
            doy = np.minimum(ys.index.day_of_year.values, 365)
            v = pd.Series(ys.values / ys.iloc[0] * 100, index=doy).groupby(level=0).last()
            yearly[y] = v.reindex(range(1, 366)).ffill().bfill().values
        res = {}
        for key, n in LOOKBACKS.items():
            ys_sel = [y for y in sorted(yearly) if n is None or y >= this_year - n]
            if len(ys_sel) < 3:
                continue
            res[key] = {"years": [ys_sel[0], ys_sel[-1]], "n": len(ys_sel),
                        "path": [round(float(x), 2) for x in np.mean([yearly[y] for y in ys_sel], axis=0)]}
        out[pair] = res
    return out


def _binom_p(k: int, n: int) -> float:
    """Zweiseitiger exakter Binomialtest gegen 50 %."""
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def season_screener(closes: pd.DataFrame, today: date) -> list[dict]:
    """Für jedes Paar das Zeitfenster (Start in den nächsten 4 Wochen, 10/20/30 Tage) mit dem
    deutlichsten Muster der letzten 15 Jahre. 'Muster' nur, wenn es die Bonferroni-Korrektur über alle
    durchsuchten Fenster dieses Paares besteht – sonst 'kein Muster'."""
    c = closes.copy()
    c.index = pd.to_datetime(c.index)
    years = list(range(today.year - SCREEN_YEARS, today.year))
    tests = SCREEN_AHEAD * len(SCREEN_LENGTHS)
    out = []
    for pair in c.columns:
        s = c[pair].dropna()
        best = None
        for d in range(SCREEN_AHEAD):
            start = today + timedelta(days=d)
            for L in SCREEN_LENGTHS:
                rets = []
                for y in years:
                    try:
                        a = date(y, start.month, min(start.day, 28))
                    except ValueError:
                        continue
                    b = a + timedelta(days=L)
                    sa, sb = s[s.index >= pd.Timestamp(a)], s[s.index >= pd.Timestamp(b)]
                    if sa.empty or sb.empty:
                        continue
                    rets.append(np.log(sb.iloc[0] / sa.iloc[0]))
                n = len(rets)
                if n < 10:
                    continue
                up = sum(r > 0 for r in rets)
                k = max(up, n - up)
                p = _binom_p(up, n)
                if best is None or p < best["p"] or (p == best["p"] and abs(np.mean(rets)) > abs(best["mean"])):
                    best = {"pair": pair, "start": start.isoformat(), "end": (start + timedelta(days=L)).isoformat(),
                            "days": L, "in_days": d, "n": n, "hits": int(k), "direction": 1 if up >= n - up else -1,
                            "mean": float(np.mean(rets)), "median": float(np.median(rets)), "p": p,
                            "yearly": [round(float(r) * 100, 2) for r in rets]}
        if best:
            best["p_adj"] = min(1.0, best["p"] * tests)
            best["pattern"] = best["p_adj"] < 0.05
            best["tests"] = tests
            out.append(best)
    return sorted(out, key=lambda x: (x["in_days"], x["p"]))


def strength_windows(strength: pd.DataFrame) -> dict:
    s = strength.dropna()
    return {k: {c: round(float((s[c].iloc[-1] - s[c].iloc[-1 - n]) * 100), 3) for c in s.columns}
            for k, n in (("1T", 1), ("1W", 5), ("1M", 20))}


def market_mood(vix: pd.Series, closes: pd.DataFrame, strength: pd.DataFrame) -> dict:
    """Beschreibende Marktstimmung (keine Prognose): VIX gegen eigenen 1-Jahres-Median, AUD/JPY-Trend
    als klassisches Risiko-Barometer, Dollar-Trend gegen den Korb."""
    v = vix.dropna()
    v.index = pd.to_datetime(v.index)
    last, med = float(v.iloc[-1]), float(v.iloc[-252:].median())
    pct = float((v.iloc[-252:] < last).mean())
    aj = closes["AUDJPY"].dropna()
    aj_chg = float(np.log(aj.iloc[-1] / aj.iloc[-21]) * 100)
    usd = float((strength["USD"].dropna().iloc[-1] - strength["USD"].dropna().iloc[-21]) * 100)
    score = (1 if last < med else -1) + (1 if aj_chg > 0 else -1)
    label = "Risk-on" if score >= 2 else "Risk-off" if score <= -2 else "gemischt"
    return {"label": label, "vix": round(last, 2), "vix_median_1y": round(med, 2), "vix_percentile_1y": round(pct, 3),
            "audjpy_20d": round(aj_chg, 2), "usd_20d": round(usd, 2),
            "text": {"Risk-on": "Ruhige Märkte: VIX unter seinem Jahresmittel und AUD/JPY steigt – Anleger gehen ins Risiko.",
                     "Risk-off": "Nervöse Märkte: VIX über seinem Jahresmittel und AUD/JPY fällt – Kapital sucht sichere Häfen.",
                     "gemischt": "Gemischtes Bild: VIX und AUD/JPY zeigen in unterschiedliche Richtungen."}[label]}
