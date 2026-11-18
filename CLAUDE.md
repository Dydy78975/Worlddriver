# Arbeitsregeln für Claude – WorlᗡDriver / FOREX NEXUS AI

Wird in jeder Sitzung automatisch geladen. Zuerst `NOTES.md` lesen (Übergabe-Notiz, aktueller Stand).

## Grundsätze (angelehnt an die Karpathy-Leitlinien, github.com/forrestchang/andrej-karpathy-skills)

1. **Erst denken, dann programmieren.** Annahmen ausdrücklich nennen. Gibt es mehrere Deutungen, sie
   kurz aufzeigen statt still eine zu wählen. Gibt es einen einfacheren Weg, ihn vorschlagen.
2. **Einfachheit zuerst.** So wenig Code wie möglich. Keine Funktionen, Schalter oder Abstraktionen,
   die niemand verlangt hat. Wenn 200 Zeilen auch 50 sein könnten: neu schreiben.
3. **Gezielte Änderungen.** Nur anfassen, was die Aufgabe verlangt; bestehenden Stil beibehalten.
   Was durch die eigene Änderung verwaist, entfernen. Fremden toten Code melden oder – wenn der Nutzer
   es verlangt hat (wie am 18.11.2026: „jede unnötige Zeile weg“) – mit Begründung entfernen.
4. **Zielgerichtet arbeiten.** Vorher festlegen, woran Erfolg erkennbar ist (meist ein Test), dann so
   lange arbeiten, bis es nachgewiesen ist. Ergebnisse nie schönreden.

## Fachliche Regeln (nicht verhandelbar)

* **Keine Zukunftsdaten.** Jeder Wert zählt erst ab `available_at`. Entscheidungszeitpunkt = 12:00 New York
  (FRED-Kurs). COT ab Freitag 15:30 New York, VIX vom Vortag, Saison nur aus Vorjahren.
* **Ehrlichkeit vor Ergebnis.** Regeln, Schwellen und Tests werden nie geändert, damit Ergebnisse besser
  aussehen. Wird eine Prüfregel geändert, steht das mit Grund in `docs/12_signal_abstimmung.md`.
* **Signale:** Nur Signale, die Entdeckung (BH-Korrektur) und Bestätigung bestehen, gehen in die geprüfte
  Abstimmung. Der Schlusstest (ab 2020) wird für keine Auswahl benutzt.
* **Ledger ist unveränderlich** (DB-Trigger). Neue Modelle nur über `train` + `promote` mit Namen.
* **Migrationen** (`db/migrations/`) nie ändern, nur neue Datei anlegen (Prüfsummenschutz).
* **Öffentliches Repo:** `site/index.html` und Dukascopy-Daten (`data/`) nicht committen.
* Abrufe mit ehrlicher Programmkennung, nie als Browser tarnen.

## Nutzer und Sprache

* Deutsch, keine Programmierkenntnisse, nutzt iPhone/iPad. Alles verständlich erklären, deutsches Zahlenformat.
* Nutzen vor Design. Die App muss ohne Vorwissen verständlich sein.

## Technik

* Python 3.12+, PostgreSQL 16, psycopg 3, pandas, scikit-learn, statsmodels. Website: eine HTML-Datei,
  Vanilla JS, keine Frameworks.
* Tests: `python -m pytest -q` (startet ein temporäres PostgreSQL). Vor jedem Commit grün.
* Arbeitsdatenbank in der Cloud (temporär): siehe `NOTES.md`.
* Git: nie auf `main` pushen; PRs nur auf Wunsch.
