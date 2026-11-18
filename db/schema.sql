-- FOREX NEXUS AI – Datenbankschema (Entwurf v0.1)
-- PostgreSQL 16
-- Erklärung der Tabellen: docs/04_datenbank.md
--
-- Grundregeln:
--   * Rohdaten sind bitemporal: period_date (worauf bezieht sich der Wert)
--     und available_at (ab wann war er öffentlich bekannt).
--   * Prognosen und ihre Eingaben sind unveränderlich (append-only).

CREATE SCHEMA IF NOT EXISTS ref;      -- Stammdaten
CREATE SCHEMA IF NOT EXISTS raw;      -- Rohdaten aus Quellen
CREATE SCHEMA IF NOT EXISTS feat;     -- berechnete Merkmale
CREATE SCHEMA IF NOT EXISTS ml;       -- Modelle, Prognosen, Auswertung
CREATE SCHEMA IF NOT EXISTS analysis; -- Analogien, Makro-Beziehungen, Regime
CREATE SCHEMA IF NOT EXISTS report;   -- Wochenberichte
CREATE SCHEMA IF NOT EXISTS setup;    -- A+-Regel-Engine (strikt getrennt)

-- =====================================================================
-- STAMMDATEN
-- =====================================================================

CREATE TABLE ref.currency (
    code            CHAR(3) PRIMARY KEY,           -- USD, EUR, ...
    name            TEXT NOT NULL,
    central_bank    TEXT NOT NULL,                 -- Fed, EZB, ...
    country_code    TEXT NOT NULL                  -- US, EA, JP, GB, CH, CA, AU, NZ
);

CREATE TABLE ref.instrument (
    instrument_id   SMALLSERIAL PRIMARY KEY,
    symbol          TEXT UNIQUE NOT NULL,          -- EURUSD
    base_ccy        CHAR(3) NOT NULL REFERENCES ref.currency(code),
    quote_ccy       CHAR(3) NOT NULL REFERENCES ref.currency(code),
    pip_size        NUMERIC NOT NULL,
    CHECK (base_ccy <> quote_ccy)
);

CREATE TABLE ref.data_source (
    source_id       SMALLSERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,          -- FRED, ALFRED, ECB, BIS, CFTC, DUKASCOPY
    url             TEXT,
    license_note    TEXT,
    has_vintages    BOOLEAN NOT NULL DEFAULT FALSE -- echte historische Datenstände?
);

-- Beschreibung jeder Makro-Zeitreihe
CREATE TABLE ref.series (
    series_id       SERIAL PRIMARY KEY,
    source_id       SMALLINT NOT NULL REFERENCES ref.data_source(source_id),
    source_code     TEXT NOT NULL,                 -- z. B. 'DGS2' bei FRED
    category        TEXT NOT NULL,                 -- policy_rate, yield_2y, yield_10y, cpi_yoy, cot, vix, ...
    currency        CHAR(3) REFERENCES ref.currency(code),
    frequency       TEXT NOT NULL,                 -- D, W, M, Q
    unit            TEXT,
    -- Wenn keine echten Vintages: geschätzte Veröffentlichungsverzögerung
    publication_lag INTERVAL,
    description     TEXT,
    UNIQUE (source_id, source_code)
);

-- Zentralbank-Sitzungen und wichtige Termine
CREATE TABLE ref.event (
    event_id        SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,                 -- cb_meeting, cpi_release, ...
    currency        CHAR(3) REFERENCES ref.currency(code),
    scheduled_at    TIMESTAMPTZ NOT NULL,
    is_unscheduled  BOOLEAN NOT NULL DEFAULT FALSE,
    outcome         JSONB,                         -- z. B. {"rate_change_bp": -25}
    available_at    TIMESTAMPTZ                    -- wann war das Ergebnis bekannt
);

-- =====================================================================
-- ROHDATEN
-- =====================================================================

CREATE TABLE raw.ingestion_run (
    run_id          BIGSERIAL PRIMARY KEY,
    source_id       SMALLINT NOT NULL REFERENCES ref.data_source(source_id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running', -- running, ok, failed
    rows_inserted   INTEGER,
    message         TEXT
);

-- Tageskurse; Schlusszeit 17:00 New York als Referenz
CREATE TABLE raw.fx_daily (
    instrument_id   SMALLINT NOT NULL REFERENCES ref.instrument(instrument_id),
    trade_date      DATE NOT NULL,
    source_id       SMALLINT NOT NULL REFERENCES ref.data_source(source_id),
    open            NUMERIC, high NUMERIC, low NUMERIC,
    close           NUMERIC NOT NULL,
    available_at    TIMESTAMPTZ NOT NULL,
    run_id          BIGINT REFERENCES raw.ingestion_run(run_id),
    PRIMARY KEY (instrument_id, trade_date, source_id)
);

-- Makro-Beobachtungen, bitemporal: jede Revision ist eine neue Zeile
CREATE TABLE raw.observation (
    series_id       INTEGER NOT NULL REFERENCES ref.series(series_id),
    period_date     DATE NOT NULL,                 -- worauf sich der Wert bezieht
    available_at    TIMESTAMPTZ NOT NULL,          -- ab wann öffentlich bekannt
    value           DOUBLE PRECISION,
    is_estimated_availability BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE = aus publication_lag geschätzt
    run_id          BIGINT REFERENCES raw.ingestion_run(run_id),
    PRIMARY KEY (series_id, period_date, available_at)
);
CREATE INDEX ON raw.observation (series_id, available_at);

-- Point-in-Time-Abfrage: letzter bekannter Stand je Periode zum Zeitpunkt as_of
CREATE FUNCTION raw.observations_as_of(p_series INTEGER, p_as_of TIMESTAMPTZ)
RETURNS TABLE (period_date DATE, value DOUBLE PRECISION, available_at TIMESTAMPTZ)
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT ON (o.period_date) o.period_date, o.value, o.available_at
    FROM raw.observation o
    WHERE o.series_id = p_series AND o.available_at <= p_as_of
    ORDER BY o.period_date, o.available_at DESC
$$;

CREATE TABLE raw.data_quality_issue (
    issue_id        BIGSERIAL PRIMARY KEY,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name      TEXT NOT NULL,                 -- gap, outlier, source_mismatch, stale
    instrument_id   SMALLINT REFERENCES ref.instrument(instrument_id),
    series_id       INTEGER REFERENCES ref.series(series_id),
    affected_date   DATE,
    severity        TEXT NOT NULL,                 -- info, warning, blocking
    details         JSONB,
    resolved_at     TIMESTAMPTZ
);

-- =====================================================================
-- FEATURES
-- =====================================================================

CREATE TABLE feat.feature_set (
    feature_set_id  SERIAL PRIMARY KEY,
    version         TEXT UNIQUE NOT NULL,          -- z. B. 'fs-2026.12-a'
    definition      JSONB NOT NULL,                -- Liste der Merkmale + Parameter
    code_commit     TEXT NOT NULL,                 -- Git-Commit des Feature-Codes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Merkmale je Paar und Stichtag, nur aus Daten mit available_at <= as_of
CREATE TABLE feat.feature_snapshot (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    feature_set_id  INTEGER NOT NULL REFERENCES feat.feature_set(feature_set_id),
    instrument_id   SMALLINT REFERENCES ref.instrument(instrument_id), -- NULL = Einzelwährung
    currency        CHAR(3) REFERENCES ref.currency(code),
    as_of           TIMESTAMPTZ NOT NULL,
    features        JSONB NOT NULL,
    input_hash      TEXT NOT NULL,                 -- Prüfsumme der verwendeten Rohdaten
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (feature_set_id, instrument_id, currency, as_of),
    CHECK ((instrument_id IS NULL) <> (currency IS NULL))
);

-- =====================================================================
-- MODELLE, PROGNOSEN, AUSWERTUNG
-- =====================================================================

CREATE TABLE ml.horizon (
    horizon_code    TEXT PRIMARY KEY,              -- 1W, 1M, 3M
    trading_days    SMALLINT NOT NULL              -- 5, 21, 63
);

-- Definition der Szenarien (z. B. neutral = |Rendite| < k * erwartete Vola)
CREATE TABLE ml.label_definition (
    label_def_id    SERIAL PRIMARY KEY,
    version         TEXT UNIQUE NOT NULL,
    neutral_k       DOUBLE PRECISION NOT NULL,
    vol_method      TEXT NOT NULL,                 -- z. B. 'ewma_60d'
    description     TEXT
);

CREATE TABLE ml.model_version (
    model_version_id SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,                 -- baseline_climatology, logreg, lgbm, xgb
    version         TEXT NOT NULL,
    model_type      TEXT NOT NULL,                 -- baseline, statistical, ml
    horizon_code    TEXT NOT NULL REFERENCES ml.horizon(horizon_code),
    feature_set_id  INTEGER REFERENCES feat.feature_set(feature_set_id),
    label_def_id    INTEGER NOT NULL REFERENCES ml.label_definition(label_def_id),
    hyperparams     JSONB,
    train_start     DATE,
    train_end       DATE,
    code_commit     TEXT NOT NULL,
    artifact_uri    TEXT,                          -- MLflow-Pfad
    is_calibrated   BOOLEAN NOT NULL DEFAULT FALSE,
    status          TEXT NOT NULL DEFAULT 'candidate'
                    CHECK (status IN ('candidate','shadow','champion','retired','rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name, version, horizon_code)
);

-- Ein täglicher Prognoselauf
CREATE TABLE ml.forecast_run (
    run_id          BIGSERIAL PRIMARY KEY,
    as_of           TIMESTAMPTZ NOT NULL,          -- Datenstand der Prognose
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    code_commit     TEXT NOT NULL,
    is_backtest     BOOLEAN NOT NULL,              -- Backtest und Live strikt getrennt
    notes           TEXT
);

-- DAS PROGNOSE-LEDGER (unveränderlich)
CREATE TABLE ml.forecast (
    forecast_id     BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES ml.forecast_run(run_id),
    model_version_id INTEGER NOT NULL REFERENCES ml.model_version(model_version_id),
    instrument_id   SMALLINT REFERENCES ref.instrument(instrument_id),
    currency        CHAR(3) REFERENCES ref.currency(code), -- für Währungsstärke-Prognosen
    horizon_code    TEXT NOT NULL REFERENCES ml.horizon(horizon_code),
    snapshot_id     BIGINT NOT NULL REFERENCES feat.feature_snapshot(snapshot_id),
    reference_price NUMERIC,                       -- Kurs zum Prognosezeitpunkt
    target_date     DATE NOT NULL,                 -- Ende des Horizonts
    p_bull          DOUBLE PRECISION NOT NULL,
    p_neutral       DOUBLE PRECISION NOT NULL,
    p_bear          DOUBLE PRECISION NOT NULL,
    expected_direction SMALLINT NOT NULL CHECK (expected_direction IN (-1,0,1)),
    expected_vol    DOUBLE PRECISION,              -- erwartete Volatilität im Horizont
    quantiles       JSONB,                         -- {"q10":..,"q50":..,"q90":..}
    uncertainty     DOUBLE PRECISION,              -- z. B. normierte Entropie 0..1
    is_display_calibrated BOOLEAN NOT NULL,        -- darf als Wahrscheinlichkeit angezeigt werden
    neutral_band    JSONB NOT NULL,                -- konkrete Grenzen bullisch/bärisch
    top_drivers     JSONB,                         -- SHAP-Beiträge
    invalidation_rules JSONB,                      -- Bedingungen für Ungültigkeit
    is_shadow       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (abs(p_bull + p_neutral + p_bear - 1) < 1e-6),
    CHECK ((instrument_id IS NULL) <> (currency IS NULL))
);
CREATE INDEX ON ml.forecast (target_date);
CREATE INDEX ON ml.forecast (instrument_id, horizon_code, created_at);

-- Unveränderlichkeit technisch erzwingen
CREATE FUNCTION ml.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Tabelle % ist unveränderlich (append-only)', TG_TABLE_NAME;
END $$;

CREATE TRIGGER forecast_immutable BEFORE UPDATE OR DELETE ON ml.forecast
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();
CREATE TRIGGER forecast_run_immutable BEFORE UPDATE OR DELETE ON ml.forecast_run
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();
CREATE TRIGGER snapshot_immutable BEFORE UPDATE OR DELETE ON feat.feature_snapshot
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();

-- Ungültigkeits-Ereignisse während der Laufzeit (Prognose selbst bleibt unverändert)
CREATE TABLE ml.forecast_invalidation (
    forecast_id     BIGINT NOT NULL REFERENCES ml.forecast(forecast_id),
    triggered_at    TIMESTAMPTZ NOT NULL,
    rule_name       TEXT NOT NULL,
    details         JSONB,
    PRIMARY KEY (forecast_id, rule_name)
);

-- Ergebnis nach Ablauf des Horizonts
CREATE TABLE ml.forecast_outcome (
    forecast_id     BIGINT PRIMARY KEY REFERENCES ml.forecast(forecast_id),
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    realized_price  NUMERIC NOT NULL,
    realized_return DOUBLE PRECISION NOT NULL,
    realized_class  SMALLINT NOT NULL CHECK (realized_class IN (-1,0,1)),
    brier           DOUBLE PRECISION NOT NULL,
    log_loss        DOUBLE PRECISION NOT NULL,
    direction_hit   BOOLEAN,
    regime_at_forecast TEXT,
    error_tags      TEXT[]                         -- Ergebnis der Fehleranalyse
);
CREATE TRIGGER outcome_immutable BEFORE UPDATE OR DELETE ON ml.forecast_outcome
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();

-- Aggregierte Kennzahlen (Backtest, OOS, Live)
CREATE TABLE ml.evaluation (
    evaluation_id   BIGSERIAL PRIMARY KEY,
    model_version_id INTEGER NOT NULL REFERENCES ml.model_version(model_version_id),
    eval_type       TEXT NOT NULL CHECK (eval_type IN ('walk_forward','out_of_sample','shadow','live')),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    segment_type    TEXT NOT NULL,                 -- all, currency, instrument, horizon, regime
    segment_value   TEXT NOT NULL,
    n_forecasts     INTEGER NOT NULL,
    metrics         JSONB NOT NULL,                -- brier, log_loss, accuracy, ece, bss_vs_baseline, ...
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Freigabeprozess Challenger -> Champion
CREATE TABLE ml.model_promotion (
    promotion_id    SERIAL PRIMARY KEY,
    challenger_id   INTEGER NOT NULL REFERENCES ml.model_version(model_version_id),
    champion_id     INTEGER REFERENCES ml.model_version(model_version_id),
    oos_evaluation_id BIGINT REFERENCES ml.evaluation(evaluation_id),
    test_results    JSONB NOT NULL,                -- z. B. Diebold-Mariano, Bootstrap-KI
    decision        TEXT NOT NULL CHECK (decision IN ('to_shadow','promoted','rejected')),
    decided_by      TEXT NOT NULL,                 -- Mensch, nie automatisch
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    rationale       TEXT
);

-- =====================================================================
-- ANALYSE: REGIME, ANALOGIEN, MAKRO-BEZIEHUNGEN
-- =====================================================================

CREATE TABLE analysis.regime (
    as_of           DATE NOT NULL,
    dimension       TEXT NOT NULL,                 -- risk (VIX), usd_trend, rate_cycle_USD, ...
    label           TEXT NOT NULL,                 -- risk_on, risk_off, hiking, cutting, ...
    method_version  TEXT NOT NULL,
    PRIMARY KEY (as_of, dimension, method_version)
);

CREATE TABLE analysis.analog_query (
    query_id        BIGSERIAL PRIMARY KEY,
    as_of           TIMESTAMPTZ NOT NULL,
    instrument_id   SMALLINT NOT NULL REFERENCES ref.instrument(instrument_id),
    conditions      JSONB NOT NULL,                -- Regeln oder Ähnlichkeitsvektor
    method          TEXT NOT NULL,                 -- rule, knn
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analysis.analog_result (
    query_id        BIGINT NOT NULL REFERENCES analysis.analog_query(query_id),
    horizon_code    TEXT NOT NULL REFERENCES ml.horizon(horizon_code),
    n_cases         INTEGER NOT NULL,
    n_independent   INTEGER NOT NULL,              -- nach Entfernen überlappender Fälle
    stats           JSONB NOT NULL,                -- Mittel, Median, Quantile, Trefferquote, KI
    unconditional   JSONB NOT NULL,                -- Vergleich zur normalen Verteilung
    case_dates      DATE[],
    PRIMARY KEY (query_id, horizon_code)
);

CREATE TABLE analysis.relationship (
    as_of           DATE NOT NULL,
    instrument_id   SMALLINT NOT NULL REFERENCES ref.instrument(instrument_id),
    driver          TEXT NOT NULL,                 -- z. B. 'rate_diff_2y', 'vix', 'dxy'
    window_days     SMALLINT NOT NULL,
    correlation     DOUBLE PRECISION,
    beta            DOUBLE PRECISION,
    beta_stability  DOUBLE PRECISION,
    break_detected  BOOLEAN NOT NULL DEFAULT FALSE,
    method_version  TEXT NOT NULL,
    PRIMARY KEY (as_of, instrument_id, driver, window_days, method_version)
);

-- =====================================================================
-- WOCHENBERICHT
-- =====================================================================

CREATE TABLE report.weekly_report (
    report_id       SERIAL PRIMARY KEY,
    week_ending     DATE UNIQUE NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    facts           JSONB NOT NULL,                -- alle Zahlen aus der Datenbank
    body_markdown   TEXT NOT NULL,
    code_commit     TEXT NOT NULL
);

-- =====================================================================
-- A+-REGEL-ENGINE (strikt getrennt von den Prognosen)
-- =====================================================================

CREATE TABLE setup.rule_definition (
    rule_id         SERIAL PRIMARY KEY,
    rule_key        TEXT NOT NULL,                 -- criterion_1 ... criterion_6
    version         TEXT NOT NULL,
    description     TEXT NOT NULL,
    parameters      JSONB,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (rule_key, version)
);

CREATE TABLE setup.evaluation_run (
    eval_run_id     BIGSERIAL PRIMARY KEY,
    as_of           TIMESTAMPTZ NOT NULL,
    instrument_id   SMALLINT NOT NULL REFERENCES ref.instrument(instrument_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE setup.rule_check (
    eval_run_id     BIGINT NOT NULL REFERENCES setup.evaluation_run(eval_run_id),
    rule_id         INTEGER NOT NULL REFERENCES setup.rule_definition(rule_id),
    passed          BOOLEAN NOT NULL,
    evidence        JSONB,
    PRIMARY KEY (eval_run_id, rule_id)
);

-- Ein A+-Setup existiert nur, wenn alle sechs Regeln bestanden sind.
CREATE VIEW setup.a_plus_setup AS
SELECT er.eval_run_id, er.as_of, er.instrument_id
FROM setup.evaluation_run er
JOIN setup.rule_check rc ON rc.eval_run_id = er.eval_run_id
GROUP BY er.eval_run_id, er.as_of, er.instrument_id
HAVING count(*) = 6 AND bool_and(rc.passed);

-- =====================================================================
-- STARTDATEN
-- =====================================================================

INSERT INTO ref.currency (code, name, central_bank, country_code) VALUES
 ('USD','US-Dollar','Federal Reserve','US'),
 ('EUR','Euro','Europäische Zentralbank','EA'),
 ('JPY','Japanischer Yen','Bank of Japan','JP'),
 ('GBP','Britisches Pfund','Bank of England','GB'),
 ('CHF','Schweizer Franken','Schweizerische Nationalbank','CH'),
 ('CAD','Kanadischer Dollar','Bank of Canada','CA'),
 ('AUD','Australischer Dollar','Reserve Bank of Australia','AU'),
 ('NZD','Neuseeland-Dollar','Reserve Bank of New Zealand','NZ');

-- 28 Paare in Marktkonvention (Priorität EUR > GBP > AUD > NZD > USD > CAD > CHF > JPY)
INSERT INTO ref.instrument (symbol, base_ccy, quote_ccy, pip_size)
SELECT b.c || q.c, b.c, q.c, CASE WHEN q.c = 'JPY' THEN 0.01 ELSE 0.0001 END
FROM (VALUES ('EUR',1),('GBP',2),('AUD',3),('NZD',4),('USD',5),('CAD',6),('CHF',7),('JPY',8)) b(c,r)
JOIN (VALUES ('EUR',1),('GBP',2),('AUD',3),('NZD',4),('USD',5),('CAD',6),('CHF',7),('JPY',8)) q(c,r)
  ON b.r < q.r;

INSERT INTO ml.horizon VALUES ('1W',5),('1M',21),('3M',63);
