"""Krypto-Analysen – jede mit ehrlicher historischer Prüfung.

* Schwankung: EWMA-Volatilität -> 80-%-Spanne für Tag/Woche/Monat; Trefferquote der Spanne im Walk-Forward.
* Trend (200-Tage-Linie) und Momentum (30 Tage): Strategie gegen Kaufen-und-Halten, mit Gebühren.
* Stimmung: Fear & Greed – was passierte nach extremer Angst bzw. Gier (nicht überlappende Fälle).
* COT: CME-Futures auf Bitcoin und Ether (Index 0–100 über 3 Jahre).
* Saisonalität: Monate und Wochentage, mit Hinweis auf die kleine Zahl an Jahren.
"""

from __future__ import annotations

from math import comb

import numpy as np
import pandas as pd

FEE = 0.001             # 0,1 % je Wechsel (typische Börsengebühr)
LAMBDA = 0.94
HORIZONS = {"1T": 1, "1W": 7, "1M": 30}     # Kalendertage (Krypto handelt täglich)


def _wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(float(c - h), 4), round(float(c + h), 4)]


def _binom_p(k, n):
    lo = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(lo + 1)) / 2 ** n)


def ewma_vol(r: pd.Series) -> pd.Series:
    return np.sqrt((r ** 2).ewm(alpha=1 - LAMBDA, adjust=False, min_periods=30).mean())


def ranges(prices: pd.DataFrame) -> dict:
    """Erwartete 80-%-Spanne je Coin und Horizont + historische Trefferquote (nur Vergangenheit genutzt)."""
    out = {}
    for c in prices:
        p = prices[c].dropna()
        r = np.log(p).diff()
        sig = ewma_vol(r)
        res = {}
        for k, h in HORIZONS.items():
            fwd = np.log(p.shift(-h) / p)
            z = (fwd / (sig * np.sqrt(h))).dropna()
            hits = []
            for i in range(365, len(z), max(1, h)):          # Walk-Forward: Quantile nur aus Daten vor dem Tag
                past = z.iloc[:max(0, i - h)]
                if len(past) < 300:
                    continue
                lo, hi = past.quantile(0.1), past.quantile(0.9)
                hits.append(lo <= z.iloc[i] <= hi)
            zall = z.iloc[:-1] if len(z) > 1 else z
            lo, hi = float(zall.quantile(0.1)), float(zall.quantile(0.9))
            s = float(sig.iloc[-1] * np.sqrt(h))
            res[k] = {"low": round(float(np.exp(lo * s) - 1), 5), "high": round(float(np.exp(hi * s) - 1), 5),
                      "vol": round(s, 5), "coverage": round(float(np.mean(hits)), 4) if hits else None, "n": len(hits)}
        out[c] = res
    return out


def _stats(eq: pd.Series, daily: pd.Series) -> dict:
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    vol = daily.std() * np.sqrt(365)
    return {"cagr": round(float(cagr), 4), "max_dd": round(float(dd), 4),
            "sharpe": round(float(daily.mean() * 365 / vol), 2) if vol > 0 else None,
            "total": round(float(eq.iloc[-1] - 1), 4)}


def trend_backtest(prices: pd.DataFrame) -> dict:
    """Regel A: halten, solange der Schlusskurs über der 200-Tage-Linie liegt (sonst Cash).
    Regel B: halten, wenn die Rendite der letzten 30 Tage positiv ist.
    Entscheidung am Tagesende, Umsetzung am nächsten Tag; 0,1 % Gebühr je Wechsel."""
    out = {}
    for c in prices:
        p = prices[c].dropna()
        p.index = pd.to_datetime(p.index)
        r = p.pct_change().fillna(0)
        res = {"hold": None, "sma200": None, "mom30": None}
        if len(p) < 400:
            out[c] = res
            continue
        start = p.index[200]
        sig = {"sma200": (p > p.rolling(200).mean()).astype(float),
               "mom30": (p / p.shift(30) - 1 > 0).astype(float)}
        rr = r[start:]
        res["hold"] = _stats((1 + rr).cumprod(), rr)
        for k, s in sig.items():
            pos = s.shift(1).fillna(0)[start:]
            trades = pos.diff().abs().fillna(pos.iloc[0])
            daily = pos * rr - trades * FEE
            eq = (1 + daily).cumprod()
            st = _stats(eq, daily)
            st["time_in_market"] = round(float(pos.mean()), 3)
            st["trades"] = int(trades.sum())
            res[k] = st
            res[k + "_curve"] = [[str(d.date()), round(float(v), 4)] for d, v in eq.iloc[::7].items()]
        res["hold_curve"] = [[str(d.date()), round(float(v), 4)] for d, v in (1 + rr).cumprod().iloc[::7].items()]
        res["signal_now"] = {"sma200": bool(sig["sma200"].iloc[-1]), "mom30": bool(sig["mom30"].iloc[-1]),
                             "sma200_level": round(float(p.rolling(200).mean().iloc[-1]), 6),
                             "dist_sma200": round(float(p.iloc[-1] / p.rolling(200).mean().iloc[-1] - 1), 4),
                             "mom30_value": round(float(p.iloc[-1] / p.iloc[-31] - 1), 4)}
        out[c] = res
    return out


def _rule(p: pd.Series, kind: str, n: int) -> pd.Series:
    return ((p > p.rolling(n).mean()) if kind == "sma" else (p / p.shift(n) - 1 > 0)).astype(float)


def _run(p: pd.Series, s: pd.Series, start) -> dict:
    r = p.pct_change().fillna(0)[start:]
    pos = s.shift(1).fillna(0)[start:]
    trades = pos.diff().abs().fillna(pos.iloc[0])
    daily = pos * r - trades * FEE
    return _stats((1 + daily).cumprod(), daily)


def robustness(prices: pd.DataFrame) -> dict:
    """Gegenprobe gegen Rosinenpicken: viele Längen statt nur 200/30 und beide Zeithälften getrennt.
    Gezählt wird, wie oft die Regel ein besseres Rendite-Risiko-Verhältnis (Sharpe) als Halten hat
    und wie oft der größte Verlust kleiner ist."""
    grid = {"sma": [50, 100, 150, 200, 250], "mom": [10, 20, 30, 60, 90]}
    out = {"grid": grid, "coins": {}}
    for c in prices:
        p = prices[c].dropna()
        p.index = pd.to_datetime(p.index)
        if len(p) < 700:
            continue
        start = p.index[260]
        mid = p.index[260 + (len(p) - 260) // 2]
        hold = _run(p, pd.Series(1.0, index=p.index), start)
        cell = {"hold": hold, "sma": {}, "mom": {}, "halves": {}}
        for kind, ns in grid.items():
            for n in ns:
                st = _run(p, _rule(p, kind, n), start)
                cell[kind][n] = {"sharpe": st["sharpe"], "max_dd": st["max_dd"], "cagr": st["cagr"]}
        for half, (a, b) in (("1", (start, mid)), ("2", (mid, p.index[-1]))):
            seg = p[:b]
            h = _run(seg, pd.Series(1.0, index=seg.index), a)
            cell["halves"][half] = {"from": str(a.date()), "to": str(b.date()), "hold": h["sharpe"],
                                    "sma200": _run(seg, _rule(seg, "sma", 200), a)["sharpe"],
                                    "mom30": _run(seg, _rule(seg, "mom", 30), a)["sharpe"]}
        out["coins"][c] = cell
    tests = [(c, k, n) for c, v in out["coins"].items() for k in grid for n in grid[k]]
    out["better_sharpe"] = sum(out["coins"][c][k][n]["sharpe"] > out["coins"][c]["hold"]["sharpe"] for c, k, n in tests)
    out["smaller_dd"] = sum(out["coins"][c][k][n]["max_dd"] > out["coins"][c]["hold"]["max_dd"] for c, k, n in tests)
    out["tests"] = len(tests)
    return out


def fng_study(fng: pd.Series, btc: pd.Series, days: int = 30) -> dict:
    """Bitcoin-Rendite über `days` Tage nach extremer Angst (< 20) bzw. Gier (> 80), nicht überlappend,
    verglichen mit allen Tagen."""
    f = fng.copy()
    f.index = pd.to_datetime(f.index)
    b = btc.dropna()
    b.index = pd.to_datetime(b.index)
    fwd = (b.shift(-days) / b - 1).reindex(f.index).dropna()
    base = fwd.copy()
    out = {"days": days, "all": {"n": int(len(base)), "mean": round(float(base.mean()), 4),
                                  "hit": round(float((base > 0).mean()), 4)}}
    for name, cond in (("fear", f < 20), ("greed", f > 80)):
        picks, last = [], None
        for d in f.index[cond.reindex(f.index, fill_value=False)]:
            if d in fwd.index and (last is None or (d - last).days >= days):
                picks.append(fwd[d])
                last = d
        x = np.array(picks)
        k = int((x > 0).sum())
        out[name] = {"n": len(x), "mean": round(float(x.mean()), 4) if len(x) else None,
                     "median": round(float(np.median(x)), 4) if len(x) else None,
                     "hit": round(k / len(x), 4) if len(x) else None, "ci": _wilson(k, len(x)),
                     "p": round(_binom_p(k, len(x)), 4) if len(x) else None}
    return out


def cot_view(cot: pd.DataFrame) -> dict:
    out = {}
    for c, g in cot.sort_values("report_date").groupby("coin"):
        g = g.copy()
        for col in ("comm_net", "spec_net", "small_net"):
            lo, hi = g[col].rolling(156, min_periods=52).min(), g[col].rolling(156, min_periods=52).max()
            g[col.replace("_net", "_idx")] = ((g[col] - lo) / (hi - lo).replace(0, np.nan) * 100).clip(0, 100)
        last = g.iloc[-1]
        tail = g.iloc[-156:]
        out[c] = {"report_date": str(last["report_date"]),
                  **{k: (None if pd.isna(last[k]) else round(float(last[k]), 0)) for k in
                     ("comm_net", "spec_net", "small_net", "comm_idx", "spec_idx", "small_idx", "open_interest")},
                  "weekly": [[str(d), float(a), float(b), float(s)] for d, a, b, s in
                             zip(tail["report_date"], tail["comm_net"], tail["spec_net"], tail["small_net"])]}
    return out


def seasonality(prices: pd.DataFrame, coin: str = "BTC") -> dict:
    p = prices[coin].dropna()
    p.index = pd.to_datetime(p.index)
    m = p.resample("ME").last()
    if p.index[-1] < m.index[-1]:              # laufenden (unvollständigen) Monat weglassen
        m = m.iloc[:-1]
    m = m.pct_change().dropna()
    months = {}
    for i in range(1, 13):
        x = m[m.index.month == i]
        months[i] = {"mean": round(float(x.mean()), 4), "median": round(float(x.median()), 4),
                     "hit": round(float((x > 0).mean()), 3), "n": int(len(x)),
                     "years": {int(d.year): round(float(v), 4) for d, v in x.items()}}
    d = p.pct_change().dropna()
    wd = {i: {"mean": round(float(d[d.index.day_of_week == i].mean()), 5),
              "hit": round(float((d[d.index.day_of_week == i] > 0).mean()), 3)} for i in range(7)}
    # Test: Wochentage – gibt es einen Tag, der sich signifikant von 50 % unterscheidet (Bonferroni über 7)?
    best = min(range(7), key=lambda i: _binom_p(int((d[d.index.day_of_week == i] > 0).sum()), int((d.index.day_of_week == i).sum())))
    xb = d[d.index.day_of_week == best]
    p_best = _binom_p(int((xb > 0).sum()), len(xb)) * 7
    return {"coin": coin, "months": months, "weekdays": wd, "weekday_best": best,
            "weekday_p_adj": round(min(1.0, p_best), 4), "years": [int(p.index.year.min()), int(p.index.year.max())]}


def overview(prices: pd.DataFrame, volume: pd.DataFrame) -> dict:
    out = {}
    for c in prices:
        p = prices[c].dropna()
        ch = lambda n: round(float(p.iloc[-1] / p.iloc[-1 - n] - 1), 4) if len(p) > n else None
        hi = p.iloc[-365:].max() if len(p) >= 30 else p.max()
        out[c] = {"price": float(p.iloc[-1]), "date": str(p.index[-1]), "chg_1d": ch(1), "chg_7d": ch(7),
                  "chg_30d": ch(30), "chg_90d": ch(90), "chg_365d": ch(365),
                  "from_high_1y": round(float(p.iloc[-1] / hi - 1), 4),
                  "vs_btc_30d": None if c == "BTC" else round(float((p.iloc[-1] / p.iloc[-31]) /
                                (prices["BTC"].iloc[-1] / prices["BTC"].iloc[-31]) - 1), 4),
                  "volume_usd_7d": round(float(volume[c].iloc[-7:].mean()), 0),
                  "history": [[str(d), round(float(v), 6)] for d, v in p.iloc[-365:].items()]}
    return out


def cot_backtest(cot: pd.DataFrame, prices: pd.DataFrame, weeks: int = 4) -> dict:
    """Spekulanten-Index extrem (> 80 bzw. < 20): Rendite der folgenden `weeks` Wochen, nicht überlappend.
    Der Bericht gilt erst ab Freitag (Stand Dienstag + 3 Tage), gemessen ab dem Schlusskurs dieses Freitags."""
    out = {}
    idx = cot.sort_values("report_date").copy()
    for c, g in idx.groupby("coin"):
        g = g.copy()
        lo, hi = g["spec_net"].rolling(156, min_periods=52).min(), g["spec_net"].rolling(156, min_periods=52).max()
        g["spec_idx"] = (g["spec_net"] - lo) / (hi - lo).replace(0, np.nan) * 100
        p = prices[c].dropna()
        p.index = pd.to_datetime(p.index)
        res = {"weeks": weeks}
        base = []
        for name, cond in (("high", g["spec_idx"] > 80), ("low", g["spec_idx"] < 20)):
            picks, last = [], None
            for d in g.loc[cond, "report_date"]:
                t0 = pd.Timestamp(d) + pd.Timedelta(days=3)
                t1 = t0 + pd.Timedelta(weeks=weeks)
                if t1 > p.index[-1] or t0 < p.index[0] or (last is not None and t0 < last):
                    continue
                picks.append(float(p.asof(t1) / p.asof(t0) - 1))
                last = t1
            x = np.array(picks)
            k = int((x > 0).sum())
            res[name] = {"n": len(x), "mean": round(float(x.mean()), 4) if len(x) else None,
                         "hit": round(k / len(x), 4) if len(x) else None, "ci": _wilson(k, len(x)),
                         "p": round(_binom_p(k, len(x)), 4) if len(x) else None}
        for d in g["report_date"]:
            t0 = pd.Timestamp(d) + pd.Timedelta(days=3)
            t1 = t0 + pd.Timedelta(weeks=weeks)
            if t0 >= p.index[0] and t1 <= p.index[-1]:
                base.append(float(p.asof(t1) / p.asof(t0) - 1))
        b = np.array(base)
        res["all"] = {"n": len(b), "mean": round(float(b.mean()), 4), "hit": round(float((b > 0).mean()), 4)}
        out[c] = res
    return out
