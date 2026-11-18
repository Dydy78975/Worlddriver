"""Qualitätsprüfungen für Tageskurse.

Alle Prüfungen sind reine Funktionen auf DataFrames (Index = Datum, Spalten = Paare)
und liefern eine Liste von Befunden. `run_checks` liest die Datenbank und speichert
die Befunde in raw.data_quality_issue.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from forex_nexus.db import connect
from forex_nexus.fx.crosses import all_pairs_from_usd

# Schwellenwerte (bewusst als Konstanten, damit sie dokumentiert und versioniert sind)
GAP_MIN_BUSINESS_DAYS = 4        # einzelne Feiertage sind normal; ab 4 fehlenden Werktagen am Stück melden
OUTLIER_SIGMA = 8.0              # Tagesbewegung > 8 robuste Standardabweichungen ...
OUTLIER_MIN_ABS = 0.02           # ... und mindestens 2 %
OUTLIER_WINDOW = 250             # Handelstage für die robuste Volatilität (nur Vergangenheit)
SPIKE_REVERSAL = 0.8             # Bewegung wird am Folgetag zu >= 80 % rückgängig gemacht -> Verdacht auf Datenfehler
ANALYSIS_START = date(1999, 1, 4)  # Euro-Start: ab hier existieren alle 28 Paare; ältere Daten bleiben gespeichert
MISMATCH_THRESHOLD = 0.02        # FRED (12:00 New York) vs. EZB (14:15 MEZ): > 2 % Unterschied melden
STALE_DAYS = {"FRED": 12, "ECB": 5}  # FRED erscheint wöchentlich, EZB täglich


@dataclass
class Finding:
    check: str
    symbol: str | None
    day: date | None
    severity: str
    details: dict = field(default_factory=dict)


def find_gaps(closes: pd.DataFrame) -> list[Finding]:
    out = []
    for sym in closes:
        s = closes[sym].dropna()
        if s.empty:
            continue
        bdays = pd.bdate_range(s.index.min(), s.index.max()).date
        missing = pd.Index(bdays).difference(pd.Index(s.index))
        if missing.empty:
            continue
        # zusammenhängende Lücken finden
        pos = pd.Index(bdays).get_indexer(missing)
        groups = np.split(missing, np.where(np.diff(pos) != 1)[0] + 1)
        for g in groups:
            if len(g) >= GAP_MIN_BUSINESS_DAYS:
                out.append(Finding("gap", sym, g[0], "warning",
                                   {"from": str(g[0]), "to": str(g[-1]), "business_days": len(g)}))
    return out


def find_outliers(closes: pd.DataFrame, control: pd.DataFrame | None = None) -> list[Finding]:
    """Extreme Tagesbewegungen finden und einordnen.

    * spike (Warnung): Sprung, der am Folgetag fast vollständig zurückgeht, UND die Kontrollquelle
      bestätigt den Sprung nicht -> Verdacht auf Datenfehler.
    * extreme_move (Info): echte Marktbewegung, z. B. Zentralbank-Überraschung oder Krise.
    """
    out = []
    for sym in closes:
        s = closes[sym].dropna()
        r = np.log(s).diff()
        # robuste Volatilität nur aus der Vergangenheit (shift(1)): kein Blick in die Zukunft
        mad = r.abs().rolling(OUTLIER_WINDOW, min_periods=60).median().shift(1) * 1.4826
        # Bei festen Kursen (z. B. Bretton Woods bis 1973) ist die Schwankung 0 -> nicht bewertbar
        z = r / mad.where(mad > 0)
        nxt = r.shift(-1)
        ctrl = None
        if control is not None and sym in control:
            ctrl = np.log(control[sym].dropna()).diff()
        hits = r[(z.abs() > OUTLIER_SIGMA) & (r.abs() > OUTLIER_MIN_ABS)]
        skip = set()
        for d, val in hits.items():
            if d in skip:
                continue
            following = nxt[d]
            reverses = bool(np.isfinite(following) and np.sign(following) == -np.sign(val)
                            and abs(following) >= SPIKE_REVERSAL * abs(val))
            confirmed = None
            if ctrl is not None and d in ctrl.index and np.isfinite(ctrl[d]):
                # Kontrollquelle zeigt eine gleichgerichtete Bewegung von mindestens halber Größe
                confirmed = bool(np.sign(ctrl[d]) == np.sign(val) and abs(ctrl[d]) >= 0.5 * abs(val))
            is_spike = reverses and confirmed is not True
            details = {"log_return": round(float(val), 5), "robust_sigma": round(float(z[d]), 1),
                       "next_day_return": None if not np.isfinite(following) else round(float(following), 5),
                       "confirmed_by_control": confirmed}
            out.append(Finding("spike" if is_spike else "extreme_move", sym, d,
                               "warning" if is_spike else "info", details))
            if reverses:
                pos = s.index.get_loc(d)
                if pos + 1 < len(s):
                    skip.add(s.index[pos + 1])   # Rückkehr-Tag nicht doppelt melden
    return out


def ecb_all_pairs(ecb_eur: pd.DataFrame) -> pd.DataFrame:
    """Alle 28 Paare aus den EZB-Kursen (EURxxx) berechnen – unabhängige Kontrolle zu FRED."""
    usd_per_eur = ecb_eur["EURUSD"]
    usd_pairs = pd.DataFrame({"EURUSD": usd_per_eur})
    for ccy, sym in [("GBP", "GBPUSD"), ("AUD", "AUDUSD"), ("NZD", "NZDUSD")]:
        usd_pairs[sym] = usd_per_eur / ecb_eur[f"EUR{ccy}"]
    for ccy in ["CAD", "CHF", "JPY"]:
        usd_pairs[f"USD{ccy}"] = ecb_eur[f"EUR{ccy}"] / usd_per_eur
    return all_pairs_from_usd(usd_pairs)


def compare_sources(primary: pd.DataFrame, control: pd.DataFrame) -> tuple[list[Finding], pd.DataFrame]:
    """Vergleicht gemeinsame Paare an gemeinsamen Tagen. Liefert Befunde und eine Statistik je Paar."""
    out, stats = [], []
    for sym in sorted(set(primary) & set(control)):
        a, b = primary[sym].dropna(), control[sym].dropna()
        common = a.index.intersection(b.index)
        if common.empty:
            continue
        diff = np.log(a[common] / b[common])
        stats.append({"symbol": sym, "days": len(common),
                      "median_abs_diff_pct": round(float(diff.abs().median() * 100), 3),
                      "p99_abs_diff_pct": round(float(diff.abs().quantile(0.99) * 100), 3),
                      "flagged": int((diff.abs() > MISMATCH_THRESHOLD).sum())})
        for d, val in diff[diff.abs() > MISMATCH_THRESHOLD].items():
            out.append(Finding("source_mismatch", sym, d, "warning",
                               {"log_diff_pct": round(float(val) * 100, 2),
                                "primary": float(a[d]), "control": float(b[d])}))
    return out, pd.DataFrame(stats)


def find_stale(closes: pd.DataFrame, source_label: str, today: date) -> list[Finding]:
    out = []
    limit = STALE_DAYS[source_label]
    for sym in closes:
        last = closes[sym].dropna().index.max()
        if last is not None and (today - last).days > limit:
            out.append(Finding("stale", sym, last, "warning",
                               {"source": source_label, "days_old": (today - last).days, "limit": limit}))
    return out


# --------------------------------------------------------------------------- Datenbank

def load_closes(conn, source_names: list[str]) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT f.trade_date, i.symbol, f.close::float8
           FROM raw.fx_daily f
           JOIN ref.instrument i USING (instrument_id)
           JOIN ref.data_source s USING (source_id)
           WHERE s.name = ANY(%s)""", (source_names,)).fetchall()
    df = pd.DataFrame(rows, columns=["date", "symbol", "close"])
    return df.pivot(index="date", columns="symbol", values="close").sort_index()


def run_checks(conninfo: str, today: date | None = None) -> dict:
    today = today or date.today()
    with connect(conninfo) as conn:
        fred = load_closes(conn, ["FRED_H10", "FRED_H10_CROSS"])
        fred = fred.loc[fred.index >= ANALYSIS_START]
        ecb = load_closes(conn, ["ECB_EXR"])
        findings = find_gaps(fred) + find_outliers(fred, control=ecb_all_pairs(ecb))
        mismatches, mismatch_stats = compare_sources(fred, ecb)
        findings += mismatches
        findings += find_stale(fred, "FRED", today) + find_stale(ecb, "ECB", today)

        ids = dict(conn.execute("SELECT symbol, instrument_id FROM ref.instrument").fetchall())
        new = 0
        for f in findings:
            new += conn.execute(
                """INSERT INTO raw.data_quality_issue (check_name, instrument_id, affected_date, severity, details)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (f.check, ids.get(f.symbol), f.day, f.severity, json.dumps(f.details))).rowcount
        conn.commit()
    return {"findings": findings, "new_in_db": new, "mismatch_stats": mismatch_stats,
            "fred": fred, "ecb": ecb}
