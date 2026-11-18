# Anleitung: So siehst du dir WorlᗡDriver auf GitHub an (iPhone)

Du brauchst **keine Programmierkenntnisse** und musst **nichts installieren**.
Du liest nur – programmiert wird von Claude.

## Die drei wichtigsten Links (einfach antippen)

| Was | Link |
|---|---|
| 📁 Das ganze Projekt | https://github.com/Dydy78975/Worlddriver/tree/claude/forex-nexus-ai-platform-6ez50s |
| 📊 Ergebnis Phase 1: Kursdiagramme aller 28 Paare | https://github.com/Dydy78975/Worlddriver/blob/claude/forex-nexus-ai-platform-6ez50s/reports/phase1/README.md |
| ✅ Automatische Tests (grüner Haken = alles in Ordnung) | https://github.com/Dydy78975/Worlddriver/actions |

Tipp: Speichere den ersten Link als Lesezeichen in Safari oder lege ihn auf den Home-Bildschirm
(Teilen-Symbol → „Zum Home-Bildschirm“).

## Warum sehe ich auf der Startseite fast nichts?

GitHub zeigt auf der Startseite den **Hauptzweig** („main“). Die Arbeit liegt aber in einem
**Arbeitszweig** („Branch“) mit dem Namen `claude/forex-nexus-ai-platform-6ez50s`.

Stell dir das wie einen Entwurfsordner vor: Erst wenn du sagst „übernehmen“, wird der Entwurf in
den Hauptordner kopiert. Das geschieht über einen **Pull Request**. Claude kann ihn für dich
vorbereiten; du tippst dann nur auf **„Merge pull request“** → **„Confirm merge“**.
Danach sieht man alles direkt auf der Startseite.

Ohne Pull Request kommst du so zum Arbeitszweig:
1. GitHub-App oder Safari öffnen → **Dydy78975/Worlddriver**.
2. Oben auf den Knopf mit **„main“** tippen.
3. `claude/forex-nexus-ai-platform-6ez50s` auswählen.

## Was steht wo?

| Ordner/Datei | Inhalt | Für dich interessant? |
|---|---|---|
| `README.md` | Startseite mit Logo und Übersicht | ⭐ ja |
| `docs/` | alle Erklärungen auf Deutsch (Plan, Architektur, Methoden) | ⭐ ja |
| `reports/` | automatisch erzeugte Ergebnisse mit Diagrammen | ⭐ ja |
| `reports/signals/README.md` | Prüfbericht: welche Signale funktionieren, welche Daten aktuell sind | ⭐ ja |
| `forex_nexus/` | der Programmcode | nein |
| `db/migrations/` | Aufbau der Datenbank | nein |
| `tests/` | automatische Prüfungen | nein |

Empfohlene Lesereihenfolge in `docs/`: 12 (Signal-Abstimmung) → 10 (Stand) → 06 (Plan).

## Testergebnisse verstehen

Unter **Actions** steht für jeden Upload ein Eintrag „Tests“:
* ✅ grüner Haken = alle automatischen Prüfungen bestanden
* 🟡 gelber Punkt = läuft gerade
* ❌ rotes Kreuz = etwas ist kaputt → schreib es einfach Claude

## Wichtig: Das Projekt ist öffentlich

Dein Repository ist **öffentlich** – jeder im Internet kann Code, Dokumente und Berichte lesen.
Kursdaten von Dukascopy werden deshalb bewusst **nicht** dort gespeichert.

Wenn du das Projekt privat machen möchtest:
GitHub in Safari öffnen → Repository → **Settings** → ganz unten **Danger Zone** →
**Change visibility** → **Make private**. Die automatischen Tests funktionieren dann weiterhin
(GitHub erlaubt privaten Projekten kostenlos 2.000 Testminuten pro Monat – mehr als genug).

## Was die Tests aktuell prüfen (65 Tests)

* Die Datenbank enthält genau 8 Währungen und 28 Paare in Marktschreibweise.
* **Keine Zukunftsdaten:** Wird ein Wirtschaftswert später korrigiert, sieht eine ältere
  Prognose weiterhin nur den damals bekannten Wert.
* **Unveränderliches Ledger:** Gespeicherte Prognosen und Ergebnisse lassen sich weder ändern noch löschen.
* Eine Tagesprognose kann nur von einem Tagesmodell stammen (nicht aus der Monatsprognose abgeleitet).
* Der Forecast-Tracker zeigt die Veränderung zur vorherigen Prognose und die Güte je Monat.
* Wahrscheinlichkeiten ergeben zusammen 100 %; Handelsspannen und Konfidenz sind plausibel.
* Wirtschaftsbeziehungen starten als Hypothese; nur du kannst sie als „validiert“ freigeben,
  und nur mit bestandenem Test.
* Kreuzkurse sind korrekt und in sich stimmig (z. B. EUR/JPY = EUR/USD × USD/JPY).
* Gespeicherte Kurse werden nie überschrieben; Hoch/Tief müssen zu Eröffnung und Schluss passen.
* Tageskerzen enden um 17:00 New York – auch bei Sommer-/Winterzeitumstellung.
* Datenfehler (Spikes) werden von echten Marktereignissen unterschieden.
* Ein A+-Setup erscheint nur, wenn alle 6 Regeln geprüft **und** bestanden sind.

## Technische Befehle (nur zur Information – richtet Claude ein)

```
python -m forex_nexus migrate              # Datenbank auf den neuesten Stand bringen
python -m forex_nexus ingest-fx            # Kurse FRED + EZB laden
python -m forex_nexus download-dukascopy   # Dukascopy-Stundenkerzen laden (langsam)
python -m forex_nexus ingest-dukascopy     # daraus Tageskerzen 17:00 New York bilden
python -m forex_nexus report-fx            # Bericht mit Diagrammen erzeugen
python -m forex_nexus load-knowledge       # Wissensbasis laden
pytest                                      # alle Tests ausführen
```
