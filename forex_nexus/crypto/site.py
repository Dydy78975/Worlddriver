"""Krypto-Website bauen: Daten laden, alle Prüfungen rechnen, `site/crypto/index.html` + `data.json` schreiben.

Die erzeugten Dateien enthalten Kurs- und Kalenderdaten Dritter (nur private Nutzung) und
werden deshalb nicht ins öffentliche Repository übernommen (.gitignore)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_nexus.crypto import analysis as A
from forex_nexus.crypto.data import NAMES, load_all

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "site" / "crypto_template.html"
OUT = ROOT / "site" / "crypto"
BERLIN = ZoneInfo("Europe/Berlin")


def fng_label(v: float) -> str:
    if v < 25:
        return "Extreme Angst"
    if v < 45:
        return "Angst"
    if v <= 55:
        return "Neutral"
    if v <= 75:
        return "Gier"
    return "Extreme Gier"


def _compact(curve: list) -> dict:
    """[[datum, wert], ...] -> {start, step_days, values} (spart Platz)."""
    if not curve:
        return {"start": None, "step": 7, "v": []}
    return {"start": curve[0][0], "step": 7, "v": [x[1] for x in curve]}


def usd_calendar() -> dict:
    from forex_nexus.ingestion.calendar import URL, USER_AGENT, parse
    from forex_nexus.ingestion.http import fetch_text
    try:
        items = parse(json.loads(fetch_text(URL, retries=2, user_agent=USER_AGENT)))
    except Exception as e:                      # Kalender ist nett zu haben, aber kein Muss
        return {"ok": False, "error": str(e)[:200], "events": []}
    ev = []
    for e in items:
        if e["currency"] != "USD" or e["impact"] not in ("High", "Medium"):
            continue
        t = e["scheduled_at"].astimezone(BERLIN)
        ev.append({"at": t.isoformat(), "day": t.date().isoformat(), "time": t.strftime("%H:%M"), "title": e["title"],
                   "impact": e["impact"], "forecast": e["forecast"], "previous": e["previous"], "actual": e["actual"]})
    return {"ok": True, "events": sorted(ev, key=lambda x: x["at"])}


def collect(refresh: bool = True) -> dict:
    d = load_all(refresh=refresh)
    prices, volume = d["prices"], d["volume"]
    ov = A.overview(prices, volume)
    rg = A.ranges(prices)
    tb = A.trend_backtest(prices)
    coins = []
    for c in prices:
        p = prices[c].dropna()
        sma = p.rolling(200).mean().iloc[-365:]
        t = tb[c]
        coins.append({
            "sym": c, "name": NAMES.get(c, c), **ov[c], "ranges": rg[c],
            "sma200": [None if np.isnan(v) else round(float(v), 6) for v in sma.values],
            "trend": {k: t.get(k) for k in ("hold", "sma200", "mom30", "signal_now")},
            "curves": {k: _compact(t.get(k + "_curve", [])) for k in ("hold", "sma200", "mom30")},
            "since": str(p.index[0]),
        })
    fng = d["fng"].copy()
    fng.index = pd.to_datetime(fng.index)
    now_v = float(fng.iloc[-1])
    return {
        "generated": datetime.now(timezone.utc).astimezone(BERLIN).isoformat(timespec="minutes"),
        "as_of": str(prices.index[-1]),
        "coins": coins,
        "fng": {"value": now_v, "label": fng_label(now_v), "date": str(fng.index[-1].date()),
                "history": [[str(i.date()), int(v)] for i, v in fng.iloc[-365:].items()],
                "study": A.fng_study(d["fng"], prices["BTC"]), "since": str(fng.index[0].date())},
        "cot": {"view": A.cot_view(d["cot"]), "test": A.cot_backtest(d["cot"], prices)},
        "season": {c: A.seasonality(prices, c) for c in ("BTC", "ETH")},
        "robust": A.robustness(prices),
        "calendar": usd_calendar(),
        "rules": {"fee": A.FEE, "fng_low": 20, "fng_high": 80},
    }


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def build(refresh: bool = True) -> Path:
    data = _clean(collect(refresh))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    return OUT / "index.html"
