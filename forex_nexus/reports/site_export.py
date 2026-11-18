"""Website WorlᗡDriver bauen: alle Inhalte kommen aus der Datenbank und werden als JSON in die
Vorlage site/template.html eingesetzt. Ergebnis: site/index.html (eine Datei, ohne Server nutzbar)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from forex_nexus.db import connect
from forex_nexus.dependencies.validation import VERDICT_TEXT, currency_strength
from forex_nexus.fx.crosses import ALL_PAIRS, MAJORS
from forex_nexus.ingestion.fred_series import load_series
from forex_nexus.ledger.pipeline import PRICE_SOURCES, code_commit
from forex_nexus.models.features import FEATURE_LABELS_DE
from forex_nexus.quality.fx_checks import ANALYSIS_START, load_closes

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "site" / "template.html"
OUTPUT = ROOT / "site" / "index.html"
WORLDMAP = ROOT / "assets" / "worldmap.json"
PLACEHOLDER = "/*__WORLDDRIVER_DATA__*/null"

HORIZON_LABEL = {"1D": "Tag", "1W": "Woche", "1M": "Monat"}
MODEL_LABEL = {"climatology": "Referenz (historische Häufigkeit)", "volref": "Schwankungs-Referenz", "logreg": "Logistische Regression", "lgbm": "LightGBM"}


def _r(x, n=6):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    return round(float(x), n)


def collect(conninfo: str) -> dict:
    with connect(conninfo) as conn:
        closes = load_closes(conn, PRICE_SOURCES)
        closes = closes[closes.index >= ANALYSIS_START]
        last = closes.index.max()
        tail = closes.iloc[-260:]
        prices = {p: [[str(d), _r(v, 6)] for d, v in tail[p].dropna().items()] for p in ALL_PAIRS if p in tail}

        strength = currency_strength(load_closes(conn, ["FRED_H10"]).loc[lambda d: d.index >= ANALYSIS_START])
        st_tail = strength.iloc[-130:]
        strength_out = {}
        for c in MAJORS:
            s = strength[c].dropna()
            strength_out[c] = {"chg_5d": _r((s.iloc[-1] - s.iloc[-6]) * 100, 3),
                               "chg_20d": _r((s.iloc[-1] - s.iloc[-21]) * 100, 3),
                               "chg_60d": _r((s.iloc[-1] - s.iloc[-61]) * 100, 3),
                               "series": [_r((v - st_tail[c].iloc[0]) * 100, 3) for v in st_tail[c]]}

        vix = load_series(conn, "VIXCLS")
        vix_last = float(vix.iloc[-1]) if len(vix) else None

        fc_rows = conn.execute(
            """SELECT t.forecast_id, t.symbol, t.horizon_code, t.model_name, t.model_version, t.as_of, t.target_date,
                      t.reference_price::float8, t.p_bull, t.p_neutral, t.p_bear, t.expected_return, t.expected_direction,
                      t.quantiles, t.expected_range_high, t.expected_range_low, t.confidence, t.confidence_label,
                      t.is_display_calibrated, t.change_p_bull, t.change_p_bear, t.prev_direction, f.invalidation_rules,
                      f.perf_snapshot, f.expected_vol
               FROM ml.v_forecast_tracker t JOIN ml.forecast f USING (forecast_id)
               WHERE NOT t.is_shadow AND NOT t.is_backtest
                 AND t.as_of = (SELECT max(as_of) FROM ml.forecast_run WHERE NOT is_backtest)""").fetchall()
        drivers = {}
        for fid, rank, key, rid, contrib, text in conn.execute(
                """SELECT d.forecast_id, d.rank, d.feature_key, d.relationship_id, d.contribution, d.explanation_de
                   FROM ml.forecast_driver d ORDER BY d.forecast_id, d.rank""").fetchall():
            drivers.setdefault(fid, []).append({"feature": key, "label": FEATURE_LABELS_DE.get(key, key),
                                                "contribution": _r(contrib, 4), "relationship_id": rid, "text": text})
        forecasts = []
        for r in fc_rows:
            (fid, sym, h, model, ver, as_of, target, ref, pb, pn, pr, er, d, q, hi, lo, conf, label, disp,
             cpb, cpr, prevd, inval, snap, evol) = r
            forecasts.append({
                "pair": sym, "horizon": h, "model": model, "model_label": MODEL_LABEL.get(model, model),
                "version": ver, "as_of": str(as_of.date()), "target_date": str(target), "price": _r(ref, 6),
                "p_bull": _r(pb, 4), "p_neutral": _r(pn, 4), "p_bear": _r(pr, 4), "expected_return": _r(er, 6),
                "direction": d, "quantiles": q, "range_high": _r(hi, 6), "range_low": _r(lo, 6),
                "expected_vol": _r(evol, 6), "confidence": _r(conf, 3), "confidence_label": label,
                "calibrated": disp, "change_p_bull": _r(cpb, 4), "change_p_bear": _r(cpr, 4), "prev_direction": prevd,
                "invalidation": inval, "regime": (snap or {}).get("regime"), "drivers": drivers.get(fid, [])})

        ledger = dict(zip(["runs", "forecasts", "shadow", "evaluated", "first_run"], conn.execute(
            """SELECT (SELECT count(*) FROM ml.forecast_run WHERE NOT is_backtest), count(*),
                      count(*) FILTER (WHERE f.is_shadow),
                      (SELECT count(*) FROM ml.forecast_outcome), (SELECT min(created_at) FROM ml.forecast_run WHERE NOT is_backtest)
               FROM ml.forecast f""").fetchone()))
        ledger["first_run"] = ledger["first_run"].isoformat() if ledger["first_run"] else None
        next_due = conn.execute(
            """SELECT horizon_code, min(target_date) FROM ml.forecast f LEFT JOIN ml.forecast_outcome o USING (forecast_id)
               WHERE o.forecast_id IS NULL GROUP BY 1""").fetchall()
        ledger["next_due"] = {h: str(d) for h, d in next_due}
        monthly = [dict(zip(["month", "model", "horizon", "n", "brier", "hit_rate", "coverage_80"],
                            [str(m), mo, h, n, _r(b, 4), _r(hr, 4), _r(cv, 4)])) for m, mo, h, _, n, b, _, hr, _, _, cv in
                   conn.execute("SELECT * FROM ml.v_performance_monthly WHERE NOT is_backtest ORDER BY month").fetchall()]
        ledger["monthly"] = monthly

        backtest = {}
        for h in HORIZON_LABEL:
            rows = conn.execute(
                """SELECT mv.name, mv.status, e.eval_type, e.segment_type, e.segment_value, e.metrics, mv.version
                   FROM ml.evaluation e JOIN ml.model_version mv USING (model_version_id)
                   WHERE mv.horizon_code = %s AND mv.version = (SELECT max(version) FROM ml.model_version WHERE horizon_code = %s)""",
                (h, h)).fetchall()
            hb = {"champion": None, "version": None, "models": {}, "yearly": {}, "currency": {}, "regime": {}}
            for name, status, et, st, sv, m, ver in rows:
                hb["version"] = ver
                if status == "champion":
                    hb["champion"] = name
                mm = hb["models"].setdefault(name, {"label": MODEL_LABEL.get(name, name), "status": status})
                keep = ("bss", "bss_ci_low", "bss_ci_high", "bss_vs_volref", "bss_vs_volref_ci_low", "hit_rate", "ece", "coverage_80", "coverage_90",
                        "oos_r2_return", "n_dates", "log_loss", "brier")
                if st == "all":
                    mm["validation" if et == "walk_forward" else "holdout"] = {k: _r(m.get(k), 5) for k in keep}
                elif st == "year":
                    hb["yearly"].setdefault(name, []).append([int(sv), _r(m["bss"], 5)])
                elif st in ("currency", "regime"):
                    hb[st].setdefault(name, {})[sv] = {k: _r(m.get(k), 5) for k in ("bss", "hit_rate", "coverage_80", "n")}
            for name in hb["yearly"]:
                hb["yearly"][name].sort()
            backtest[h] = hb

        promotions = [{"horizon": h, "model": MODEL_LABEL.get(n, n), "version": v, "decided_by": by,
                       "decided_at": at.isoformat(), "rationale": why, "needs_confirmation": "ausstehend" in by}
                      for h, n, v, by, at, why in conn.execute(
                          """SELECT mv.horizon_code, mv.name, mv.version, p.decided_by, p.decided_at, p.rationale
                             FROM ml.model_promotion p JOIN ml.model_version mv ON mv.model_version_id = p.challenger_id
                             ORDER BY p.decided_at""").fetchall()]

        deps = []
        for row in conn.execute(
                """SELECT r.relationship_id, r.currency, r.driver_key, d.name_de, d.category, d.data_status, r.expected_sign,
                          r.mechanism_de, r.causal_chain, r.conditions_de, r.status, r.origin,
                          c.estimate, c.p_value, c.q_value, c.stability, c.window_start, c.window_end, c.n_obs,
                          p.estimate, p.p_value, p.oos_metrics, p.lag_periods, c.priced_in
                   FROM dep.relationship r JOIN dep.driver d USING (driver_key)
                   LEFT JOIN LATERAL (SELECT * FROM dep.relationship_test t WHERE t.relationship_id = r.relationship_id
                                      AND t.method = 'ols_hac_contemporaneous' ORDER BY t.test_id DESC LIMIT 1) c ON TRUE
                   LEFT JOIN LATERAL (SELECT * FROM dep.relationship_test t WHERE t.relationship_id = r.relationship_id
                                      AND t.method = 'ols_hac_predictive' ORDER BY t.test_id DESC LIMIT 1) p ON TRUE
                   ORDER BY r.currency, r.relationship_id""").fetchall():
            (rid, ccy, dkey, dname, cat, dstat, sign, mech, chain, cond, status, origin,
             cb, cp, cq, stab, ws, we, n, pb_, pp, oos, lead, priced) = row
            verdict = (stab or {}).get("verdict") or ("keine Daten" if dstat == "missing" else "nicht geprüft")
            deps.append({"id": rid, "currency": ccy, "driver_key": dkey, "driver": dname, "category": cat,
                         "data_status": dstat, "expected_sign": sign, "mechanism": mech, "chain": chain,
                         "conditions": cond, "status": status, "origin": origin, "verdict": verdict,
                         "verdict_text": VERDICT_TEXT.get(verdict, ""),
                         "contemporaneous": None if cb is None else {"beta": _r(cb, 4), "p": _r(cp, 4), "q": _r(cq, 4),
                                                                      "r2": _r((stab or {}).get("contemporaneous_r2"), 4),
                                                                      "n": n, "from": str(ws), "to": str(we)},
                         "subperiods": (stab or {}).get("subperiods"), "recent": (stab or {}).get("recent_36m"),
                         "predictive": None if pb_ is None else {"beta": _r(pb_, 4), "p": _r(pp, 4), "oos": oos,
                                                                  "lead_months": lead},
                         "priced_in": priced})

        economies = [dict(zip(["code", "name", "currency", "notes"], r)) for r in
                     conn.execute("SELECT economy_code, name_de, currency, notes_de FROM dep.economy").fetchall()]

        quality = [dict(zip(["check", "severity", "count"], r)) for r in conn.execute(
            """SELECT check_name, severity, count(*) FROM raw.data_quality_issue
               WHERE affected_date >= %s OR affected_date IS NULL GROUP BY 1, 2 ORDER BY 1""", (ANALYSIS_START,)).fetchall()]
        sources = [dict(zip(["source", "last_run", "status", "rows"], [s, t.isoformat() if t else None, st, n])) for s, t, st, n in
                   conn.execute("""SELECT DISTINCT ON (d.name) d.name, r.finished_at, r.status, r.rows_inserted
                                   FROM raw.ingestion_run r JOIN ref.data_source d USING (source_id)
                                   ORDER BY d.name, r.run_id DESC""").fetchall()]
        last_obs = {code: str(d) for code, d in conn.execute(
            """SELECT s.source_code, max(o.period_date) FROM raw.observation o JOIN ref.series s USING (series_id)
               GROUP BY 1""").fetchall()}

    return {
        "meta": {"generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"), "as_of": str(last),
                 "code_commit": code_commit(), "price_basis": "FRED H.10 Mittagskurse New York (vorläufig)",
                 "vix": _r(vix_last, 2)},
        "pairs": ALL_PAIRS, "majors": MAJORS, "prices": prices, "strength": strength_out,
        "forecasts": forecasts, "ledger": ledger, "backtest": backtest, "promotions": promotions,
        "dependencies": deps, "economies": economies, "quality": quality, "sources": sources, "series_last": last_obs,
    }


def build(conninfo: str, output: Path = OUTPUT) -> Path:
    data = collect(conninfo)
    data["map"] = json.loads(WORLDMAP.read_text(encoding="utf-8"))
    html = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError("Platzhalter für die Daten fehlt in site/template.html")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).replace("</", "<\\/")
    output.write_text(html.replace(PLACEHOLDER, payload), encoding="utf-8")
    return output
