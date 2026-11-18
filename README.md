<p align="center"><img src="assets/logo.svg" alt="WorlᗡDriver" width="420"></p>

# WorlᗡDriver

**Website:** WorlᗡDriver (erstes D gespiegelt) · **Prognose-Engine:** FOREX NEXUS AI

Predictive Forex Intelligence Plattform ausschließlich für die 8 Hauptwährungen
(USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD) und ihre 28 Paare.

Kern: **Signal-Abstimmung je Paar** für Tag und Woche – 43 Signale aus Zinsen, Zinserwartung, Inflation,
Arbeitsmarkt, Positionierung (COT), Saison, Risikostimmung und Rohstoffen, jedes über 27 Jahre streng geprüft.
Dazu die erwartete Spanne (80 %) für Tag/Woche/Monat, unveränderlich gespeichert und laufend gegen die
Realität gemessen.

## Status

**18.11.2026:** Signal-Prüfung und Abstimmung je Paar, Arbeitslosenquoten aller 8 Währungsräume, schlanke
Website. Ehrliches Ergebnis: noch kein Signal besteht die Prüfung – siehe
[Signal-Abstimmung](docs/12_signal_abstimmung.md) und [aktueller Prüfbericht](reports/signals/README.md).
Details: [Stand und Bedienung](docs/10_stand_und_bedienung.md).

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
10. [Stand der Software und Bedienung](docs/10_stand_und_bedienung.md)
12. [Signal-Abstimmung und Aufräumen](docs/12_signal_abstimmung.md)

(09 Dependency Engine und 11 Fundamentale Wochenansicht wurden am 18.11.2026 entfernt, Begründung in 12.)

Die Website wird mit `python -m forex_nexus daily` erzeugt (`site/index.html`, nicht im Repository, da sie Kalenderdaten zur persönlichen Nutzung enthält).

## Grundsätze

* Keine Zukunftsdaten: Jeder Datenpunkt trägt den Zeitpunkt seiner Veröffentlichung.
* Prognosen sind unveränderlich (von der Datenbank erzwungen).
* Jedes Modell und jedes Signal muss einfache Referenzen schlagen – sonst fliegt es raus.
* Wahrscheinlichkeiten werden nur angezeigt, wenn sie nachweislich kalibriert sind.
* Neue Modelle nur nach Out-of-Sample-Test, Schattenbetrieb und manueller Freigabe.
* Statistische Prognose und A+-Trading-Setup sind strikt getrennt.

Hinweis: Persönliches Analysewerkzeug, keine Anlageberatung.
