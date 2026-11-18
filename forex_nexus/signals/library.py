"""Katalog der Einzelsignale. Jedes Signal ist eine einfache, erklärbare Regel und liefert je Handelstag
und Paar +1 (long), −1 (short) oder 0 (keine Aussage). Ob ein Signal etwas taugt, entscheidet allein
die Prüfung in validate.py – hier steht nur die ökonomische Idee.

Währungssignale werden auf Paare übertragen: Paar BASIS/KURS = Wert(BASIS) − Wert(KURS).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS
from forex_nexus.signals.data import Inputs

RISK_SCORE = {"AUD": 1.0, "NZD": 1.0, "CAD": 0.5, "GBP": 0.3, "EUR": 0.0, "USD": -0.5, "CHF": -1.0, "JPY": -1.0}


@dataclass(frozen=True)
class Signal:
    key: str
    family: str
    label: str          # kurzer Name für die Website
    idea: str           # ökonomische Idee in einem Satz
    rule: Callable[[Inputs], pd.DataFrame]


def pair_diff(f: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({p: f[p[:3]] - f[p[3:]] for p in ALL_PAIRS}, index=f.index)


def sign(x: pd.DataFrame, deadzone: float = 0.0, direction: int = 1) -> pd.DataFrame:
    out = np.where(x > deadzone, 1, np.where(x < -deadzone, -1, 0)) * direction
    return pd.DataFrame(out, index=x.index, columns=x.columns).where(x.notna(), 0).astype(int)


def _ccy(key, family, label, idea, factor, deadzone, direction=1, source="macro"):
    def rule(i: Inputs):
        f = getattr(i, source)[factor]
        return _on_dates(sign(pair_diff(f), deadzone, direction), i)
    return Signal(key, family, label, idea, rule)


def _on_dates(df: pd.DataFrame, i: Inputs) -> pd.DataFrame:
    df = df.copy()
    df.index = i.closes.index
    return df


def _trend(n):
    def rule(i):
        lp = np.log(i.closes)
        return sign(lp - lp.shift(n))
    return rule


def _revert(n):
    def rule(i):
        lp = np.log(i.closes)
        return sign(lp - lp.shift(n), direction=-1)
    return rule


def _cot_extreme(col, contrarian):
    def rule(i):
        x = i.cot[col]
        c = pd.DataFrame(np.where(x >= 80, 1, np.where(x <= 20, -1, 0)), index=x.index, columns=x.columns)
        c = c.where(x.notna(), 0) * (-1 if contrarian else 1)
        return _on_dates(sign(pair_diff(c)), i)
    return rule


def _season(min_years=8, use_hit=True):
    """Gleicher Kalendermonat in den Vorjahren (nur abgeschlossene Jahre vor dem aktuellen)."""
    def rule(i):
        c = i.closes
        m = np.log(c.resample("ME").last()).diff()
        out = pd.DataFrame(0, index=c.index, columns=c.columns)
        for month in range(1, 13):
            mm = m[m.index.month == month]
            # Wert für Jahr Y: Statistik der Jahre < Y
            hit = (mm > 0).astype(float).where(mm.notna()).expanding().mean().shift(1)
            mean = mm.expanding().mean().shift(1)
            n = mm.notna().astype(int).cumsum().shift(1)
            if use_hit:
                s = np.where(hit >= 0.6, 1, np.where(hit <= 0.4, -1, 0))
            else:
                s = np.sign(mean.fillna(0).values)
            s = pd.DataFrame(s, index=mm.index, columns=c.columns).where(n >= min_years, 0)
            for y, row in zip(mm.index.year, s.values):
                mask = (c.index.year == y) & (c.index.month == month)
                out.loc[mask] = row
        return out.astype(int)
    return rule


def _risk(kind):
    """Risikostimmung × Risikoprofil des Paares (AUD/NZD profitieren von Risikofreude, JPY/CHF von Angst)."""
    def rule(i):
        rs = pd.Series({p: RISK_SCORE[p[:3]] - RISK_SCORE[p[3:]] for p in ALL_PAIRS})
        if kind == "vix_chg":
            mood = -np.sign(np.log(i.vix / i.vix.shift(5)))             # VIX steigt -> Risk-off
        elif kind == "vix_level":
            mood = -np.sign(i.vix - i.vix.rolling(250, min_periods=200).median())
        else:                                                           # AUD/JPY-Trend 20 Tage
            aj = np.log(i.closes["AUDJPY"])
            mood = np.sign(aj - aj.shift(20))
        mood = pd.Series(np.asarray(mood, dtype=float), index=i.closes.index).fillna(0)
        dirn = np.where(rs.abs() >= 0.5, np.sign(rs), 0)
        return pd.DataFrame(np.outer(mood.values, dirn), index=i.closes.index, columns=ALL_PAIRS).astype(int)
    return rule


def _commodity(months):
    def rule(i):
        f = i.commodity[months].fillna(0)
        return _on_dates(sign(pair_diff(f), 0.02), i)
    return rule


# Bei Kurs-Regeln ist die Richtung vorab unklar -> beide Richtungen (Trend und Gegenbewegung) für jedes Fenster
PRICE_WINDOWS = ((1, "1 Tag"), (3, "3 Tage"), (5, "1 Woche"), (20, "1 Monat"), (60, "3 Monate"), (120, "6 Monate"),
                 (250, "1 Jahr"))

SIGNALS: list[Signal] = [
    # --- Kursverlauf
    *[Signal(f"trend_{n}", "Kursverlauf", f"Trend {lbl}", f"Der Kurs ist über {lbl} gestiegen → er steigt weiter.", _trend(n))
      for n, lbl in PRICE_WINDOWS],
    *[Signal(f"revert_{n}", "Kursverlauf", f"Gegenbewegung {lbl}", f"Nach einer Bewegung über {lbl} folgt eine Gegenbewegung.", _revert(n))
      for n, lbl in PRICE_WINDOWS],
    # --- Zinsen und Zinserwartung
    _ccy("carry", "Zinsen", "Zinsvorteil (Carry)", "Die Währung mit dem höheren Leitzins wird bevorzugt.", "rate", 0.25),
    _ccy("rate_chg_3m", "Zinserwartung", "Leitzins-Kurs 3 Monate", "Die Notenbank, die zuletzt stärker erhöht (weniger gesenkt) hat, stützt ihre Währung.", "rate_chg_3m", 0.1),
    _ccy("rate_chg_6m", "Zinserwartung", "Leitzins-Kurs 6 Monate", "Wie oben, über 6 Monate.", "rate_chg_6m", 0.1),
    _ccy("rate_chg_12m", "Zinserwartung", "Leitzins-Kurs 12 Monate", "Wie oben, über 12 Monate.", "rate_chg_12m", 0.1),
    _ccy("y10", "Zinsen", "Anleiherendite 10 J.", "Die Währung mit der höheren langfristigen Rendite wird bevorzugt.", "y10", 0.25),
    _ccy("y10_chg_1m", "Zinserwartung", "Renditeanstieg 1 Monat", "Steigende Anleiherenditen zeigen steigende Zinserwartungen.", "y10_chg_1m", 0.05),
    _ccy("y10_chg_3m", "Zinserwartung", "Renditeanstieg 3 Monate", "Wie oben, über 3 Monate.", "y10_chg_3m", 0.05),
    _ccy("curve", "Zinserwartung", "Zinskurve", "Eine steilere Zinskurve deutet auf künftige Zinserhöhungen.", "curve", 0.25),
    _ccy("real_rate", "Zinsen", "Realzins", "Höherer Zins nach Abzug der Inflation zieht Kapital an.", "real_rate", 0.25),
    # --- Inflation
    _ccy("infl_hawk", "Inflation", "Inflation (Notenbank-Sicht)", "Höhere Inflation zwingt die Notenbank zu höheren Zinsen.", "infl", 0.25),
    _ccy("infl_ppp", "Inflation", "Inflation (Kaufkraft-Sicht)", "Höhere Inflation entwertet die Währung.", "infl", 0.25, -1),
    _ccy("infl_chg_3m", "Inflation", "Inflationsanstieg 3 Monate", "Steigende Inflation macht Zinserhöhungen wahrscheinlicher.", "infl_chg_3m", 0.1),
    # --- Arbeitsmarkt
    _ccy("unemp", "Arbeitsmarkt", "Arbeitslosenquote", "Die Währung mit der niedrigeren Arbeitslosigkeit wird bevorzugt.", "unemp", 0.5, -1),
    _ccy("unemp_chg_3m", "Arbeitsmarkt", "Arbeitslosigkeit 3 Monate", "Steigende Arbeitslosigkeit schwächt die Währung.", "unemp_chg_3m", 0.1, -1),
    _ccy("unemp_chg_6m", "Arbeitsmarkt", "Arbeitslosigkeit 6 Monate", "Wie oben, über 6 Monate.", "unemp_chg_6m", 0.1, -1),
    _ccy("unemp_chg_12m", "Arbeitsmarkt", "Arbeitslosigkeit 12 Monate", "Wie oben, über 12 Monate.", "unemp_chg_12m", 0.1, -1),
    # --- Positionierung (COT)
    _ccy("cot_spec_level", "Spekulation (COT)", "Spekulanten-Positionierung", "Mit den großen Spekulanten handeln.", "spec_idx", 20, 1, "cot"),
    _ccy("cot_spec_flow", "Spekulation (COT)", "Spekulanten kaufen zu", "Spekulanten haben in 4 Wochen netto zugekauft.", "spec_chg_oi", 0.02, 1, "cot"),
    _ccy("cot_comm_level", "Spekulation (COT)", "Commercials-Positionierung", "Mit den Absicherern (Commercials) handeln.", "comm_idx", 20, 1, "cot"),
    _ccy("cot_small_contra", "Spekulation (COT)", "Gegen Kleinanleger", "Gegen die Positionierung der kleinen Händler handeln.", "small_idx", 20, -1, "cot"),
    Signal("cot_spec_extreme", "Spekulation (COT)", "Spekulanten-Extrem (konträr)", "Extreme Spekulanten-Positionen kippen.", _cot_extreme("spec_idx", True)),
    Signal("cot_comm_extreme", "Spekulation (COT)", "Commercials-Extrem", "Extreme Commercials-Positionen zeigen die Richtung.", _cot_extreme("comm_idx", False)),
    # --- Saisonalität
    Signal("season_hit", "Saisonalität", "Saison (Trefferquote)", "Im gleichen Monat lief das Paar in ≥ 60 % der Vorjahre gleich.", _season(use_hit=True)),
    Signal("season_mean", "Saisonalität", "Saison (Durchschnitt)", "Durchschnittliche Richtung des Monats in den Vorjahren.", _season(use_hit=False)),
    # --- Risikostimmung
    Signal("risk_vix_chg", "Risikostimmung", "VIX-Veränderung", "Fallender VIX → Risikowährungen (AUD, NZD) vor sicheren Häfen (JPY, CHF).", _risk("vix_chg")),
    Signal("risk_vix_level", "Risikostimmung", "VIX-Niveau", "VIX unter seinem Jahresmedian → Risikowährungen bevorzugt.", _risk("vix_level")),
    Signal("risk_audjpy", "Risikostimmung", "AUD/JPY-Barometer", "Steigender AUD/JPY zeigt Risikofreude an.", _risk("audjpy")),
    # --- Rohstoffe
    Signal("commodity_1m", "Rohstoffe", "Rohstoffpreise 1 Monat", "Steigende Exportpreise (Öl, Eisenerz, Kupfer …) stützen CAD, AUD, NZD.", _commodity(1)),
    Signal("commodity_3m", "Rohstoffe", "Rohstoffpreise 3 Monate", "Wie oben, über 3 Monate.", _commodity(3)),
]

BY_KEY = {s.key: s for s in SIGNALS}

# Fundamental-Abstimmung: je Idee EINE Richtung nach ökonomischer Erwartung (keine Auswahl nach Ergebnis).
# Kurs-Regeln fehlen, weil Trend und Gegenbewegung sich gegenseitig aufheben würden; bei COT gilt die
# klassische Sicht „mit den Commercials, gegen Kleinanleger und Spekulanten-Extreme“.
FUNDAMENTAL_VOTE = ["carry", "y10", "real_rate", "rate_chg_3m", "rate_chg_6m", "rate_chg_12m", "y10_chg_1m",
                    "y10_chg_3m", "curve", "infl_hawk", "infl_chg_3m", "unemp", "unemp_chg_3m", "unemp_chg_6m",
                    "unemp_chg_12m", "cot_comm_level", "cot_comm_extreme", "cot_small_contra", "cot_spec_extreme",
                    "season_hit", "risk_vix_chg", "risk_vix_level", "risk_audjpy", "commodity_1m", "commodity_3m"]
