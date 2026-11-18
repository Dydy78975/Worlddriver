"""Gesamtablauf mit künstlichen Kursen: train → promote → forecast → (neue Kurse) → evaluate → Website."""

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from forex_nexus.dependencies import knowledge
from forex_nexus.ingestion.fx_daily import store_rows
from forex_nexus.ledger import pipeline
from forex_nexus.reports import site_export
from tests.test_engine import synthetic_closes, synthetic_vix

NY = ZoneInfo("America/New_York")


def _store(db_url, closes):
    rows = closes.stack().rename("close").reset_index()
    rows.columns = ["trade_date", "symbol", "close"]
    rows["available_at"] = [datetime.combine(d, time(12), NY) for d in rows["trade_date"]]
    direct = rows["symbol"].str.contains("USD")          # wie im Betrieb: Dollar-Paare direkt, Rest Kreuzkurse
    store_rows(db_url, "FRED_H10", rows[direct])
    store_rows(db_url, "FRED_H10_CROSS", rows[~direct])


def _store_vix(conn, vix):
    sid = conn.execute("SELECT series_id FROM ref.series WHERE source_code = 'VIXCLS'").fetchone()[0]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO raw.observation (series_id, period_date, available_at, value) VALUES (%s, %s, %s, %s)",
                        [(sid, d, datetime.combine(d, time(23), NY), float(v)) for d, v in vix.items()])


@pytest.fixture(scope="module")
def closes_all():
    return synthetic_closes("2004-01-01", "2008-03-31")


def test_full_pipeline(db_url, conn, closes_all, tmp_path, monkeypatch):
    knowledge.load(db_url)
    cut = closes_all.index[closes_all.index <= pd.Timestamp("2007-12-31").date()][-1]
    first, later = closes_all.loc[:cut], closes_all.loc[closes_all.index > cut]
    _store(db_url, first)
    _store_vix(conn, synthetic_vix(closes_all.index))
    monkeypatch.setattr(pipeline, "ANALYSIS_START", pd.Timestamp("2004-01-01").date())

    summary = pipeline.train(db_url, tmp_path, log=lambda m: None)
    assert set(summary["horizons"]) == {"1D", "1W", "1M"}
    version = summary["version"]
    for h, info in summary["horizons"].items():
        assert info["champion_recommendation"] in ("climatology", "volref")    # reiner Zufall: kein Richtungsmodell
        pipeline.promote(db_url, version, h, info["champion_recommendation"], "Test", "Testfreigabe")
    with pytest.raises(ValueError):
        pipeline.promote(db_url, version, "1D", "logreg", "  ", "ohne Namen")

    r1 = pipeline.forecast(db_url, log=lambda m: None)
    assert r1["written"] == 28 * 3 * 4
    assert pipeline.forecast(db_url, log=lambda m: None)["skipped"] == 1      # gleicher Tag: nichts Neues

    champions = conn.execute(
        """SELECT count(*), count(*) FILTER (WHERE horizon_code = '1D' AND expected_range_high IS NULL)
           FROM ml.forecast WHERE NOT is_shadow""").fetchone()
    assert champions == (84, 28)                                               # Tagesprognose ohne Spanne
    drivers = conn.execute("SELECT count(*) FROM ml.forecast_driver").fetchone()[0]
    assert drivers == 84 * 4

    assert pipeline.evaluate_due(db_url, log=lambda m: None) == 0              # noch nichts fällig
    _store(db_url, later)                                                      # die Zeit vergeht …
    n = pipeline.evaluate_due(db_url, log=lambda m: None)
    assert n == 28 * 3 * 4
    assert pipeline.evaluate_due(db_url, log=lambda m: None) == 0
    row = conn.execute("""SELECT min(brier), max(brier), bool_and(realized_price > 0), count(*) FILTER (WHERE in_interval_80)
                          FROM ml.forecast_outcome""").fetchone()
    assert 0 <= row[0] <= row[1] <= 2 and row[2]
    assert 0.5 < row[3] / n < 0.98

    # Prognose am neuen Tag nutzt den eingefrorenen Trainingsstand (train_end bleibt unverändert)
    before = conn.execute("SELECT model_version_id, train_end FROM ml.model_version WHERE status = 'champion' ORDER BY 1").fetchall()
    assert pipeline.forecast(db_url, log=lambda m: None)["written"] == 28 * 3 * 4
    after = conn.execute("SELECT model_version_id, train_end FROM ml.model_version WHERE status = 'champion' ORDER BY 1").fetchall()
    assert before == after

    monkeypatch.setattr(site_export, "ANALYSIS_START", pd.Timestamp("2004-01-01").date())
    out = site_export.build(db_url, tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert site_export.PLACEHOLDER not in html
    payload = html.split("const D = ", 1)[1].split(";\nconst $ =", 1)[0]
    data = json.loads(payload.replace("<\\/", "</"))
    assert len([f for f in data["forecasts"] if f["horizon"] == "1D"]) == 28
    assert data["ledger"]["evaluated"] == 336
    assert set(data["backtest"]) == {"1D", "1W", "1M"}
    assert len(data["dependencies"]) == 28
