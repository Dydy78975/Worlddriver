"""Kommandozeile:  python -m forex_nexus migrate | status | ingest-fx | check-fx | report-fx [Ordner] | load-knowledge | download-dukascopy [Startjahr] | ingest-dukascopy | ingest-fred-series | train | promote <Version> <Horizont> <Modell> <Name> <Begründung> | forecast | evaluate | validate-dependencies | build-site | daily | ingest-cot | ingest-calendar | crypto-site [--offline]"""

import sys

from forex_nexus.config import database_url
from forex_nexus.db import connect
from forex_nexus.db.migrate import migrate


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    url = database_url() if cmd not in ("download-dukascopy", "crypto-site") else None
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
    if cmd == "train":
        from pathlib import Path

        from forex_nexus.ledger.pipeline import train
        s = train(url, Path(argv[2] if len(argv) > 2 else "data/train"))
        print(f"Version {s['version']}: " + ", ".join(
            f"{h}: Empfehlung {v['champion_recommendation']}" for h, v in s["horizons"].items()))
        return 0
    if cmd == "promote":
        from forex_nexus.ledger.pipeline import promote
        pid = promote(url, argv[2], argv[3], argv[4], argv[5], " ".join(argv[6:]))
        print(f"Freigabe {pid} gespeichert: {argv[4]} {argv[3]} ({argv[2]}) durch {argv[5]}")
        return 0
    if cmd == "forecast":
        from forex_nexus.ledger.pipeline import forecast
        forecast(url)
        return 0
    if cmd == "evaluate":
        from forex_nexus.ledger.pipeline import evaluate_due
        evaluate_due(url)
        return 0
    if cmd == "ingest-cot":
        from forex_nexus.ingestion.cot import ingest
        print(ingest(url))
        return 0
    if cmd == "ingest-calendar":
        from forex_nexus.ingestion.calendar import ingest
        print(ingest(url))
        return 0
    if cmd == "daily":
        # Kompletter Tagesablauf: Daten laden, prüfen, prognostizieren, auswerten, Website bauen
        from datetime import date
        from pathlib import Path

        from forex_nexus.ingestion.fred_series import ingest as ingest_series
        from forex_nexus.ingestion.fx_daily import ingest_all
        from forex_nexus.ledger.pipeline import evaluate_due, forecast
        from forex_nexus.quality.fx_checks import run_checks
        from forex_nexus.reports.fx_overview import plot_pairs, write_markdown
        from forex_nexus.reports.site_export import build
        for r in ingest_all(url):
            print(f"{r['source']}: {r['inserted']} neue Kurse")
        print(f"Makro/Rohstoffe: {len(ingest_series(url))} Reihen aktualisiert")
        from forex_nexus.ingestion import calendar as cal, cot
        print(f"COT: {cot.ingest(url)}")
        print(f"Kalender: {cal.ingest(url)}")
        result = run_checks(url, date.today())
        print(f"Qualitätsprüfung: {result['new_in_db']} neue Befunde")
        out = Path("reports/phase1")
        out.mkdir(parents=True, exist_ok=True)
        plot_pairs(result["fred"], out / "kurse_28_paare.png")
        write_markdown(result, out / "README.md", "kurse_28_paare.png", date.today())
        forecast(url)
        evaluate_due(url)
        print(f"Website: {build(url)}")
        return 0
    if cmd == "crypto-site":
        from forex_nexus.crypto.site import build as build_crypto
        print(f"Krypto-Website geschrieben: {build_crypto(refresh='--offline' not in argv)}")
        return 0
    if cmd == "build-site":
        from forex_nexus.reports.site_export import build
        print(f"Website geschrieben: {build(url)}")
        return 0
    if cmd == "validate-dependencies":
        from forex_nexus.dependencies.validation import run
        from forex_nexus.ledger.pipeline import code_commit
        for r in run(url, code_commit()):
            print(f"{r['currency']} ← {r['driver_name']}: {r['verdict']}")
        return 0
    if cmd == "ingest-fred-series":
        from forex_nexus.ingestion.fred_series import ingest
        for r in ingest(url):
            print(f"{r['series']}: {r['values']} Werte, letzter {r['last']}")
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
