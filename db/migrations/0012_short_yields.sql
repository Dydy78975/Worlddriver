-- Migration 0012: Kurzfristige Staatsanleihe-Renditen direkt von Notenbanken und Ministerien (Zinserwartung
-- des Marktes). FRED führt außer den USA keine aktuellen kurzen Renditen. Für CHF (SNB-Reihen enden 07/2025)
-- und NZD (RBNZ sperrt automatische Abrufe) gibt es derzeit keine Quelle. Großbritannien: die Bank of England
-- veröffentlicht als kürzeste Reihe die 5-jährige Par-Rendite.

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('CB_YIELDS', 'https://www.ecb.europa.eu',
  'Renditen von EZB, Bank of Canada, Reserve Bank of Australia, Finanzministerium Japan, Bank of England. Öffentliche Daten.', FALSE);

INSERT INTO ref.series (source_id, source_code, category, currency, frequency, publication_lag, description)
SELECT s.source_id, v.code, 'yield_2y', v.ccy, 'D', '1 day'::interval, v.descr
FROM ref.data_source s, (VALUES
 ('ECB_2Y', 'EUR', 'Rendite 2 J. Euroraum (EZB-Zinsstrukturkurve)'),
 ('BOC_2Y', 'CAD', 'Rendite 2 J. Kanada (Bank of Canada)'),
 ('RBA_2Y', 'AUD', 'Rendite 2 J. Australien (RBA)'),
 ('MOF_2Y', 'JPY', 'Rendite 2 J. Japan (Finanzministerium)'),
 ('BOE_5Y', 'GBP', 'Rendite 5 J. Großbritannien (Bank of England; kürzeste verfügbare Reihe)')
) AS v(code, ccy, descr)
WHERE s.name = 'CB_YIELDS';

UPDATE ref.series SET currency = 'USD' WHERE source_code = 'DGS2';
