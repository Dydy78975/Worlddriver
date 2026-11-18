"""Wissensbasis (knowledge/relationships.yaml) prüfen und in die Datenbank laden.

Regeln:
* Neue Beziehungen starten immer als 'hypothesis'.
* Der Status wird hier NIE hochgestuft. Ändert sich das erwartete Vorzeichen einer bereits
  geprüften Beziehung, wird sie auf 'testing' zurückgesetzt.
* Beziehungen werden nie gelöscht; fehlt eine in der Datei, wird das nur gemeldet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from forex_nexus.db import connect
from forex_nexus.fx.crosses import MAJORS

KNOWLEDGE_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "relationships.yaml"
CATEGORIES = {"energy", "metals", "agriculture", "dairy", "precious", "industry", "risk", "rates", "trade", "geopolitics"}


class KnowledgeError(ValueError):
    pass


@dataclass
class LoadResult:
    version: str
    drivers: int
    new_relationships: int
    updated_relationships: int
    reset_to_testing: list[str]
    missing_in_file: list[str]


def read_and_validate(path: Path = KNOWLEDGE_FILE) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = []
    if not data.get("version"):
        errors.append("version fehlt")
    drivers = data.get("drivers") or {}
    for key, d in drivers.items():
        if ":" not in key:
            errors.append(f"Treiber {key}: Schlüssel muss 'kategorie:name' sein")
        if d.get("category") not in CATEGORIES:
            errors.append(f"Treiber {key}: unbekannte Kategorie {d.get('category')}")
        if not d.get("name"):
            errors.append(f"Treiber {key}: name fehlt")
        if "fred" in d:
            f = d["fred"]
            if f.get("frequency") not in ("D", "W", "M") or not f.get("series") or f.get("publication_lag_days") is None:
                errors.append(f"Treiber {key}: fred braucht series, frequency (D/W/M), publication_lag_days")
    seen = set()
    for i, r in enumerate(data.get("relationships") or []):
        tag = f"Beziehung {i + 1} ({r.get('currency')} / {r.get('driver')})"
        if r.get("currency") not in MAJORS:
            errors.append(f"{tag}: Währung muss eine der 8 Hauptwährungen sein")
        if r.get("driver") not in drivers:
            errors.append(f"{tag}: Treiber nicht definiert")
        if r.get("expected_sign") not in (1, -1, None):
            errors.append(f"{tag}: expected_sign muss 1, -1 oder null sein")
        if not r.get("mechanism"):
            errors.append(f"{tag}: mechanism fehlt")
        chain = r.get("causal_chain")
        if not isinstance(chain, list) or not chain or not all(isinstance(s, str) and s for s in chain):
            errors.append(f"{tag}: causal_chain muss eine nicht-leere Liste von Sätzen sein")
        key = (r.get("currency"), r.get("driver"))
        if key in seen:
            errors.append(f"{tag}: doppelt")
        seen.add(key)
    if errors:
        raise KnowledgeError("Wissensbasis ungültig:\n- " + "\n- ".join(errors))
    return data


def load(conninfo: str, path: Path = KNOWLEDGE_FILE) -> LoadResult:
    data = read_and_validate(path)
    version = str(data["version"])
    new = updated = 0
    reset: list[str] = []
    with connect(conninfo) as conn:
        src = conn.execute("SELECT source_id FROM ref.data_source WHERE name = 'FRED_COMMODITY'").fetchone()[0]
        for key, d in data["drivers"].items():
            series_id = None
            if "fred" in d:
                f = d["fred"]
                series_id = conn.execute(
                    """INSERT INTO ref.series (source_id, source_code, category, frequency, publication_lag, description)
                       VALUES (%s, %s, %s, %s, make_interval(days => %s), %s)
                       ON CONFLICT (source_id, source_code) DO UPDATE
                         SET frequency = EXCLUDED.frequency, publication_lag = EXCLUDED.publication_lag,
                             description = EXCLUDED.description
                       RETURNING series_id""",
                    (src, f["series"], d["category"], f["frequency"], f["publication_lag_days"], d["name"])).fetchone()[0]
            conn.execute(
                """INSERT INTO dep.driver (driver_key, name_de, category, price_series_id, data_status, notes_de)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (driver_key) DO UPDATE SET name_de = EXCLUDED.name_de, category = EXCLUDED.category,
                     price_series_id = EXCLUDED.price_series_id, data_status = EXCLUDED.data_status, notes_de = EXCLUDED.notes_de""",
                (key, d["name"], d["category"], series_id, "available" if series_id else "missing", d.get("notes")))

        existing = {(c, k): (rid, sign, status) for rid, c, k, sign, status in conn.execute(
            "SELECT relationship_id, currency, driver_key, expected_sign, status FROM dep.relationship").fetchall()}
        in_file = set()
        for r in data["relationships"]:
            key = (r["currency"], r["driver"])
            in_file.add(key)
            values = (r["mechanism"], json.dumps(r["causal_chain"], ensure_ascii=False), r.get("conditions"), version)
            if key not in existing:
                rid = conn.execute(
                    """INSERT INTO dep.relationship (currency, driver_key, origin, expected_sign, mechanism_de,
                           causal_chain, conditions_de, knowledge_version)
                       VALUES (%s, %s, 'expert', %s, %s, %s, %s, %s) RETURNING relationship_id""",
                    (r["currency"], r["driver"], r.get("expected_sign"), *values)).fetchone()[0]
                conn.execute(
                    """INSERT INTO dep.relationship_status_log (relationship_id, old_status, new_status, reason_de, decided_by)
                       VALUES (%s, NULL, 'hypothesis', %s, 'system')""",
                    (rid, f"Aus Wissensbasis {version} übernommen"))
                new += 1
                continue
            rid, old_sign, status = existing[key]
            conn.execute(
                """UPDATE dep.relationship SET mechanism_de = %s, causal_chain = %s, conditions_de = %s,
                       knowledge_version = %s, expected_sign = %s WHERE relationship_id = %s""",
                (*values, r.get("expected_sign"), rid))
            updated += 1
            if old_sign != r.get("expected_sign") and status not in ("hypothesis", "testing", "rejected"):
                conn.execute(
                    """INSERT INTO dep.relationship_status_log (relationship_id, old_status, new_status, reason_de, decided_by)
                       VALUES (%s, %s, 'testing', %s, 'system')""",
                    (rid, status, f"Erwartetes Vorzeichen in Wissensbasis {version} geändert – erneute Prüfung nötig"))
                reset.append(f"{key[0]}/{key[1]}")
        conn.commit()
    missing = [f"{c}/{k}" for (c, k) in existing if (c, k) not in in_file]
    return LoadResult(version, len(data["drivers"]), new, updated, reset, missing)
