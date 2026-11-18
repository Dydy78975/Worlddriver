# 04 – Datenbankstruktur

Stand: 18.11.2026 · Das vollständige, lauffähige Schema steht in [`db/migrations/0001_initial.sql`](../db/migrations/0001_initial.sql)
(getestet mit PostgreSQL 16: legt alle Tabellen und die 28 Paare an; Änderungs- und
Löschversuche am Prognose-Ledger werden von der Datenbank abgewiesen).

## Die Datenbank in einfachen Worten

Stell dir die Datenbank als sieben Aktenschränke vor:

| Schrank (Schema) | Inhalt | Darf geändert werden? |
|---|---|---|
| `ref` – Stammdaten | 8 Währungen, 28 Paare, Datenquellen, Zeitreihen-Beschreibungen, Zentralbank-Termine | ja (selten) |
| `raw` – Rohdaten | Kurse und Wirtschaftsdaten, genau wie geliefert, mit Zeitpunkt der Veröffentlichung | nur ergänzen |
| `feat` – Merkmale | daraus berechnete Kennzahlen je Paar und Tag | nur ergänzen |
| `ml` – Prognosen | Modelle, Prognose-Ledger, Ergebnisse, Auswertungen, Freigaben | Ledger: **nie** |
| `analysis` – Analysen | Marktregime, historische Analogien, Makro-Beziehungen | nur ergänzen |
| `report` – Berichte | Wochenberichte | nur ergänzen |
| `setup` – A+-Engine | deine 6 Regeln und deren Prüfergebnisse | getrennt von allem anderen |

## Die drei wichtigsten Konstruktionsideen

### 1. Zwei Zeitstempel für jeden Datenpunkt (bitemporal)

Tabelle `raw.observation`:

| series | period_date | available_at | value |
|---|---|---|---|
| US-CPI | 2026-09-01 | 2026-10-15 14:30 | 2,9 |
| US-CPI | 2026-09-01 | 2026-11-13 14:30 | 3,0 *(Revision)* |

Eine Prognose vom 20.10.2026 sieht nur **2,9**. Eine Prognose vom 20.11.2026 sieht **3,0**.
Die Funktion `raw.observations_as_of(serie, zeitpunkt)` liefert genau diesen Stand.
Damit ist Look-ahead Bias auf Datenbankebene ausgeschlossen, sofern alle Features
über diese Funktion lesen – das sichern wir mit automatischen Tests ab.

Wenn eine Quelle keine historischen Datenstände hat, wird `available_at` aus dem
Veröffentlichungsabstand geschätzt und `is_estimated_availability = TRUE` gesetzt.
So bleibt sichtbar, wo das System schätzen musste.

### 2. Unveränderliches Prognose-Ledger

`ml.forecast_run`, `ml.forecast`, `feat.feature_snapshot` und `ml.forecast_outcome` sind
durch Trigger geschützt. Jede Prognose speichert:

* Zeitpunkt und Datenstand (`as_of`), Modellversion, Git-Commit des Codes,
* Verweis auf den exakten Merkmals-Snapshot inklusive Prüfsumme der Rohdaten,
* Wahrscheinlichkeiten bullisch/neutral/bärisch (Summe = 1, von der DB geprüft),
* ob die Wahrscheinlichkeiten **angezeigt** werden dürfen (`is_display_calibrated`),
* Richtung, erwartete Volatilität, Quantile, Unsicherheit,
* wichtigste Einflussfaktoren und Ungültigkeitsbedingungen.

Ungültig gewordene Prognosen werden nicht geändert, sondern in
`ml.forecast_invalidation` vermerkt. Backtest-Prognosen und Live-Prognosen sind über
`forecast_run.is_backtest` strikt getrennt – die echte Erfolgsbilanz besteht nur aus Live-Prognosen.

### 3. Kontrollierter Lernprozess

* `ml.model_version.status`: `candidate → shadow → champion → retired` (oder `rejected`).
* `ml.evaluation` speichert Kennzahlen getrennt nach Art (Walk-Forward, Out-of-Sample,
  Schatten, Live) und Segment (Währung, Paar, Horizont, Regime).
* `ml.model_promotion` dokumentiert jede Freigabe mit Testergebnissen,
  Begründung und **wer** entschieden hat. Es gibt keinen automatischen Wechsel.

## Tabellenübersicht

```
ref.currency ──< ref.instrument (28 Paare)
ref.data_source ──< ref.series ──< raw.observation (bitemporal)
ref.instrument ──< raw.fx_daily
raw.ingestion_run, raw.data_quality_issue, ref.event

feat.feature_set ──< feat.feature_snapshot
ml.horizon, ml.label_definition ──< ml.model_version
ml.forecast_run ──< ml.forecast >── feat.feature_snapshot
ml.forecast ──1:1── ml.forecast_outcome
ml.forecast ──< ml.forecast_invalidation
ml.model_version ──< ml.evaluation ──< ml.model_promotion

analysis.regime · analysis.analog_query ──< analysis.analog_result · analysis.relationship
report.weekly_report
setup.rule_definition ──< setup.rule_check >── setup.evaluation_run  →  View setup.a_plus_setup
```

## A+-Setups

Die View `setup.a_plus_setup` liefert nur Prüfläufe, bei denen **genau sechs Regeln
geprüft und alle bestanden** wurden. Fehlt eine Prüfung oder schlägt eine fehl,
erscheint kein Setup. Die A+-Tabellen haben keine Verbindung zu `ml.forecast`;
falls eines deiner Kriterien die Prognose nutzt, wird das als Beleg (`evidence`)
in der jeweiligen Regelprüfung festgehalten.

## Offene Punkte

* Speicherung von Intraday-Kursen (falls deine A+-Kriterien sie brauchen).
* Genaue Struktur der 6 A+-Regeln – folgt, sobald du sie beschreibst.
* Die Struktur wird über neue Migrationsdateien (`0002_…sql`) weiterentwickelt.
  `0001_initial.sql` wird nie mehr verändert – das prüft ein automatischer Test.
