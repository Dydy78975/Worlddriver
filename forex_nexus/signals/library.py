"""Modelle je Währung. Jedes Modell ist eine einfache, erklärbare Regel und liefert je Handelstag für
SEINE Währung +1 (stärker), −1 (schwächer) oder 0 (keine Aussage). Ob ein Modell etwas taugt, entscheidet
allein die Prüfung in validate.py – hier steht nur die ökonomische Idee.

* Gemeinsame Makro-Modelle vergleichen die Währung mit dem Durchschnitt der anderen 7
  (z. B. „Leitzins höher als im Schnitt“ → stärker).
* Treiber-Modelle nutzen, was gerade diese Währung bewegt (NZD: Milchprodukte, Fleisch, Wolle;
  AUD: Eisenerz, Kohle, Metalle; CAD: Öl, Gas, Holz; JPY/EUR/GBP: Energie als Importeure;
  JPY/CHF/USD: sichere Häfen).
* Jede Idee steht genau einmal im Katalog, mit der ökonomisch erwarteten Richtung (keine Spiegelbilder,
  keine Füllmodelle). Jeder Treiber über 3 Zeitfenster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import MAJORS
from forex_nexus.signals.data import WINDOWS_DAILY, WINDOWS_MONTHLY, Inputs

RISK_SCORE = {"AUD": 1.0, "NZD": 1.0, "CAD": 0.5, "GBP": 0.3, "EUR": 0.0, "USD": -0.5, "CHF": -1.0, "JPY": -1.0}

# Treiber je Währung: (Reihe, Name, Richtung, Begründung). Richtung +1: Treiber steigt -> Währung stärker.
DRIVERS = {
    "NZD": [("WPU023", "Milchprodukte", 1, "Milchprodukte sind Neuseelands wichtigster Export (US-Preise als Ersatz für Global Dairy Trade)"),
            ("PCU311511311511", "Trinkmilch", 1, "Milchpreise treiben die Exporterlöse"),
            ("PBEEFUSDM", "Rindfleisch", 1, "Fleisch ist ein großer Exportposten"),
            ("PLAMBUSDM", "Lammfleisch", 1, "Neuseeland ist größter Lammexporteur"),
            ("PWOOLCUSDM", "Wolle", 1, "Wolle (grob) ist ein traditioneller Export"),
            ("PLOGSKUSDM", "Rundholz", 1, "Holz geht vor allem nach China")],
    "AUD": [("PIORECRUSDM", "Eisenerz", 1, "Eisenerz ist Australiens größter Export"),
            ("PCOALAUUSDM", "Kohle", 1, "Kohle ist ein Hauptexport"),
            ("PNGASJPUSDM", "Flüssiggas (Asien)", 1, "Australien ist großer LNG-Exporteur"),
            ("PCOPPUSDM", "Kupfer", 1, "Metallexporte"),
            ("PALUMUSDM", "Aluminium", 1, "Aluminium und Bauxit"),
            ("PWHEAMTUSDM", "Weizen", 1, "Getreideexporte"),
            ("PWOOLFUSDM", "Wolle", 1, "Australien ist größter Exporteur feiner Wolle"),
            ("PBEEFUSDM", "Rindfleisch", 1, "Australien ist großer Rindfleischexporteur")],
    "CAD": [("DCOILWTICO", "Rohöl WTI", 1, "Öl ist Kanadas wichtigster Export"),
            ("DHHNGSP", "Erdgas USA", 1, "Gas geht in die USA"),
            ("WPU081", "Schnittholz", 1, "Holz ist ein großer Export in die USA"),
            ("PALUMUSDM", "Aluminium", 1, "Kanada ist großer Aluminiumproduzent"),
            ("PNICKUSDM", "Nickel", 1, "Kanada ist großer Nickelproduzent")],
    "JPY": [("DCOILWTICO", "Rohöl", -1, "Japan importiert fast alle Energie"),
            ("PNGASJPUSDM", "Flüssiggas (Asien)", -1, "Japan ist großer LNG-Importeur"),
            ("VIXCLS", "Angst-Index VIX", 1, "Der Yen ist ein sicherer Hafen"),
            ("DGS2", "US-Rendite 2 J.", -1, "Steigende US-Zinsen machen Yen-Kredite attraktiver (Carry)")],
    "CHF": [("VIXCLS", "Angst-Index VIX", 1, "Der Franken ist ein sicherer Hafen"),
            ("DGS2", "US-Rendite 2 J.", -1, "Steigende US-Zinsen lassen Kapital aus dem Franken abfließen")],
    "EUR": [("PNGASEUUSDM", "Erdgas Europa", -1, "Die Eurozone importiert ihr Gas"),
            ("DCOILBRENTEU", "Rohöl Brent", -1, "Die Eurozone importiert ihr Öl"),
            ("DGS2", "US-Rendite 2 J.", -1, "Steigende US-Zinsen stärken den Dollar gegen den Euro")],
    "GBP": [("PNGASEUUSDM", "Erdgas Europa", -1, "Großbritannien importiert Gas"),
            ("DCOILBRENTEU", "Rohöl Brent", -1, "Großbritannien ist Netto-Energieimporteur")],
    "USD": [("VIXCLS", "Angst-Index VIX", 1, "Der Dollar ist in Krisen gefragt"),
            ("DGS2", "US-Rendite 2 J.", 1, "Steigende kurzfristige US-Zinsen ziehen Kapital an")],
}
NO_SHORT_YIELD = {"CHF", "NZD"}       # keine aktuelle Quelle für 2-jährige Renditen (siehe ingestion/yields.py)
DAILY_CODES = {"DCOILWTICO", "DCOILBRENTEU", "DHHNGSP", "VIXCLS", "DGS2"}

# Gemeinsame Makro-Modelle: (Schlüssel, Familie, Name, Idee, Faktor, Schwelle, Richtung, stimmt mit)
MACRO = [
    ("rate", "Leitzins", "Leitzins", "Höherer Leitzins als im Schnitt zieht Kapital an (Carry).", "rate", 0.25, 1),
    *[(f"rate_chg_{m}m", "Zinserwartung", f"Leitzins-Kurs {m} M.", f"Die Notenbank hat in {m} Monaten stärker erhöht als die anderen.", f"rate_chg_{m}m", 0.1, 1)
      for m in (3, 6, 12)],
    ("y10", "Renditen", "Rendite 10 J.", "Höhere langfristige Rendite als im Schnitt.", "y10", 0.25, 1),
    *[(f"y10_chg_{m}m", "Renditen", f"Renditeanstieg {m} M.", f"Die Anleiherendite stieg in {m} Monaten stärker als anderswo.", f"y10_chg_{m}m", 0.05, 1)
      for m in (1, 3, 6)],
    *[(f"y2_chg_{m}m", "Zinserwartung", f"Rendite 2 J. {m} M.", f"Die kurzfristige Rendite stieg in {m} Monaten stärker als anderswo: der Markt erwartet höhere Zinsen.", f"y2_chg_{m}m", 0.05, 1)
      for m in (1, 3, 6)],
    ("y2_vs_rate", "Zinserwartung", "Rendite 2 J. über Leitzins", "Liegt die 2-jährige Rendite über dem Leitzins, erwartet der Markt Zinserhöhungen.", "y2_vs_rate", 0.1, 1),
    ("curve", "Zinserwartung", "Zinskurve", "Eine steilere Zinskurve deutet auf künftige Zinserhöhungen.", "curve", 0.25, 1),
    *[(f"curve_chg_{m}m", "Zinserwartung", f"Zinskurve {m} M.", f"Die Zinskurve wurde in {m} Monaten steiler als anderswo.", f"curve_chg_{m}m", 0.1, 1) for m in (3, 6)],
    ("real_rate", "Leitzins", "Realzins", "Höherer Zins nach Abzug der Inflation.", "real_rate", 0.25, 1),
    *[(f"real_rate_chg_{m}m", "Leitzins", f"Realzins {m} M.", f"Der Realzins stieg in {m} Monaten stärker als anderswo.", f"real_rate_chg_{m}m", 0.1, 1) for m in (3, 6)],
    ("infl", "Inflation", "Inflation", "Höhere Inflation zwingt die Notenbank zu höheren Zinsen.", "infl", 0.25, 1),
    *[(f"infl_chg_{m}m", "Inflation", f"Inflationsanstieg {m} M.", f"Die Inflation stieg in {m} Monaten stärker als anderswo.", f"infl_chg_{m}m", 0.1, 1)
      for m in (3, 6, 12)],
    ("unemp", "Arbeitsmarkt", "Arbeitslosenquote", "Niedrigere Arbeitslosigkeit als im Schnitt.", "unemp", 0.5, -1),
    *[(f"unemp_chg_{m}m", "Arbeitsmarkt", f"Arbeitslosigkeit {m} M.", f"Steigt die Arbeitslosigkeit in {m} Monaten stärker als anderswo, wird die Währung schwächer.", f"unemp_chg_{m}m", 0.1, -1)
      for m in (3, 6, 12)],
]
COT = [  # (Schlüssel, Name, Idee, Spalte, Art, Richtung)
    ("cot_comm", "Commercials-Positionierung", "Mit den Absicherern (Commercials) handeln.", "comm_idx", "level", 1),
    ("cot_comm_extreme", "Commercials-Extrem", "Extreme Commercials-Positionen zeigen die Richtung.", "comm_idx", "extreme", 1),
    ("cot_spec_extreme", "Spekulanten-Extrem", "Extreme Spekulanten-Positionen kippen.", "spec_idx", "extreme", -1),
    ("cot_spec_flow", "Spekulanten kaufen zu", "Spekulanten haben in 4 Wochen netto zugekauft (Momentum der Positionierung).", "spec_chg_oi", "flow", 1),
    ("cot_small", "Gegen Kleinanleger", "Gegen die Positionierung der kleinen Händler.", "small_idx", "level", -1),
]
# Kurs-Regeln: kurzfristig Gegenbewegung, mittelfristig Trend (Erwartung aus der Literatur)
PRICE = [(1, "1 Tag", -1), (5, "1 Woche", -1), (20, "1 Monat", 1), (60, "3 Monate", 1), (120, "6 Monate", 1),
         (250, "1 Jahr", 1)]


@dataclass(frozen=True)
class Model:
    key: str            # z. B. "NZD:drv_WPU023_3"
    currency: str
    family: str
    label: str
    idea: str
    rule: Callable[[Inputs], pd.Series]


def sign(x: pd.Series, deadzone: float = 0.0, direction: int = 1) -> pd.Series:
    out = np.where(x > deadzone, 1, np.where(x < -deadzone, -1, 0)) * direction
    return pd.Series(out, index=x.index).where(x.notna(), 0).astype(int)


def relative(f: pd.DataFrame, c: str) -> pd.Series:
    """Wert der Währung minus Durchschnitt der anderen 7 (nur Währungen mit Daten)."""
    return f[c] - f.drop(columns=c).mean(axis=1)


def _dates(s: pd.Series, i: Inputs) -> pd.Series:
    return pd.Series(np.asarray(s), index=i.closes.index)


def _macro(c, factor, dz, d):
    return lambda i: _dates(sign(relative(i.macro[factor], c), dz, d), i)


def _cot(c, col, kind, d):
    def rule(i):
        if kind == "extreme":
            x = i.cot[col][c]
            s = pd.Series(np.where(x >= 80, 1, np.where(x <= 20, -1, 0)), index=x.index).where(x.notna(), 0) * d
            return _dates(s, i)
        dz = 20 if kind == "level" else 0.02
        return _dates(sign(relative(i.cot[col], c), dz, d), i)
    return rule


def _price(c, n, d):
    return lambda i: sign(i.strength[c] - i.strength[c].shift(n), 0, d)


def _season(c):
    """Gleicher Kalendermonat in den Vorjahren (nur abgeschlossene Jahre, mindestens 8)."""
    def rule(i):
        st = i.strength[c]
        m = st.resample("ME").last().diff()
        out = pd.Series(0, index=st.index)
        for month in range(1, 13):
            mm = m[m.index.month == month]
            prior_hit = (mm > 0).astype(float).where(mm.notna()).expanding().mean().shift(1)
            n = mm.notna().astype(int).cumsum().shift(1)
            v = np.where(prior_hit >= 0.6, 1, np.where(prior_hit <= 0.4, -1, 0))
            v = pd.Series(v, index=mm.index).where(n >= 8, 0)
            for ts, val in v.items():
                out[(st.index.year == ts.year) & (st.index.month == month)] = val
        return out.astype(int)
    return rule


def _risk(c, kind):
    rs = RISK_SCORE[c]

    def rule(i):
        if kind == "vix_chg":
            mood = -np.sign(np.log(i.vix / i.vix.shift(5)))
        elif kind == "vix_level":
            mood = -np.sign(i.vix - i.vix.rolling(250, min_periods=200).median())
        else:
            aj = np.log(i.closes["AUDJPY"])
            mood = np.sign(aj - aj.shift(20))
        mood = pd.Series(np.asarray(mood, dtype=float), index=i.closes.index).fillna(0)
        return (mood * (np.sign(rs) if abs(rs) >= 0.5 else 0)).astype(int)
    return rule


def _driver(code, n, d):
    dz = 0.05 if code == "DGS2" else 0.01                    # Rendite: 0,05 Prozentpunkte; Preise: 1 %
    return lambda i: sign(i.drivers[(code, n)], dz, d) if (code, n) in i.drivers else pd.Series(0, index=i.closes.index)


def _build() -> list[Model]:
    out = []
    for c in MAJORS:
        for key, fam, label, idea, factor, dz, d in MACRO:
            if factor.startswith("y2") and c in NO_SHORT_YIELD:
                continue
            out.append(Model(f"{c}:{key}", c, fam, label, idea, _macro(c, factor, dz, d)))
        for key, label, idea, col, kind, d in COT:
            out.append(Model(f"{c}:{key}", c, "Positionierung (COT)", label, idea, _cot(c, col, kind, d)))
        out.append(Model(f"{c}:season", c, "Saisonalität", "Saison",
                         "Im gleichen Monat lief die Währung in mindestens 60 % der Vorjahre gleich.", _season(c)))
        if abs(RISK_SCORE[c]) >= 0.5:                        # nur Risiko- und Fluchtwährungen
            for kind, label, idea in (("vix_chg", "VIX-Veränderung", "Fallender VIX: Risikowährungen gefragt, sichere Häfen weniger."),
                                      ("vix_level", "VIX-Niveau", "VIX unter seinem Jahresmedian: Risikofreude."),
                                      ("audjpy", "AUD/JPY-Barometer", "Steigender AUD/JPY zeigt Risikofreude an.")):
                out.append(Model(f"{c}:risk_{kind}", c, "Risikostimmung", label, idea, _risk(c, kind)))
        for n, lbl, d in PRICE:
            name, idea = ((f"Trend {lbl}", f"Die Währung ist über {lbl} gestiegen und steigt weiter.") if d > 0 else
                          (f"Gegenbewegung {lbl}", f"Nach einer Bewegung über {lbl} folgt eine Gegenbewegung."))
            out.append(Model(f"{c}:price_{n}", c, "Kursverlauf", name, idea, _price(c, n, d)))
        for code, name, d, why in DRIVERS.get(c, []):
            windows = WINDOWS_DAILY if code in DAILY_CODES else WINDOWS_MONTHLY
            for n, wl in windows:
                move = "stärker" if d > 0 else "schwächer"
                out.append(Model(f"{c}:drv_{code}_{n}", c, "Treiber", f"{name} {wl}",
                                 f"{why}. Steigt der Wert über {wl}, wird die Währung {move}.", _driver(code, n, d)))
    return out


MODELS: list[Model] = _build()
BY_KEY = {m.key: m for m in MODELS}
