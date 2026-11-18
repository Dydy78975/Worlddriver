"""Ergebnis der Signal-Prüfung: kompakte Daten für die Website, lesbarer Bericht und Datenstand-Prüfung."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from forex_nexus.signals.data import COMMODITY_DRIVERS, MAX_DAYS_SINCE_RELEASE
from forex_nexus.signals.library import BY_KEY, FUNDAMENTAL_VOTE, SIGNALS
from forex_nexus.signals.validate import HORIZONS, PERIODS

# Welche Datenreihe speist welche Signale (für die Prüfung „hat jeder Datensatz einen Nutzen?“)
USES = {
    "short_rate": ["carry", "rate_chg_3m", "rate_chg_6m", "rate_chg_12m", "curve", "real_rate"],
    "yield_10y": ["y10", "y10_chg_1m", "y10_chg_3m", "curve"],
    "cpi_index": ["infl_hawk", "infl_ppp", "infl_chg_3m", "real_rate"],
    "unemployment": ["unemp", "unemp_chg_3m", "unemp_chg_6m", "unemp_chg_12m"],
    "risk": ["risk_vix_chg", "risk_vix_level"],
}
PERIOD_LABEL = {"entdeckung": "Entdeckung 1999–2012", "bestaetigung": "Bestätigung 2013–2019", "schlusstest": "Schlusstest ab 2020"}


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def _cell(st: dict) -> list:
    """[Rendite p. a., t-Wert, Trefferquote] – kompakt für die Website."""
    return [_r(st["annual"], 4), _r(st["t"], 2), _r(st["hit"], 3)]


def site_payload(res: dict) -> dict:
    out = {"rules": {"periods": {k: list(v) for k, v in PERIODS.items()}, "cost": res["rules"]["cost"],
                     "fdr": res["rules"]["fdr"], "confirm_t": res["rules"]["confirm_t"],
                     "tests": res["rules"]["tests_per_horizon"]},
           "signals": [{"key": s.key, "family": s.family, "label": s.label, "idea": s.idea,
                        "fundamental": s.key in FUNDAMENTAL_VOTE} for s in SIGNALS],
           "horizons": {}}
    for h, H in res["horizons"].items():
        stats = {k: {"panel": {p: _cell(v["panel"][p]) for p in PERIODS},
                     "ccy": {c: {**{p: _cell(st[p]) for p in PERIODS}, "valid": st["gueltig"]}
                             for c, st in v["currencies"].items()}}
                 for k, v in H["signals"].items()}
        out["horizons"][h] = {
            "label": HORIZONS[h], "valid": [list(u) for u in H["valid"]], "stats": stats,
            "checked": _vote_out(H["checked"]), "fundamental": _vote_out(H["fundamental"]),
        }
    return out


def _vote_out(v: dict) -> dict:
    cur = v["current"]
    return {"date": cur["date"], "test": v["test"],
            "pairs": {p: {k: (_r(x, 3) if k == "share_bull" else x) for k, x in d.items() if k != "signals"}
                      | {"votes": {s["signal"]: s["vote"] for s in d["signals"]}} for p, d in cur["pairs"].items()}}


def data_audit(conn, now: datetime | None = None) -> list[dict]:
    """Jede Datenreihe: Stand, Alter, ob aktuell, und wofür sie gebraucht wird."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        """SELECT d.name, s.source_code, s.category, s.currency, s.frequency, s.description, max(o.period_date),
                  max(o.available_at)
           FROM ref.series s JOIN ref.data_source d USING (source_id) LEFT JOIN raw.observation o USING (series_id)
           WHERE s.active GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY s.category, s.currency NULLS LAST, s.source_code""").fetchall()
    commodity_codes = {c for codes in COMMODITY_DRIVERS.values() for c in codes}
    out = []
    for src, code, cat, ccy, freq, descr, last, released in rows:
        uses = USES.get(cat, [])
        if code == "VIXCLS":
            uses = USES["risk"]
        elif code in commodity_codes:
            uses = ["commodity_1m", "commodity_3m"]
        age = None if released is None else (now - released).days
        fresh = released is not None and age <= MAX_DAYS_SINCE_RELEASE.get(freq, 76)
        out.append({"source": src, "code": code, "category": cat, "currency": ccy, "frequency": freq,
                    "description": descr, "last": None if last is None else str(last), "days_since_release": age,
                    "fresh": fresh, "used_by": uses})
    return out


def write_markdown(res: dict, audit: list[dict], path: Path) -> None:
    lines = [f"# Signal-Prüfung – Stand {datetime.now(timezone.utc):%d.%m.%Y}", "",
             "Automatisch erzeugt von `python -m forex_nexus signals`. Regeln: siehe "
             "[docs/12_signal_abstimmung.md](../../docs/12_signal_abstimmung.md).", ""]
    for h, H in res["horizons"].items():
        lines += [f"## {HORIZONS[h]} ({h})", "",
                  f"Geprüft: {len(SIGNALS)} Signale × 8 Währungen = {res['rules']['tests_per_horizon']} Kombinationen. "
                  f"**Gültig: {len(H['valid'])}.**", ""]
        if H["valid"]:
            lines += ["Gültige Signale: " + ", ".join(f"{BY_KEY[k].label} ({c})" for k, c in H["valid"]), ""]
        lines += ["Die 10 stärksten Kombinationen in der Entdeckung und was danach aus ihnen wurde "
                  "(Rendite pro Jahr nach Kosten, t-Wert):", "",
                  "| Signal | Währung | " + " | ".join(PERIOD_LABEL.values()) + " | gültig |", "|---|---|---|---|---|---|"]
        units = [(k, c, st) for k, v in H["signals"].items() for c, st in v["currencies"].items()
                 if st["entdeckung"]["t"] is not None]
        units.sort(key=lambda u: -u[2]["entdeckung"]["t"])
        for k, c, st in units[:10]:
            cells = [("–" if st[p]["t"] is None else f"{st[p]['annual'] * 100:+.1f} % (t {st[p]['t']:.1f})").replace(".", ",")
                     for p in PERIODS]
            lines.append(f"| {BY_KEY[k].label} | {c} | " + " | ".join(cells) + f" | {'ja' if st['gueltig'] else 'nein'} |")
        t = H["fundamental"]["test"]
        lines += ["", f"**Fundamental-Abstimmung ({len(FUNDAMENTAL_VOTE)} Signale, ungeprüft) im Schlusstest ab {t['from']}:**", "",
                  "| Stufe | Fälle | Trefferquote | 95-%-Intervall |", "|---|---|---|---|"]
        for name, b in t["buckets"].items():
            ci = "–" if not b.get("ci") else f"{b['ci'][0] * 100:.0f}–{b['ci'][1] * 100:.0f} %"
            hit = "–" if b.get("hit") is None else f"{b['hit'] * 100:.1f} %"
            lines.append(f"| {name} | {b['n']} | {hit} | {ci} |".replace(".", ","))
        hit = t["all"]["hit"]
        lines += ["", "Insgesamt: " + ("–" if hit is None else f"{hit * 100:.1f}".replace(".", ","))
                  + " % Treffer (Zufall = 50 %), Ergebnis vor Kosten.", ""]
    lines += ["## Datenstand und Nutzen", "", "| Reihe | Währung | letzter Wert | aktuell | genutzt von |", "|---|---|---|---|---|"]
    for a in audit:
        lines.append(f"| {a['description'] or a['code']} | {a['currency'] or '–'} | {a['last'] or '–'} | "
                     f"{'ja' if a['fresh'] else '**nein**'} | {', '.join(a['used_by']) or 'keine Signale'} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_and_write(conninfo: str, out_dir: Path) -> dict:
    import json

    from forex_nexus.db import connect
    from forex_nexus.signals.data import load_inputs
    from forex_nexus.signals.validate import run
    with connect(conninfo) as conn:
        inputs = load_inputs(conn)
        audit = data_audit(conn)
    res = run(inputs)
    payload = site_payload(res) | {"audit": audit}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signals.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
                                          encoding="utf-8")
    write_markdown(res, audit, out_dir / "README.md")
    return payload

