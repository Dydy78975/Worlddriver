"""Dukascopy: Stundenkerzen laden und zu Tageskerzen mit Schluss 17:00 New York zusammenfassen.

Hinweise:
* Dateiformat .bi5 = LZMA-komprimiert, je Kerze 24 Byte (Big Endian):
  Sekunden seit Periodenbeginn (int32), Open, Close, Low, High (int32, Preis x 10^5 bzw. x 10^3 bei JPY),
  Volumen (float32). Monatsangabe in der URL beginnt bei 00 = Januar.
* Es werden BID-Kurse verwendet.
* Nutzung vermutlich nur privat erlaubt: Rohdaten werden NICHT im öffentlichen Git-Repository gespeichert,
  sondern nur im lokalen Zwischenspeicher (Ordner data/, von Git ausgeschlossen).
* Dukascopy begrenzt die Abfragerate stark. Der Abruf ist daher langsam, wiederholt automatisch und
  setzt nach einer Unterbrechung dort fort, wo er aufgehört hat.
"""

from __future__ import annotations

import lzma
import struct
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from forex_nexus.fx.crosses import ALL_PAIRS
from forex_nexus.ingestion.http import NotFound, fetch_bytes

BASE_URL = "https://datafeed.dukascopy.com/datafeed/{symbol}/{year}/{month0:02d}/BID_candles_hour_1.bi5"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "dukascopy"
NEW_YORK = ZoneInfo("America/New_York")
RECORD = struct.Struct(">5if")
FIRST_MONTH = date(2003, 5, 1)       # frühestmögliche Daten bei Dukascopy
MIN_HOURS_FULL_DAY = 18               # weniger Handelsstunden = verkürzter Tag (z. B. Feiertag)


def price_divisor(symbol: str) -> float:
    return 1e3 if symbol.endswith("JPY") else 1e5


def decode_hour_candles(raw: bytes, month_start: datetime, divisor: float) -> pd.DataFrame:
    """Entpackt eine Monatsdatei. Liefert nur Stunden mit Umsatz (Wochenenden haben Volumen 0)."""
    if not raw:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    data = lzma.decompress(raw)
    if len(data) % RECORD.size:
        raise ValueError("Dukascopy-Datei beschädigt (Länge kein Vielfaches von 24 Byte)")
    rows = []
    for t, o, c, lo, hi, v in RECORD.iter_unpack(data):
        if v <= 0:
            continue
        rows.append((month_start + timedelta(seconds=t), o / divisor, hi / divisor, lo / divisor, c / divisor, float(v)))
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).set_index("time")
    bad = (df["low"] > df[["open", "close"]].min(axis=1) + 1e-12) | (df["high"] < df[["open", "close"]].max(axis=1) - 1e-12)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} Kerzen mit unmöglichen Hoch/Tief-Werten")
    return df


def to_ny_close_days(hourly: pd.DataFrame) -> pd.DataFrame:
    """Stundenkerzen (UTC) -> Tageskerzen mit Schluss 17:00 New York.

    Ein Handelstag läuft von 17:00 New York des Vortags bis 17:00 New York (Sommerzeit wird
    automatisch berücksichtigt). Trick: Uhrzeit in New York + 7 Stunden ergibt das Datum des Handelstags.
    """
    if hourly.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "hours"])
    ny = hourly.index.tz_convert(NEW_YORK)
    trade_date = (ny + pd.Timedelta(hours=7)).date
    g = hourly.groupby(trade_date)
    days = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
        "close": g["close"].last(), "volume": g["volume"].sum(), "hours": g.size(),
    })
    days.index.name = "trade_date"
    return days[[d.weekday() < 5 for d in days.index]]   # Sitzungen am Samstag/Sonntag verwerfen


def months(start: date, end: date):
    d = date(start.year, start.month, 1)
    while d <= end:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def cache_path(symbol: str, month: date) -> Path:
    return CACHE_DIR / symbol / f"{month:%Y-%m}.bi5"


def download(symbols=ALL_PAIRS, start: date = FIRST_MONTH, end: date | None = None,
             pause: float = 1.5, log=print) -> dict:
    """Lädt fehlende Monatsdateien in den Zwischenspeicher. Der laufende Monat wird übersprungen
    (Monatsdateien erscheinen erst nach Monatsende). Fehlt eine Datei bei der Quelle, wird eine
    leere Datei als Merker gespeichert."""
    today = date.today()
    end = end or date(today.year, today.month, 1) - timedelta(days=1)
    stats = {"loaded": 0, "cached": 0, "missing": 0}
    for symbol in symbols:
        for m in months(start, end):
            path = cache_path(symbol, m)
            if path.exists():
                stats["cached"] += 1
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            url = BASE_URL.format(symbol=symbol, year=m.year, month0=m.month - 1)
            try:
                raw = fetch_bytes(url)
                stats["loaded"] += 1
            except NotFound:
                raw = b""
                stats["missing"] += 1
            tmp = path.with_suffix(".part")
            tmp.write_bytes(raw)
            tmp.replace(path)          # erst vollständig schreiben, dann umbenennen
            time.sleep(pause)
        log(f"{symbol}: fertig ({stats})")
    return stats


def load_daily_from_cache(symbols=ALL_PAIRS) -> pd.DataFrame:
    """Liest alle zwischengespeicherten Monate und liefert Tageskerzen im Langformat."""
    frames = []
    for symbol in symbols:
        parts = []
        for path in sorted((CACHE_DIR / symbol).glob("*.bi5")):
            y, m = map(int, path.stem.split("-"))
            parts.append(decode_hour_candles(path.read_bytes(), datetime(y, m, 1, tzinfo=timezone.utc),
                                             price_divisor(symbol)))
        parts = [p for p in parts if not p.empty]
        if not parts:
            continue
        hourly = pd.concat(parts).sort_index()
        hourly = hourly[~hourly.index.duplicated()]
        days = to_ny_close_days(hourly)
        days["symbol"] = symbol
        frames.append(days.reset_index())
    if not frames:
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume", "hours", "symbol"])
    return pd.concat(frames, ignore_index=True)


MIN_HOURS_KEEP = 6   # Tage mit weniger Handelsstunden sind Randstücke (z. B. Monatsende ohne Folgemonat)


def ingest(conninfo: str, symbols=ALL_PAIRS) -> dict:
    """Zwischengespeicherte Dukascopy-Daten als Tageskerzen in raw.fx_daily schreiben."""
    from forex_nexus.ingestion.fx_daily import store_rows

    days = load_daily_from_cache(symbols)
    if days.empty:
        return {"rows": 0, "inserted": 0, "dropped_fragments": 0, "short_sessions": 0}
    fragments = days["hours"] < MIN_HOURS_KEEP
    days = days[~fragments].copy()
    days["available_at"] = [datetime.combine(d, datetime.min.time().replace(hour=17), NEW_YORK) for d in days["trade_date"]]
    result = store_rows(conninfo, "DUKASCOPY_BID", days)
    result["dropped_fragments"] = int(fragments.sum())
    result["short_sessions"] = int((days["hours"] < MIN_HOURS_FULL_DAY).sum())
    return result
