-- Migration 0004: Dukascopy als Quelle für Tageskerzen (Schluss 17:00 New York)

INSERT INTO ref.data_source (name, url, license_note, has_vintages) VALUES
 ('DUKASCOPY_BID',
  'https://datafeed.dukascopy.com',
  'Dukascopy BID-Stundenkerzen, zu Tageskerzen mit Schluss 17:00 New York zusammengefasst. '
  'Nutzung vermutlich nur privat: Rohdaten nicht veröffentlichen.',
  FALSE);

-- Hoch/Tief müssen zu Eröffnung und Schluss passen (gilt für alle Quellen mit OHLC)
ALTER TABLE raw.fx_daily ADD CONSTRAINT fx_daily_ohlc_consistent CHECK (
    high IS NULL OR low IS NULL OR open IS NULL OR
    (low <= least(open, close) AND high >= greatest(open, close) AND low > 0));
