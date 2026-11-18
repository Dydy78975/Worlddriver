"""Kommandozeile:  python -m forex_nexus migrate | status | ingest-fx | check-fx | report-fx [Ordner] | load-knowledge | download-dukascopy [Startjahr] | ingest-dukascopy"""

import sys

from forex_nexus.config import database_url
from forex_nexus.db import connect
from forex_nexus.db.migrate import migrate


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    url = database_url() if cmd != "download-dukascopy" else None
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
    if cmd == "ingest-fx":
        from forex_nexus.ingestion.fx_daily import ingest_all
        for r in ingest_all(url):
            print(f"{r['source']}: {r['rows']} Werte geliefert, {r['inserted']} neu, {r['revisions']} abweichend")
        return 0
    if cmd == "download-dukascopy":
        from datetime import date

        from forex_nexus.ingestion import dukascopy
        start = date(int(argv[2]), 1, 1) if len(argv) > 2 else dukascopy.FIRST_MONTH
        print(dukascopy.download(start=max(start, dukascopy.FIRST_MONTH), log=lambda m: print(m, flush=True)))
        return 0
    if cmd == "ingest-dukascopy":
        from forex_nexus.ingestion import dukascopy
        print(dukascopy.ingest(url))
        return 0
    if cmd == "load-knowledge":
        from forex_nexus.dependencies.knowledge import load
        r = load(url)
        print(f"Wissensbasis {r.version}: {r.drivers} Treiber, {r.new_relationships} neue und "
              f"{r.updated_relationships} aktualisierte Beziehungen")
        for x in r.reset_to_testing:
            print(f"  zurück auf 'testing' (Vorzeichen geändert): {x}")
        for x in r.missing_in_file:
            print(f"  Hinweis: {x} steht nicht mehr in der Datei (wird nicht gelöscht)")
        return 0
    if cmd in ("check-fx", "report-fx"):
        from datetime import date
        from pathlib import Path

        from forex_nexus.quality.fx_checks import run_checks
        today = date.today()
        result = run_checks(url, today)
        print(f"{len(result['findings'])} Befunde, davon {result['new_in_db']} neu gespeichert")
        if cmd == "report-fx":
            from forex_nexus.reports.fx_overview import plot_pairs, write_markdown
            out = Path(argv[2] if len(argv) > 2 else "reports/phase1")
            out.mkdir(parents=True, exist_ok=True)
            plot_pairs(result["fred"], out / "kurse_28_paare.png")
            write_markdown(result, out / "README.md", "kurse_28_paare.png", today)
            print(f"Bericht geschrieben: {out}/README.md")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
