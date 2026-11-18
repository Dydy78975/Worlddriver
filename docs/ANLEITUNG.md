# Anleitung: So arbeitest du mit dem Projekt (iPhone)

Du brauchst **keinen Computer** und musst **nichts installieren**.

## So ist es aufgebaut

| Wo | Was passiert dort |
|---|---|
| **Claude-App (iPhone)** | Du sagst, was als Nächstes passieren soll. Claude programmiert und testet in einer Cloud-Umgebung. |
| **GitHub (App oder Safari)** | Hier liegt das Projekt dauerhaft: Code, Dokumente, Testergebnisse. |
| **Später: kleiner Server** (ab Phase 4) | Läuft Tag und Nacht, sammelt Daten, erstellt täglich Prognosen. Das Dashboard öffnest du im iPhone-Browser. |

Dein alter Mac wird nicht benötigt.

## Fortschritt prüfen

**Aktuelle Ergebnisse:** Datei `reports/phase1/README.md` – dort siehst du alle 28 Kursdiagramme.

1. GitHub-App öffnen → Repository **Worlddriver**.
2. Branch `claude/forex-nexus-ai-platform-6ez50s` auswählen.
3. **Dokumente lesen:** Ordner `docs/` – alle Dateien sind auf Deutsch.
4. **Tests ansehen:** Reiter **Actions** → Lauf „Tests“.
   * ✅ grüner Haken = alle automatischen Prüfungen bestanden
   * ❌ rotes Kreuz = etwas ist kaputt → sag es mir einfach in der Claude-App

## Was die Tests aktuell prüfen (54 Tests)

* Die Datenbank enthält genau 8 Währungen und 28 Paare in Marktschreibweise.
* Die drei Horizonte 1 Woche / 1 Monat / 3 Monate sind angelegt.
* **Keine Zukunftsdaten:** Wird ein Wirtschaftswert später korrigiert, sieht eine
  ältere Prognose weiterhin nur den damals bekannten Wert.
* **Unveränderliches Ledger:** Gespeicherte Prognosen und Ergebnisse lassen sich
  weder ändern noch löschen.
* Wahrscheinlichkeiten müssen zusammen 100 % ergeben.
* Ein A+-Setup erscheint nur, wenn alle 6 Regeln geprüft **und** bestanden sind.
* Einmal eingespielte Datenbank-Änderungen dürfen nicht nachträglich verändert werden.
* Kreuzkurse werden korrekt berechnet (z. B. EUR/JPY = EUR/USD × USD/JPY) und sind in sich stimmig.
* Gespeicherte Kurse werden nie überschrieben; geänderte Neulieferungen werden gemeldet.
* Die Qualitätsprüfungen erkennen Lücken, Datenfehler (Spikes) und echte Marktereignisse.
* Eine Tagesprognose kann nur von einem Tagesmodell stammen (nicht aus der Monatsprognose abgeleitet).
* Der Forecast-Tracker zeigt die Veränderung zur vorherigen Prognose und die Güte je Monat.
* Wirtschaftsbeziehungen starten als Hypothese; nur du kannst sie als „validiert“ freigeben,
  und nur mit bestandenem Test. Änderungen am erwarteten Vorzeichen setzen die Prüfung zurück.

## Für später (nur zur Information)

Technische Befehle auf dem Server – richtet Claude ein, du musst sie nicht kennen:

```
python -m forex_nexus migrate   # Datenbank auf den neuesten Stand bringen
python -m forex_nexus status    # Zustand anzeigen
pytest                           # alle Tests ausführen
```
