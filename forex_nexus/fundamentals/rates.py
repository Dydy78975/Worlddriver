"""Zinsen und Notenbanken: Kurzfristzins (nahe Leitzins), 10-jährige Rendite, Inflation und Zinsdifferenzen.

Inflation wird nur dann für den Realzins verwendet, wenn sie aktuell ist (Monatsdaten höchstens 4 Monate,
Quartalsdaten höchstens 7 Monate alt). Ältere Werte werden angezeigt, aber deutlich als veraltet markiert.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS

BANKS = {"USD": "Federal Reserve", "EUR": "Europäische Zentralbank", "JPY": "Bank of Japan", "GBP": "Bank of England",
         "CHF": "Schweizerische Nationalbank", "CAD": "Bank of Canada", "AUD": "Reserve Bank of Australia",
         "NZD": "Reserve Bank of New Zealand"}


def _series(conn, category: str, ccy: str):
    row = conn.execute("""SELECT s.source_code, s.frequency, s.description FROM ref.series s
                          WHERE s.category = %s AND s.currency = %s""", (category, ccy)).fetchone()
    if not row:
        return None, None, None
    vals = conn.execute(
        """SELECT DISTINCT ON (o.period_date) o.period_date, o.value FROM raw.observation o
           JOIN ref.series s USING (series_id) WHERE s.source_code = %s ORDER BY o.period_date, o.available_at DESC""",
        (row[0],)).fetchall()
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in vals}).sort_index()
    return s, row[1], {"code": row[0], "description": row[2]}


def _r(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def build(conn, now: datetime) -> dict:
    out = {}
    for c in MAJORS:
        sr, _, sr_meta = _series(conn, "short_rate", c)
        y10, _, y_meta = _series(conn, "yield_10y", c)
        cpi, cfreq, c_meta = _series(conn, "cpi_index", c)
        e = {"bank": BANKS[c], "short": None, "y10": None, "inflation": None}
        if sr is not None and len(sr):
            m = sr.resample("ME").last().dropna()
            e["short"] = {"value": _r(sr.iloc[-1]), "date": str(sr.index[-1].date()), "source": sr_meta,
                          "chg_3m": _r(m.iloc[-1] - m.iloc[-4]) if len(m) > 4 else None,
                          "chg_12m": _r(m.iloc[-1] - m.iloc[-13]) if len(m) > 13 else None,
                          "history": [[str(d.date())[:7], _r(v)] for d, v in m.iloc[-60:].items()]}
        if y10 is not None and len(y10):
            m = y10.resample("ME").last().dropna()
            e["y10"] = {"value": _r(y10.iloc[-1]), "date": str(y10.index[-1].date()), "source": y_meta,
                        "chg_12m": _r(m.iloc[-1] - m.iloc[-13]) if len(m) > 13 else None,
                        "history": [[str(d.date())[:7], _r(v)] for d, v in m.iloc[-60:].items()]}
        if cpi is not None and len(cpi) > 13:
            lag = 4 if cfreq == "Q" else 12
            yoy = (cpi / cpi.shift(lag) - 1).dropna() * 100
            last = yoy.index[-1]
            age_months = (now.year - last.year) * 12 + now.month - last.month
            e["inflation"] = {"value": _r(yoy.iloc[-1], 1), "date": str(last.date())[:7], "source": c_meta,
                              "stale": age_months > (7 if cfreq == "Q" else 4), "age_months": age_months}
        if e["short"] and e["y10"]:
            e["curve"] = _r(e["y10"]["value"] - e["short"]["value"])
        if e["short"] and e["inflation"] and not e["inflation"]["stale"]:
            e["real"] = _r(e["short"]["value"] - e["inflation"]["value"])
        out[c] = e
    carry = {}
    for p in ALL_PAIRS:
        b, q = out[p[:3]].get("short"), out[p[3:]].get("short")
        carry[p] = None if not b or not q else _r(b["value"] - q["value"])
    return {"currencies": out, "carry": carry}
