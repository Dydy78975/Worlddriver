"""Eingangsdaten für die Signale, streng zum Entscheidungszeitpunkt (point-in-time).

Entscheidungszeitpunkt eines Handelstags = 12:00 New York (Zeitpunkt des FRED-Kurses).
Ein Makrowert zählt erst, wenn sein available_at davor liegt. Zu alte Werte (Quelle eingestellt oder
verspätet) werden verworfen, damit kein veralteter Wert als „aktuell“ in ein Signal einfließt.
Hinweis: FRED liefert keine historischen Datenstände; ältere Perioden sind die heute bekannten
(ggf. revidierten) Werte. Das ist in docs/12_signal_abstimmung.md offen beschrieben.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS

NEW_YORK = ZoneInfo("America/New_York")
PRICE_SOURCES = ["FRED_H10", "FRED_H10_CROSS"]
START = "1999-01-04"
# Veraltet, wenn seit der Veröffentlichung des letzten Werts mehr als Periodenlänge + 45 Tage vergangen sind
# (dann ist der nächste Wert überfällig, z. B. weil die Quelle eingestellt wurde).
MAX_DAYS_SINCE_RELEASE = {"D": 21, "W": 21, "M": 76, "Q": 137}   # D: BIS liefert Tageswerte wöchentlich
# Zeitfenster für Treiber-Änderungen: Tagesreihen in Tagen, Monatsreihen in Monaten
WINDOWS_DAILY = ((7, "1 Woche"), (30, "1 Monat"), (91, "3 Monate"))
WINDOWS_MONTHLY = ((1, "1 Monat"), (3, "3 Monate"), (6, "6 Monate"))


@dataclass
class Inputs:
    closes: pd.DataFrame            # Handelstage x 28 Paare
    when: pd.DatetimeIndex          # Entscheidungszeitpunkt je Handelstag (UTC)
    macro: dict                     # Name -> DataFrame (Handelstage x Währung)
    cot: dict                       # Name -> DataFrame (Handelstage x Währung)
    vix: pd.Series                  # VIX des Vortags je Handelstag
    strength: pd.DataFrame          # Handelstage x Währung: Log-Stärke gegen den Korb der anderen 7
    drivers: dict                   # (Reihe, Fenster) -> Series je Handelstag: Änderung (Log, Rendite: Punkte)


def decision_times(dates) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return (idx + pd.Timedelta(hours=12)).tz_localize(NEW_YORK).tz_convert("UTC")


def load_closes(conn) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT f.trade_date, i.symbol, f.close::float8 FROM raw.fx_daily f
           JOIN ref.instrument i USING (instrument_id) JOIN ref.data_source s USING (source_id)
           WHERE s.name = ANY(%s) AND f.trade_date >= %s""", (PRICE_SOURCES, START)).fetchall()
    df = pd.DataFrame(rows, columns=["date", "symbol", "close"])
    c = df.pivot(index="date", columns="symbol", values="close").sort_index()
    c.index = pd.to_datetime(c.index)
    c = c[c.notna().sum(axis=1) >= 20]                  # Feiertage ohne Kurse entfernen
    return c[[p for p in ALL_PAIRS if p in c]].ffill(limit=2)


def load_periods(conn, code: str) -> tuple[pd.DataFrame, str]:
    """Je Periode der Wert und der früheste Veröffentlichungszeitpunkt."""
    rows = conn.execute(
        """SELECT o.period_date, o.value, min(o.available_at) OVER (PARTITION BY o.period_date), s.frequency
           FROM raw.observation o JOIN ref.series s USING (series_id)
           WHERE s.source_code = %s ORDER BY o.period_date, o.available_at DESC""", (code,)).fetchall()
    if not rows:
        return pd.DataFrame(columns=["value", "avail"]), "M"
    df = pd.DataFrame(rows, columns=["period", "value", "avail", "freq"]).drop_duplicates("period")
    df["period"] = pd.to_datetime(df["period"])
    return df.set_index("period")[["value", "avail"]], rows[0][3]


def as_of(values: pd.Series, avail: pd.Series, when: pd.DatetimeIndex, freq: str) -> pd.Series:
    """Für jeden Zeitpunkt den Wert der jüngsten bereits veröffentlichten Periode (oder NaN, wenn zu alt)."""
    avail = pd.to_datetime(avail.reindex(values.index), utc=True)
    ev = pd.DataFrame({"avail": avail.reset_index(drop=True), "period": values.index,
                       "value": values.reset_index(drop=True)})
    ev = ev.dropna().sort_values("avail")
    if ev.empty:
        return pd.Series(np.nan, index=when)
    ev = ev[ev["period"] >= ev["period"].cummax()]       # nur Veröffentlichungen, die eine neuere Periode bringen
    q = pd.DataFrame({"when": when}).reset_index(drop=True)
    m = pd.merge_asof(q, ev, left_on="when", right_on="avail", direction="backward")
    since = (m["when"] - m["avail"]).dt.days
    m.loc[since > MAX_DAYS_SINCE_RELEASE.get(freq, 76), "value"] = np.nan
    return pd.Series(m["value"].values, index=when)


def change(s: pd.Series, months: int = 0, days: int = 0) -> pd.Series:
    """Veränderung gegenüber dem Stand vor `months` Monaten bzw. `days` Tagen (Periodenbasis)."""
    s = s.dropna().sort_index()
    past = s.reindex(s.index - pd.DateOffset(months=months, days=days), method="ffill")
    return pd.Series(s.values - past.values, index=s.index)


def _per_currency(conn, category: str) -> dict:
    out = {}
    for ccy, code in conn.execute("SELECT currency, source_code FROM ref.series WHERE category = %s AND active",
                                  (category,)).fetchall():
        df, freq = load_periods(conn, code)
        if not df.empty:
            out[ccy] = (df["value"].astype(float), df["avail"], freq)
    return out


def _factor(series: dict, when, transform) -> pd.DataFrame:
    cols = {}
    for ccy, (v, avail, freq) in series.items():
        t = transform(v, freq)
        cols[ccy] = as_of(t, avail, when, freq)
    return pd.DataFrame(cols, index=when).reindex(columns=MAJORS)


def _yoy(v: pd.Series, freq: str) -> pd.Series:
    """Veränderung gegenüber dem Vorjahr in % (nach Kalender, gleich für Monats- und Quartalsreihen)."""
    v = v.dropna().sort_index()
    past = v.reindex(v.index - pd.DateOffset(years=1), method="ffill")
    return pd.Series((v.values / past.values - 1) * 100, index=v.index)


def currency_strength(closes: pd.DataFrame) -> pd.DataFrame:
    """Log-Stärke jeder Währung gegen den Durchschnitt der anderen 7 (aus den Dollar-Paaren)."""
    lu = {"USD": pd.Series(0.0, index=closes.index)}
    for c in MAJORS:
        if c != "USD":
            lu[c] = np.log(closes[c + "USD"]) if c + "USD" in closes else -np.log(closes["USD" + c])
    lu = pd.DataFrame(lu)[MAJORS]
    return pd.DataFrame({c: lu[c] - lu.drop(columns=c).mean(axis=1) for c in MAJORS})


def load_inputs(conn) -> Inputs:
    closes = load_closes(conn)
    when = decision_times(closes.index)
    sr, y10 = _per_currency(conn, "short_rate"), _per_currency(conn, "yield_10y")
    cpi, un = _per_currency(conn, "cpi_index"), _per_currency(conn, "unemployment")
    y2 = _per_currency(conn, "yield_2y")
    lvl = lambda v, f: v                                        # noqa: E731
    macro = {"rate": _factor(sr, when, lvl), "y10": _factor(y10, when, lvl), "infl": _factor(cpi, when, _yoy),
             "unemp": _factor(un, when, lvl)}
    for m in (3, 6, 12):
        macro[f"rate_chg_{m}m"] = _factor(sr, when, lambda v, f, m=m: change(v, m))
        macro[f"infl_chg_{m}m"] = _factor(cpi, when, lambda v, f, m=m: change(_yoy(v, f), m))
        macro[f"unemp_chg_{m}m"] = _factor(un, when, lambda v, f, m=m: change(v, m))
    for m in (1, 3, 6):
        macro[f"y10_chg_{m}m"] = _factor(y10, when, lambda v, f, m=m: change(v, m))
        macro[f"y2_chg_{m}m"] = _factor(y2, when, lambda v, f, m=m: change(v, m))
    macro["y2_vs_rate"] = _factor(y2, when, lvl) - macro["rate"]
    macro["curve"] = macro["y10"] - macro["rate"]
    macro["real_rate"] = macro["rate"] - macro["infl"]
    for m in (3, 6):                                             # Handelstage ≈ 21 je Monat
        macro[f"curve_chg_{m}m"] = macro["curve"] - macro["curve"].shift(21 * m)
        macro[f"real_rate_chg_{m}m"] = macro["real_rate"] - macro["real_rate"].shift(21 * m)

    cot = _cot(conn, when)
    vix_df, _ = load_periods(conn, "VIXCLS")
    vix = as_of(vix_df["value"].astype(float), vix_df["avail"], when, "D") if not vix_df.empty else pd.Series(np.nan, index=when)
    return Inputs(closes, when, macro, cot, vix, currency_strength(closes), _drivers(conn, when, closes.index))


def _drivers(conn, when, dates) -> dict:
    """Änderung jeder Treiberreihe über 3 Zeitfenster, zum Entscheidungszeitpunkt bekannt.
    Preise als Log-Änderung; Renditen, Aufschläge und Indizes (LEVEL_CODES) als Änderung in Punkten."""
    from forex_nexus.signals.library import DRIVERS, LEVEL_CODES
    codes = sorted({code for lst in DRIVERS.values() for code, *_ in lst})
    out = {}
    for code in codes:
        if code == "BTP_BUND":                                   # Italien-Aufschlag = Italien − Deutschland
            it, freq = load_periods(conn, "IRLTLT01ITM156N")
            de, _ = load_periods(conn, "IRLTLT01DEM156N")
            if it.empty or de.empty:
                continue
            df = it.join(de, rsuffix="_de", how="inner")
            df = pd.DataFrame({"value": df["value"].astype(float) - df["value_de"].astype(float),
                               "avail": df[["avail", "avail_de"]].max(axis=1)})
        else:
            df, freq = load_periods(conn, code)
        if df.empty:
            continue
        v = df["value"].astype(float)
        v = v if code in LEVEL_CODES else np.log(v.where(v > 0))
        windows = WINDOWS_MONTHLY if freq in ("M", "Q") else WINDOWS_DAILY
        for n, _ in windows:
            ch = change(v, months=n) if freq in ("M", "Q") else change(v, days=n)
            out[(code, n)] = as_of(ch, df["avail"], when, freq).set_axis(dates)
    return out


COT_WINDOW = 156            # Wochen (3 Jahre) für den COT-Index


def cot_indices(cot: pd.DataFrame, window: int = COT_WINDOW) -> pd.DataFrame:
    """COT-Index 0–100 je Gruppe: Lage der Netto-Position im Bereich der letzten `window` Wochen.
    cot: Spalten currency, report_date, available_at, open_interest, comm_/noncomm_/nonrept_long/short."""
    out = []
    for _, g in cot.sort_values("report_date").groupby("currency"):
        g = g.copy()
        g["comm_net"] = g["comm_long"] - g["comm_short"]
        g["spec_net"] = g["noncomm_long"] - g["noncomm_short"]
        g["small_net"] = (g["nonrept_long"] - g["nonrept_short"]) if "nonrept_long" in g else np.nan
        for col, name in (("comm_net", "comm_idx"), ("spec_net", "spec_idx"), ("small_net", "small_idx")):
            lo = g[col].rolling(window, min_periods=52).min()
            hi = g[col].rolling(window, min_periods=52).max()
            g[name] = ((g[col] - lo) / (hi - lo).replace(0, np.nan) * 100).clip(0, 100)
        g["spec_chg_4w"] = g["spec_net"].diff(4)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def _cot(conn, when) -> dict:
    rows = conn.execute(
        """SELECT currency, report_date, available_at, open_interest, comm_long, comm_short, noncomm_long, noncomm_short,
                  nonrept_long, nonrept_short FROM raw.cot_position""").fetchall()
    cols = ("comm_idx", "spec_idx", "small_idx", "spec_chg_oi")
    if not rows:
        return {c: pd.DataFrame(np.nan, index=when, columns=MAJORS) for c in cols}
    cot = pd.DataFrame(rows, columns=["currency", "report_date", "available_at", "open_interest", "comm_long",
                                      "comm_short", "noncomm_long", "noncomm_short", "nonrept_long", "nonrept_short"])
    idx = cot_indices(cot)
    idx["spec_chg_oi"] = idx["spec_chg_4w"] / idx["open_interest"].replace(0, np.nan)
    out = {}
    for col in cols:
        frame = {}
        for ccy, g in idx.groupby("currency"):
            g = g.set_index(pd.to_datetime(g["report_date"]))
            frame[ccy] = as_of(g[col].astype(float), g["available_at"], when, "W")
        out[col] = pd.DataFrame(frame, index=when).reindex(columns=MAJORS)
    return out
