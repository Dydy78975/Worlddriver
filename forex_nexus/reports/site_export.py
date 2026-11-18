"""Website WorlᗡDriver bauen: alle Inhalte kommen aus der Datenbank und werden als JSON in die
Vorlage site/template.html eingesetzt. Ergebnis: site/index.html (eine Datei, ohne Server nutzbar).

Inhalt: Signal-Abstimmung je Paar (Tag/Woche), erwartete Spanne aus dem Prognose-Ledger,
Wirtschaftskalender der Woche, Datenstand."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from forex_nexus.db import connect
from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS
from forex_nexus.ledger.pipeline import code_commit
from forex_nexus.signals.data import load_closes
from forex_nexus.signals.report import run_and_write

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "index.html"
PLACEHOLDER = "/*__WORLDDRIVER_DATA__*/null"
BERLIN = ZoneInfo("Europe/Berlin")


def _r(x, n=6):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    return round(float(x), n)


def pips(pair: str, price: float, log_move: float) -> float:
    pip = 0.01 if pair.endswith("JPY") else 0.0001
    return price * (np.exp(log_move) - 1) / pip


def week_window(now: datetime) -> tuple[datetime, datetime]:
    """Montag bis Montag der laufenden Woche; am Wochenende schon die kommende Woche."""
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if now.weekday() >= 5:
        monday += timedelta(days=7)
    return monday, monday + timedelta(days=7)


def load_events(conn, start: datetime, end: datetime) -> list[dict]:
    rows = conn.execute(
        """SELECT currency, scheduled_at, title, impact, forecast, previous, actual FROM ref.event
           WHERE event_type = 'calendar' AND scheduled_at >= %s AND scheduled_at < %s ORDER BY scheduled_at""",
        (start, end)).fetchall()
    out = []
    for ccy, at, title, impact, fc, prev, act in rows:
        local = at.astimezone(BERLIN)
        out.append({"currency": ccy, "at": local.isoformat(), "day": local.date().isoformat(),
                    "time": local.strftime("%H:%M"), "title": title, "impact": impact, "forecast": fc,
                    "previous": prev, "actual": act})
    return out


def ranges(conn) -> dict:
    """Erwartete Spanne (80 %) je Paar und Horizont aus den neuesten Champion-Prognosen des Ledgers,
    dazu, wie oft die 80-%-Spanne im Backtest tatsächlich getroffen hat."""
    rows = conn.execute(
        """SELECT i.symbol, f.horizon_code, f.reference_price::float8, f.quantiles, f.target_date, r.as_of
           FROM ml.forecast f JOIN ml.forecast_run r USING (run_id) JOIN ref.instrument i USING (instrument_id)
           WHERE NOT f.is_shadow AND NOT r.is_backtest
             AND r.as_of = (SELECT max(as_of) FROM ml.forecast_run WHERE NOT is_backtest)""").fetchall()
    coverage = dict(conn.execute(
        """SELECT mv.horizon_code, (e.metrics->>'coverage_80')::float8 FROM ml.evaluation e
           JOIN ml.model_version mv USING (model_version_id)
           WHERE mv.status = 'champion' AND e.segment_type = 'all' AND e.eval_type = 'out_of_sample'""").fetchall())
    live = dict(conn.execute(
        """SELECT f.horizon_code, avg(o.in_interval_80::int)::float8 FROM ml.forecast_outcome o
           JOIN ml.forecast f USING (forecast_id) WHERE NOT f.is_shadow GROUP BY 1""").fetchall())
    out = {}
    for sym, h, price, q, target, as_of in rows:
        out.setdefault(sym, {})[h] = {"price": _r(price, 6), "target": str(target),
                                       "low": _r(price * np.exp(q["q10"]), 6), "high": _r(price * np.exp(q["q90"]), 6),
                                       "pips": _r(pips(sym, price, (q["q90"] - q["q10"]) / 2), 0)}
    return {"pairs": out, "coverage_backtest": {h: _r(v, 3) for h, v in coverage.items()},
            "coverage_live": {h: _r(v, 3) for h, v in live.items()}}


REPORT_DIR = ROOT / "reports" / "signals"


def collect(conninfo: str, now: datetime | None = None, report_dir: Path = REPORT_DIR) -> dict:
    now = now or datetime.now(BERLIN)
    signals = run_and_write(conninfo, report_dir)
    with connect(conninfo) as conn:
        closes = load_closes(conn)
        tail = closes.iloc[-130:]
        prices = {p: [[str(d.date()), _r(v, 6)] for d, v in tail[p].dropna().items()] for p in ALL_PAIRS if p in tail}
        start, end = week_window(now)
        events = load_events(conn, start, end)
        rng = ranges(conn)
        quality = [dict(zip(["check", "severity", "count"], r)) for r in conn.execute(
            """SELECT check_name, severity, count(*) FROM raw.data_quality_issue
               WHERE resolved_at IS NULL GROUP BY 1, 2 ORDER BY 1""").fetchall()]
        runs = [dict(zip(["source", "last_run", "status"], [s, t.isoformat() if t else None, st])) for s, t, st in
                conn.execute("""SELECT DISTINCT ON (d.name) d.name, r.finished_at, r.status
                                FROM raw.ingestion_run r JOIN ref.data_source d USING (source_id)
                                ORDER BY d.name, r.run_id DESC""").fetchall()]
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                 "as_of": str(closes.index.max().date()), "code_commit": code_commit(),
                 "price_basis": "FRED H.10 Mittagskurse New York", "calendar_source": "Forex Factory",
                 "week": {"start": start.date().isoformat(), "kw": int(start.isocalendar()[1])}},
        "pairs": ALL_PAIRS, "majors": MAJORS, "prices": prices, "signals": signals, "ranges": rng,
        "events": events, "quality": quality, "runs": runs,
    }


def build(conninfo: str, output: Path = OUTPUT, report_dir: Path = REPORT_DIR) -> Path:
    data = collect(conninfo, report_dir=report_dir)
    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError("Platzhalter für die Daten fehlt in site/template.html")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).replace("</", "<\\/")
    output.write_text(html.replace(PLACEHOLDER, payload), encoding="utf-8")
    return output
