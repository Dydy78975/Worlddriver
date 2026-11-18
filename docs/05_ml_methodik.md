# 05 – Prognose- und Validierungsmethodik

Stand: 18.11.2026 · Status: Entwurf zur Freigabe

## Zielgröße (was genau vorhergesagt wird)

* Logarithmische Rendite des Paares vom Prognosetag bis zum Ende des Horizonts
  (1W = 5, 1M = 21, 3M = 63 Handelstage), Schlusskurs 17:00 New York.
* Einteilung in drei Klassen anhand der erwarteten Volatilität σₕ des Horizonts:
  * **bullisch:** Rendite > +k · σₕ
  * **neutral:** dazwischen
  * **bärisch:** Rendite < −k · σₕ
  * Startwert k = 0,5 → historisch grob je ein Drittel pro Klasse. k wird einmal
    festgelegt und versioniert, nicht nachträglich angepasst.
* Zusätzlich: Quantilprognose der Rendite (10 %, 50 %, 90 %) für die Unsicherheitsspanne.

## Merkmale (erste Version)

Alle Merkmale werden je Paar als **Differenz Basis- minus Quotewährung** gebildet.

| Gruppe | Beispiele |
|---|---|
| Zinsen | Leitzinsdifferenz; 2J- und 10J-Renditedifferenz; deren Veränderung über 1/3/6 Monate |
| Zinspfad | Änderung der 2J-Rendite um Zentralbanksitzungen; Richtung der letzten Zinsentscheidungen |
| Inflation | CPI-Jahresrate und deren 3-Monats-Trend (Differenz) |
| Positionierung | COT-Netto-Position als Perzentil der letzten 3 Jahre; Veränderung; Extrem-Flag |
| Dollar | DXY-Trend (20/60/120 Tage), relevant für USD-Paare und als Risiko-Faktor |
| Risiko | VIX-Niveau und -Veränderung; Regime-Kennzeichen |
| Kurs | Momentum 1/3/12 Monate; realisierte Volatilität; Abstand zum 200-Tage-Mittel |
| Saisonalität | Monat, Quartalsende |

Neue Merkmale werden nur aufgenommen, wenn sie im Walk-Forward-Test einen
messbaren Beitrag leisten.

## Modelle

| Stufe | Modell | Zweck |
|---|---|---|
| 0 | **Klimatologie**: historische Klassenhäufigkeit | Mindestanforderung |
| 0 | **Random Walk / neutral** | Mindestanforderung |
| 0 | **Momentum-Regel** (3M-Trend) und **Carry-Regel** (Zinsdifferenz) | bekannte einfache Effekte |
| 1 | **Multinomiale logistische Regression** (regularisiert) | statistischer Benchmark, gut interpretierbar |
| 2 | **LightGBM** | nichtlineare Zusammenhänge |
| 2 | **XGBoost** | Vergleich zu LightGBM |
| 3 | weitere (z. B. Ensemble) | nur bei messbarem Mehrwert |

Panel-Ansatz: ein Modell je Horizont über alle 28 Paare. Zusätzlich ein Modell für
die 8 Einzelwährungen (Stärke gegenüber dem Korb) als Konsistenzprüfung.

## Validierung gegen Leakage

1. **Walk-Forward:** Training auf Daten bis Jahr t, Test auf Jahr t+1; dann Fenster
   weiterschieben. Ergebnis: eine lückenlose Reihe echter Out-of-Sample-Prognosen ab ca. 2008.
2. **Purging und Embargo:** Trainingsbeobachtungen, deren Zielzeitraum in den
   Testzeitraum hineinreicht, werden entfernt; zusätzlich Lücke = Horizontlänge.
3. **Finaler Hold-out:** Die letzten ca. 2 Jahre werden während der gesamten
   Entwicklung **nicht angesehen**. Sie werden erst für die Freigabe-Entscheidung
   geöffnet – und danach gilt ein neuer Zeitraum als Hold-out.
4. **Point-in-Time-Daten** aus der Datenbank (siehe `04_datenbank.md`).
5. **Hyperparameter** werden nur innerhalb der Trainingsfenster optimiert (verschachtelt).
6. **Automatische Tests**, z. B.: „Kein Merkmal zum Zeitpunkt T verwendet einen Wert
   mit available_at > T“, „Kalibrierung nur auf Out-of-Sample-Prognosen trainiert“.
7. **Zählung der Versuche:** Jede getestete Modellvariante wird protokolliert, damit
   ein zufälliger Glückstreffer unter vielen Versuchen erkennbar bleibt.

## Kennzahlen

| Kennzahl | Bedeutung | Gut ist |
|---|---|---|
| Brier Score (3 Klassen) | mittlerer quadratischer Fehler der Wahrscheinlichkeiten | niedriger |
| Brier Skill Score | Verbesserung gegenüber Klimatologie in % | > 0 |
| Log Loss | bestraft selbstsichere Fehlprognosen stark | niedriger |
| Trefferquote (Richtung) | Anteil richtiger Richtungen (ohne neutrale) | > 50 %, mit Konfidenzintervall |
| Kalibrierung (ECE, Kalibrierungskurve) | stimmen 60 %-Prognosen in ~60 % der Fälle? | ECE niedrig |
| Diebold-Mariano / Bootstrap | ist der Unterschied zum Vergleichsmodell statistisch belastbar? | p < 0,05 |

Jede Kennzahl wird aufgeschlüsselt nach **Währung, Paar, Horizont, Regime und Modellversion**.

## Wann gelten Wahrscheinlichkeiten als „kalibriert“?

Ein Modell darf Wahrscheinlichkeiten anzeigen, wenn **alle** Bedingungen erfüllt sind
(Schwellen sind Startwerte und werden versioniert):

* Out-of-Sample-Stichprobe ≥ 300 nicht überlappende Prognosen für diesen Horizont
  (für 3M wird dafür der Panel-Ansatz über alle Paare benötigt),
* Brier Skill Score gegenüber Klimatologie > 0 mit 95 %-Konfidenz,
* Expected Calibration Error ≤ 0,05,
* im laufenden Live-Betrieb keine deutliche Verschlechterung (Überwachung).

Sonst zeigt das System: Richtung, Unsicherheit und den Hinweis
**„Wahrscheinlichkeiten nicht ausreichend validiert“**.

## Self-Learning-Zyklus

```
täglich:      Prognosen erzeugen → Ledger
täglich:      fällige Prognosen auswerten → forecast_outcome
wöchentlich:  Kennzahlen, Fehleranalyse, Bericht
quartalsweise: Challenger trainieren → Walk-Forward → Hold-out-Test → Vergleich mit Champion
              → Schattenbetrieb (8–12 Wochen) → deine Freigabe
```

**Fehleranalyse:** Für falsche Prognosen wird geprüft, welche Einflussfaktoren sich
nach dem Prognosezeitpunkt anders entwickelt haben und ob Fehler in bestimmten
Regimen gehäuft auftreten. Diese Fehlermuster werden als `error_tags` gespeichert
und fließen als Hypothesen in den nächsten Challenger ein – geprüft, nicht automatisch.

## Historische Analogien – statistische Regeln

* Fälle, deren Zeitfenster sich überlappen, zählen nur einmal (`n_independent`).
* Unter 20 unabhängigen Fällen: Ergebnis wird als „anekdotisch“ markiert.
* Immer Vergleich mit der unbedingten Verteilung: Eine Trefferquote von 60 % ist nur
  interessant, wenn sie sich deutlich vom Normalfall unterscheidet.
