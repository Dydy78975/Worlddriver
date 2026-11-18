"""Statistische Prüfung der Wirtschaftsbeziehungen (Dependency Engine).

Je Beziehung (Währung, Treiber) zwei Tests auf Monatsbasis:
  1. GLEICHZEITIG (erklärend): Veränderung der Währungsstärke im Monat vs. Veränderung des Treibers
     im selben Monat (jeweils Monatsdurchschnitte). Beantwortet: „Bewegen sie sich gemeinsam?“
  2. VORAUSLAUFEND (prognostisch): Treiberveränderung im Monat m vs. Währungsrendite in einem SPÄTEREN
     Monat – erst nachdem der Treiberwert veröffentlicht war (Veröffentlichungsverzögerung beachtet).
     Beantwortet: „Hilft der Treiber, die Zukunft vorherzusagen?“

Währungsstärke = Währung gegen gleich gewichteten Korb der anderen 7 Hauptwährungen.
Standardfehler: Newey-West (HAC). Mehrfachtest-Korrektur: Benjamini-Hochberg.
Der Status einer Beziehung wird hier NIE geändert – das Ergebnis ist eine Empfehlung für dich.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

from forex_nexus.db import connect
from forex_nexus.fx.crosses import MAJORS, usd_per_unit
from forex_nexus.ingestion.fred_series import load_series
from forex_nexus.quality.fx_checks import ANALYSIS_START, load_closes

SUBPERIODS = [("2000-01-01", "2008-12-31"), ("2009-01-01", "2015-12-31"), ("2016-01-01", "2100-01-01")]
OOS_START = "2010-01-01"
ROLLING_MONTHS = 36
P_LIMIT = 0.05


def currency_strength(closes: pd.DataFrame) -> pd.DataFrame:
    """Log-Stärke jeder Währung gegen den Korb der anderen 7 (täglich)."""
    usd_cols = [c for c in closes.columns if "USD" in c]
    lu = np.log(usd_per_unit(closes[usd_cols].dropna()))
    return pd.DataFrame({c: lu[c] - lu[[o for o in MAJORS if o != c]].mean(axis=1) for c in MAJORS})


def _ols_hac(y: pd.Series, x: pd.Series, maxlags: int = 3):
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    if len(d) < 36:
        return None
    res = sm.OLS(d["y"], sm.add_constant(d["x"])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {"beta": float(res.params["x"]), "se": float(res.bse["x"]), "p": float(res.pvalues["x"]),
            "t": float(res.tvalues["x"]), "r2": float(res.rsquared), "n": int(len(d)),
            "start": d.index.min(), "end": d.index.max()}


def _target_lead(frequency: str, lag_days: int) -> int:
    """Wie viele Monate nach dem Treibermonat die Ziel-Rendite beginnt: Monatswert m ist bekannt am
    Monatsende + Verzögerung; Ziel ist der erste volle Kalendermonat danach."""
    months_until_known = int(np.ceil(lag_days / 30.0)) if lag_days > 0 else 0
    return 1 + months_until_known


def analyse(strength: pd.DataFrame, driver: pd.Series, currency: str, frequency: str, lag_days: int,
            expected_sign: int | None) -> dict:
    """Beide Tests + Stabilität + Out-of-Sample für eine Beziehung."""
    drv = driver.copy()
    drv.index = pd.to_datetime(drv.index)
    drv = drv[drv > 0]                              # Log-Veränderungen nur für positive Preise
    s = strength[currency].copy()
    s.index = pd.to_datetime(s.index)
    s_avg = s.resample("ME").mean()
    s_end = s.resample("ME").last()
    d_avg = np.log(drv.resample("ME").mean())
    ds, dd = s_avg.diff(), d_avg.diff()
    out = {"currency": currency}

    # 1) gleichzeitig
    c = _ols_hac(ds, dd)
    out["contemporaneous"] = c
    subs = []
    for a, b in SUBPERIODS:
        r = _ols_hac(ds[a:b], dd[a:b])
        subs.append(None if r is None else {"from": a[:4], "to": min(b[:4], str(ds.index.max().year)),
                                            "beta": r["beta"], "p": r["p"]})
    out["subperiods"] = subs
    roll = pd.concat([ds.rename("y"), dd.rename("x")], axis=1).dropna().iloc[-ROLLING_MONTHS:]
    out["recent"] = _ols_hac(roll["y"], roll["x"]) if len(roll) >= 36 else None

    # 2) vorauslaufend
    lead = _target_lead(frequency, lag_days)
    fwd = s_end.diff().shift(-lead)                 # Stärke-Veränderung im Zielmonat m + lead
    p = _ols_hac(fwd, dd)
    out["predictive"] = p
    out["lead_months"] = lead
    d = pd.concat([fwd.rename("y"), dd.rename("x")], axis=1).dropna()
    preds, actual = [], []
    for t in d.index[d.index >= OOS_START]:
        train = d[d.index <= t - pd.DateOffset(months=lead)]
        if len(train) < 36:
            continue
        beta = np.polyfit(train["x"], train["y"], 1)
        preds.append(np.polyval(beta, d.loc[t, "x"]))
        actual.append(d.loc[t, "y"])
    if preds:
        pr, ac = np.array(preds), np.array(actual)
        out["oos"] = {"n": len(pr), "r2": float(1 - ((ac - pr) ** 2).sum() / (ac ** 2).sum()),
                      "hit_rate": float((np.sign(pr) == np.sign(ac)).mean())}
    else:
        out["oos"] = None

    # Bewertung
    sign_ok = (c is not None) and (expected_sign is None or np.sign(c["beta"]) == expected_sign)
    same_sign = sum(1 for x in subs if x and c and np.sign(x["beta"]) == np.sign(c["beta"]))
    out["explanatory_pass"] = bool(c is not None and c["p"] < P_LIMIT and sign_ok and same_sign >= 2)
    out["predictive_pass"] = bool(p is not None and p["p"] < P_LIMIT and out["oos"] and out["oos"]["r2"] > 0
                                  and (expected_sign is None or np.sign(p["beta"]) == expected_sign))
    weakening = bool(out["explanatory_pass"] and out["recent"] and
                     (abs(out["recent"]["t"]) < 1.0 or np.sign(out["recent"]["beta"]) != np.sign(c["beta"])))
    out["weakening"] = weakening
    if c is not None and c["p"] < P_LIMIT and expected_sign is not None and not sign_ok:
        verdict = "gegenteilig"
    elif out["predictive_pass"]:
        verdict = "vorauslaufend"
    elif out["explanatory_pass"]:
        verdict = "schwächer werdend" if weakening else "erklärend"
    elif c is not None and c["p"] < P_LIMIT:
        verdict = "instabil"
    else:
        verdict = "nicht belegt"
    out["verdict"] = verdict
    out["priced_in"] = {"label": "sofort eingepreist" if out["explanatory_pass"] and not out["predictive_pass"]
                        else "Vorlauf vorhanden" if out["predictive_pass"] else "kein messbarer Zusammenhang",
                        "contemporaneous_r2": None if c is None else c["r2"]}
    return out


VERDICT_TEXT = {
    "vorauslaufend": "Belegt mit Vorlauf: Der Treiber hilft, spätere Bewegungen vorherzusagen. Empfehlung: prüfen und freigeben.",
    "erklärend": "Belegt als gleichzeitiger Zusammenhang: erklärt Bewegungen, ist aber sofort eingepreist (keine Vorhersagekraft).",
    "schwächer werdend": "Langfristig belegt, in den letzten 3 Jahren aber deutlich schwächer.",
    "instabil": "Statistisch auffällig, aber nicht über verschiedene Zeiträume stabil.",
    "gegenteilig": "Signifikant – aber mit umgekehrtem Vorzeichen als erwartet. Die Hypothese stimmt so nicht.",
    "nicht belegt": "Kein belastbarer Zusammenhang in den Daten.",
    "keine Daten": "Noch keine Datenquelle angebunden.",
}


def run(conninfo: str, code_commit: str = "unbekannt") -> list[dict]:
    with connect(conninfo) as conn:
        closes = load_closes(conn, ["FRED_H10"])
        closes = closes[closes.index >= ANALYSIS_START]
        strength = currency_strength(closes)
        rels = conn.execute(
            """SELECT r.relationship_id, r.currency, r.driver_key, r.expected_sign, d.name_de, s.source_code,
                      s.frequency, extract(epoch FROM s.publication_lag)::int / 86400
               FROM dep.relationship r JOIN dep.driver d USING (driver_key)
               LEFT JOIN ref.series s ON s.series_id = d.price_series_id ORDER BY r.relationship_id""").fetchall()
        series_cache = {}
        results = []
        for rid, ccy, dkey, sign, dname, code, freq, lag in rels:
            base = {"relationship_id": rid, "currency": ccy, "driver_key": dkey, "driver_name": dname,
                    "expected_sign": sign}
            if code is None:
                results.append({**base, "verdict": "keine Daten"})
                continue
            if code not in series_cache:
                series_cache[code] = load_series(conn, code)
            res = analyse(strength, series_cache[code], ccy, freq, lag or 0, sign)
            results.append({**base, **res, "frequency": freq, "lag_days": lag})

        tested = [r for r in results if r.get("contemporaneous")]
        for key in ("contemporaneous", "predictive"):
            ps = [r[key]["p"] if r.get(key) else 1.0 for r in tested]
            if ps:
                q = multipletests(ps, method="fdr_bh")[1]
                for r, qv in zip(tested, q):
                    r[f"{key}_q"] = float(qv)

        run_id = conn.execute(
            """INSERT INTO dep.analysis_run (run_type, as_of, n_tests, fdr_level, settings, code_commit)
               VALUES ('validation', now(), %s, 0.10, %s, %s) RETURNING run_id""",
            (2 * len(tested), json.dumps({"subperiods": SUBPERIODS, "oos_start": OOS_START, "p_limit": P_LIMIT,
                                          "rolling_months": ROLLING_MONTHS, "strength": "gegen Korb der anderen 7"}),
             code_commit)).fetchone()[0]
        for r in tested:
            for key, lag_p, method, passed in (("contemporaneous", 0, "ols_hac_contemporaneous", r["explanatory_pass"]),
                                               ("predictive", r["lead_months"], "ols_hac_predictive", r["predictive_pass"])):
                t = r.get(key)
                if t is None:
                    continue
                conn.execute(
                    """INSERT INTO dep.relationship_test (run_id, relationship_id, currency, driver_key, frequency,
                           window_start, window_end, lag_periods, method, n_obs, estimate, std_error, p_value, q_value,
                           oos_metrics, stability, priced_in, passed)
                       VALUES (%s,%s,%s,%s,'M',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, r["relationship_id"], r["currency"], r["driver_key"], t["start"].date(), t["end"].date(),
                     lag_p, method, t["n"], t["beta"], t["se"], t["p"], r.get(f"{key}_q"),
                     json.dumps(r["oos"]) if key == "predictive" else None,
                     json.dumps({"subperiods": r["subperiods"], "recent_36m": _clean(r["recent"]),
                                 "weakening": r["weakening"], "verdict": r["verdict"],
                                 "contemporaneous_r2": r["contemporaneous"]["r2"] if r.get("contemporaneous") else None,
                                 "lead_months": r["lead_months"]}),
                     json.dumps(r["priced_in"]), passed))
        conn.commit()
    for r in results:
        r["verdict_text"] = VERDICT_TEXT[r["verdict"]]
    return results


def _clean(d):
    if d is None:
        return None
    return {k: (str(v.date()) if hasattr(v, "date") else v) for k, v in d.items()}
