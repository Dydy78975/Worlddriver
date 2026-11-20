"""Datenabruf für die Krypto-Seite. Rohdaten werden lokal in data/crypto/ zwischengespeichert (nicht im Repository)."""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

import pandas as pd

from forex_nexus.ingestion.http import fetch_text

COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "LINK"]
NAMES = {"BTC": "Bitcoin", "ETH": "Ether", "BNB": "BNB", "SOL": "Solana", "XRP": "XRP", "DOGE": "Dogecoin",
         "ADA": "Cardano", "LINK": "Chainlink"}
KLINES = "https://data-api.binance.vision/api/v3/klines?symbol={sym}USDT&interval=1d&limit=1000&startTime={start}"
FNG = "https://api.alternative.me/fng/?limit=0&format=json"
COT_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
COT_CODES = {"133741": "BTC", "146021": "ETH"}          # CME Bitcoin, CME Ether (cash settled)
CACHE = Path(__file__).resolve().parents[2] / "data" / "crypto"


def parse_klines(rows: list) -> pd.DataFrame:
    """Binance-Tageskerzen (UTC 00:00) -> DataFrame. Die laufende, unfertige Kerze wird verworfen."""
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
                                     "trades", "tb_base", "tb_quote", "ignore"])
    df["date"] = pd.to_datetime(df["open_time"], unit="ms").dt.date
    df = df[df["close_time"] < int(time.time() * 1000)]
    for c in ("open", "high", "low", "close", "quote_volume"):
        df[c] = df[c].astype(float)
    return df.set_index("date")[["open", "high", "low", "close", "quote_volume"]]


def fetch_coin(sym: str, start_ms: int = 1500000000000) -> pd.DataFrame:
    parts, start = [], start_ms
    while True:
        rows = json.loads(fetch_text(KLINES.format(sym=sym, start=start)))
        if not rows:
            break
        parts.append(parse_klines(rows))
        if len(rows) < 1000:
            break
        start = rows[-1][0] + 86_400_000
        time.sleep(0.3)
    df = pd.concat(parts) if parts else pd.DataFrame()
    return df[~df.index.duplicated()]


def parse_fng(js: dict) -> pd.Series:
    d = {pd.Timestamp(int(x["timestamp"]), unit="s").date(): int(x["value"]) for x in js["data"]}
    return pd.Series(d).sort_index()


def fetch_cot() -> pd.DataFrame:
    codes = ",".join(f"'{c}'" for c in COT_CODES)
    q = {"$select": "report_date_as_yyyy_mm_dd,cftc_contract_market_code,open_interest_all,comm_positions_long_all,"
                    "comm_positions_short_all,noncomm_positions_long_all,noncomm_positions_short_all,"
                    "nonrept_positions_long_all,nonrept_positions_short_all",
         "$where": f"cftc_contract_market_code in({codes})", "$order": "report_date_as_yyyy_mm_dd", "$limit": "5000"}
    rows = json.loads(fetch_text(COT_API + "?" + urllib.parse.urlencode(q)))
    df = pd.DataFrame(rows)
    df["coin"] = df["cftc_contract_market_code"].map(COT_CODES)
    df["report_date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"]).dt.date
    for a, b in (("comm", "comm_positions"), ("spec", "noncomm_positions"), ("small", "nonrept_positions")):
        df[f"{a}_net"] = df[f"{b}_long_all"].astype(float) - df[f"{b}_short_all"].astype(float)
    df["open_interest"] = df["open_interest_all"].astype(float)
    return df[["coin", "report_date", "comm_net", "spec_net", "small_net", "open_interest"]]


def load_all(refresh: bool = True) -> dict:
    """Lädt alles (bei refresh frisch aus dem Netz) und speichert eine Kopie im Zwischenspeicher."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    if refresh:
        prices = {c: fetch_coin(c) for c in COINS}
        out["prices"] = pd.DataFrame({c: p["close"] for c, p in prices.items()}).sort_index()
        out["highs"] = pd.DataFrame({c: p["high"] for c, p in prices.items()}).sort_index()
        out["lows"] = pd.DataFrame({c: p["low"] for c, p in prices.items()}).sort_index()
        out["volume"] = pd.DataFrame({c: p["quote_volume"] for c, p in prices.items()}).sort_index()
        out["fng"] = parse_fng(json.loads(fetch_text(FNG)))
        out["cot"] = fetch_cot()
        pd.to_pickle(out, CACHE / "raw.pkl")
    else:
        out = pd.read_pickle(CACHE / "raw.pkl")
    return out
