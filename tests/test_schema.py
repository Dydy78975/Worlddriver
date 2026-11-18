"""Grundlegende Garantien der Datenbank (Phase 0)."""

import itertools

import psycopg
import pytest

from forex_nexus.db.migrate import MigrationError, migrate

MAJORS = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]  # Marktkonvention


# --- Stammdaten ---------------------------------------------------------------

def test_eight_currencies(conn):
    codes = {r[0] for r in conn.execute("SELECT code FROM ref.currency")}
    assert codes == set(MAJORS)


def test_28_pairs_in_market_convention(conn):
    rows = conn.execute("SELECT symbol, base_ccy, quote_ccy, pip_size FROM ref.instrument").fetchall()
    expected = {a + b for a, b in itertools.combinations(MAJORS, 2)}
    assert {r[0] for r in rows} == expected
    assert len(rows) == 28
    for symbol in ("EURUSD", "GBPUSD", "USDJPY", "AUDNZD", "EURCHF", "CADJPY"):
        assert symbol in expected
    for symbol, _, quote, pip in rows:
        assert float(pip) == (0.01 if quote == "JPY" else 0.0001), symbol


def test_horizons(conn):
    rows = dict(conn.execute("SELECT horizon_code, trading_days FROM ml.horizon").fetchall())
    assert rows == {"1D": 1, "1W": 5, "1M": 20, "3M": 63}   # 3M ist angelegt, aber inaktiv


# --- Point-in-Time ------------------------------------------------------------

def _series(conn):
    src = conn.execute("INSERT INTO ref.data_source (name, has_vintages) VALUES ('ALFRED', true) RETURNING source_id").fetchone()[0]
    return conn.execute(
        "INSERT INTO ref.series (source_id, source_code, category, currency, frequency) "
        "VALUES (%s, 'CPIAUCSL', 'cpi', 'USD', 'M') RETURNING series_id", (src,)
    ).fetchone()[0]


def test_observations_as_of_never_sees_the_future(conn):
    sid = _series(conn)
    conn.execute(
        """INSERT INTO raw.observation (series_id, period_date, available_at, value) VALUES
           (%(s)s, '2026-09-01', '2026-10-15 12:30+00', 2.9),   -- Erstveröffentlichung
           (%(s)s, '2026-09-01', '2026-11-13 13:30+00', 3.0),   -- Revision
           (%(s)s, '2026-10-01', '2026-11-13 13:30+00', 3.1)""", {"s": sid},
    )

    def as_of(ts):
        return conn.execute(
            "SELECT period_date::text, value FROM raw.observations_as_of(%s, %s) ORDER BY 1", (sid, ts)
        ).fetchall()

    assert as_of("2026-10-01 00:00+00") == []                                  # noch nichts bekannt
    assert as_of("2026-10-20 00:00+00") == [("2026-09-01", 2.9)]               # nur Erstwert
    assert as_of("2026-11-13 13:29+00") == [("2026-09-01", 2.9)]               # eine Minute vorher
    assert as_of("2026-11-20 00:00+00") == [("2026-09-01", 3.0), ("2026-10-01", 3.1)]


# --- Unveränderliches Prognose-Ledger -------------------------------------------

def _forecast(conn, p=(0.4, 0.3, 0.3)):
    conn.execute("INSERT INTO ml.label_definition (version, neutral_k, vol_method) VALUES ('t', 0.5, 'ewma_60d') ON CONFLICT DO NOTHING")
    mv = conn.execute(
        "INSERT INTO ml.model_version (name, version, model_type, horizon_code, label_def_id, code_commit) "
        "SELECT 'climatology', gen_random_uuid()::text, 'baseline', '1W', label_def_id, 'abc' "
        "FROM ml.label_definition WHERE version='t' RETURNING model_version_id"
    ).fetchone()[0]
    fs = conn.execute(
        "INSERT INTO feat.feature_set (version, definition, code_commit) VALUES (gen_random_uuid()::text, '{}', 'abc') RETURNING feature_set_id"
    ).fetchone()[0]
    snap = conn.execute(
        "INSERT INTO feat.feature_snapshot (feature_set_id, instrument_id, as_of, features, input_hash) "
        "VALUES (%s, 1, now(), '{}', 'h') RETURNING snapshot_id", (fs,)
    ).fetchone()[0]
    run = conn.execute(
        "INSERT INTO ml.forecast_run (as_of, code_commit, is_backtest) VALUES (now(), 'abc', false) RETURNING run_id"
    ).fetchone()[0]
    return conn.execute(
        """INSERT INTO ml.forecast (run_id, model_version_id, instrument_id, horizon_code, snapshot_id,
               target_date, p_bull, p_neutral, p_bear, expected_direction, is_display_calibrated, neutral_band)
           VALUES (%s, %s, 1, '1W', %s, current_date + 7, %s, %s, %s, 1, false, '{}') RETURNING forecast_id""",
        (run, mv, snap, *p),
    ).fetchone()[0]


@pytest.mark.parametrize("stmt", [
    "UPDATE ml.forecast SET p_bull = 0.9",
    "DELETE FROM ml.forecast",
    "UPDATE ml.forecast_run SET notes = 'x'",
    "DELETE FROM feat.feature_snapshot",
])
def test_ledger_is_append_only(conn, stmt):
    _forecast(conn)
    with pytest.raises(psycopg.errors.RaiseException, match="unveränderlich"):
        conn.execute(stmt)


def test_probabilities_must_sum_to_one(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        _forecast(conn, p=(0.5, 0.3, 0.3))


def test_outcome_is_immutable(conn):
    fid = _forecast(conn)
    conn.execute(
        "INSERT INTO ml.forecast_outcome (forecast_id, realized_price, realized_return, realized_class, brier, log_loss) "
        "VALUES (%s, 1.1, 0.01, 1, 0.5, 0.9)", (fid,)
    )
    with pytest.raises(psycopg.errors.RaiseException):
        conn.execute("UPDATE ml.forecast_outcome SET brier = 0")


# --- A+-Regel-Engine ----------------------------------------------------------

def _setup_run(conn, results):
    ids = [conn.execute(
        "INSERT INTO setup.rule_definition (rule_key, version, description) VALUES (%s, '1', 'Test') "
        "ON CONFLICT (rule_key, version) DO UPDATE SET description = EXCLUDED.description RETURNING rule_id",
        (f"criterion_{i}",)).fetchone()[0] for i in range(1, 7)]
    run = conn.execute(
        "INSERT INTO setup.evaluation_run (as_of, instrument_id) VALUES (now(), 1) RETURNING eval_run_id"
    ).fetchone()[0]
    for rid, passed in zip(ids, results):
        conn.execute("INSERT INTO setup.rule_check VALUES (%s, %s, %s)", (run, rid, passed))
    return run


@pytest.mark.parametrize("results, expected", [
    ([True] * 6, True),
    ([True] * 5 + [False], False),
    ([True] * 5, False),        # eine Regel nicht geprüft -> kein Setup
])
def test_a_plus_requires_all_six(conn, results, expected):
    run = _setup_run(conn, results)
    found = conn.execute("SELECT 1 FROM setup.a_plus_setup WHERE eval_run_id = %s", (run,)).fetchone()
    assert (found is not None) is expected


# --- Migrationen --------------------------------------------------------------

def test_migrate_is_idempotent(db_url):
    assert migrate(db_url) == []


def test_changed_migration_is_rejected(db_url, tmp_path):
    from forex_nexus.db.migrate import MIGRATIONS_DIR
    for f in MIGRATIONS_DIR.glob("*.sql"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8") + "\n-- verändert\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="verändert"):
        migrate(db_url, tmp_path)


def test_migrate_works_on_non_utf8_database(admin_url):
    """Regression: Server mit SQL_ASCII-Standard brach an Umlauten im Schema ab."""
    name = "fnx_test_sqlascii"
    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}"')
        c.execute(f"CREATE DATABASE \"{name}\" ENCODING 'SQL_ASCII' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0")
    try:
        assert migrate(psycopg.conninfo.make_conninfo(admin_url, dbname=name))[0] == "0001"
    finally:
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
