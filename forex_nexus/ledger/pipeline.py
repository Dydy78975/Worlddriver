"""Training, Freigabe, tägliche Prognose und Auswertung – die Abläufe rund um das Prognose-Ledger.

Ablauf und Regeln:
  train     – Walk-Forward-Backtest je Horizont, Kennzahlen, neue Modellversionen als 'candidate'.
              Ändert NICHTS an laufenden Prognosen.
  promote   – Freigabe eines Kandidaten als Champion (nur mit Namen der entscheidenden Person,
              dokumentiert in ml.model_promotion).
  forecast  – täglicher Lauf: alle aktiven Versionen (Champion + Schatten) werden mit ihrem
              EINGEFRORENEN Trainingsstand (train_end) deterministisch neu aufgebaut und prognostizieren
              ab dem neuesten Kurs. Keine Parameteränderung im Live-Betrieb.
  evaluate  – fällige Prognosen mit der tatsächlichen Entwicklung vergleichen.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from forex_nexus.db import connect
from forex_nexus.ingestion.fred_series import load_series
from forex_nexus.models import engine
from forex_nexus.models.features import (EWMA_LAMBDA, FEATURE_LABELS_DE, FEATURES, HORIZONS, NEUTRAL_K,
                                         build_panel, vix_regime)
from forex_nexus.quality.fx_checks import ANALYSIS_START, load_closes

NEW_YORK = ZoneInfo("America/New_York")
PRICE_SOURCES = ["FRED_H10", "FRED_H10_CROSS"]
FEATURE_SET_VERSION = "fs-2026.11-a"
LABEL_VERSION = "ld-2026.11-a"
VIX_RELATED = {"vix_level", "vix_chg_5d", "vix_x_risk"}


def code_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).resolve().parents[2], check=True).stdout.strip()
    except Exception:
        return "unbekannt"


def load_panel(conn, as_of: date | None = None) -> pd.DataFrame:
    closes = load_closes(conn, PRICE_SOURCES)
    closes = closes[closes.index >= ANALYSIS_START]
    if as_of is not None:
        closes = closes[closes.index <= as_of]
    vix = load_series(conn, "VIXCLS")
    return build_panel(closes, vix)


def _ensure_definitions(conn, commit: str) -> tuple[int, int]:
    conn.execute(
        """INSERT INTO ml.label_definition (version, neutral_k, vol_method, description)
           VALUES (%s, %s, %s, %s) ON CONFLICT (version) DO NOTHING""",
        (LABEL_VERSION, NEUTRAL_K, f"ewma_{EWMA_LAMBDA}",
         "bullisch/bärisch, wenn |Rendite| > k · EWMA-Volatilität · √Horizont, sonst neutral"))
    conn.execute(
        """INSERT INTO feat.feature_set (version, definition, code_commit) VALUES (%s, %s, %s)
           ON CONFLICT (version) DO NOTHING""",
        (FEATURE_SET_VERSION, json.dumps({"features": FEATURES, "vix": "Vortag (Mittagskurs-Daten)",
                                          "price_sources": PRICE_SOURCES}), commit))
    lid = conn.execute("SELECT label_def_id FROM ml.label_definition WHERE version = %s", (LABEL_VERSION,)).fetchone()[0]
    fid = conn.execute("SELECT feature_set_id FROM feat.feature_set WHERE version = %s", (FEATURE_SET_VERSION,)).fetchone()[0]
    return lid, fid


# --------------------------------------------------------------------------- train

def train(conninfo: str, out_dir: Path, log=print) -> dict:
    """Backtest aller Horizonte; legt Kandidaten-Versionen an und schreibt Kennzahlen."""
    commit = code_commit()
    version = f"{date.today():%Y.%m.%d}-{commit[:7]}"
    with connect(conninfo) as conn:
        panel = load_panel(conn)
        lid, fid = _ensure_definitions(conn, commit)
        conn.commit()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"version": version, "code_commit": commit, "horizons": {}}
    for horizon in HORIZONS:
        log(f"Walk-Forward {horizon} …")
        oos = engine.walk_forward(panel, horizon, log=lambda m: None)
        rep = engine.evaluate(oos, horizon)
        train_end = panel.loc[panel[f"target_date_{horizon}"].notna(), f"target_date_{horizon}"].max().date()
        oos.to_pickle(out_dir / f"oos_{horizon}.pkl")
        with connect(conninfo) as conn:
            ids = {}
            for m in engine.MODELS:
                ids[m] = conn.execute(
                    """INSERT INTO ml.model_version (name, version, model_type, horizon_code, feature_set_id,
                           label_def_id, hyperparams, train_start, train_end, code_commit, is_calibrated, status, components)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'candidate', %s)
                       ON CONFLICT (name, version, horizon_code) DO UPDATE SET status = ml.model_version.status
                       RETURNING model_version_id""",
                    (m, version, "baseline" if m in ("climatology", "volref") else "ml", horizon, fid, lid,
                     json.dumps({"model": m}), ANALYSIS_START, train_end, commit,
                     m == rep.champion and rep.display_calibrated,
                     json.dumps({"direction": m, "return": "ridge" if rep.use_return_model else "zero (OOS-R² <= 0)",
                                 "interval": "empirische Quantile × EWMA-Volatilität",
                                 "range": "empirische Spanne der Schlusskurse × EWMA-Volatilität"}))).fetchone()[0]
                # erneuter Lauf derselben Version: alte Kennzahlen dieser Version ersetzen (keine Dubletten)
                # (Kennzahlen, auf die eine Freigabe verweist, bleiben als Beleg erhalten)
                conn.execute("""DELETE FROM ml.evaluation e WHERE e.model_version_id = %s AND NOT EXISTS
                                (SELECT 1 FROM ml.model_promotion p WHERE p.oos_evaluation_id = e.evaluation_id)""", (ids[m],))
                for eval_type, part, metr in (("walk_forward", oos[oos.year <= engine.VALIDATION_END_YEAR], rep.validation[m]),
                                              ("out_of_sample", oos[oos.year > engine.VALIDATION_END_YEAR], rep.holdout.get(m))):
                    if metr:
                        conn.execute(
                            """INSERT INTO ml.evaluation (model_version_id, eval_type, period_start, period_end,
                                   segment_type, segment_value, n_forecasts, metrics)
                               VALUES (%s, %s, %s, %s, 'all', 'all', %s, %s)""",
                            (ids[m], eval_type, part["date"].min().date(), part["date"].max().date(), metr["n"], json.dumps(metr)))
            for row in rep.yearly:
                conn.execute(
                    """INSERT INTO ml.evaluation (model_version_id, eval_type, period_start, period_end,
                           segment_type, segment_value, n_forecasts, metrics)
                       VALUES (%s, %s, %s, %s, 'year', %s, 0, %s)""",
                    (ids[row["model"]], "walk_forward" if row["year"] <= engine.VALIDATION_END_YEAR else "out_of_sample",
                     date(row["year"], 1, 1), date(row["year"], 12, 31), str(row["year"]),
                     json.dumps({"brier": row["brier"], "bss": row["bss"]})))
            for row in rep.by_segment:
                conn.execute(
                    """INSERT INTO ml.evaluation (model_version_id, eval_type, period_start, period_end,
                           segment_type, segment_value, n_forecasts, metrics)
                       VALUES (%s, 'walk_forward', %s, %s, %s, %s, %s, %s)""",
                    (ids[row["model"]], oos["date"].min().date(), oos["date"].max().date(), row["segment_type"],
                     row["segment_value"], row["n"], json.dumps({k: v for k, v in row.items()
                                                                 if k not in ("model", "segment_type", "segment_value")})))
            conn.commit()
        summary["horizons"][horizon] = {
            "champion_recommendation": rep.champion, "use_return_model": rep.use_return_model,
            "display_calibrated": rep.display_calibrated, "validation": rep.validation, "holdout": rep.holdout,
            "yearly": rep.yearly, "by_segment": rep.by_segment, "model_version_ids": ids, "train_end": str(train_end)}
        log(f"  {horizon}: empfohlener Champion {rep.champion}, Anzeige kalibriert: {rep.display_calibrated}")
    (out_dir / "train_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------- promote

def promote(conninfo: str, version: str, horizon: str, model: str, decided_by: str, rationale: str) -> int:
    """Gibt einen Kandidaten als Champion frei; alle anderen Modelle derselben Version laufen im Schatten mit."""
    if not decided_by.strip():
        raise ValueError("Eine Freigabe braucht den Namen der entscheidenden Person")
    with connect(conninfo) as conn:
        rows = dict(conn.execute(
            "SELECT name, model_version_id FROM ml.model_version WHERE version = %s AND horizon_code = %s",
            (version, horizon)).fetchall())
        if model not in rows:
            raise ValueError(f"Modell {model} {horizon} in Version {version} nicht gefunden")
        old = conn.execute("SELECT model_version_id FROM ml.model_version WHERE horizon_code = %s AND status = 'champion'",
                           (horizon,)).fetchone()
        ev = conn.execute(
            """SELECT evaluation_id, metrics FROM ml.evaluation WHERE model_version_id = %s
               AND segment_type = 'all' ORDER BY eval_type DESC LIMIT 1""", (rows[model],)).fetchone()
        conn.execute("UPDATE ml.model_version SET status = 'retired' WHERE horizon_code = %s AND status IN ('champion', 'shadow')",
                     (horizon,))
        conn.execute("UPDATE ml.model_version SET status = 'champion' WHERE model_version_id = %s", (rows[model],))
        for name, mid in rows.items():
            if name != model:
                conn.execute("UPDATE ml.model_version SET status = 'shadow' WHERE model_version_id = %s", (mid,))
        pid = conn.execute(
            """INSERT INTO ml.model_promotion (challenger_id, champion_id, oos_evaluation_id, test_results, decision,
                   decided_by, rationale) VALUES (%s, %s, %s, %s, 'promoted', %s, %s) RETURNING promotion_id""",
            (rows[model], old[0] if old else None, ev[0] if ev else None, json.dumps(ev[1] if ev else {}),
             decided_by, rationale)).fetchone()[0]
        conn.commit()
    return pid


# --------------------------------------------------------------------------- forecast

def _confidence(validated: dict | None, display: bool, probs: np.ndarray, quality_ok: bool) -> tuple[float, str]:
    """Konfidenz 0..1 (keine Wahrscheinlichkeit): ohne nachgewiesene Güte immer niedrig."""
    entropy = -(probs * np.log(np.clip(probs, 1e-9, 1))).sum() / np.log(3)
    sharp = 1 - entropy
    skill = max(0.0, (validated or {}).get("bss_ci_low") or 0.0)
    score = min(1.0, 10 * skill) * 0.6 + sharp * 0.4
    if not display or not quality_ok:
        score = min(score, 0.3)
    return round(float(score), 3), ("hoch" if score >= 0.6 else "mittel" if score >= 0.35 else "niedrig")


def forecast(conninfo: str, log=print) -> dict:
    commit = code_commit()
    with connect(conninfo) as conn:
        versions = conn.execute(
            """SELECT mv.model_version_id, mv.name, mv.version, mv.horizon_code, mv.status, mv.train_end,
                      mv.is_calibrated, mv.components
               FROM ml.model_version mv WHERE mv.status IN ('champion', 'shadow') ORDER BY mv.horizon_code, mv.status""").fetchall()
        if not versions:
            raise RuntimeError("Kein freigegebenes Modell vorhanden – zuerst 'train' und 'promote' ausführen")
        panel = load_panel(conn)
        ids = dict(conn.execute("SELECT symbol, instrument_id FROM ref.instrument").fetchall())
        rel = {}
        for rid, ccy in conn.execute("SELECT relationship_id, currency FROM dep.relationship WHERE driver_key = 'risk:vix'").fetchall():
            rel[ccy] = rid
        open_issues = conn.execute(
            """SELECT count(*) FROM raw.data_quality_issue WHERE severity IN ('warning','blocking')
               AND check_name IN ('spike','stale') AND resolved_at IS NULL""").fetchone()[0]
        perf = {}
        for mid, metrics in conn.execute(
                """SELECT model_version_id, metrics FROM ml.evaluation WHERE segment_type = 'all' AND eval_type = 'walk_forward'""").fetchall():
            perf[mid] = metrics
        _, fid = _ensure_definitions(conn, commit)
        conn.commit()

    last_date = panel["date"].max()
    as_of = datetime.combine(last_date.date(), time(12, 0), NEW_YORK)
    result = {"as_of": str(last_date.date()), "written": 0, "skipped": 0}
    with connect(conninfo) as conn:
        exists = conn.execute("SELECT run_id FROM ml.forecast_run WHERE as_of = %s AND NOT is_backtest", (as_of,)).fetchone()
        if exists:
            result["skipped"] = 1
            log(f"Prognosen für {last_date.date()} existieren bereits – nichts geändert (Ledger ist unveränderlich).")
            return result
        run_id = conn.execute(
            "INSERT INTO ml.forecast_run (as_of, code_commit, is_backtest, notes) VALUES (%s, %s, false, %s) RETURNING run_id",
            (as_of, commit, "Täglicher Lauf; Kurse: FRED-Mittagskurse New York (vorläufig, bis Dukascopy verfügbar)")).fetchone()[0]
        snapshots = {}
        today_rows = panel[panel["date"] == last_date].set_index("pair")
        for pair, row in today_rows.iterrows():
            feats = {f: (None if pd.isna(row[f]) else round(float(row[f]), 6)) for f in FEATURES}
            hist = panel.loc[panel["pair"] == pair, ["date", "price"]]
            digest = hashlib.sha256(pd.util.hash_pandas_object(hist, index=False).values.tobytes()).hexdigest()
            snapshots[pair] = conn.execute(
                """INSERT INTO feat.feature_snapshot (feature_set_id, instrument_id, as_of, features, input_hash)
                   VALUES (%s, %s, %s, %s, %s) RETURNING snapshot_id""",
                (fid, ids[pair], as_of, json.dumps({**feats, "sigma_daily": float(row["sigma"]), "price": float(row["price"])}),
                 digest)).fetchone()[0]

        for horizon in HORIZONS:
            h = HORIZONS[horizon]
            hv = [v for v in versions if v[3] == horizon]
            if not hv:
                continue
            train_end = pd.Timestamp(hv[0][5])
            frozen = panel.copy()
            # eingefrorener Trainingsstand: nur Beobachtungen, deren Ergebnis bis train_end bekannt war
            mask_unknown = frozen[f"target_date_{horizon}"] > train_end
            frozen.loc[mask_unknown, [f"y_{horizon}", f"cls_{horizon}"]] = np.nan
            champ = next((v for v in hv if v[4] == "champion"), hv[0])
            use_ret = "ridge" in json.dumps(champ[7])
            preds = engine.live_forecast(frozen, horizon, champ[1], use_ret, models=tuple(v[1] for v in hv))
            target = (last_date + pd.offsets.BDay(h)).date()
            for mid, name, ver, _, status, _, calibrated, _ in hv:
                for _, r in preds.iterrows():
                    probs = np.array([r[f"{name}_p_bear"], r[f"{name}_p_neutral"], r[f"{name}_p_bull"]])
                    probs = probs / probs.sum()
                    direction = int(np.sign(probs[2] - probs[0])) if abs(probs[2] - probs[0]) > 0.02 else 0
                    conf, label = _confidence(perf.get(mid), bool(calibrated), probs, open_issues == 0)
                    band = NEUTRAL_K * r["sigma"] * np.sqrt(h)
                    quant = {f"q{int(q * 100):02d}": round(float(r[f"q{int(q * 100):02d}"]), 6) for q in engine.QUANTILES}
                    regime = vix_regime(pd.Series([r["vix_level"]])).iloc[0]
                    fid_row = conn.execute(
                        """INSERT INTO ml.forecast (run_id, model_version_id, instrument_id, horizon_code, snapshot_id,
                               reference_price, target_date, p_bull, p_neutral, p_bear, expected_direction, expected_vol,
                               quantiles, uncertainty, is_display_calibrated, neutral_band, top_drivers, invalidation_rules,
                               is_shadow, expected_return, expected_range_high, expected_range_low, confidence,
                               confidence_label, perf_snapshot)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING forecast_id""",
                        (run_id, mid, ids[r["pair"]], horizon, snapshots[r["pair"]], float(r["price"]), target,
                         float(probs[2]), float(probs[1]), float(probs[0]), direction, float(r["sigma"] * np.sqrt(h)),
                         json.dumps(quant), float(-(probs * np.log(np.clip(probs, 1e-9, 1))).sum() / np.log(3)),
                         bool(calibrated), json.dumps({"lower": -float(band), "upper": float(band), "k": NEUTRAL_K}),
                         json.dumps([{"feature": f, "label": FEATURE_LABELS_DE[f], "contribution": round(c, 4)}
                                     for f, c in r["contrib"]]),
                         json.dumps(_invalidation(r, h)),
                         status != "champion", float(r["ret_pred"]),
                         None if h == 1 else float(r["hi_pred"]), None if h == 1 else float(r["lo_pred"]),
                         conf, label, json.dumps({"validation": perf.get(mid), "regime": regime,
                                                  "model": name, "version": ver}))).fetchone()[0]
                    if status == "champion":
                        for rank, (f, c) in enumerate(r["contrib"], start=1):
                            ccy_rel = None
                            if f in VIX_RELATED:
                                ccy_rel = rel.get(r["pair"][:3]) or rel.get(r["pair"][3:])
                            conn.execute(
                                """INSERT INTO ml.forecast_driver (forecast_id, rank, feature_key, relationship_id,
                                       contribution, explanation_de) VALUES (%s, %s, %s, %s, %s, %s)""",
                                (fid_row, rank, f, ccy_rel, round(c, 5), _explain(f, c, r)))
                    result["written"] += 1
        conn.commit()
    log(f"{result['written']} Prognosen für {result['as_of']} gespeichert.")
    return result


def _invalidation(r, h) -> list[dict]:
    s = float(r["sigma"] * np.sqrt(h))
    return [
        {"rule": "kursbewegung", "text_de": f"Kurs bewegt sich mehr als {1.5 * s * 100:.2f} % gegen die erwartete Richtung".replace(".", ","),
         "threshold_log": 1.5 * s},
        {"rule": "risikostimmung", "text_de": "VIX steigt über 30 (Wechsel in ein Stress-Regime)", "vix_above": 30},
        {"rule": "zentralbank", "text_de": "Außerplanmäßige Zinsentscheidung einer der beiden Zentralbanken"},
    ]


def _explain(feature: str, contribution: float, r) -> str:
    direction = "stützt" if contribution > 0 else "belastet"
    label = FEATURE_LABELS_DE[feature]
    pair = f"{r['pair'][:3]}/{r['pair'][3:]}"
    value = r[feature]
    return f"{label} (Wert {value:+.2f}) {direction} {pair} in diesem Modell."


# --------------------------------------------------------------------------- evaluate

def evaluate_due(conninfo: str, log=print) -> int:
    """Vergleicht fällige Live-Prognosen mit dem tatsächlichen Kurs (erster Kurs am oder nach dem Zieldatum)."""
    with connect(conninfo) as conn:
        due = conn.execute(
            """SELECT f.forecast_id, i.symbol, r.as_of, f.target_date, f.reference_price::float8, f.p_bull, f.p_neutral,
                      f.p_bear, f.expected_return, f.quantiles, f.neutral_band, f.perf_snapshot
               FROM ml.forecast f JOIN ml.forecast_run r USING (run_id) JOIN ref.instrument i USING (instrument_id)
               LEFT JOIN ml.forecast_outcome o USING (forecast_id)
               WHERE o.forecast_id IS NULL AND NOT r.is_backtest""").fetchall()
        if not due:
            return 0
        closes = load_closes(conn, PRICE_SOURCES)
        n = 0
        for fid, sym, as_of, target, ref, pb, pn, pr, er, q, band, snap in due:
            s = closes[sym].dropna()
            after = s[s.index >= target]
            if after.empty:
                continue
            realized = float(after.iloc[0])
            path = s[(s.index > as_of.date()) & (s.index <= after.index[0])]
            y = float(np.log(realized / ref))
            cls = 1 if y > band["upper"] else -1 if y < band["lower"] else 0
            probs = np.array([pr, pn, pb])
            onehot = np.array([cls == -1, cls == 0, cls == 1], dtype=float)
            qs = {float(k[1:]) / 100: v for k, v in q.items()}
            pinball = float(np.mean([max(t * (y - v), (t - 1) * (y - v)) for t, v in qs.items()]))
            hi = float(np.log(path.max() / ref)) if len(path) else None
            lo = float(np.log(path.min() / ref)) if len(path) else None
            conn.execute(
                """INSERT INTO ml.forecast_outcome (forecast_id, realized_price, realized_return, realized_class, brier,
                       log_loss, direction_hit, regime_at_forecast, realized_range_high, realized_range_low, return_error,
                       pinball_loss, crps, in_interval_80, in_interval_90)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (fid, realized, y, cls, float(((probs - onehot) ** 2).sum()),
                 float(-np.log(max(1e-6, probs[[-1, 0, 1].index(cls)]))),
                 None if pb == pr or y == 0 else bool(np.sign(pb - pr) == np.sign(y)),
                 (snap or {}).get("regime"), None if hi is None else max(hi, 0.0), None if lo is None else min(lo, 0.0),
                 y - (er or 0.0), pinball, 2 * pinball, q["q10"] <= y <= q["q90"], q["q05"] <= y <= q["q95"]))
            n += 1
        conn.commit()
    log(f"{n} Prognosen ausgewertet.")
    return n
