-- Migration 0005: COT-Positionierung (CFTC) und Wirtschaftskalender

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('CFTC_COT', 'https://publicreporting.cftc.gov',
  'CFTC Commitments of Traders (Legacy, Futures Only). Öffentliche Daten. Stand Dienstag, veröffentlicht Freitag 15:30 New York.', FALSE),
 ('FF_CALENDAR', 'https://nfs.faireconomy.media',
  'Wirtschaftskalender von Forex Factory (Wochen-Feed). Nur zur persönlichen Nutzung; nicht weiterveröffentlichen.', FALSE);

-- Wöchentliche Positionen je Währungs-Future
CREATE TABLE raw.cot_position (
    contract_code   TEXT NOT NULL,
    currency        CHAR(3) NOT NULL REFERENCES ref.currency(code),
    report_date     DATE NOT NULL,                 -- Stichtag (Dienstag)
    available_at    TIMESTAMPTZ NOT NULL,          -- Veröffentlichung (Freitag 15:30 New York)
    open_interest   BIGINT,
    comm_long       BIGINT, comm_short    BIGINT,  -- Commercials (Absicherer, Banken)
    noncomm_long    BIGINT, noncomm_short BIGINT,  -- Large Speculators (Fonds)
    nonrept_long    BIGINT, nonrept_short BIGINT,  -- kleine Händler
    run_id          BIGINT REFERENCES raw.ingestion_run(run_id),
    PRIMARY KEY (contract_code, report_date)
);

-- Kalender-Termine: bestehende Tabelle ref.event erweitern
ALTER TABLE ref.event
    ADD COLUMN title      TEXT,
    ADD COLUMN impact     TEXT CHECK (impact IN ('High','Medium','Low','Holiday')),
    ADD COLUMN forecast   TEXT,
    ADD COLUMN previous   TEXT,
    ADD COLUMN actual     TEXT,
    ADD COLUMN source_key TEXT UNIQUE;
