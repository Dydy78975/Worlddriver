-- Migration 0009: Reihen, die die Signale brauchen (VIX und Rohstoffe der Rohstoffwährungen).
-- Bisher legte die entfernte Wissensbasis (load-knowledge) sie an; jetzt gehören sie ins Schema.
-- ON CONFLICT: bestehende Datenbanken haben die Reihen bereits.

INSERT INTO ref.series (source_id, source_code, category, frequency, publication_lag, description)
SELECT s.source_id, v.code, v.cat, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('VIXCLS',      'risk',        'D', '1 day',   'Volatilitätsindex VIX (Risikostimmung)'),
 ('DCOILWTICO',  'energy',      'D', '7 days',  'Rohöl WTI (USA)'),
 ('PCOALAUUSDM', 'energy',      'M', '45 days', 'Kraftwerkskohle Australien'),
 ('PIORECRUSDM', 'metals',      'M', '45 days', 'Eisenerz'),
 ('PCOPPUSDM',   'metals',      'M', '45 days', 'Kupfer'),
 ('PBEEFUSDM',   'agriculture', 'M', '45 days', 'Rindfleisch'),
 ('PLOGSKUSDM',  'agriculture', 'M', '45 days', 'Rundholz (Weichholz)')
) AS v(code, cat, freq, lag, descr)
WHERE s.name = 'FRED_COMMODITY'
ON CONFLICT (source_id, source_code) DO NOTHING;
