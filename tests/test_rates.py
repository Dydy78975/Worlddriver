"""Zinsen & Notenbanken: Veränderungen, Inflation mit Aktualitätsprüfung, Realzins, Zinsdifferenz."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from forex_nexus.fundamentals import rates


def _store(conn, code, points):
    sid = conn.execute("SELECT series_id FROM ref.series WHERE source_code = %s", (code,)).fetchone()[0]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO raw.observation (series_id, period_date, available_at, value) VALUES (%s, %s, now(), %s)",
                        [(sid, d.date(), v) for d, v in points])


def test_rates_build(db_url, conn):
    months = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
    _store(conn, "DFF", [(d, 3.0 + 0.05 * i) for i, d in enumerate(months)])
    _store(conn, "ECBDFR", [(d, 2.0) for d in months])
    _store(conn, "DGS10", [(d, 4.0) for d in months])
    _store(conn, "CPIAUCSL", [(d, 100 * 1.03 ** (i / 12)) for i, d in enumerate(months)])
    _store(conn, "GBRCPIALLMINMEI", [(d, 100 + i) for i, d in enumerate(months[:15])])   # endet 2025-03 -> veraltet
    out = rates.build(conn, datetime(2026, 11, 18, tzinfo=timezone.utc))
    usd, eur, gbp = out["currencies"]["USD"], out["currencies"]["EUR"], out["currencies"]["GBP"]
    assert usd["short"]["value"] == pytest.approx(3.0 + 0.05 * 33)
    assert usd["short"]["chg_12m"] == pytest.approx(0.6)
    assert usd["inflation"]["value"] == pytest.approx(3.0, abs=0.05) and not usd["inflation"]["stale"]
    assert usd["real"] == pytest.approx(usd["short"]["value"] - usd["inflation"]["value"], abs=0.01)
    assert usd["curve"] == pytest.approx(4.0 - usd["short"]["value"])
    assert gbp["inflation"]["stale"] and "real" not in gbp
    assert out["carry"]["EURUSD"] == pytest.approx(2.0 - usd["short"]["value"])
    assert out["carry"]["GBPUSD"] is None                                              # kein Zins für GBP
