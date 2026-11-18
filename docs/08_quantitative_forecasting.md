# 08 – Quantitative Forecasting Engine

> **Stand 18.11.2026:** Die Richtungsmodelle (logistische Regression, LightGBM) und das Renditemodell wurden nach dem Walk-Forward-Test entfernt – sie schlugen die einfachen Referenzen nicht. In Betrieb sind Referenz, Schwankungs-Referenz und die Spannen-Prognose. Richtungssignale prüft jetzt die Signal-Abstimmung: [12_signal_abstimmung.md](12_signal_abstimmung.md).

Stand: 18.11.2026 · Status: Architektur festgelegt, Datenbank umgesetzt (Migration 0003), Modelle folgen

Gilt ausschließlich für die 8 Hauptwährungen **USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD**
und ihre 28 Paare.

## 1. Horizonte – drei unabhängige Modelle

| Code | Horizont | Zielgröße | Eigenes Modell |
|---|---|---|---|
| `1D` | täglich | Log-Rendite vom Schluss heute bis Schluss nächster Handelstag | ja |
| `1W` | wöchentlich | Log-Rendite über 5 Handelstage | ja |
| `1M` | monatlich | Log-Rendite über 20 Handelstage | ja |
| `3M` | Quartal | 63 Handelstage – angelegt, aber **inaktiv** | später |

**Schlusskurs:** 17:00 New York (Marktstandard). **Prognosezeitpunkt:** kurz nach 17:00 New York.

**Die Datenbank erzwingt, dass jeder Horizont ein eigenes Modell hat:** Eine Prognose mit
Horizont `1D` kann technisch nur von einem Modell gespeichert werden, das für `1D` trainiert
wurde (Fremdschlüssel `forecast_model_horizon_fk`). Eine Tagesprognose kann also nicht aus der
Monatsprognose abgeleitet werden. Ein Test prüft das.

## 2. Ergebnisse je Prognose

| Anforderung | Umsetzung | Datenbankfeld |
|---|---|---|
| Erwartete Kursveränderung in % | Erwartungswert der Rendite (geschrumpft, siehe 4.2) | `expected_return` |
| Erwartete Richtung | Bullish / Neutral / Bearish aus den Wahrscheinlichkeiten | `expected_direction` |
| Wahrscheinlichkeitsverteilung | P(steigt), P(seitwärts), P(fällt) | `p_bull`, `p_neutral`, `p_bear` |
| Erwartete Handelsspanne | erwartetes Hoch und Tief bis zum Horizont | `expected_range_high`, `expected_range_low` |
| Prognoseintervall | Quantile 5 %…95 % der Rendite | `quantiles` |
| Wichtigste Einflussfaktoren | SHAP-Beiträge, verknüpft mit Wirtschaftsbeziehungen | `ml.forecast_driver` |
| Vergleich mit vorheriger Prognose | automatisch berechnet | Sicht `ml.v_forecast_tracker` |
| Konfidenz | 0–1 + niedrig/mittel/hoch (siehe 5) | `confidence`, `confidence_label` |
| Historische Modellperformance | Gütewerte, wie sie zum Prognosezeitpunkt bekannt waren | `perf_snapshot` |

**Seitwärts (neutral)** heißt: Die Rendite bleibt innerhalb von ±k · σₕ, wobei σₕ die
erwartete Volatilität des Horizonts ist (Startwert k = 0,5). „Seitwärts“ bedeutet damit für ein
ruhiges Paar wie EUR/CHF etwas anderes als für ein schwankendes wie GBP/JPY.

## 3. Ehrliche Erwartung je Horizont

| Horizont | Was gut vorhersagbar ist | Was kaum vorhersagbar ist |
|---|---|---|
| Täglich | **Schwankungsbreite und Handelsspanne** (Volatilität ist stark vorhersagbar) | Richtung: nahe Zufall; 51–52 % Trefferquote wäre schon gut |
| Wöchentlich | Volatilität, Spanne; schwache Effekte aus Zinsdifferenz, Momentum, Risikostimmung | genaue Rendite |
| Monatlich | Richtung etwas besser (Carry, Momentum, Makro, Rohstoffe) | genaue Rendite |

Darum ist die wertvollste Tagesinformation meist die **erwartete Spanne**, nicht die Richtung.
Das System zeigt das offen an.

## 4. Modellaufbau je Horizont

Jedes Horizont-Modell besteht aus vier Komponenten, beschrieben in `ml.model_version.components`.

### 4.1 Volatilität und Handelsspanne
* Referenz: Volatilität der letzten 60 Tage.
* Modelle: EWMA, GARCH(1,1), HAR-Modell auf Basis von Hoch/Tief/Schluss (Parkinson- bzw.
  Garman-Klass-Schätzer), LightGBM mit Kalender und Ereignissen (Zentralbanktermine, Inflationsdaten).
* Spanne: erwartete maximale Auf- und Abwärtsbewegung bis zum Horizont, über Quantilmodelle geschätzt.
* **Voraussetzung:** tägliche Hoch/Tief-Kurse mit Schluss 17:00 New York → Phase 1b (Dukascopy).

### 4.2 Erwartete Rendite
* Referenz: **0 %** (Random Walk) – die schwer zu schlagende Messlatte.
* Modelle: Ridge-Regression, LightGBM, XGBoost.
* **Schrumpfung:** Die Modellschätzung wird mit der nachgewiesenen Out-of-Sample-Güte gewichtet.
  Ist das Out-of-Sample-R² ≤ 0, wird die erwartete Rendite auf 0 gesetzt und als
  „keine verlässliche Renditeprognose“ gekennzeichnet. Das verhindert scheinbar präzise Zahlen ohne Aussagekraft.

### 4.3 Richtungswahrscheinlichkeiten
* Referenz: historische Häufigkeiten (Klimatologie).
* Modelle: multinomiale logistische Regression (Benchmark), LightGBM, XGBoost.
* Kalibrierung (Isotonic / Platt) nur auf Out-of-Sample-Prognosen.
* Angezeigt werden die Wahrscheinlichkeiten nur, wenn die Kriterien aus `05_ml_methodik.md` erfüllt sind.

### 4.4 Prognoseintervall
* Quantil-Modelle (LightGBM-Quantile) plus **konforme Kalibrierung** im Walk-Forward:
  Das 80-%-Intervall wird so angepasst, dass es historisch tatsächlich in ca. 80 % der Fälle traf.

### 4.5 Konsistenzprüfungen vor dem Speichern
* Wahrscheinlichkeiten summieren sich zu 1 (Datenbank prüft).
* Median und erwartete Richtung widersprechen sich nicht grob.
* Spanne hoch ≥ 0 ≥ Spanne tief (Datenbank prüft).
* Paarprognosen sind untereinander stimmig (z. B. EUR/USD, USD/JPY → EUR/JPY); grobe Widersprüche werden markiert.

## 5. Konfidenz

Die Konfidenz ist **keine Wahrscheinlichkeit**, sondern eine Einstufung aus vier Teilen:

1. **Nachgewiesene Güte** für dieses Paar, diesen Horizont und das aktuelle Regime
   (untere Grenze des Konfidenzintervalls des Brier Skill Score).
2. **Schärfe** der aktuellen Prognose (wie deutlich weichen die Wahrscheinlichkeiten von der Gleichverteilung ab).
3. **Datenqualität** (offene Befunde aus der Qualitätsprüfung senken die Konfidenz).
4. **Neuheit der Lage** (wie ungewöhnlich die aktuelle Situation verglichen mit den Trainingsdaten ist).

Ohne nachgewiesene Güte ist die Konfidenz immer „niedrig“, egal wie deutlich das Modell ist.

## 6. Speicherung und Point-in-Time

* Jede Prognose wird mit Zeitstempel, Modellversion, Git-Commit, Merkmals-Snapshot und
  Prüfsumme der Eingangsdaten unveränderlich gespeichert (siehe `04_datenbank.md`).
* `perf_snapshot` hält fest, welche Modellgüte **zum Prognosezeitpunkt** bekannt war.
  Spätere Auswertungen verändern diese Angabe nicht.
* Täglicher Ablauf (Zeiten New York):

| Zeit | Schritt |
|---|---|
| 17:05 | Schlusskurse laden, Qualitätsprüfung |
| 17:15 | Merkmale berechnen (nur Daten mit `available_at` ≤ jetzt) |
| 17:30 | Prognosen aller drei Horizonte → Ledger |
| 17:45 | fällige Prognosen auswerten → `forecast_outcome` |

## 7. Auswertung nach Ablauf des Horizonts

| Bereich | Kennzahlen |
|---|---|
| Rendite | Fehler (tatsächlich − erwartet), MAE, RMSE, Out-of-Sample-R² gegenüber 0 % |
| Richtung | Trefferquote mit Konfidenzintervall, Brier Score, Log Loss, Brier Skill Score |
| Verteilung | Pinball-Loss (Quantile), CRPS, Trefferquote der 80-/90-%-Intervalle (Kupiec-Test) |
| Spanne | Abweichung erwartetes vs. tatsächliches Hoch/Tief |
| Kalibrierung | Kalibrierungskurve, Expected Calibration Error |
| Aufschlüsselung | je Währung, Paar, Horizont, Marktregime, Modellversion |
| Signifikanz | Diebold-Mariano-Test (HAC), Bootstrap; Korrektur, weil 28 Paare × 3 Horizonte getestet werden |

## 8. Forecast-Tracker – wird das System besser?

* **`ml.v_forecast_tracker`**: jede jemals erstellte Prognose mit Status (offen / ausgewertet /
  invalidiert), Ergebnis, Fehler und Veränderung gegenüber der vorherigen Prognose.
* **`ml.v_performance_monthly`**: Güte je Monat, Modell und Horizont.
* Im Wochenbericht und Dashboard:
  * Verlauf des Brier Skill Score gegenüber der Referenzprognose (gleitend über 52 Wochen) mit Konfidenzband,
  * Historie aller Modellwechsel (Champion-Wechsel),
  * eine klare Aussage: **„besser“**, **„nicht nachweisbar besser“** oder **„schlechter“**.
    „Besser“ erscheint nur bei statistisch belastbarem Unterschied.
* Backtest- und Live-Prognosen werden immer getrennt ausgewiesen. Nur Live-Prognosen zählen als echte Erfolgsbilanz.

## 9. Validierung (gilt für alle drei Horizonte getrennt)

* Walk-Forward mit wachsendem Fenster. Neu-Training: `1D`/`1W` vierteljährlich, `1M` halbjährlich.
* Purging und Embargo mindestens in Länge des Horizonts.
* Finaler Hold-out (letzte 2 Jahre) bleibt bis zur Freigabeentscheidung verschlossen.
* Hyperparameter nur innerhalb der Trainingsfenster.
* Jede getestete Variante wird protokolliert (Schutz vor Zufallstreffern durch viele Versuche).
* Freigabe: Challenger → Schattenbetrieb → manuelle Freigabe (siehe `03_architektur.md`).
