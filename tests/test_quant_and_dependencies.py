"""Migration 0003: Quantitative Prognosen, Forecast-Tracker, Dependency Engine."""

import json

import psycopg
import pytest

from forex_nexus.dependencies import knowledge


# --- Horizonte ------------------------------------------------------------------

def test_active_horizons_daily_weekly_monthly(conn):
    rows = dict(conn.execute("SELECT horizon_code, trading_days FROM ml.horizon WHERE is_active").fetchall())
    assert rows == {"1D": 1, "1W": 5, "1M": 20}


# --- Hilfsfunktionen ------------------------------------------------------------------

def _model(conn, horizon, name="lgbm"):
    conn.execute("INSERT INTO ml.label_definition (version, neutral_k, vol_method) VALUES ('t', 0.5, 'ewma') ON CONFLICT DO NOTHING")
    return conn.execute(
        """INSERT INTO ml.model_version (name, version, model_type, horizon_code, label_def_id, code_commit)
           SELECT %s, gen_random_uuid()::text, 'ml', %s, label_def_id, 'abc' FROM ml.label_definition
           WHERE version = 't' RETURNING model_version_id""", (name, horizon)).fetchone()[0]


def _snapshot(conn):
    fs = conn.execute("INSERT INTO feat.feature_set (version, definition, code_commit) VALUES (gen_random_uuid()::text, '{}', 'abc') RETURNING feature_set_id").fetchone()[0]
    return conn.execute("INSERT INTO feat.feature_snapshot (feature_set_id, instrument_id, as_of, features, input_hash) VALUES (%s, 1, clock_timestamp(), '{}', 'h') RETURNING snapshot_id", (fs,)).fetchone()[0]


def _forecast(conn, model_id, horizon, expected_return=0.001, p=(0.4, 0.35, 0.25), as_of="2026-11-16 22:00+00", **extra):
    run = conn.execute("INSERT INTO ml.forecast_run (as_of, code_commit, is_backtest) VALUES (%s, 'abc', false) RETURNING run_id", (as_of,)).fetchone()[0]
    cols = {"run_id": run, "model_version_id": model_id, "instrument_id": 1, "horizon_code": horizon,
            "snapshot_id": _snapshot(conn), "target_date": "2026-11-20", "p_bull": p[0], "p_neutral": p[1], "p_bear": p[2],
            "expected_direction": 1, "is_display_calibrated": False, "neutral_band": "{}",
            "expected_return": expected_return, **extra}
    sql = f"INSERT INTO ml.forecast ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING forecast_id"
    return conn.execute(sql, list(cols.values())).fetchone()[0]


# --- Eigenes Modell je Horizont -----------------------------------------------------------

def test_daily_forecast_cannot_come_from_monthly_model(conn):
    monthly = _model(conn, "1M")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _forecast(conn, monthly, "1D")
    daily = _model(conn, "1D")
    assert _forecast(conn, daily, "1D")


def test_range_and_confidence_constraints(conn):
    m = _model(conn, "1W")
    with pytest.raises(psycopg.errors.CheckViolation):
        _forecast(conn, m, "1W", expected_range_high=-0.01)
    with pytest.raises(psycopg.errors.CheckViolation):
        _forecast(conn, m, "1W", confidence=1.5)
    assert _forecast(conn, m, "1W", expected_range_high=0.012, expected_range_low=-0.009, confidence=0.6,
                     quantiles=json.dumps({"q10": -0.008, "q50": 0.001, "q90": 0.010}))


def test_driver_explanations_are_immutable(conn):
    m = _model(conn, "1D")
    f = _forecast(conn, m, "1D")
    conn.execute("INSERT INTO ml.forecast_driver (forecast_id, rank, feature_key, contribution, explanation_de) VALUES (%s, 1, 'risk:vix:chg_5d', 0.04, 'Test')", (f,))
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE ml.forecast_driver SET contribution = 0")


# --- Forecast-Tracker ---------------------------------------------------------------------

def test_tracker_shows_change_vs_previous_forecast(conn):
    m = _model(conn, "1W")
    _forecast(conn, m, "1W", expected_return=0.002, p=(0.5, 0.3, 0.2), as_of="2026-11-09 22:00+00")
    f2 = _forecast(conn, m, "1W", expected_return=-0.001, p=(0.3, 0.3, 0.4), as_of="2026-11-16 22:00+00")
    row = conn.execute(
        "SELECT prev_expected_return, change_expected_return, change_p_bull, state FROM ml.v_forecast_tracker WHERE forecast_id = %s",
        (f2,)).fetchone()
    assert row[0] == pytest.approx(0.002)
    assert row[1] == pytest.approx(-0.003)
    assert row[2] == pytest.approx(-0.2)
    assert row[3] == "offen"


def test_performance_view_aggregates_evaluated_forecasts(conn):
    m = _model(conn, "1D")
    f = _forecast(conn, m, "1D")
    conn.execute(
        """INSERT INTO ml.forecast_outcome (forecast_id, realized_price, realized_return, realized_class, brier, log_loss,
               direction_hit, return_error, in_interval_80)
           VALUES (%s, 1.1, 0.003, 1, 0.42, 0.9, true, 0.002, true)""", (f,))
    row = conn.execute("SELECT n, brier, hit_rate, coverage_80 FROM ml.v_performance_monthly").fetchone()
    assert row[0] == 1 and row[1] == pytest.approx(0.42) and row[2] == 1 and row[3] == 1


# --- Dependency Engine ------------------------------------------------------------------------

def test_knowledge_file_is_valid_and_covers_all_8_currencies():
    data = knowledge.read_and_validate()
    assert {r["currency"] for r in data["relationships"]} == {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"}


def test_invalid_knowledge_is_rejected(tmp_path):
    bad = tmp_path / "k.yaml"
    bad.write_text("version: x\ndrivers:\n  risk:vix: {name: VIX, category: risk}\n"
                   "relationships:\n  - {currency: SEK, driver: risk:vix, expected_sign: 2, mechanism: x, causal_chain: []}\n")
    with pytest.raises(knowledge.KnowledgeError) as e:
        knowledge.read_and_validate(bad)
    msg = str(e.value)
    assert "Hauptwährungen" in msg and "expected_sign" in msg and "causal_chain" in msg


def test_load_knowledge_all_start_as_hypothesis_and_is_idempotent(db_url, conn):
    r1 = knowledge.load(db_url)
    assert r1.new_relationships == 28
    statuses = {s for (s,) in conn.execute("SELECT DISTINCT status FROM dep.relationship")}
    assert statuses == {"hypothesis"}
    assert conn.execute("SELECT count(*) FROM dep.relationship_status_log").fetchone()[0] == 28
    r2 = knowledge.load(db_url)
    assert r2.new_relationships == 0 and r2.updated_relationships == 28
    available = conn.execute("SELECT count(*) FROM dep.driver WHERE data_status = 'available'").fetchone()[0]
    assert available == 14   # Milch, Gold, China-Aktivität fehlen noch


def _rel(conn, db_url):
    knowledge.load(db_url)
    return conn.execute("SELECT relationship_id FROM dep.relationship WHERE currency='AUD' AND driver_key='metals:iron_ore'").fetchone()[0]


def _test(conn, rid, passed):
    run = conn.execute("INSERT INTO dep.analysis_run (run_type, as_of, settings, code_commit) VALUES ('validation', now(), '{}', 'abc') RETURNING run_id").fetchone()[0]
    return conn.execute(
        """INSERT INTO dep.relationship_test (run_id, relationship_id, currency, driver_key, frequency, window_start,
               window_end, lag_periods, method, n_obs, passed)
           VALUES (%s, %s, 'AUD', 'metals:iron_ore', 'M', '2005-01-01', '2020-12-31', 1, 'ols_hac', 190, %s)
           RETURNING test_id""", (run, rid, passed)).fetchone()[0]


def test_status_cannot_be_changed_directly(db_url, conn):
    rid = _rel(conn, db_url)
    with pytest.raises(psycopg.errors.RaiseException, match="status_log"):
        conn.execute("UPDATE dep.relationship SET status = 'validated' WHERE relationship_id = %s", (rid,))


@pytest.mark.parametrize("decided_by, passed, error", [
    ("system", True, "Person"),
    ("Inhaber", False, "nicht bestanden"),
])
def test_validation_requires_human_and_passed_test(db_url, conn, decided_by, passed, error):
    rid = _rel(conn, db_url)
    tid = _test(conn, rid, passed)
    with pytest.raises(psycopg.errors.RaiseException, match=error):
        conn.execute("INSERT INTO dep.relationship_status_log (relationship_id, old_status, new_status, reason_de, test_id, decided_by) "
                     "VALUES (%s, 'hypothesis', 'validated', 'x', %s, %s)", (rid, tid, decided_by))


def test_validation_by_human_with_passed_test(db_url, conn):
    rid = _rel(conn, db_url)
    tid = _test(conn, rid, True)
    conn.execute("INSERT INTO dep.relationship_status_log (relationship_id, old_status, new_status, reason_de, test_id, decided_by) "
                 "VALUES (%s, 'hypothesis', 'validated', 'Alle Tests bestanden', %s, 'Inhaber')", (rid, tid))
    row = conn.execute("SELECT status, last_passed FROM dep.v_relationship_overview WHERE relationship_id = %s", (rid,)).fetchone()
    assert row == ("validated", True)


def test_sign_change_resets_validated_relationship(db_url, conn, tmp_path):
    rid = _rel(conn, db_url)
    tid = _test(conn, rid, True)
    conn.execute("INSERT INTO dep.relationship_status_log (relationship_id, old_status, new_status, reason_de, test_id, decided_by) "
                 "VALUES (%s, 'hypothesis', 'validated', 'ok', %s, 'Inhaber')", (rid, tid))
    text = knowledge.KNOWLEDGE_FILE.read_text(encoding="utf-8")
    marker = "  - currency: AUD\n    driver: metals:iron_ore\n    expected_sign: 1"
    assert marker in text
    changed = tmp_path / "k.yaml"
    changed.write_text(text.replace(marker, marker[:-1] + "-1"), encoding="utf-8")
    result = knowledge.load(db_url, changed)
    assert result.reset_to_testing == ["AUD/metals:iron_ore"]
    assert conn.execute("SELECT status FROM dep.relationship WHERE relationship_id = %s", (rid,)).fetchone()[0] == "testing"


def test_relationship_tests_are_immutable(db_url, conn):
    rid = _rel(conn, db_url)
    tid = _test(conn, rid, True)
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE dep.relationship_test SET passed = false WHERE test_id = %s", (tid,))
