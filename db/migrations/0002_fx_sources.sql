-- Migration 0002: Kursquellen für Phase 1 und Duplikatschutz für Qualitätsmeldungen.

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('FRED_H10',
  'https://fred.stlouisfed.org',
  'Federal Reserve H.10, Mittagskurse New York (Kaufkurse). Öffentliche Daten.',
  FALSE),
 ('FRED_H10_CROSS',
  'https://fred.stlouisfed.org',
  'Aus FRED_H10 berechnete Kreuzkurse (abgeleitet, keine eigene Quelle).',
  FALSE),
 ('ECB_EXR',
  'https://data-api.ecb.europa.eu',
  'EZB-Referenzkurse, ca. 14:15 MEZ, veröffentlicht ca. 16:00 MEZ. Kontrollquelle.',
  FALSE);

-- Ein Qualitätsproblem wird nur einmal gemeldet, auch wenn die Prüfung mehrfach läuft.
CREATE UNIQUE INDEX data_quality_issue_unique
    ON raw.data_quality_issue (check_name, instrument_id, series_id, affected_date)
    NULLS NOT DISTINCT;
