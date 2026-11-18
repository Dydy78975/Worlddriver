-- Migration 0003: Quantitative Forecasting Engine + Global Economic Dependency Engine
-- Erklärung: docs/08_quantitative_forecasting.md und docs/09_dependency_engine.md

-- =====================================================================
-- 1. HORIZONTE: täglich / wöchentlich / monatlich (je eigenes Modell)
-- =====================================================================

ALTER TABLE ml.horizon ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE ml.horizon ADD COLUMN label_de TEXT;

INSERT INTO ml.horizon (horizon_code, trading_days) VALUES ('1D', 1);
UPDATE ml.horizon SET trading_days = 20 WHERE horizon_code = '1M';
UPDATE ml.horizon SET is_active = FALSE WHERE horizon_code = '3M';   -- reserviert für später
UPDATE ml.horizon SET label_de = CASE horizon_code
    WHEN '1D' THEN 'Täglich (1 Handelstag)'
    WHEN '1W' THEN 'Wöchentlich (5 Handelstage)'
    WHEN '1M' THEN 'Monatlich (20 Handelstage)'
    WHEN '3M' THEN 'Quartal (63 Handelstage, inaktiv)' END;
ALTER TABLE ml.horizon ALTER COLUMN label_de SET NOT NULL;

-- =====================================================================
-- 2. MODELLE: jedes Modell gehört zu genau einem Horizont
-- =====================================================================

-- Ein „Modell“ ist ein Prognosesystem aus Komponenten (Richtung, Rendite, Volatilität/Spanne, Quantile)
ALTER TABLE ml.model_version ADD COLUMN components JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE ml.model_version ADD CONSTRAINT model_version_id_horizon_uq UNIQUE (model_version_id, horizon_code);

-- Erzwingt: Eine Tagesprognose kann nur von einem Tagesmodell stammen (keine Ableitung aus der Monatsprognose)
ALTER TABLE ml.forecast ADD CONSTRAINT forecast_model_horizon_fk
    FOREIGN KEY (model_version_id, horizon_code) REFERENCES ml.model_version (model_version_id, horizon_code);

-- =====================================================================
-- 3. QUANTITATIVE PROGNOSE-FELDER
-- =====================================================================

ALTER TABLE ml.forecast
    ADD COLUMN expected_return     DOUBLE PRECISION,  -- erwartete Log-Rendite über den Horizont (0.0012 = +0,12 %)
    ADD COLUMN expected_range_high DOUBLE PRECISION,  -- erwartete maximale Aufwärtsbewegung bis zum Horizont (Log, >= 0)
    ADD COLUMN expected_range_low  DOUBLE PRECISION,  -- erwartete maximale Abwärtsbewegung (Log, <= 0)
    ADD COLUMN confidence          DOUBLE PRECISION,  -- 0..1, aus validierter Modellgüte + aktueller Unsicherheit
    ADD COLUMN confidence_label    TEXT,              -- niedrig / mittel / hoch
    ADD COLUMN perf_snapshot       JSONB,             -- Modellgüte, wie sie ZUM PROGNOSEZEITPUNKT bekannt war
    ADD CONSTRAINT forecast_confidence_range CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    ADD CONSTRAINT forecast_range_signs CHECK (
        (expected_range_high IS NULL OR expected_range_high >= 0) AND
        (expected_range_low  IS NULL OR expected_range_low  <= 0));
-- quantiles (bestehend) enthält das Prognoseintervall: {"q05":..,"q10":..,"q25":..,"q50":..,"q75":..,"q90":..,"q95":..}

-- Auswertung nach Ablauf des Horizonts
ALTER TABLE ml.forecast_outcome
    ADD COLUMN realized_range_high DOUBLE PRECISION,
    ADD COLUMN realized_range_low  DOUBLE PRECISION,
    ADD COLUMN return_error        DOUBLE PRECISION,  -- tatsächlich - erwartet
    ADD COLUMN pinball_loss        DOUBLE PRECISION,  -- Güte der Quantile (Mittel über alle Quantile)
    ADD COLUMN crps                DOUBLE PRECISION,  -- Güte der gesamten Verteilung
    ADD COLUMN in_interval_80      BOOLEAN,           -- lag das Ergebnis im 80-%-Intervall (q10..q90)?
    ADD COLUMN in_interval_90      BOOLEAN;           -- im 90-%-Intervall (q05..q95)?

-- Erklärung je Prognose: welcher Faktor / welche Wirtschaftsbeziehung hat wie stark beigetragen
CREATE TABLE ml.forecast_driver (
    forecast_id     BIGINT NOT NULL REFERENCES ml.forecast(forecast_id),
    rank            SMALLINT NOT NULL,
    feature_key     TEXT NOT NULL,                 -- z. B. 'commodity:iron_ore:ret_20d'
    relationship_id INTEGER,                       -- Verweis auf dep.relationship (FK unten)
    contribution    DOUBLE PRECISION NOT NULL,     -- SHAP-Beitrag in Wahrscheinlichkeit bzw. Rendite
    explanation_de  TEXT,
    PRIMARY KEY (forecast_id, rank)
);

-- =====================================================================
-- 4. GLOBAL ECONOMIC DEPENDENCY ENGINE
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS dep;

-- Volkswirtschaften: die 8 Währungsräume + wichtige Partner (z. B. China)
CREATE TABLE dep.economy (
    economy_code    TEXT PRIMARY KEY,              -- US, EA, JP, GB, CH, CA, AU, NZ, CN
    name_de         TEXT NOT NULL,
    currency        CHAR(3) REFERENCES ref.currency(code),  -- NULL für Partner ohne Hauptwährung (CN)
    notes_de        TEXT
);

-- Güter und Treiber (Rohstoffe, Agrar, Industrie, Finanz-Faktoren)
CREATE TABLE dep.driver (
    driver_key      TEXT PRIMARY KEY,              -- z. B. 'commodity:iron_ore', 'risk:vix'
    name_de         TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (category IN
                    ('energy','metals','agriculture','dairy','precious','industry','risk','rates','trade','geopolitics')),
    hs_codes        TEXT[],                        -- Zolltarifnummern für Handelsdaten
    price_series_id INTEGER REFERENCES ref.series(series_id),   -- NULL = noch keine Datenquelle
    data_status     TEXT NOT NULL DEFAULT 'missing' CHECK (data_status IN ('available','partial','missing')),
    notes_de        TEXT
);

-- Handelsabhängigkeit: Anteil eines Guts an Exporten/Importen eines Landes (point-in-time)
CREATE TABLE dep.trade_exposure (
    economy_code    TEXT NOT NULL REFERENCES dep.economy(economy_code),
    partner_code    TEXT NOT NULL DEFAULT 'WORLD',
    driver_key      TEXT NOT NULL REFERENCES dep.driver(driver_key),
    flow            TEXT NOT NULL CHECK (flow IN ('export','import')),
    period_year     SMALLINT NOT NULL,
    value_usd       DOUBLE PRECISION,
    share_of_flow   DOUBLE PRECISION,              -- Anteil an allen Exporten bzw. Importen
    share_of_gdp    DOUBLE PRECISION,
    source_id       SMALLINT REFERENCES ref.data_source(source_id),
    available_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (economy_code, partner_code, driver_key, flow, period_year, available_at)
);

-- Eine Wirtschaftsbeziehung: Hypothese oder validierter Zusammenhang
CREATE TABLE dep.relationship (
    relationship_id SERIAL PRIMARY KEY,
    currency        CHAR(3) NOT NULL REFERENCES ref.currency(code),
    driver_key      TEXT NOT NULL REFERENCES dep.driver(driver_key),
    origin          TEXT NOT NULL CHECK (origin IN ('expert','literature','discovered')),
    expected_sign   SMALLINT CHECK (expected_sign IN (-1, 1)),   -- NULL bei entdeckten Kandidaten
    mechanism_de    TEXT NOT NULL,                 -- Kurzbeschreibung
    causal_chain    JSONB NOT NULL,                -- Liste der Schritte der Wirkungskette
    conditions_de   TEXT,                          -- wann gilt sie (Regime), wann nicht
    status          TEXT NOT NULL DEFAULT 'hypothesis' CHECK (status IN
                    ('hypothesis','testing','validated','weakening','broken','rejected')),
    status_since    TIMESTAMPTZ NOT NULL DEFAULT now(),
    knowledge_version TEXT NOT NULL,               -- Version der Wissensdatei
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (currency, driver_key)
);

ALTER TABLE ml.forecast_driver ADD CONSTRAINT forecast_driver_relationship_fk
    FOREIGN KEY (relationship_id) REFERENCES dep.relationship(relationship_id);

-- Ein Analyse-Lauf (Validierung, Entdeckung, Überwachung)
CREATE TABLE dep.analysis_run (
    run_id          BIGSERIAL PRIMARY KEY,
    run_type        TEXT NOT NULL CHECK (run_type IN ('validation','discovery','monitoring')),
    as_of           TIMESTAMPTZ NOT NULL,          -- Datenstand: nur Daten mit available_at <= as_of
    n_tests         INTEGER,                       -- Anzahl getesteter Kombinationen (für Mehrfachtest-Korrektur)
    fdr_level       DOUBLE PRECISION,
    settings        JSONB NOT NULL,
    code_commit     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ergebnis eines statistischen Tests (unveränderlich)
CREATE TABLE dep.relationship_test (
    test_id         BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES dep.analysis_run(run_id),
    relationship_id INTEGER REFERENCES dep.relationship(relationship_id),   -- NULL = Kandidat aus Entdeckung
    currency        CHAR(3) NOT NULL REFERENCES ref.currency(code),
    driver_key      TEXT NOT NULL REFERENCES dep.driver(driver_key),
    frequency       TEXT NOT NULL CHECK (frequency IN ('D','W','M')),
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    lag_periods     SMALLINT NOT NULL,             -- 0 = gleichzeitig, >0 = Treiber läuft voraus
    method          TEXT NOT NULL,                 -- z. B. 'ols_hac', 'rolling_beta', 'granger', 'cusum'
    regime          TEXT NOT NULL DEFAULT 'all',
    n_obs           INTEGER NOT NULL,
    estimate        DOUBLE PRECISION,
    std_error       DOUBLE PRECISION,              -- HAC (Newey-West), robust gegen Autokorrelation
    p_value         DOUBLE PRECISION,
    q_value         DOUBLE PRECISION,              -- nach Mehrfachtest-Korrektur (Benjamini-Hochberg)
    oos_metrics     JSONB,                         -- Out-of-Sample-Ergebnisse (z. B. R², Trefferquote)
    stability       JSONB,                         -- Teilperioden, Vorzeichenwechsel, Strukturbruch
    priced_in       JSONB,                         -- war die Information bereits im Kurs?
    passed          BOOLEAN,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON dep.relationship_test (relationship_id, created_at);

-- Jeder Statuswechsel einer Beziehung mit Begründung (unveränderlich)
CREATE TABLE dep.relationship_status_log (
    log_id          BIGSERIAL PRIMARY KEY,
    relationship_id INTEGER NOT NULL REFERENCES dep.relationship(relationship_id),
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    old_status      TEXT,
    new_status      TEXT NOT NULL,
    reason_de       TEXT NOT NULL,
    test_id         BIGINT REFERENCES dep.relationship_test(test_id),
    decided_by      TEXT NOT NULL                  -- 'system' nur für Abstufungen; Aufwertung zu 'validated' nur durch Menschen
);

-- Regel: Nur ein Mensch darf eine Beziehung als 'validated' freigeben
CREATE FUNCTION dep.check_status_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.new_status = 'validated' AND NEW.decided_by = 'system' THEN
        RAISE EXCEPTION 'Eine Beziehung darf nur durch eine Person als validiert freigegeben werden';
    END IF;
    IF NEW.new_status = 'validated' AND NEW.test_id IS NULL THEN
        RAISE EXCEPTION 'Freigabe als validiert erfordert einen bestandenen Test (test_id)';
    END IF;
    IF NEW.new_status = 'validated' AND NOT EXISTS (
        SELECT 1 FROM dep.relationship_test t WHERE t.test_id = NEW.test_id AND t.passed) THEN
        RAISE EXCEPTION 'Der angegebene Test wurde nicht bestanden';
    END IF;
    UPDATE dep.relationship SET status = NEW.new_status, status_since = NEW.changed_at
        WHERE relationship_id = NEW.relationship_id;
    RETURN NEW;
END $$;
CREATE TRIGGER relationship_status_change BEFORE INSERT ON dep.relationship_status_log
    FOR EACH ROW EXECUTE FUNCTION dep.check_status_change();

-- Status darf nur über das Protokoll geändert werden
CREATE FUNCTION dep.forbid_direct_status_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status AND pg_trigger_depth() < 2 THEN
        RAISE EXCEPTION 'Status bitte über dep.relationship_status_log ändern (nachvollziehbar)';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER relationship_status_guard BEFORE UPDATE ON dep.relationship
    FOR EACH ROW EXECUTE FUNCTION dep.forbid_direct_status_update();

CREATE TRIGGER forecast_driver_immutable BEFORE UPDATE OR DELETE ON ml.forecast_driver
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();
CREATE TRIGGER relationship_test_immutable BEFORE UPDATE OR DELETE ON dep.relationship_test
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();
CREATE TRIGGER relationship_status_log_immutable BEFORE UPDATE OR DELETE ON dep.relationship_status_log
    FOR EACH ROW EXECUTE FUNCTION ml.forbid_change();

-- =====================================================================
-- 5. FORECAST-TRACKER (Sichten)
-- =====================================================================

-- Alle Prognosen mit Ergebnis und Vergleich zur vorherigen Prognose desselben Paares/Horizonts/Modells
CREATE VIEW ml.v_forecast_tracker AS
SELECT
    f.forecast_id, r.as_of, f.created_at, r.is_backtest, f.is_shadow,
    i.symbol, f.horizon_code, mv.name AS model_name, mv.version AS model_version, mv.status AS model_status,
    f.target_date, f.reference_price,
    f.expected_return, f.expected_direction, f.p_bull, f.p_neutral, f.p_bear,
    f.quantiles, f.expected_range_high, f.expected_range_low,
    f.confidence, f.confidence_label, f.is_display_calibrated,
    LAG(f.expected_return) OVER w AS prev_expected_return,
    f.expected_return - LAG(f.expected_return) OVER w AS change_expected_return,
    LAG(f.expected_direction) OVER w AS prev_direction,
    f.p_bull - LAG(f.p_bull) OVER w AS change_p_bull,
    f.p_bear - LAG(f.p_bear) OVER w AS change_p_bear,
    CASE WHEN o.forecast_id IS NOT NULL THEN 'ausgewertet'
         WHEN EXISTS (SELECT 1 FROM ml.forecast_invalidation v WHERE v.forecast_id = f.forecast_id) THEN 'invalidiert'
         ELSE 'offen' END AS state,
    o.realized_return, o.realized_class, o.return_error, o.direction_hit,
    o.brier, o.log_loss, o.pinball_loss, o.crps, o.in_interval_80, o.in_interval_90,
    o.realized_range_high, o.realized_range_low, o.regime_at_forecast
FROM ml.forecast f
JOIN ml.forecast_run r USING (run_id)
JOIN ml.model_version mv USING (model_version_id)
LEFT JOIN ref.instrument i ON i.instrument_id = f.instrument_id
LEFT JOIN ml.forecast_outcome o USING (forecast_id)
WINDOW w AS (PARTITION BY f.instrument_id, f.currency, f.horizon_code, mv.name, r.is_backtest, f.is_shadow
             ORDER BY r.as_of, f.forecast_id);

-- Entwicklung der Modellgüte je Monat: wird das System besser?
CREATE VIEW ml.v_performance_monthly AS
SELECT
    date_trunc('month', t.as_of)::date AS month,
    t.model_name, t.horizon_code, t.is_backtest,
    count(*)                                         AS n,
    avg(t.brier)                                     AS brier,
    avg(t.log_loss)                                  AS log_loss,
    avg(CASE WHEN t.direction_hit THEN 1.0 ELSE 0.0 END) FILTER (WHERE t.direction_hit IS NOT NULL) AS hit_rate,
    avg(abs(t.return_error))                         AS mae_return,
    avg(t.pinball_loss)                              AS pinball,
    avg(CASE WHEN t.in_interval_80 THEN 1.0 ELSE 0.0 END) FILTER (WHERE t.in_interval_80 IS NOT NULL) AS coverage_80
FROM ml.v_forecast_tracker t
WHERE t.state = 'ausgewertet' AND NOT t.is_shadow
GROUP BY 1, 2, 3, 4;

-- Aktueller Stand jeder Wirtschaftsbeziehung mit letztem Test
CREATE VIEW dep.v_relationship_overview AS
SELECT r.relationship_id, r.currency, r.driver_key, d.name_de AS driver_name, d.data_status,
       r.origin, r.expected_sign, r.status, r.status_since, r.mechanism_de,
       lt.estimate AS last_estimate, lt.p_value AS last_p_value, lt.q_value AS last_q_value,
       lt.lag_periods AS last_lag, lt.window_end AS last_tested_until, lt.passed AS last_passed
FROM dep.relationship r
JOIN dep.driver d USING (driver_key)
LEFT JOIN LATERAL (
    SELECT * FROM dep.relationship_test t
    WHERE t.relationship_id = r.relationship_id
    ORDER BY t.created_at DESC, t.test_id DESC LIMIT 1) lt ON TRUE;

-- =====================================================================
-- 6. STAMMDATEN
-- =====================================================================

INSERT INTO dep.economy (economy_code, name_de, currency, notes_de) VALUES
 ('US','USA','USD','Weltreservewährung; seit ca. 2019 Netto-Ölexporteur'),
 ('EA','Eurozone','EUR','Großer Energieimporteur; starke Industrieexporte (v. a. Deutschland)'),
 ('JP','Japan','JPY','Fast vollständig von Energieimporten abhängig; großer Auslandsgläubiger'),
 ('GB','Vereinigtes Königreich','GBP','Dienstleistungsexporte (Finanzen); Leistungsbilanzdefizit'),
 ('CH','Schweiz','CHF','Sicherer Hafen; Gold-Handelsdrehscheibe; Pharma- und Präzisionsexporte'),
 ('CA','Kanada','CAD','Großer Öl- und Gasexporteur, v. a. in die USA'),
 ('AU','Australien','AUD','Rohstoffexporteur: Eisenerz, Kohle, LNG, Gold; Hauptabnehmer China'),
 ('NZ','Neuseeland','NZD','Agrarexporteur: Milchprodukte, Fleisch, Holz; Hauptabnehmer China'),
 ('CN','China',NULL,'Wichtigster Abnehmer für AUD- und NZD-Rohstoffe; keine der 8 Hauptwährungen');

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('FRED_COMMODITY','https://fred.stlouisfed.org',
  'Rohstoffpreise über FRED (u. a. EIA, IMF Primary Commodity Prices). Öffentliche Daten.', FALSE);
