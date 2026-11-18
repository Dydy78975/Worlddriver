"""Wirtschaftskalender (Forex Factory Wochen-Feed): Termine der 8 Hauptwährungen mit Wichtigkeit.

Rote Ordner = High, orange = Medium, gelb = Low, grau = Feiertag. Die Daten sind nur zur persönlichen
Nutzung bestimmt und werden nicht im öffentlichen Repository gespeichert.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from forex_nexus.db import connect
from forex_nexus.fx.crosses import MAJORS
from forex_nexus.ingestion.http import fetch_text

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
USER_AGENT = "WorlDDriver/1.0 (persoenliches Analysewerkzeug)"


def parse(items: list[dict]) -> list[dict]:
    out = []
    for e in items:
        ccy = e.get("country")
        if ccy not in MAJORS or e.get("impact") not in ("High", "Medium", "Low", "Holiday"):
            continue
        when = datetime.fromisoformat(e["date"])
        out.append({"currency": ccy, "scheduled_at": when, "title": e.get("title", "").strip(), "impact": e["impact"],
                    "forecast": e.get("forecast") or None, "previous": e.get("previous") or None,
                    "actual": e.get("actual") or None,
                    "source_key": f"FF|{ccy}|{when.astimezone(timezone.utc):%Y-%m-%dT%H:%M}|{e.get('title', '').strip()}"})
    return out


def ingest(conninfo: str) -> dict:
    events = parse(json.loads(fetch_text(URL, retries=2, user_agent=USER_AGENT)))
    now = datetime.now(timezone.utc)
    with connect(conninfo) as conn:
        for e in events:
            conn.execute(
                """INSERT INTO ref.event (event_type, currency, scheduled_at, title, impact, forecast, previous, actual,
                       source_key, available_at)
                   VALUES ('calendar', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (source_key) DO UPDATE SET forecast = EXCLUDED.forecast, previous = EXCLUDED.previous,
                       actual = coalesce(EXCLUDED.actual, ref.event.actual), impact = EXCLUDED.impact""",
                (e["currency"], e["scheduled_at"], e["title"], e["impact"], e["forecast"], e["previous"], e["actual"],
                 e["source_key"], now))
        conn.commit()
    return {"events": len(events), "high": sum(e["impact"] == "High" for e in events)}
