"""Merkmale und Zielgrößen für die Prognosemodelle (Panel über alle 28 Paare).

Point-in-Time-Regeln:
* Kursmerkmale zum Tag t verwenden nur Schlusskurse bis einschließlich t (Kurs ist zum Prognosezeitpunkt bekannt).
* VIX: Der Wechselkurs ist ein Mittagskurs New York, der VIX-Schluss entsteht erst um 16:15 New York.
  Deshalb wird der VIX vom VORTAG verwendet.
* Zielgrößen (Rendite, Klasse, Spanne) liegen in der Zukunft und werden ausschließlich zur Auswertung
  bzw. zum Training mit ausreichendem Abstand (Purging/Embargo) genutzt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = {"1D": 1, "1W": 5, "1M": 20}
EWMA_LAMBDA = 0.94
NEUTRAL_K = 0.5
MOMENTUM_WINDOWS = (5, 20, 60, 250)

# Risikoneigung der Währungen (Expertenannahme, versioniert): positiv = profitiert von Risikofreude
RISK_SCORE = {"AUD": 1.0, "NZD": 1.0, "CAD": 0.5, "GBP": 0.3, "EUR": 0.0, "USD": -0.5, "CHF": -1.0, "JPY": -1.0}

FEATURES = [f"mom_{n}" for n in MOMENTUM_WINDOWS] + [
    "vol_ratio", "vix_level", "vix_chg_5d", "risk_score", "vix_x_risk", "dow_0", "dow_4", "month_end"]

FEATURE_LABELS_DE = {
    "mom_5": "Kursdynamik 1 Woche", "mom_20": "Kursdynamik 1 Monat", "mom_60": "Kursdynamik 3 Monate",
    "mom_250": "Kursdynamik 1 Jahr", "vol_ratio": "Aktuelle vs. langfristige Schwankung",
    "vix_level": "Risikostimmung (VIX-Niveau)", "vix_chg_5d": "Veränderung der Risikostimmung (VIX, 5 Tage)",
    "risk_score": "Risikoprofil des Paares", "vix_x_risk": "Risikostimmung × Risikoprofil des Paares",
    "dow_0": "Wochentag Montag", "dow_4": "Wochentag Freitag", "month_end": "Monatsende",
}


def ewma_vol(returns: pd.Series, lam: float = EWMA_LAMBDA) -> pd.Series:
    """Tägliche EWMA-Volatilität (RiskMetrics). Wert am Tag t nutzt Renditen bis einschließlich t."""
    return np.sqrt((returns ** 2).ewm(alpha=1 - lam, adjust=False, min_periods=20).mean())


def build_panel(closes: pd.DataFrame, vix: pd.Series | None = None) -> pd.DataFrame:
    """closes: Index = Handelstage, Spalten = Paare. Liefert ein Langformat mit Merkmalen und Zielgrößen
    für alle Horizonte."""
    closes = closes.sort_index()
    closes = closes[closes.notna().sum(axis=1) >= 20]          # Feiertage ohne Kurse entfernen
    idx = pd.DatetimeIndex(pd.to_datetime(closes.index))

    vix_prev = None
    if vix is not None and not vix.empty:
        v = vix.copy()
        v.index = pd.to_datetime(v.index)
        v = v.sort_index().reindex(idx.union(v.index)).ffill().reindex(idx)
        vix_prev = v.shift(1)                                    # Vortag (siehe Modulbeschreibung)

    frames = []
    for pair in closes.columns:
        p = pd.Series(closes[pair].values, index=idx).dropna()
        if len(p) < 300:
            continue
        logp = np.log(p)
        r = logp.diff()
        sigma = ewma_vol(r)
        df = pd.DataFrame(index=p.index)
        df["pair"] = pair
        df["price"] = p
        df["sigma"] = sigma
        for n in MOMENTUM_WINDOWS:
            df[f"mom_{n}"] = (logp - logp.shift(n)) / (sigma * np.sqrt(n))
        df["vol_ratio"] = r.rolling(20).std() / r.rolling(250).std()
        if vix_prev is not None:
            vp = vix_prev.reindex(p.index)
            df["vix_level"] = np.log(vp)
            df["vix_chg_5d"] = np.log(vp / vp.shift(5))
        else:
            df["vix_level"] = np.nan
            df["vix_chg_5d"] = np.nan
        rs = RISK_SCORE[pair[:3]] - RISK_SCORE[pair[3:]]
        df["risk_score"] = rs
        df["vix_x_risk"] = df["vix_chg_5d"] * rs
        dow = p.index.day_of_week
        df["dow_0"] = (dow == 0).astype(float)
        df["dow_4"] = (dow == 4).astype(float)
        nxt = p.index[1:].append(pd.DatetimeIndex([p.index[-1] + pd.Timedelta(days=3)]))
        df["month_end"] = (nxt.month != p.index.month).astype(float)

        for code, h in HORIZONS.items():
            fut = logp.shift(-h)
            y = fut - logp
            band = NEUTRAL_K * sigma * np.sqrt(h)
            df[f"y_{code}"] = y
            df[f"cls_{code}"] = np.where(y.isna(), np.nan, np.where(y > band, 1, np.where(y < -band, -1, 0)))
            # Spanne der Schlusskurse bis zum Horizont (echtes Hoch/Tief folgt mit Dukascopy-Daten)
            path = pd.concat([logp.shift(-j) - logp for j in range(1, h + 1)], axis=1)
            df[f"hi_{code}"] = path.max(axis=1, skipna=False).clip(lower=0)
            df[f"lo_{code}"] = path.min(axis=1, skipna=False).clip(upper=0)
            df[f"target_date_{code}"] = pd.Series(p.index, index=p.index).shift(-h)
        frames.append(df)
    panel = pd.concat(frames)
    panel.index.name = "date"
    return panel.reset_index()


def vix_regime(vix_level_log: pd.Series) -> pd.Series:
    """Marktregime aus dem VIX des Vortags: ruhig (< 15), normal (15–25), Stress (> 25)."""
    v = np.exp(vix_level_log)
    return pd.Series(np.select([v < 15, v <= 25, v > 25], ["ruhig", "normal", "Stress"], default="unbekannt"),
                     index=vix_level_log.index)
