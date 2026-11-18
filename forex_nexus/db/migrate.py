"""Einfacher, nachvollziehbarer Migrations-Mechanismus.

Jede Datei in db/migrations/ (z. B. 0001_initial.sql) wird genau einmal
eingespielt und mit Prüfsumme in fnx_meta.schema_migration vermerkt.
Wird eine bereits eingespielte Datei nachträglich verändert, bricht der
Vorgang ab – so bleibt die Datenbankgeschichte überprüfbar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from forex_nexus.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    files = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    migrations = [Migration(f.name.split("_", 1)[0], f) for f in files]
    versions = [m.version for m in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationError(f"Doppelte Migrationsnummern in {directory}")
    return migrations


_META_SQL = """
CREATE SCHEMA IF NOT EXISTS fnx_meta;
CREATE TABLE IF NOT EXISTS fnx_meta.schema_migration (
    version     TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def migrate(conninfo: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Spielt alle fehlenden Migrationen ein. Gibt die neu eingespielten Versionen zurück."""
    applied_now: list[str] = []
    with connect(conninfo, autocommit=False) as conn:
        conn.execute(_META_SQL)
        conn.execute("LOCK TABLE fnx_meta.schema_migration IN EXCLUSIVE MODE")
        done = dict(conn.execute("SELECT version, checksum FROM fnx_meta.schema_migration").fetchall())
        for m in discover(directory):
            if m.version in done:
                if done[m.version] != m.checksum:
                    raise MigrationError(
                        f"Migration {m.path.name} wurde nach dem Einspielen verändert. "
                        "Änderungen bitte als neue Migrationsdatei anlegen."
                    )
                continue
            conn.execute(m.sql)
            conn.execute(
                "INSERT INTO fnx_meta.schema_migration (version, filename, checksum) VALUES (%s, %s, %s)",
                (m.version, m.path.name, m.checksum),
            )
            applied_now.append(m.version)
        conn.commit()
    return applied_now
