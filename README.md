# FOREX NEXUS AI (Arbeitstitel)

Predictive Forex Intelligence Plattform für die 8 Hauptwährungen
(USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD) und ihre 28 Paare.

Prognosehorizonte: 1 Woche · 1 Monat · 3 Monate.
Jede Prognose wird unveränderlich gespeichert und nach Ablauf des Horizonts
gegen die tatsächliche Entwicklung gemessen.

## Status

**Phase 0 (Fundament) abgeschlossen.** Planung freigegeben am 18.11.2026.

→ [Anleitung für dich (iPhone)](docs/ANLEITUNG.md)

Planungsdokumente:

1. [Technische Machbarkeit](docs/01_machbarkeit.md)
2. [Datenquellen und Kosten](docs/02_datenquellen_und_kosten.md)
3. [Technische Architektur](docs/03_architektur.md)
4. [Datenbankstruktur](docs/04_datenbank.md) – Schema: [`db/migrations/0001_initial.sql`](db/migrations/0001_initial.sql)
5. [Prognose- und Validierungsmethodik](docs/05_ml_methodik.md)
6. [Entwicklungsplan](docs/06_entwicklungsplan.md)

## Grundsätze

* Keine Zukunftsdaten: Jeder Datenpunkt trägt den Zeitpunkt seiner Veröffentlichung.
* Prognosen sind unveränderlich (von der Datenbank erzwungen).
* Jedes Modell muss einfache Referenzprognosen schlagen.
* Wahrscheinlichkeiten werden nur angezeigt, wenn sie nachweislich kalibriert sind.
* Neue Modelle nur nach Out-of-Sample-Test, Schattenbetrieb und manueller Freigabe.
* Statistische Prognose und A+-Trading-Setup sind strikt getrennt.

Hinweis: Persönliches Analysewerkzeug, keine Anlageberatung.
