<p align="center"><img src="assets/logo.svg" alt="WorlᗡDriver" width="420"></p>

# WorlᗡDriver

**Website:** WorlᗡDriver (erstes D gespiegelt) · **Prognose-Engine:** FOREX NEXUS AI

Predictive Forex Intelligence Plattform ausschließlich für die 8 Hauptwährungen
(USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD) und ihre 28 Paare.

Prognosehorizonte: **täglich · wöchentlich · monatlich** – je ein eigenes, validiertes Modell.
Jede Prognose wird unveränderlich gespeichert und nach Ablauf des Horizonts
gegen die tatsächliche Entwicklung gemessen.

## Status

**Erste lauffähige Version (18.11.2026):** Prognose-Engine für Tag/Woche/Monat, unveränderliches Ledger,
Forecast-Tracker, Dependency Engine und Website. Details: [Stand und Bedienung](docs/10_stand_und_bedienung.md).

→ [Ergebnis Phase 1: Kursdiagramme und Datenqualität](reports/phase1/README.md)

→ [Anleitung für dich (iPhone)](docs/ANLEITUNG.md)

Planungsdokumente:

1. [Technische Machbarkeit](docs/01_machbarkeit.md)
2. [Datenquellen und Kosten](docs/02_datenquellen_und_kosten.md)
3. [Technische Architektur](docs/03_architektur.md)
4. [Datenbankstruktur](docs/04_datenbank.md) – Schema: [`db/migrations/0001_initial.sql`](db/migrations/0001_initial.sql)
5. [Prognose- und Validierungsmethodik](docs/05_ml_methodik.md)
6. [Entwicklungsplan](docs/06_entwicklungsplan.md)
7. [Ergebnisse Phase 1a](docs/07_phase1_ergebnisse.md)
8. [Quantitative Forecasting Engine](docs/08_quantitative_forecasting.md)
9. [Global Economic Dependency Engine](docs/09_dependency_engine.md)
10. [Stand der Software und Bedienung](docs/10_stand_und_bedienung.md)
11. [Fundamentale Wochenansicht: Cockpit, Paare, Kalender, COT, Saisonalität](docs/11_fundamentale_wochenansicht.md)

Die Website wird mit `python -m forex_nexus daily` erzeugt (`site/index.html`, nicht im Repository, da sie Kalenderdaten zur persönlichen Nutzung enthält).

Weitere Dokumente: – Wissensbasis: [`knowledge/relationships.yaml`](knowledge/relationships.yaml)

## Grundsätze

* Keine Zukunftsdaten: Jeder Datenpunkt trägt den Zeitpunkt seiner Veröffentlichung.
* Prognosen sind unveränderlich (von der Datenbank erzwungen).
* Jedes Modell muss einfache Referenzprognosen schlagen.
* Wahrscheinlichkeiten werden nur angezeigt, wenn sie nachweislich kalibriert sind.
* Neue Modelle nur nach Out-of-Sample-Test, Schattenbetrieb und manueller Freigabe.
* Statistische Prognose und A+-Trading-Setup sind strikt getrennt.

Hinweis: Persönliches Analysewerkzeug, keine Anlageberatung.
