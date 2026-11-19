-- Migration 0011: Treiber je Währung für die Modelle je Währung (docs/12_signal_abstimmung.md).
-- NZD: Milchprodukte (Weltmarktpreise von Global Dairy Trade gibt es nicht auf FRED; beste Alternative:
--      US-Erzeugerpreise Milchprodukte, BLS), Lamm, Wolle. AUD: Wolle. CAD: Holz (Erzeugerpreise
--      Schnittholz, BLS), Nickel. JPY/CHF/EUR/USD: 2-jährige US-Rendite.
-- Reihen, die Migration 0008 abgeschaltet hatte, werden wieder gebraucht (Brent, Erdgas, Aluminium, Weizen).

INSERT INTO ref.series (source_id, source_code, category, frequency, publication_lag, description)
SELECT s.source_id, v.code, v.cat, v.freq, v.lag::interval, v.descr
FROM ref.data_source s, (VALUES
 ('WPU023',          'agriculture', 'M', '30 days', 'Erzeugerpreise Milchprodukte (USA, BLS)'),
 ('PCU311511311511', 'agriculture', 'M', '30 days', 'Erzeugerpreise Trinkmilch (USA, BLS)'),
 ('PLAMBUSDM',       'agriculture', 'M', '45 days', 'Lammfleisch'),
 ('PWOOLFUSDM',      'agriculture', 'M', '45 days', 'Wolle fein'),
 ('PWOOLCUSDM',      'agriculture', 'M', '45 days', 'Wolle grob'),
 ('PNICKUSDM',       'metals',      'M', '45 days', 'Nickel'),
 ('WPU081',          'agriculture', 'M', '30 days', 'Erzeugerpreise Schnittholz (USA, BLS)'),
 ('DGS2',            'yield_2y',    'D', '1 day',   'Rendite 2-jährige US-Staatsanleihe')
) AS v(code, cat, freq, lag, descr)
WHERE s.name = 'FRED_COMMODITY'
ON CONFLICT (source_id, source_code) DO NOTHING;

UPDATE ref.series SET active = TRUE
WHERE source_code IN ('DCOILBRENTEU', 'DHHNGSP', 'PNGASEUUSDM', 'PNGASJPUSDM', 'PALUMUSDM', 'PWHEAMTUSDM');
