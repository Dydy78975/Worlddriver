"""Makro- und Rohstoffreihen laden: FRED (Rohstoffe, Zinsen, Arbeitsmarkt) und einzelne EZB-Reihen.

Point-in-Time: FRED liefert für diese Reihen keine historischen Datenstände. Der Veröffentlichungs-
zeitpunkt wird deshalb vorsichtig geschätzt:  available_at = Ende der Periode + publication_lag
(is_estimated_availability = TRUE). Beispiel: Eisenerz-Monatsdurchschnitt September (Periode endet
30.09.) mit 45 Tagen Verzögerung -> gilt ab 14.11. als bekannt.
"""

from __future__ import annotations

import io
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from forex_nexus.db import connect
from forex_nexus.ingestion.fx_daily import FRED_URL, parse_fred_csv
from forex_nexus.ingestion.http import fetch_text

SOURCES = ("FRED_COMMODITY", "FRED_RATES", "FRED_LABOUR", "ECB_SERIES")
ECB_SERIES_URL = "https://data-api.ecb.europa.eu/service/data/{key}?format=csvdata"


def parse_ecb_series(text: str) -> pd.Series:
    """EZB-CSV einer einzelnen Reihe -> Series(Periodenbeginn -> Wert). '2026-09' -> 2026-09-01."""
    df = pd.read_csv(io.StringIO(text), usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
    df["date"] = pd.to_datetime(df["TIME_PERIOD"]).dt.date
    return df.set_index("date")["OBS_VALUE"].astype(float).sort_index()


def fetch_values(source: str, code: str) -> pd.Series:
    if source == "ECB_SERIES":
        return parse_ecb_series(fetch_text(ECB_SERIES_URL.format(key=code)))
    return parse_fred_csv(fetch_text(FRED_URL.format(series=code)), require_positive=False)


def period_end(d, frequency: str):
    if frequency == "M":
        return (pd.Timestamp(d) + pd.offsets.MonthEnd(0)).date()
    if frequency == "Q":
        return (pd.Timestamp(d) + pd.offsets.QuarterEnd(0)).date()
    if frequency == "W":
        return d + timedelta(days=6)
    return d


def ingest(conninfo: str, pause: float = 1.0, sources=SOURCES) -> list[dict]:
    results = []
    with connect(conninfo) as conn:
        series = conn.execute(
            """SELECT s.series_id, s.source_code, s.frequency, extract(epoch FROM s.publication_lag)::int, s.source_id, d.name
               FROM ref.series s JOIN ref.data_source d USING (source_id)
               WHERE d.name = ANY(%s) AND s.active ORDER BY s.series_id""", (list(sources),)).fetchall()
    for series_id, code, freq, lag_seconds, src, source in series:
        values = fetch_values(source, code)
        lag = timedelta(seconds=lag_seconds or 0)
        rows = [(series_id, d, datetime.combine(period_end(d, freq), datetime.min.time(), timezone.utc)
                 + timedelta(hours=23) + lag, float(v)) for d, v in values.items()]
        with connect(conninfo) as conn:
            run_id = conn.execute("INSERT INTO raw.ingestion_run (source_id) VALUES (%s) RETURNING run_id", (src,)).fetchone()[0]
            conn.execute("CREATE TEMP TABLE stage (period_date DATE, available_at TIMESTAMPTZ, value FLOAT8) ON COMMIT DROP")
            with conn.cursor().copy("COPY stage FROM STDIN") as cp:
                for _, d, at, v in rows:
                    cp.write_row((d, at, v))
            # Bereits bekannte Perioden mit gleichem Wert nicht erneut speichern; geänderte Werte
            # (Revisionen) werden als neuer Datenstand mit aktuellem Zeitstempel ergänzt.
            conn.execute(
                """INSERT INTO raw.observation (series_id, period_date, available_at, value, is_estimated_availability, run_id)
                   SELECT %s, s.period_date,
                          CASE WHEN prev.value IS NULL THEN s.available_at ELSE greatest(s.available_at, now()) END,
                          s.value, prev.value IS NULL, %s
                   FROM stage s
                   LEFT JOIN LATERAL (SELECT o.value FROM raw.observation o
                                      WHERE o.series_id = %s AND o.period_date = s.period_date
                                      ORDER BY o.available_at DESC LIMIT 1) prev ON TRUE
                   WHERE prev.value IS NULL OR prev.value <> s.value
                   ON CONFLICT DO NOTHING""", (series_id, run_id, series_id))
            conn.execute("UPDATE raw.ingestion_run SET finished_at = now(), status = 'ok', rows_inserted = %s WHERE run_id = %s",
                         (len(rows), run_id))
            conn.commit()
        results.append({"series": code, "values": len(rows), "last": str(values.index.max())})
        time.sleep(pause)
    return results


def load_series(conn, source_code: str, as_of: datetime | None = None) -> pd.Series:
    """Werte einer Reihe, optional nur mit available_at <= as_of (letzter bekannter Stand je Periode)."""
    rows = conn.execute(
        """SELECT DISTINCT ON (o.period_date) o.period_date, o.value, o.available_at
           FROM raw.observation o JOIN ref.series s USING (series_id)
           WHERE s.source_code = %s AND (%s::timestamptz IS NULL OR o.available_at <= %s)
           ORDER BY o.period_date, o.available_at DESC""", (source_code, as_of, as_of)).fetchall()
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows, columns=["period_date", "value", "available_at"]).set_index("period_date")
    s = df["value"].astype(float)
    s.attrs["available_at"] = df["available_at"]
    return s
