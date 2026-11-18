"""COT-Daten der CFTC (Legacy-Bericht, nur Futures) für die 8 Hauptwährungen laden.

Point-in-Time: Die Positionen gelten für Dienstag, werden aber erst am Freitag um 15:30 New York
veröffentlicht. Genau dieser Zeitpunkt wird als available_at gespeichert.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from forex_nexus.db import connect
from forex_nexus.ingestion.http import fetch_text

NEW_YORK = ZoneInfo("America/New_York")
API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
CONTRACTS = {  # CFTC-Kontraktcode -> Währung
    "099741": "EUR", "097741": "JPY", "096742": "GBP", "092741": "CHF",
    "090741": "CAD", "232741": "AUD", "112741": "NZD", "098662": "USD",   # USD = Dollar-Index (ICE)
}
FIELDS = ["report_date_as_yyyy_mm_dd", "cftc_contract_market_code", "open_interest_all",
          "comm_positions_long_all", "comm_positions_short_all", "noncomm_positions_long_all",
          "noncomm_positions_short_all", "nonrept_positions_long_all", "nonrept_positions_short_all"]


def release_time(report_date) -> datetime:
    """Freitag derselben Woche, 15:30 New York (regulärer Veröffentlichungstermin der CFTC)."""
    friday = report_date + timedelta(days=(4 - report_date.weekday()) % 7)
    return datetime.combine(friday, time(15, 30), NEW_YORK)


def parse(rows: list[dict]) -> list[tuple]:
    out = []
    for r in rows:
        code = r.get("cftc_contract_market_code")
        if code not in CONTRACTS:
            continue
        d = datetime.fromisoformat(r["report_date_as_yyyy_mm_dd"][:10]).date()
        num = lambda k: int(float(r[k])) if r.get(k) not in (None, "") else None
        out.append((code, CONTRACTS[code], d, release_time(d), num("open_interest_all"),
                    num("comm_positions_long_all"), num("comm_positions_short_all"),
                    num("noncomm_positions_long_all"), num("noncomm_positions_short_all"),
                    num("nonrept_positions_long_all"), num("nonrept_positions_short_all")))
    return out


def fetch(since: str = "2005-01-01") -> list[dict]:
    codes = ",".join(f"'{c}'" for c in CONTRACTS)
    q = {"$select": ",".join(FIELDS), "$where": f"cftc_contract_market_code in({codes}) AND report_date_as_yyyy_mm_dd >= '{since}'",
         "$order": "report_date_as_yyyy_mm_dd", "$limit": "50000"}
    return json.loads(fetch_text(API + "?" + urllib.parse.urlencode(q)))


def ingest(conninfo: str, since: str = "2005-01-01") -> dict:
    rows = parse(fetch(since))
    with connect(conninfo) as conn:
        src = conn.execute("SELECT source_id FROM ref.data_source WHERE name = 'CFTC_COT'").fetchone()[0]
        run_id = conn.execute("INSERT INTO raw.ingestion_run (source_id) VALUES (%s) RETURNING run_id", (src,)).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO raw.cot_position (contract_code, currency, report_date, available_at, open_interest,
                       comm_long, comm_short, noncomm_long, noncomm_short, nonrept_long, nonrept_short, run_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                [r + (run_id,) for r in rows])
        conn.execute("UPDATE raw.ingestion_run SET finished_at = now(), status = 'ok', rows_inserted = %s WHERE run_id = %s",
                     (len(rows), run_id))
        conn.commit()
    return {"rows": len(rows), "last": str(max(r[2] for r in rows)) if rows else None}
