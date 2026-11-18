"""COT-Positionierung, Saisonalität und Konfluenz je Paar – mit historischer Trefferquote.

Point-in-Time-Regeln:
* COT gilt erst ab Veröffentlichung (Freitag 15:30 New York), nicht ab dem Stichtag (Dienstag).
* Saisonalität für ein Jahr Y nutzt nur Jahre vor Y.
* Trend (Währungsstärke) nutzt nur Kurse bis zum Entscheidungszeitpunkt.
Die Konfluenz ist eine REGEL, kein trainiertes Modell. Wie gut sie früher funktioniert hätte, wird
mit genau denselben Regeln über die Vergangenheit gemessen und neben jedem Signal angezeigt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS

NEW_YORK = ZoneInfo("America/New_York")
COT_WINDOW = 156            # Wochen (3 Jahre) für den COT-Index
COT_EXTREME = (20, 80)      # Extremzonen des Index
COT_DIFF = 20               # Mindestabstand der COT-Indizes zweier Währungen für ein Paarsignal
TREND_DAYS = 20             # Handelstage für die Währungsstärke
TREND_MIN = 0.5             # Mindestunterschied in % für ein Trendsignal
SEASON_HIT = 0.6            # Saisonsignal, wenn ≥ 60 % (bzw. ≤ 40 %) der Vorjahre gleich liefen
SEASON_MIN_YEARS = 8

CCY_NAME = {"USD": "US-Dollar", "EUR": "Euro", "JPY": "Yen", "GBP": "Pfund", "CHF": "Franken",
            "CAD": "Kanadischer Dollar", "AUD": "Australischer Dollar", "NZD": "Neuseeland-Dollar"}
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
             "November", "Dezember"]


# --------------------------------------------------------------------------- COT

def cot_indices(cot: pd.DataFrame, window: int = COT_WINDOW) -> pd.DataFrame:
    """cot: Spalten currency, report_date, available_at, comm_long/short, noncomm_long/short, open_interest."""
    out = []
    for ccy, g in cot.sort_values("report_date").groupby("currency"):
        g = g.copy()
        g["comm_net"] = g["comm_long"] - g["comm_short"]
        g["spec_net"] = g["noncomm_long"] - g["noncomm_short"]
        g["small_net"] = (g["nonrept_long"] - g["nonrept_short"]) if "nonrept_long" in g else np.nan
        for col, name in (("comm_net", "comm_idx"), ("spec_net", "spec_idx"), ("small_net", "small_idx")):
            if g[col].isna().all():
                g[name] = np.nan
                continue
            lo = g[col].rolling(window, min_periods=52).min()
            hi = g[col].rolling(window, min_periods=52).max()
            g[name] = ((g[col] - lo) / (hi - lo).replace(0, np.nan) * 100).clip(0, 100)
        g["comm_chg_4w"] = g["comm_net"].diff(4)
        g["spec_chg_4w"] = g["spec_net"].diff(4)
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else cot


def cot_as_of(idx: pd.DataFrame, when: datetime) -> pd.DataFrame:
    """Letzter veröffentlichter Bericht je Währung zum Zeitpunkt `when`."""
    known = idx[idx["available_at"] <= when]
    return known.sort_values("report_date").groupby("currency").tail(1).set_index("currency")


def cot_label(v: float | None) -> str:
    if v is None or np.isnan(v):
        return "keine Daten"
    if v >= COT_EXTREME[1]:
        return "extrem hoch"
    if v <= COT_EXTREME[0]:
        return "extrem tief"
    return "neutral"


# --------------------------------------------------------------------------- Saisonalität

def monthly_returns(closes: pd.DataFrame) -> pd.DataFrame:
    c = closes.copy()
    c.index = pd.to_datetime(c.index)
    return np.log(c.resample("ME").last()).diff().dropna(how="all")


def season_stats(monthly: pd.DataFrame, before_year: int | None = None) -> dict:
    """Je Spalte und Kalendermonat: Mittelwert, Trefferquote (Anteil positiver Jahre), Anzahl, t-Wert."""
    m = monthly if before_year is None else monthly[monthly.index.year < before_year]
    stats = {}
    for col in m.columns:
        s = m[col].dropna()
        per = {}
        for month in range(1, 13):
            x = s[s.index.month == month]
            if len(x) < 3:
                continue
            sd = x.std(ddof=1)
            per[month] = {"mean": float(x.mean()), "hit": float((x > 0).mean()), "n": int(len(x)),
                          "t": float(x.mean() / (sd / np.sqrt(len(x)))) if sd > 0 else 0.0}
        stats[col] = per
    return stats


def season_signal(st: dict | None) -> int:
    if not st or st["n"] < SEASON_MIN_YEARS:
        return 0
    return 1 if st["hit"] >= SEASON_HIT else -1 if st["hit"] <= 1 - SEASON_HIT else 0


def season_validation(monthly: pd.DataFrame, first_year: int = 2008) -> dict:
    """Hätte die Saisonalität funktioniert? Je Jahr nur Vorjahre nutzen und die Richtung des Monats prüfen."""
    hits = []
    for year in range(first_year, monthly.index.year.max() + 1):
        prior = season_stats(monthly, before_year=year)
        cur = monthly[monthly.index.year == year]
        for ts, row in cur.iterrows():
            for col in monthly.columns:
                sig = season_signal(prior.get(col, {}).get(ts.month))
                if sig and not np.isnan(row[col]) and row[col] != 0:
                    hits.append(np.sign(row[col]) == sig)
    n = len(hits)
    return {"n": n, "hit_rate": float(np.mean(hits)) if n else None, "ci": _wilson(sum(hits), n)}


# --------------------------------------------------------------------------- Konfluenz

@dataclass
class PairView:
    pair: str
    direction: int
    confluence: int
    factors: dict          # Faktor -> {signal, value, text}
    against: list


def strength_change(strength: pd.DataFrame, upto: pd.Timestamp, days: int = TREND_DAYS) -> pd.Series:
    s = strength[strength.index <= upto]
    if len(s) <= days:
        return pd.Series(np.nan, index=strength.columns)
    return (s.iloc[-1] - s.iloc[-1 - days]) * 100


def pair_view(pair: str, cot_now: pd.DataFrame, trend: pd.Series, season: dict, month: int) -> PairView:
    b, q = pair[:3], pair[3:]
    f = {}
    cb = cot_now["comm_idx"].get(b, np.nan) if not cot_now.empty else np.nan
    cq = cot_now["comm_idx"].get(q, np.nan) if not cot_now.empty else np.nan
    diff = cb - cq
    sig = 0 if np.isnan(diff) else (1 if diff >= COT_DIFF else -1 if diff <= -COT_DIFF else 0)
    f["cot"] = {"signal": sig, "value": None if np.isnan(diff) else float(diff),
                "text": "keine Daten" if np.isnan(diff) else
                f"Commercials-Index {b} {cb:.0f} vs. {q} {cq:.0f} (Differenz {diff:+.0f})"}
    td = trend.get(b, np.nan) - trend.get(q, np.nan)
    sig = 0 if np.isnan(td) else (1 if td >= TREND_MIN else -1 if td <= -TREND_MIN else 0)
    f["trend"] = {"signal": sig, "value": None if np.isnan(td) else float(td),
                  "text": "keine Daten" if np.isnan(td) else f"Stärke 20 Tage: {b} {trend.get(b):+.2f} %, {q} {trend.get(q):+.2f} %".replace(".", ",")}
    st = season.get(pair, {}).get(month)
    sig = season_signal(st)
    f["season"] = {"signal": sig, "value": None if not st else float(st["mean"]),
                   "text": "zu wenige Jahre" if not st else
                   f"{MONTHS_DE[month - 1]}: in {st['hit'] * 100:.0f} % von {st['n']} Jahren gestiegen, Ø {st['mean'] * 100:+.2f} %".replace(".", ",")}
    total = sum(x["signal"] for x in f.values())
    direction = int(np.sign(total))
    confluence = sum(1 for x in f.values() if direction and x["signal"] == direction)
    against = [k for k, x in f.items() if direction and x["signal"] == -direction]
    return PairView(pair, direction, confluence, f, against)


def confluence_backtest(closes: pd.DataFrame, strength: pd.DataFrame, cot_idx: pd.DataFrame,
                        monthly: pd.DataFrame, start: str = "2008-01-01") -> dict:
    """Jede Woche (Freitagabend) die Regel anwenden, Ergebnis = Kursänderung Montag bis Freitag der Folgewoche."""
    c = closes.copy()
    c.index = pd.to_datetime(c.index)
    dates = c.index
    fridays = pd.date_range(start, dates.max() - pd.Timedelta(days=8), freq="W-FRI")
    season_cache: dict[int, dict] = {}
    rows = []
    for fri in fridays:
        when = datetime.combine(fri.date(), time(18, 0), NEW_YORK)
        cot_now = cot_as_of(cot_idx, when) if not cot_idx.empty else pd.DataFrame()
        trend = strength_change(strength, fri)
        y = fri.year
        if y not in season_cache:
            season_cache[y] = season_stats(monthly, before_year=y)
        nxt = dates[dates > fri]
        if len(nxt) < 5:
            continue
        entry, exit_ = nxt[0], nxt[min(4, len(nxt) - 1)]
        month = entry.month
        for pair in ALL_PAIRS:
            v = pair_view(pair, cot_now, trend, season_cache[y], month)
            if not v.direction:
                continue
            r = np.log(c.at[exit_, pair] / c.at[entry, pair])
            if np.isnan(r) or r == 0:
                continue
            rows.append((v.confluence, np.sign(r) == v.direction, r * v.direction))
    df = pd.DataFrame(rows, columns=["confluence", "hit", "ret"])
    out = {}
    for k, g in df.groupby("confluence"):
        out[int(k)] = {"n": int(len(g)), "hit_rate": float(g["hit"].mean()), "avg_return": float(g["ret"].mean()),
                       "ci": _wilson(int(g["hit"].sum()), len(g))}
    return out


def cot_extreme_backtest(cot_idx: pd.DataFrame, strength: pd.DataFrame, weeks: int = 4) -> dict:
    """Commercials-Index extrem → Währungsstärke über die folgenden `weeks` Wochen ab Veröffentlichung."""
    s = strength.copy()
    s.index = pd.to_datetime(s.index)
    res = {"hoch": [], "tief": []}
    for _, r in cot_idx.dropna(subset=["comm_idx"]).iterrows():
        start = pd.Timestamp(r["available_at"].astimezone(NEW_YORK).date()) + pd.Timedelta(days=3)
        win = s.loc[start:start + pd.Timedelta(weeks=weeks), r["currency"]].dropna()
        if len(win) < 5:
            continue
        chg = win.iloc[-1] - win.iloc[0]
        if r["comm_idx"] >= COT_EXTREME[1]:
            res["hoch"].append(chg > 0)
        elif r["comm_idx"] <= COT_EXTREME[0]:
            res["tief"].append(chg < 0)
    return {k: {"n": len(v), "hit_rate": float(np.mean(v)) if v else None, "ci": _wilson(int(sum(v)), len(v))}
            for k, v in res.items()}


def currency_scores(cot_now: pd.DataFrame, trend: pd.Series, season_ccy: dict, month: int) -> dict:
    """Gesamteinschätzung je Währung aus den drei Faktoren (−1 … +1)."""
    out = {}
    for c in MAJORS:
        parts = []
        ci = cot_now["comm_idx"].get(c, np.nan) if not cot_now.empty else np.nan
        parts.append(None if np.isnan(ci) else (ci - 50) / 50)
        t = trend.get(c, np.nan)
        parts.append(None if np.isnan(t) else float(np.clip(t / 1.5, -1, 1)))
        st = season_ccy.get(c, {}).get(month)
        parts.append(None if not st else float(np.clip(st["mean"] / 0.005, -1, 1)))
        vals = [p for p in parts if p is not None]
        out[c] = {"score": float(np.mean(vals)) if vals else 0.0, "cot": parts[0], "trend": parts[1], "season": parts[2],
                  "cot_idx": None if np.isnan(ci) else float(ci), "trend_pct": None if np.isnan(t) else float(t),
                  "season_mean": None if not st else st["mean"], "season_hit": None if not st else st["hit"]}
    return out


def _wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(c - h), float(c + h)]


def pips(pair: str, price: float, log_move: float) -> float:
    pip = 0.01 if pair.endswith("JPY") else 0.0001
    return price * (np.exp(log_move) - 1) / pip
