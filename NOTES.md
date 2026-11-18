# Übergabe-Notiz – WorlᗡDriver / FOREX NEXUS AI

Stand: 18.11.2026 · Website: https://claude.ai/artifact/HbAihgkuZ3q8qsu7xAWUBj (privat, Version 8) · Branch `claude/charming-volta-yvgpff` (enthält alles aus `claude/forex-nexus-ai-platform-6ez50s`)
· Arbeitsregeln: `CLAUDE.md`

## Ziel
- Fundamentales Trading-Tool nur für USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD und ihre 28 Paare.
- Nutzer-Wunsch 18.11.2026: je Paar viele **geprüfte** Signale (Arbeitslosenquote, Zinserwartung,
  Spekulation …) → Punkte-System „x von y Signalen long = z %“, Tag- und Wochenansicht. Alles Unnötige weg.
  Nutzen vor Design; leicht verständlich.
- Nutzer: Deutsch, keine Programmierkenntnisse, iPhone/iPad.

## Fertig
- Signal-Modul `forex_nexus/signals/`: 43 Signale (`library.py`), Daten point-in-time (`data.py`),
  Prüfung Entdeckung 1999–2012 (BH 10 %) → Bestätigung 2013–2019 (t > 1) → Schlusstest ab 2020 je
  Signal × Währung, Tag + Woche, 0,03 % Kosten (`validate.py`), Bericht + Datenstand (`report.py`).
  Befehl `python -m forex_nexus signals`, Bericht `reports/signals/README.md`.
- **Ergebnis: 0 von 344 Kombinationen bestehen (Tag und Woche).** Fundamental-Abstimmung (25 Signale,
  ungeprüft) traf seit 2020 in 50,8 % (Tag) / 50,9 % (Woche). Wird offen so angezeigt. Details:
  `docs/12_signal_abstimmung.md` (inkl. offengelegter Design-Iterationen).
- Neu: Arbeitslosenquoten aller 8 Währungsräume (Migration 0007; Eurozone von der EZB, Quelle `ECB_SERIES`).
- Entfernt (mit Beleg in docs/12): logreg, LightGBM, Ridge-Rendite, Einflussfaktoren, Konfluenz, Saison-Screener,
  Dependency-Engine + Wissensbasis, 11 Website-Ansichten, 7 ungenutzte Datenreihen (Migration 0008: `ref.series.active`).
- Engine: nur noch `climatology` + `volref` + Spannen (80-%-Intervall trifft 80 %). 168 Prognosen je Lauf.
- Website (`site/template.html`, eine Datei): Übersicht (Abstimmung je Paar), Paar-Seite (Signale einzeln mit
  Schlusstest-Ergebnis, Spanne, Termine, Kurs), Signal-Prüfung, Kalender, Rechner, Datenstand. Mobil geprüft.
- 78 Tests grün. Migration 0009 legt VIX- und Rohstoffreihen an (früher durch die gelöschte Wissensbasis).

## Gerade in Arbeit / nächster Schritt
- BIS angebunden (Migration 0010): Verbraucherpreise GB/JP/CH/CA/AU/NZ und offizielle Leitzinsen der 6 Notenbanken.
  Alle Datenreihen aktuell; Prüfung weiterhin 0 von 344 (Tag/Woche).
- Nächste Kandidaten für Signalkraft: 2-J.-Renditen, Konsens-Überraschungen (Ist vs. Erwartung), Dukascopy Hoch/Tief.

## Offen / bekannte Probleme
- **Kein dauerhafter Betrieb:** Cloud-DB temporär (`/var/tmp/fnxw`, Port 5495, DB `fnx_check`; Neuaufbau:
  initdb + `migrate` + `ingest-fx` + `ingest-fred-series` + `ingest-cot` + `ingest-calendar` + `train` +
  `promote` + `forecast` + `build-site`).
- Kurse = FRED-Mittagskurse (wöchentlich aktualisiert); Dukascopy nur vom eigenen Server.
- Spannen-Modelle vom Nutzer bestätigt (Freigaben 4–6, 18.11.2026).
- A+-Regel-Engine: wartet auf die 6 Kriterien des Nutzers.
- Die geplante tägliche Aufgabe (`trig_017cgKCoLFTF76c2subGa5aC`) ist an die alte Sitzung gebunden.

## Wichtige Dateien
- `db/migrations/000X_*.sql` – Schema; nie ändern, nur neue Datei anlegen.
- `forex_nexus/__main__.py` – CLI (`daily` = alles).
- `forex_nexus/signals/` – Signale, Prüfung, Abstimmung, Bericht.
- `forex_nexus/models/`, `forex_nexus/ledger/pipeline.py` – Spannen-Prognose, Ledger, train/promote/forecast/evaluate.
- `forex_nexus/ingestion/` – FRED, EZB, CFTC, Kalender, Dukascopy.
- `forex_nexus/reports/site_export.py` – Daten → `site/index.html` aus `site/template.html`.
- `tests/` – pytest; `conftest.py` startet temporäres PostgreSQL 16.

## Regeln und Entscheidungen
- Siehe `CLAUDE.md`. Kurz: keine Zukunftsdaten; Prüfregeln nie nachträglich zugunsten der Ergebnisse ändern;
  Ledger unveränderlich; Migrationen nur ergänzen; `site/index.html` und `data/` nie committen; nie auf `main` pushen.
