"""Migration 0003: Prognosen je Horizont, Spannen, Forecast-Tracker (Datenbank-Regeln)."""

import json

import psycopg
import pytest


# --- Horizonte ------------------------------------------------------------------

def test_active_horizons_daily_weekly_monthly(conn):
    rows = dict(conn.execute("SELECT horizon_code, trading_days FROM ml.horizon WHERE is_active").fetchall())
    assert rows == {"1D": 1, "1W": 5, "1M": 20}


# --- Hilfsfunktionen ------------------------------------------------------------------

def _model(conn, horizon, name="volref"):
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

