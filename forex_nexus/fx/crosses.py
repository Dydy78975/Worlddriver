"""Kreuzkurse aus Dollar-Kursen berechnen.

Idee: Jeder Kurs wird zuerst in „US-Dollar pro 1 Einheit Währung“ umgerechnet
(usd_per). Ein beliebiges Paar BASE/QUOTE ist dann usd_per[BASE] / usd_per[QUOTE].
Beispiel: EURJPY = (USD pro EUR) / (USD pro JPY) = EURUSD * USDJPY.
"""

from __future__ import annotations

import itertools

import pandas as pd

# Marktkonvention: die Währung weiter vorne ist die Basiswährung.
MAJORS = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
ALL_PAIRS = [a + b for a, b in itertools.combinations(MAJORS, 2)]


def usd_per_unit(usd_pairs: pd.DataFrame) -> pd.DataFrame:
    """usd_pairs: Spalten = Symbole mit USD (z. B. EURUSD, USDJPY), Index = Datum."""
    out = pd.DataFrame(index=usd_pairs.index)
    out["USD"] = 1.0
    for ccy in MAJORS:
        if ccy == "USD":
            continue
        if f"{ccy}USD" in usd_pairs:
            out[ccy] = usd_pairs[f"{ccy}USD"]
        elif f"USD{ccy}" in usd_pairs:
            out[ccy] = 1.0 / usd_pairs[f"USD{ccy}"]
        else:
            raise KeyError(f"Kein Dollar-Kurs für {ccy}")
    return out


def all_pairs_from_usd(usd_pairs: pd.DataFrame) -> pd.DataFrame:
    """Liefert alle 28 Paare. Ein Kreuzkurs existiert nur, wenn beide Bestandteile vorhanden sind."""
    u = usd_per_unit(usd_pairs)
    return pd.DataFrame({p: u[p[:3]] / u[p[3:]] for p in ALL_PAIRS}, index=u.index)
