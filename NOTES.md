# Übergabe-Notiz – WorlᗡDriver / FOREX NEXUS AI

Stand: 18.11.2026 · Website: https://claude.ai/artifact/HbAihgkuZ3q8qsu7xAWUBj (privat, Version 8) · Branch `claude/charming-volta-yvgpff` (enthält alles aus `claude/forex-nexus-ai-platform-6ez50s`)
· Arbeitsregeln: `CLAUDE.md`

## Ziel
- Fundamentales Trading-Tool nur für USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD und ihre 28 Paare.
- Nutzer-Wunsch 18.11.2026: je Paar viele **geprüfte** Signale (Arbeitslosenquote, Zinserwartung,
  Spekulation …) → Punkte-System „x von y Signalen long = z %“, Tag- und Wochenansicht. Alles Unnötige weg.
  Nutzen vor Design; leicht verständlich.
- Nutzer: Deutsch, keine Programmierkenntnisse, iPhone/iPad.

## Fertig (Stand 19.11.2026)
- **Modelle je Währung** (`forex_nexus/signals/`): 443 Modelle, 50–68 je Währung, aus Leitzins, Renditen 10 J. und 2 J.,
  Zinserwartung, Inflation, Arbeitsmarkt, COT, Saison, Risikostimmung, Kursverlauf und eigenen Treibern
  (NZD Milch/Fleisch/Wolle/Holz, AUD Erze/Kohle/LNG/Agrar, CAD Öl/Gas/Holz/Metalle, Importeure Energie negativ,
  sichere Häfen VIX, Risiko-Treiber Italien-Aufschlag/Kreditaufschlag/Finanzstress). Gemessen an der Währungsstärke gegen die anderen 7; Tag, Woche, Monat.
- **Kombi-Modell je Währung** (logistische Regression): Bestätigung (Training ≤ 2012, Prüfung 2013–2019),
  Schlusstest (Training ≤ 2019, eingefroren, Prüfung ab 2020), Trefferquote je Sicherheitsstufe mit 95-%-Bereich.
- **Ergebnis:** 0 Einzelmodelle bestehen; Kombi bestätigt nur CHF/Woche (58 % / 56 %, mit Risiko-Treibern). 70 % werden nicht verlässlich
  erreicht. Details: `docs/12_signal_abstimmung.md`, `reports/signals/README.md`.
- Datenquellen: FRED, EZB, BIS (Inflation, Leitzinsen), CFTC, Forex Factory, neu 2-J.-Renditen von EZB, Bank of Canada,
  RBA, Finanzministerium Japan, Bank of England (5 J.; drosselt stark, braucht Pausen). Alle Reihen aktuell, jede
  speist Modelle. Netzwerk-Umgebung „worlddriver“ um die Notenbank-Hosts erweitert.
- Website (Artifact, Version 9): Übersicht Währungen + Paare, Seite je Währung (Kombi, Aussagekraft, alle Modelle),
  Paar, Prüfung, Kalender, Rechner, Datenstand. Unbestätigte Einschätzungen grau markiert.
- Spannen-Prognose (Ledger) unverändert; Modelle vom Nutzer bestätigt. 83 Tests grün.
- Bug-Prüfung alle 30 Min. per CronCreate (geht bei Neustart des Workers verloren → neu anlegen).

## Offen / bekannte Probleme
- Bank of England 5-J.-Rendite läuft (eine Anfrage; Kennung ohne „python“, sonst Sperre).
- CHF und NZD ohne 2-J.-Rendite (SNB-Reihen enden 07/2025, RBNZ sperrt Abrufe); Global Dairy Trade ohne freie Schnittstelle.
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
