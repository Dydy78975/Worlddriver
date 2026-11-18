-- Migration 0010: BIS-Statistik als Quelle für Inflation und offizielle Leitzinsen.
-- Grund: Die OECD-Reihen auf FRED sind eingestellt (Verbraucherpreise GB/JP/CH/CA/AU/NZ enden 2021–2025).
-- Die BIS führt Verbraucherpreise (WS_LONG_CPI, Index) und die offiziellen Leitzinsen (WS_CBPOL, täglich)
-- einheitlich für alle 8 Währungsräume. Die abgelösten Reihen werden nicht mehr genutzt (active = FALSE),
-- ihre Werte bleiben gespeichert.
-- Australien und Neuseeland melden Preise nur je Quartal; die BIS-Monatsreihe wiederholt den Quartalswert,
-- deshalb Frequenz Q (Quartalsende + 60 Tage Veröffentlichung).

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('BIS', 'https://stats.bis.org',
  'BIS Data Portal (Bank für Internationalen Zahlungsausgleich). Öffentliche Daten, Quelle: BIS.', FALSE);

INSERT INTO ref.series (source_id, source_code, category, currency, frequency, publication_lag, description)
SELECT s.source_id, v.code, v.cat, v.ccy, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('WS_LONG_CPI/1.0/M.GB.628', 'cpi_index',  'GBP', 'M', '45 days', 'Verbraucherpreise Großbritannien (BIS)'),
 ('WS_LONG_CPI/1.0/M.JP.628', 'cpi_index',  'JPY', 'M', '45 days', 'Verbraucherpreise Japan (BIS)'),
 ('WS_LONG_CPI/1.0/M.CH.628', 'cpi_index',  'CHF', 'M', '45 days', 'Verbraucherpreise Schweiz (BIS)'),
 ('WS_LONG_CPI/1.0/M.CA.628', 'cpi_index',  'CAD', 'M', '45 days', 'Verbraucherpreise Kanada (BIS)'),
 ('WS_LONG_CPI/1.0/M.AU.628', 'cpi_index',  'AUD', 'Q', '60 days', 'Verbraucherpreise Australien (BIS, Quartal)'),
 ('WS_LONG_CPI/1.0/M.NZ.628', 'cpi_index',  'NZD', 'Q', '60 days', 'Verbraucherpreise Neuseeland (BIS, Quartal)'),
 ('WS_CBPOL/1.0/D.GB',        'short_rate', 'GBP', 'D', '1 day',   'Leitzins Bank of England (BIS)'),
 ('WS_CBPOL/1.0/D.JP',        'short_rate', 'JPY', 'D', '1 day',   'Leitzins Bank of Japan (BIS)'),
 ('WS_CBPOL/1.0/D.CH',        'short_rate', 'CHF', 'D', '1 day',   'Leitzins Schweizerische Nationalbank (BIS)'),
 ('WS_CBPOL/1.0/D.CA',        'short_rate', 'CAD', 'D', '1 day',   'Leitzins Bank of Canada (BIS)'),
 ('WS_CBPOL/1.0/D.AU',        'short_rate', 'AUD', 'D', '1 day',   'Leitzins Reserve Bank of Australia (BIS)'),
 ('WS_CBPOL/1.0/D.NZ',        'short_rate', 'NZD', 'D', '1 day',   'Leitzins Reserve Bank of New Zealand (BIS)')
) AS v(code, cat, ccy, freq, lag, descr)
WHERE s.name = 'BIS';

UPDATE ref.series SET active = FALSE
WHERE source_code IN ('GBRCPIALLMINMEI', 'JPNCPIALLMINMEI', 'CHECPIALLMINMEI', 'CANCPIALLMINMEI',
                      'AUSCPIALLQINMEI', 'NZLCPIALLQINMEI',
                      'IRSTCI01GBM156N', 'IRSTCI01JPM156N', 'IRSTCI01CHM156N', 'IRSTCI01CAM156N',
                      'IRSTCI01AUM156N', 'IR3TIB01NZM156N');
