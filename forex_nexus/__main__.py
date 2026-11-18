"""Kommandozeile:  python -m forex_nexus migrate | status"""

import sys

from forex_nexus.config import database_url
from forex_nexus.db import connect
from forex_nexus.db.migrate import migrate


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    url = database_url()
    if cmd == "migrate":
        applied = migrate(url)
        print("Eingespielt:", ", ".join(applied) if applied else "nichts – Datenbank ist aktuell")
        return 0
    if cmd == "status":
        with connect(url) as conn:
            exists = conn.execute("SELECT to_regclass('fnx_meta.schema_migration')").fetchone()[0]
            if exists is None:
                print("Datenbank ist noch leer. Bitte zuerst: python -m forex_nexus migrate")
                return 1
            rows = conn.execute(
                "SELECT version, filename, applied_at FROM fnx_meta.schema_migration ORDER BY version"
            ).fetchall()
            pairs = conn.execute("SELECT count(*) FROM ref.instrument").fetchone()[0]
        for v, f, t in rows:
            print(f"Migration {v}: {f} ({t:%Y-%m-%d %H:%M})")
        print(f"Währungspaare in der Datenbank: {pairs}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
