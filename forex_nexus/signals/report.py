"""Ergebnis der Prüfung: kompakte Daten für die Website, lesbarer Bericht und Datenstand-Prüfung."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from forex_nexus.fx.crosses import MAJORS
from forex_nexus.signals.data import MAX_DAYS_SINCE_RELEASE
from forex_nexus.signals.library import MACRO, MODELS
from forex_nexus.signals.validate import HORIZONS, PERIODS

PERIOD_LABEL = {"entdeckung": "Entdeckung 1999–2012", "bestaetigung": "Bestätigung 2013–2019", "schlusstest": "Schlusstest ab 2020"}
# Welche Makro-Kategorie speist welche Modelle (Prüfung „hat jede Datenreihe einen Nutzen?“)
_FACTOR_USE = {"short_rate": ("rate", "curve", "real_rate", "y2_vs_rate"), "yield_10y": ("y10", "curve"),
               "yield_2y": ("y2",), "cpi_index": ("infl", "real_rate"), "unemployment": ("unemp",)}


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def _cell(st: dict) -> list:
    """[Rendite p. a., t-Wert, Trefferquote] – kompakt für die Website."""
    return [_r(st["annual"]), _r(st["t"], 2), _r(st["hit"], 3)]


def _tab(rows: list[dict]) -> list:
    return [{k: (_r(v, 3) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]


def site_payload(res: dict) -> dict:
    out = {"rules": {"periods": {k: list(v) for k, v in PERIODS.items()}, **{k: res["rules"][k] for k in ("cost", "fdr", "confirm_t", "models")}},
           "models": [{"key": m.key, "currency": m.currency, "family": m.family, "label": m.label, "idea": m.idea} for m in MODELS],
           "horizons": {}}
    for h, H in res["horizons"].items():
        cur = {}
        for c, C in H["currencies"].items():
            cb = C["combo"]
            cur[c] = {"all": C["all"], "checked": C["checked"], "vote_test": _tab(C["vote_test"]),
                      "combo": {"p_up": _r(cb["p_up"], 3), "confirmed": cb["confirmed"], "confirm": _tab(cb["confirm"]),
                                "test": _tab(cb["test"]), "weights": cb["weights"]}}
        out["horizons"][h] = {"label": HORIZONS[h], "date": H["date"], "valid": H["valid"],
                              "stats": {k: {p: _cell(v[p]) for p in PERIODS} for k, v in H["models"].items()},
                              "currencies": cur,
                              "pairs": {p: {"all": {k: v for k, v in x["all"].items() if k != "votes"}, "p_up": _r(x["p_up"], 3)}
                                        for p, x in H["pairs"].items()}}
    return out


def data_audit(conn, now: datetime | None = None) -> list[dict]:
    """Jede aktive Datenreihe: Stand, ob aktuell, und wie viele Modelle sie speist."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute(
        """SELECT d.name, s.source_code, s.category, s.currency, s.frequency, s.description, max(o.period_date),
                  max(o.available_at)
           FROM ref.series s JOIN ref.data_source d USING (source_id) LEFT JOIN raw.observation o USING (series_id)
           WHERE s.active GROUP BY 1, 2, 3, 4, 5, 6 ORDER BY s.category, s.currency NULLS LAST, s.source_code""").fetchall()
    out = []
    for src, code, cat, ccy, freq, descr, last, released in rows:
        if cat in _FACTOR_USE:                                 # Makro: speist alle 8 Währungen (relativer Vergleich)
            names = {k for k, *_, factor, _dz, _d in MACRO if factor.split("_chg")[0] in _FACTOR_USE[cat]
                     or factor.startswith(_FACTOR_USE[cat])}
            used = sum(1 for m in MODELS if m.key.split(":")[1] in names or f"drv_{code}_" in m.key)
        elif code == "VIXCLS":
            used = sum(1 for m in MODELS if m.family == "Risikostimmung" or f"drv_{code}_" in m.key)
        else:
            used = sum(1 for m in MODELS if f"drv_{code}_" in m.key)
        age = None if released is None else (now - released).days
        out.append({"source": src, "code": code, "category": cat, "currency": ccy, "frequency": freq,
                    "description": descr, "last": None if last is None else str(last), "days_since_release": age,
                    "fresh": released is not None and age <= MAX_DAYS_SINCE_RELEASE.get(freq, 76), "models": used})
    return out


def _pct(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f} %".replace(".", ",")


def write_markdown(res: dict, audit: list[dict], path: Path) -> None:
    by = {m.key: m for m in MODELS}
    lines = [f"# Prüfung der Modelle je Währung – Stand {datetime.now(timezone.utc):%d.%m.%Y}", "",
             f"Automatisch erzeugt von `python -m forex_nexus signals`. {len(MODELS)} Modelle "
             f"({', '.join(f'{c} {sum(m.currency == c for m in MODELS)}' for c in MAJORS)}). "
             "Regeln: [docs/12_signal_abstimmung.md](../../docs/12_signal_abstimmung.md).", ""]
    for h, H in res["horizons"].items():
        lines += [f"## {HORIZONS[h]} ({h})", "", f"**Gültige Einzelmodelle: {len(H['valid'])} von {len(MODELS)}.**"
                  + (" " + ", ".join(f"{by[k].label} ({by[k].currency})" for k in H["valid"]) if H["valid"] else ""), "",
                  "Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, "
                  "Anteil dieser Fälle):", "",
                  "| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |", "|---|---|---|---|---|"]
        for c, C in H["currencies"].items():
            cb = C["combo"]

            def cell(tab):
                if not tab:
                    return "–"
                a, s = tab[0], tab[2]
                return f"{_pct(a['hit'])} / {_pct(s['hit'])} ({_pct(s['share'], 0)})"
            lines.append(f"| {c} | {cell(cb['confirm'])} | {cell(cb['test'])} | {'ja' if cb['confirmed'] else 'nein'} | {_pct(cb['p_up'], 0)} |")
        units = sorted(((k, v) for k, v in H["models"].items() if v["entdeckung"]["t"] is not None),
                       key=lambda kv: -kv[1]["entdeckung"]["t"])[:10]
        lines += ["", "Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):", "",
                  "| Modell | Währung | " + " | ".join(PERIOD_LABEL.values()) + " | gültig |", "|---|---|---|---|---|---|"]
        for k, v in units:
            cells = [("–" if v[p]["t"] is None else f"{v[p]['annual'] * 100:+.1f} % (t {v[p]['t']:.1f})").replace(".", ",") for p in PERIODS]
            lines.append(f"| {by[k].label} | {by[k].currency} | " + " | ".join(cells) + f" | {'ja' if v['gueltig'] else 'nein'} |")
        lines.append("")
    lines += ["## Datenstand und Nutzen", "", "| Reihe | Währung | letzter Wert | aktuell | speist Modelle |", "|---|---|---|---|---|"]
    for a in audit:
        lines.append(f"| {a['description'] or a['code']} | {a['currency'] or '–'} | {a['last'] or '–'} | "
                     f"{'ja' if a['fresh'] else '**nein**'} | {a['models'] or '**keine**'} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_and_write(conninfo: str, out_dir: Path) -> dict:
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

