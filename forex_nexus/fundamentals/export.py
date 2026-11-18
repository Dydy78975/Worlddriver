"""Fundamentale Wochenansicht für die Website: Cockpit-Aussage, Währungen, Paare (Woche + Tage),
Kalender, COT, Saisonalität und historische Trefferquoten der Signale."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_nexus.fundamentals import analysis as A
from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS

BERLIN = ZoneInfo("Europe/Berlin")
NEW_YORK = ZoneInfo("America/New_York")
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _r(x, n=4):
    if x is None:
        return None
    try:
        if np.isnan(x):
            return None
    except TypeError:
        pass
    return round(float(x), n)


def load_cot(conn) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT currency, report_date, available_at, open_interest, comm_long, comm_short, noncomm_long, noncomm_short,
                  nonrept_long, nonrept_short FROM raw.cot_position""").fetchall()
    return pd.DataFrame(rows, columns=["currency", "report_date", "available_at", "open_interest", "comm_long",
                                       "comm_short", "noncomm_long", "noncomm_short", "nonrept_long", "nonrept_short"])


def load_events(conn, start: datetime, end: datetime) -> list[dict]:
    rows = conn.execute(
        """SELECT currency, scheduled_at, title, impact, forecast, previous, actual FROM ref.event
           WHERE event_type = 'calendar' AND scheduled_at >= %s AND scheduled_at < %s ORDER BY scheduled_at""",
        (start, end)).fetchall()
    out = []
    for ccy, at, title, impact, fc, prev, act in rows:
        local = at.astimezone(BERLIN)
        out.append({"currency": ccy, "at": local.isoformat(), "day": local.date().isoformat(),
                    "time": local.strftime("%H:%M"), "title": title, "impact": impact, "forecast": fc,
                    "previous": prev, "actual": act})
    return out


def build(conn, closes: pd.DataFrame, strength: pd.DataFrame, forecasts: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(BERLIN)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if now.weekday() >= 5:                       # am Wochenende schon die kommende Woche zeigen
        monday += timedelta(days=7)
    week_end = monday + timedelta(days=7)

    strength = strength.copy()
    strength.index = pd.to_datetime(strength.index)
    cot = load_cot(conn)
    cot_idx = A.cot_indices(cot) if not cot.empty else cot
    cot_now = A.cot_as_of(cot_idx, now) if not cot.empty else pd.DataFrame()
    trend = A.strength_change(strength, strength.index.max())
    monthly = A.monthly_returns(closes)
    month = monday.month if monday.month == (monday + timedelta(days=4)).month else (monday + timedelta(days=4)).month
    season_pairs = A.season_stats(monthly, before_year=now.year)
    smonthly = strength.resample("ME").last().diff().dropna(how="all")
    season_ccy = A.season_stats(smonthly, before_year=now.year)

    # Historische Trefferquoten (gleiche Regeln, nur damals verfügbare Daten)
    validation = {"season": A.season_validation(monthly),
                  "cot": A.cot_extreme_backtest(cot_idx, strength) if not cot.empty else {},
                  "confluence": A.confluence_backtest(closes, strength, cot_idx, monthly) if not cot.empty else {}}

    events = load_events(conn, monday, week_end)
    scores = A.currency_scores(cot_now, trend, season_ccy, month)
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    strong, weak = ranked[0][0], ranked[-1][0]

    fc = {(f["pair"], f["horizon"]): f for f in forecasts}
    days = [(monday + timedelta(days=i)).date() for i in range(5)]
    pairs = []
    for p in ALL_PAIRS:
        v = A.pair_view(p, cot_now, trend, season_pairs, month)
        d1, w1 = fc.get((p, "1D")), fc.get((p, "1W"))
        price = (d1 or w1 or {}).get("price")
        day_pips = None if not d1 or not price else A.pips(p, price, (d1["quantiles"]["q90"] - d1["quantiles"]["q10"]) / 2)
        week_pips = None if not w1 or not price else A.pips(p, price, (w1["quantiles"]["q90"] - w1["quantiles"]["q10"]) / 2)
        pair_events = [e for e in events if e["currency"] in (p[:3], p[3:])]
        pairs.append({
            "pair": p, "direction": v.direction, "confluence": v.confluence, "against": v.against,
            "factors": {k: {"signal": x["signal"], "value": _r(x["value"]), "text": x["text"]} for k, x in v.factors.items()},
            "cot_diff": _r(v.factors["cot"]["value"], 1), "price": price,
            "day_range_pips": _r(day_pips, 0), "week_range_pips": _r(week_pips, 0),
            "high_events": sum(1 for e in pair_events if e["impact"] == "High"),
            "days": [{"date": d.isoformat(), "weekday": WEEKDAYS_DE[d.weekday()],
                      "events": [e for e in pair_events if e["day"] == d.isoformat() and e["impact"] in ("High", "Medium", "Holiday")]}
                     for d in days],
        })

    cot_out = {}
    if not cot.empty:
        for c in MAJORS:
            g = cot_idx[cot_idx["currency"] == c].sort_values("report_date")
            g = g[g["available_at"] <= now]
            if g.empty:
                continue
            last = g.iloc[-1]
            tail = g.iloc[-156:]
            cot_out[c] = {
                "report_date": str(last["report_date"]), "released": last["available_at"].astimezone(BERLIN).isoformat(),
                "comm_idx": _r(last["comm_idx"], 0), "spec_idx": _r(last["spec_idx"], 0),
                "comm_net": int(last["comm_net"]), "spec_net": int(last["spec_net"]),
                "comm_chg_4w": None if pd.isna(last["comm_chg_4w"]) else int(last["comm_chg_4w"]),
                "spec_chg_4w": None if pd.isna(last["spec_chg_4w"]) else int(last["spec_chg_4w"]),
                "open_interest": None if pd.isna(last["open_interest"]) else int(last["open_interest"]),
                "label": A.cot_label(last["comm_idx"]),
                "history": [[str(d), _r(a, 0), _r(b, 0)] for d, a, b in zip(tail["report_date"], tail["comm_idx"], tail["spec_idx"])],
                "weekly": [[str(d), int(cn), int(sn), None if pd.isna(sm) else int(sm)] for d, cn, sn, sm in
                           zip(tail["report_date"], tail["comm_net"], tail["spec_net"], tail["small_net"])],
                "small_idx": _r(last.get("small_idx"), 0),
                "contract": "US-Dollar-Index (ICE)" if c == "USD" else f"{A.CCY_NAME[c]}-Future (CME)",
            }

    season_out = {"month": month, "month_name": A.MONTHS_DE[month - 1], "pairs": {}, "currencies": {}}
    for p in ALL_PAIRS:
        season_out["pairs"][p] = {m: {k: _r(v, 5) if k != "n" else v for k, v in st.items()} for m, st in season_pairs.get(p, {}).items()}
    for c in MAJORS:
        season_out["currencies"][c] = {m: {k: _r(v, 5) if k != "n" else v for k, v in st.items()} for m, st in season_ccy.get(c, {}).items()}
    season_out["years"] = [int(monthly.index.year.min()), int(now.year - 1)]

    upcoming = [e for e in events if e["at"] >= now.isoformat()]
    top_event = next((e for e in upcoming if e["impact"] == "High" and e["currency"] in (strong, weak)), None) or \
        next((e for e in upcoming if e["impact"] == "High"), None)
    best = sorted([x for x in pairs if x["direction"]], key=lambda x: (-x["confluence"], -abs(x["cot_diff"] or 0)))
    from forex_nexus.fundamentals import extras
    vix_s = None
    try:
        from forex_nexus.ingestion.fred_series import load_series
        vix_s = load_series(conn, "VIXCLS")
    except Exception:
        vix_s = None
    extra = {
        "season_paths": extras.seasonal_paths(closes, now.year),
        "screener": extras.season_screener(closes, now.date()),
        "strength_windows": extras.strength_windows(strength),
        "mood": extras.market_mood(vix_s, closes, strength) if vix_s is not None and len(vix_s) > 260 and "AUDJPY" in closes else None,
    }
    return {
        "extra": extra,
        "week": {"start": monday.date().isoformat(), "end": (monday + timedelta(days=4)).date().isoformat(),
                 "kw": int(monday.isocalendar()[1]), "days": [d.isoformat() for d in days]},
        "headline": {"strong": strong, "weak": weak, "strong_name": A.CCY_NAME[strong], "weak_name": A.CCY_NAME[weak],
                     "top_event": top_event, "best_pair": best[0]["pair"] if best else None,
                     "best_direction": best[0]["direction"] if best else 0, "best_confluence": best[0]["confluence"] if best else 0},
        "currencies": [{"ccy": c, "name": A.CCY_NAME[c], **{k: _r(v) for k, v in s.items()}} for c, s in ranked],
        "pairs": pairs, "events": events, "cot": cot_out, "season": season_out, "validation": validation,
        "rules": {"cot_diff": A.COT_DIFF, "trend_min": A.TREND_MIN, "season_hit": A.SEASON_HIT,
                  "cot_extreme": list(A.COT_EXTREME), "cot_window_weeks": A.COT_WINDOW},
    }
