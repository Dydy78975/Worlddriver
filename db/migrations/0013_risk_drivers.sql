-- Migration 0013: Risiko-Treiber für EUR, CHF, USD, GBP, JPY, AUD, NZD (docs/12_signal_abstimmung.md).
-- Italien-Aufschlag (Rendite Italien minus Deutschland, 10 J.): Eurokrisen-Angst. Kreditaufschlag BAA gegenüber
-- US-Staatsanleihen und Finanzstress-Index der Chicago Fed: Stress an den Märkten. (Hochzins-Aufschläge von ICE
-- liefert FRED nur für 3 Jahre, deshalb BAA.)

INSERT INTO ref.series (source_id, source_code, category, frequency, publication_lag, description)
SELECT s.source_id, v.code, v.cat, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('IRLTLT01ITM156N', 'spread', 'M', '35 days', 'Rendite 10 J. Italien (für den Italien-Aufschlag)'),
 ('BAA10Y',          'spread', 'D', '1 day',   'Kreditaufschlag Unternehmensanleihen BAA gegenüber US-Staatsanleihen'),
 ('NFCI',            'risk',   'W', '5 days',  'Finanzstress-Index der Chicago Fed (NFCI)')
) AS v(code, cat, freq, lag, descr)
WHERE s.name = 'FRED_RATES';
