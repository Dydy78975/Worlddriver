# 03 – Technische Architektur

Stand: 18.11.2026 · Status: Entwurf zur Freigabe

## Leitprinzipien

1. **Reproduzierbarkeit:** Jede Prognose lässt sich später exakt nachrechnen –
   gleiche Daten, gleicher Code, gleiche Modellversion.
2. **Point-in-Time:** Das System kennt zu jedem Zeitpunkt nur, was damals öffentlich war.
3. **Unveränderliches Prognose-Ledger:** Gespeicherte Prognosen werden nie geändert
   oder gelöscht. Die Datenbank verhindert das technisch.
4. **Kontrolliertes Lernen:** Neue Modelle laufen erst im Schattenbetrieb und werden
   nur nach bestandenem Test und deiner Freigabe übernommen.
5. **Strikte Trennung:** Statistische Prognose ≠ Trading-Setup.
6. **Klein anfangen, sauber erweitern:** Jeder Baustein ist ein eigenes Modul mit Tests.

## Überblick

```
 ┌──────────────────────── DATENQUELLEN ────────────────────────┐
 │ FRED/ALFRED · EZB · BIS · CFTC · Dukascopy · Zentralbanken     │
 └──────────────────────────────┬────────────────────────────────┘
                                │ (1) Ingestion: täglich, mit available_at
                                ▼
 ┌──────────────── PostgreSQL – ROHDATEN (bitemporal) ───────────┐
 │ Kurse · Zinsen · Renditen · Inflation · COT · VIX · Termine    │
 └──────────────────────────────┬────────────────────────────────┘
                                │ (2) Datenqualitäts-Prüfungen
                                ▼
 ┌──────────── FEATURE-ENGINE (Point-in-Time, versioniert) ──────┐
 │ Zinsdifferenzen · Momentum · Volatilität · COT-Extreme ·      │
 │ DXY-Trend · VIX-Regime · Saisonalität · Inflationstrend        │
 └───────┬───────────────────┬────────────────────┬──────────────┘
         ▼                   ▼                    ▼
 ┌──────────────┐   ┌─────────────────┐   ┌───────────────────┐
 │ (3) PREDICTIVE│   │ (4) HISTORISCHE │   │ (5) MAKRO-        │
 │ ENGINE        │   │ ANALOGIE-ENGINE │   │ BEZIEHUNGS-ENGINE │
 │ Baselines,    │   │ ähnliche Lagen, │   │ rollierende       │
 │ LogReg, LGBM, │   │ bedingte        │   │ Korrelationen,    │
 │ XGBoost,      │   │ Statistik       │   │ Strukturbrüche,   │
 │ Kalibrierung  │   │                 │   │ Regime            │
 └──────┬────────┘   └────────┬────────┘   └─────────┬─────────┘
        ▼                     │                      │
 ┌──────────────────────┐     │                      │
 │ (6) PROGNOSE-LEDGER   │◄────┘                      │
 │ append-only, mit      │                            │
 │ Input-Snapshot-Hash   │                            │
 └──────┬───────────────┘                            │
        ▼ nach Ablauf des Horizonts                    │
 ┌──────────────────────┐   ┌────────────────────────┐ │
 │ (7) EVALUATION        │──►│ (8) MODELL-REGISTRY     │ │
 │ Brier, LogLoss,       │   │ Champion / Challenger / │ │
 │ Kalibrierung, je      │   │ Schatten, Freigabe nur  │ │
 │ Währung/Horizont/     │   │ nach OOS-Test           │ │
 │ Regime, Fehleranalyse │   └────────────────────────┘ │
 └──────┬───────────────┘                              │
        ▼                                              ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ (9) „WHAT CHANGED?“-WOCHENBERICHT  ·  (10) DASHBOARD          │
 └─────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────┐
 │ (11) A+-REGEL-ENGINE – eigener Bereich, liest Prognosen nur  │
 │ als eine von mehreren Eingaben, schreibt in eigene Tabellen   │
 └─────────────────────────────────────────────────────────────┘
```

## Komponenten im Detail

### (1) Ingestion
* Ein Python-Modul pro Quelle (`fred.py`, `ecb.py`, `bis.py`, `cftc.py`, …).
* Jede Abfrage wird protokolliert (`ingestion_run`): Zeitpunkt, Quelle, Anzahl Zeilen, Fehler.
* Werte werden **nie überschrieben**. Eine Revision wird als neuer Datenstand mit
  neuem `available_at` gespeichert.

### (2) Datenqualität
* Lücken, Ausreißer (z. B. Tagesbewegung > 8 Standardabweichungen), Abweichung
  zwischen zwei Kursquellen, verspätete Daten.
* Bei Fehlern: keine Prognose für das betroffene Paar, Warnung im Bericht.

### (3) Predictive Engine
* **Zielgröße:** Rendite des Paares über 5, 21 bzw. 63 Handelstage.
* **Drei Szenarien:** bullisch / neutral / bärisch. „Neutral“ = Rendite innerhalb
  ±k × erwartete Volatilität des Horizonts (k wird einmal festgelegt, z. B. 0,5,
  und versioniert). So bedeutet „neutral“ bei allen Paaren und Horizonten dasselbe.
* **Modelle:** Referenzprognosen → Logistische Regression → LightGBM → XGBoost.
* **Kalibrierung:** Isotonic oder Platt-Scaling, nur auf Out-of-Sample-Daten trainiert.
* **Ausgabe je Paar und Horizont:**
  * Wahrscheinlichkeiten der drei Szenarien (nur wenn das Modell als kalibriert gilt),
  * erwartete Richtung,
  * Unsicherheit: Spannweite (z. B. 10/50/90-%-Quantile) + Entropie der Wahrscheinlichkeiten,
  * wichtigste Einflussfaktoren (SHAP-Werte),
  * Ungültigkeitsbedingungen (siehe unten).
* **Ungültigkeitsbedingungen** werden regelbasiert erzeugt, z. B.:
  * Kurs schließt jenseits von Einstieg ± 1,5 × erwartete Horizont-Volatilität gegen die Richtung,
  * wichtigster Einflussfaktor kehrt sich um (z. B. Zinsdifferenz dreht um mehr als X bp),
  * Regimewechsel (z. B. VIX steigt über 30),
  * außerplanmäßige Zentralbank-Entscheidung.
  Wird eine Bedingung erfüllt, wird die Prognose als „invalidiert“ markiert –
  sie bleibt aber im Ledger und zählt in der Auswertung mit.

### (4) Historische Analogie-Engine
* Beschreibt die heutige Lage als Vektor (Zinsdifferenz-Trend, DXY-Trend,
  COT-Perzentil, Inflationstrend, Zinspfad-Änderung, VIX-Regime).
* Sucht vergleichbare Zeitpunkte in der Vergangenheit – **nur** mit Daten, die damals verfügbar waren.
* Zeigt: Anzahl Fälle, Verteilung der Folgerenditen, Trefferquote mit Konfidenzintervall,
  Vergleich zur unbedingten Verteilung (war die Situation überhaupt besonders?).
* Zwei Modi: Regel-Abfrage („Zinsdifferenz USA–EZ +25 bp in 4 Wochen UND COT > 90. Perzentil“)
  und Ähnlichkeitssuche (k nächste Nachbarn).

### (5) Makro-Beziehungs-Engine
* Rollierende Korrelationen und Betas (z. B. EUR/USD vs. 2J-Zinsdifferenz) über 3, 6, 12 Monate.
* Stabilitätsmaße: Schwankung der Betas, Strukturbruch-Tests (CUSUM, Chow), Vorzeichenwechsel.
* Regime-Kennzeichnung: Risikostimmung (VIX), Dollar-Trend, Zinszyklus je Zentralbank.
* Ergebnis fließt als Information in Bericht und als Merkmal (z. B. „Beziehung stabil ja/nein“) in die Modelle.

### (6) Prognose-Ledger
* Jede Prognose wird mit Zeitstempel, Modellversion, Code-Version (Git-Commit),
  Feature-Werten und einem **Prüf-Hash der Eingangsdaten** gespeichert.
* Datenbank-Trigger verbieten `UPDATE` und `DELETE`.

### (7) Evaluation
* Läuft täglich: Welche Prognosen sind fällig? → tatsächliche Rendite eintragen → Kennzahlen.
* Kennzahlen: Brier Score, Log Loss, Trefferquote, Kalibrierungskurve,
  Expected Calibration Error, Brier Skill Score gegenüber Referenzprognose.
* Aufschlüsselung: je Währung, Paar, Horizont, Regime, Modellversion.
* Fehleranalyse: Welche Situationen führen wiederholt zu Fehlern?
  (z. B. „bärische EUR-Prognosen in Risk-off-Phasen zu oft falsch“).

### (8) Modell-Registry und Freigabeprozess
```
 entwickelt ──► Walk-Forward-Backtest ──► Out-of-Sample-Test (nie zuvor genutzt)
            ──► Vergleich mit Champion (statistischer Test, z. B. Diebold-Mariano)
            ──► Schattenbetrieb (mind. 8–12 Wochen, Prognosen werden geloggt, aber nicht angezeigt)
            ──► deine Freigabe ──► Champion
```
* Jeder Schritt wird in `model_promotion` dokumentiert.
* Parameter ändern sich im Live-Betrieb nie automatisch.
* Neu-Training erfolgt in festen Zyklen (z. B. quartalsweise), nicht spontan.

### (9) Wochenbericht „What changed?“
* Vergleicht den aktuellen Snapshot mit dem der Vorwoche: Prognoseänderungen,
  Währungsstärke-Ranking, Zinsdifferenzen, COT, neue Zentralbank-Entscheidungen,
  zuletzt fällige Prognosen und warum falsche Prognosen falsch waren
  (welche Einflussfaktoren sich anders entwickelt haben).
* Fakten kommen ausschließlich aus der Datenbank. Optional formuliert ein
  Sprachmodell den Fließtext, darf aber keine Zahlen erfinden.

### (10) Dashboard
* Start: **Streamlit** (Python, schnell, ohne Web-Programmierung).
* Später bei Bedarf: FastAPI + Web-Frontend.

### (11) A+-Regel-Engine
* Deine sechs Kriterien als einzelne, testbare Regeln.
* Ein Setup erscheint **nur**, wenn alle sechs erfüllt sind; jede Regel wird mit Ergebnis protokolliert.
* Eigene Tabellen, eigene Ansicht. Die Prognose ist höchstens **eines** der Kriterien – nie das Setup selbst.

## Technologie-Auswahl

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | Python 3.12 | Standard für Datenanalyse und ML |
| Datenbank | PostgreSQL 16 | zuverlässig, kostenlos, Trigger für Unveränderlichkeit, JSON-Felder |
| Datenbank-Migrationen | Alembic | Änderungen an der Struktur nachvollziehbar |
| Datenverarbeitung | pandas, numpy | Standard |
| Statistik | statsmodels, scipy | Regressionen, Strukturbruch-Tests |
| ML | scikit-learn, LightGBM, XGBoost | wie gewünscht |
| Erklärbarkeit | SHAP | Einflussfaktoren je Prognose |
| Experiment-/Modellverwaltung | MLflow | Versionen, Metriken, Artefakte |
| Zeitsteuerung | zuerst cron, später Prefect | einfach starten |
| Tests | pytest | jede Leakage-Regel bekommt einen Test |
| Laufzeitumgebung | Docker Compose | gleiche Umgebung auf PC und Server |
| Dashboard | Streamlit | schnell sichtbare Ergebnisse |
| Versionskontrolle | Git / GitHub | jede Änderung nachvollziehbar |

## Ordnerstruktur (geplant)

```
forex_nexus/
  ingestion/       # eine Datei pro Datenquelle
  quality/         # Datenqualitäts-Prüfungen
  features/        # Point-in-Time-Feature-Berechnung
  models/          # Baselines, LogReg, LightGBM, XGBoost, Kalibrierung
  validation/      # Walk-Forward, Purging/Embargo, Metriken
  ledger/          # Prognosen schreiben, Ergebnisse auswerten
  analogs/         # historische Mustererkennung
  macro/           # Makro-Beziehungen, Regime
  registry/        # Champion/Challenger, Freigaben
  reports/         # Wochenbericht
  setups/          # A+-Regel-Engine (getrennt)
  dashboard/       # Streamlit-App
db/                # Datenbankschema und Migrationen
tests/
docs/
```
