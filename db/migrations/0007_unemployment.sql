-- Migration 0007: Arbeitslosenquoten der 8 Währungsräume (FRED/OECD, Eurozone von der EZB)
-- Veröffentlichungsverzögerung bewusst vorsichtig: OECD-Reihen erscheinen auf FRED später als die
-- nationalen Erstveröffentlichungen.

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('FRED_LABOUR', 'https://fred.stlouisfed.org',
  'Arbeitslosenquoten über FRED (BLS, OECD). Öffentliche Daten.', FALSE),
 ('ECB_SERIES', 'https://data-api.ecb.europa.eu',
  'Statistiken der EZB (Data Portal). Öffentliche Daten, Quelle: EZB.', FALSE);

INSERT INTO ref.series (source_id, source_code, category, currency, frequency, publication_lag, description)
SELECT s.source_id, v.code, 'unemployment', v.ccy, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('UNRATE',          'USD', 'M', '10 days', 'Arbeitslosenquote USA (BLS)'),
 ('LRHUTTTTGBM156S', 'GBP', 'M', '75 days', 'Arbeitslosenquote Großbritannien (OECD)'),
 ('LRHUTTTTJPM156S', 'JPY', 'M', '45 days', 'Arbeitslosenquote Japan (OECD)'),
 ('LRHUTTTTCHQ156S', 'CHF', 'Q', '75 days', 'Arbeitslosenquote Schweiz (OECD, Quartal)'),
 ('LRHUTTTTCAM156S', 'CAD', 'M', '20 days', 'Arbeitslosenquote Kanada (OECD)'),
 ('LRHUTTTTAUM156S', 'AUD', 'M', '45 days', 'Arbeitslosenquote Australien (OECD)'),
 ('LRHUTTTTNZQ156S', 'NZD', 'Q', '75 days', 'Arbeitslosenquote Neuseeland (OECD, Quartal)')
) AS v(code, ccy, freq, lag, descr)
WHERE s.name = 'FRED_LABOUR';

INSERT INTO ref.series (source_id, source_code, category, currency, frequency, publication_lag, description)
SELECT source_id, 'LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T', 'unemployment', 'EUR', 'M', '35 days',
       'Arbeitslosenquote Eurozone (EZB/Eurostat)'
FROM ref.data_source WHERE name = 'ECB_SERIES';
