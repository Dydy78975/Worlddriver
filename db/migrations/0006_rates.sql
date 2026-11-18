-- Migration 0006: Zinsen, Renditen und Inflation der 8 Währungsräume (FRED)

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('FRED_RATES', 'https://fred.stlouisfed.org',
  'Zinsen, Renditen und Verbraucherpreise über FRED (Fed, EZB, OECD, Eurostat). Öffentliche Daten.', FALSE);

INSERT INTO ref.series (source_id, source_code, category, currency, frequency, publication_lag, description)
SELECT s.source_id, v.code, v.cat, v.ccy, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('DFF',                'short_rate', 'USD', 'D', '1 day',   'Effektiver Leitzins USA (Fed Funds)'),
 ('ECBDFR',             'short_rate', 'EUR', 'D', '1 day',   'EZB-Einlagesatz'),
 ('IRSTCI01GBM156N',    'short_rate', 'GBP', 'M', '35 days', 'Tagesgeldsatz Großbritannien (OECD), nahe Leitzins'),
 ('IRSTCI01JPM156N',    'short_rate', 'JPY', 'M', '35 days', 'Tagesgeldsatz Japan (OECD), nahe Leitzins'),
 ('IRSTCI01CHM156N',    'short_rate', 'CHF', 'M', '35 days', 'Tagesgeldsatz Schweiz (OECD), nahe Leitzins'),
 ('IRSTCI01CAM156N',    'short_rate', 'CAD', 'M', '35 days', 'Tagesgeldsatz Kanada (OECD), nahe Leitzins'),
 ('IRSTCI01AUM156N',    'short_rate', 'AUD', 'M', '35 days', 'Tagesgeldsatz Australien (OECD), nahe Leitzins'),
 ('IR3TIB01NZM156N',    'short_rate', 'NZD', 'M', '35 days', '3-Monats-Interbankensatz Neuseeland (OECD)'),
 ('DGS10',              'yield_10y',  'USD', 'D', '1 day',   'Rendite 10-jährige US-Staatsanleihe'),
 ('IRLTLT01DEM156N',    'yield_10y',  'EUR', 'M', '35 days', 'Rendite 10-jährige Bundesanleihe (Proxy Eurozone)'),
 ('IRLTLT01GBM156N',    'yield_10y',  'GBP', 'M', '35 days', 'Rendite 10-jährige britische Staatsanleihe'),
 ('IRLTLT01JPM156N',    'yield_10y',  'JPY', 'M', '35 days', 'Rendite 10-jährige japanische Staatsanleihe'),
 ('IRLTLT01CHM156N',    'yield_10y',  'CHF', 'M', '35 days', 'Rendite 10-jährige Schweizer Bundesobligation'),
 ('IRLTLT01CAM156N',    'yield_10y',  'CAD', 'M', '35 days', 'Rendite 10-jährige kanadische Staatsanleihe'),
 ('IRLTLT01AUM156N',    'yield_10y',  'AUD', 'M', '35 days', 'Rendite 10-jährige australische Staatsanleihe'),
 ('IRLTLT01NZM156N',    'yield_10y',  'NZD', 'M', '35 days', 'Rendite 10-jährige neuseeländische Staatsanleihe'),
 ('CPIAUCSL',           'cpi_index',  'USD', 'M', '45 days', 'Verbraucherpreisindex USA'),
 ('CP0000EZ19M086NEST', 'cpi_index',  'EUR', 'M', '20 days', 'HICP Eurozone (Index)'),
 ('GBRCPIALLMINMEI',    'cpi_index',  'GBP', 'M', '45 days', 'Verbraucherpreisindex Großbritannien (OECD)'),
 ('JPNCPIALLMINMEI',    'cpi_index',  'JPY', 'M', '45 days', 'Verbraucherpreisindex Japan (OECD)'),
 ('CHECPIALLMINMEI',    'cpi_index',  'CHF', 'M', '45 days', 'Verbraucherpreisindex Schweiz (OECD)'),
 ('CANCPIALLMINMEI',    'cpi_index',  'CAD', 'M', '45 days', 'Verbraucherpreisindex Kanada (OECD)'),
 ('AUSCPIALLQINMEI',    'cpi_index',  'AUD', 'Q', '60 days', 'Verbraucherpreisindex Australien (OECD, Quartal)'),
 ('NZLCPIALLQINMEI',    'cpi_index',  'NZD', 'Q', '60 days', 'Verbraucherpreisindex Neuseeland (OECD, Quartal)')
) AS v(code, cat, ccy, freq, lag, descr)
WHERE s.name = 'FRED_RATES';

ALTER TABLE ref.series DROP CONSTRAINT IF EXISTS series_frequency_check;
