"""Tageskurse laden: FRED H.10 (Hauptquelle) und EZB-Referenzkurse (Kontrolle).

Zeitstempel (available_at):
  Ein Wechselkurs ist ein Marktpreis und zum Beobachtungszeitpunkt öffentlich.
  * FRED H.10: Mittagskurs New York  -> 12:00 America/New_York am Handelstag
  * EZB:       Referenzkurs 14:15 MEZ, veröffentlicht ca. 16:00 -> 16:00 Europe/Berlin
  Hinweis für den Live-Betrieb: FRED veröffentlicht die H.10-Reihen nur wöchentlich.
  Für tägliche Prognosen werden daher zusätzlich die EZB-Kurse bzw. Dukascopy benötigt.
"""

from __future__ import annotations

import io
import time as time_mod
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from forex_nexus.db import connect
from forex_nexus.fx.crosses import all_pairs_from_usd
from forex_nexus.ingestion.http import fetch_text

NEW_YORK = ZoneInfo("America/New_York")
FRANKFURT = ZoneInfo("Europe/Berlin")

# FRED-Reihe -> Paar in Marktkonvention (alle sieben sind bereits in Marktschreibweise)
FRED_SERIES = {
    "DEXUSEU": "EURUSD",
    "DEXUSUK": "GBPUSD",
    "DEXUSAL": "AUDUSD",
    "DEXUSNZ": "NZDUSD",
    "DEXCAUS": "USDCAD",
    "DEXSZUS": "USDCHF",
    "DEXJPUS": "USDJPY",
}
ECB_CURRENCIES = ["USD", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"]

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
ECB_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.{ccys}.EUR.SP00.A"
           "?format=csvdata&startPeriod={start}")


# --------------------------------------------------------------------------- Parser

def parse_fred_csv(text: str, require_positive: bool = True) -> pd.Series:
    """FRED-CSV -> Series(Datum -> Wert). Leere Werte bzw. '.' = kein Handelstag.
    require_positive: für Wechselkurse Pflicht; Rohstoffe können negativ sein (WTI am 20.04.2020)."""
    df = pd.read_csv(io.StringIO(text), na_values=[".", ""])
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    s = df.dropna().set_index("date")["value"].astype(float)
    if require_positive and (s <= 0).any():
        raise ValueError("FRED lieferte nicht-positive Kurse")
    return s


def parse_ecb_csv(text: str) -> pd.DataFrame:
    """EZB-CSV -> DataFrame(Datum x EURxxx)."""
    df = pd.read_csv(io.StringIO(text), usecols=["CURRENCY", "TIME_PERIOD", "OBS_VALUE"])
    df = df.dropna(subset=["OBS_VALUE"])
    df["symbol"] = "EUR" + df["CURRENCY"]
    df["date"] = pd.to_datetime(df["TIME_PERIOD"]).dt.date
    return df.pivot(index="date", columns="symbol", values="OBS_VALUE").astype(float).sort_index()


# --------------------------------------------------------------------------- Abruf

def fetch_fred_usd_pairs() -> pd.DataFrame:
    cols = {}
    for sid, sym in FRED_SERIES.items():
        cols[sym] = parse_fred_csv(fetch_text(FRED_URL.format(series=sid)))
        time_mod.sleep(1)   # Quelle schonen
    return pd.DataFrame(cols).sort_index()


def fetch_ecb_eur_pairs(start: str = "1999-01-01") -> pd.DataFrame:
    return parse_ecb_csv(fetch_text(ECB_URL.format(ccys="+".join(ECB_CURRENCIES), start=start)))


# --------------------------------------------------------------------------- Speichern

def _long(frame: pd.DataFrame, tz: ZoneInfo, local_time: time) -> pd.DataFrame:
    df = frame.stack(future_stack=True).dropna().rename("close").reset_index()
    df.columns = ["trade_date", "symbol", "close"]
    df["available_at"] = [datetime.combine(d, local_time, tz) for d in df["trade_date"]]
    return df


def store(conninfo: str, source_name: str, frame: pd.DataFrame, tz: ZoneInfo, local_time: time) -> dict:
    """Schlusskurse (breites Format: Datum x Paar) speichern."""
    return store_rows(conninfo, source_name, _long(frame, tz, local_time))


def store_rows(conninfo: str, source_name: str, rows: pd.DataFrame) -> dict:
    """Schreibt Kurse unveränderlich: Vorhandene Werte werden nie überschrieben.
    Weicht ein neu gelieferter Schlusskurs ab, wird das als Qualitätsproblem 'source_revision' gemeldet.

    rows: Spalten symbol, trade_date, close, available_at und optional open, high, low."""
    rows = rows.copy()
    for col in ("open", "high", "low"):
        if col not in rows:
            rows[col] = None
    with connect(conninfo) as conn:
        source_id = conn.execute("SELECT source_id FROM ref.data_source WHERE name = %s", (source_name,)).fetchone()[0]
        run_id = conn.execute(
            "INSERT INTO raw.ingestion_run (source_id) VALUES (%s) RETURNING run_id", (source_id,)
        ).fetchone()[0]
        conn.commit()
        try:
            conn.execute("""CREATE TEMP TABLE stage (symbol TEXT, trade_date DATE, open NUMERIC, high NUMERIC,
                            low NUMERIC, close NUMERIC, available_at TIMESTAMPTZ) ON COMMIT DROP""")
            with conn.cursor().copy("COPY stage FROM STDIN") as cp:
                for r in rows.itertuples(index=False):
                    cp.write_row((r.symbol, r.trade_date, _num(r.open), _num(r.high), _num(r.low),
                                  _num(r.close), r.available_at))
            revisions = conn.execute(
                """INSERT INTO raw.data_quality_issue (check_name, instrument_id, affected_date, severity, details)
                   SELECT 'source_revision', i.instrument_id, s.trade_date, 'warning',
                          jsonb_build_object('source', %s::text, 'stored', f.close, 'new', s.close)
                   FROM stage s
                   JOIN ref.instrument i ON i.symbol = s.symbol
                   JOIN raw.fx_daily f ON f.instrument_id = i.instrument_id AND f.trade_date = s.trade_date
                                       AND f.source_id = %s
                   WHERE f.close <> s.close
                   ON CONFLICT DO NOTHING""", (source_name, source_id)).rowcount
            inserted = conn.execute(
                """INSERT INTO raw.fx_daily (instrument_id, trade_date, source_id, open, high, low, close, available_at, run_id)
                   SELECT i.instrument_id, s.trade_date, %s, s.open, s.high, s.low, s.close, s.available_at, %s
                   FROM stage s JOIN ref.instrument i ON i.symbol = s.symbol
                   ON CONFLICT DO NOTHING""", (source_id, run_id)).rowcount
            conn.execute(
                "UPDATE raw.ingestion_run SET finished_at = now(), status = 'ok', rows_inserted = %s, message = %s WHERE run_id = %s",
                (inserted, f"{revisions} abweichende Werte gemeldet", run_id))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            conn.execute("UPDATE raw.ingestion_run SET finished_at = now(), status = 'failed', message = %s WHERE run_id = %s",
                         (str(exc)[:500], run_id))
            conn.commit()
            raise
    return {"source": source_name, "rows": len(rows), "inserted": inserted, "revisions": revisions}


def _num(x):
    return None if x is None or (isinstance(x, float) and x != x) else round(float(x), 8)


def ingest_all(conninfo: str) -> list[dict]:
    usd = fetch_fred_usd_pairs()
    all28 = all_pairs_from_usd(usd)
    crosses = all28.drop(columns=list(usd.columns))
    ecb = fetch_ecb_eur_pairs()
    return [
        store(conninfo, "FRED_H10", usd, NEW_YORK, time(12, 0)),
        store(conninfo, "FRED_H10_CROSS", crosses, NEW_YORK, time(12, 0)),
        store(conninfo, "ECB_EXR", ecb, FRANKFURT, time(16, 0)),
    ]
