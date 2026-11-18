# 06 – Entwicklungsplan

Stand: 18.11.2026 · Status: **freigegeben** · Phase 0 und 1a abgeschlossen

## Arbeitsweise

* Kleine Schritte. Jeder Schritt endet mit etwas, das du **selbst sehen und prüfen** kannst
  (eine Tabelle, ein Diagramm, ein Testergebnis).
* Ich erkläre vor jedem Schritt, was gebaut wird und warum, und danach, wie du es prüfst.
* Jeder Schritt wird in Git gespeichert, damit nichts verloren geht und jede Änderung nachvollziehbar ist.
* Du triffst die fachlichen Entscheidungen (z. B. Freigabe eines Modells). Ich setze technisch um.

## Wichtigster Planungsgrundsatz

Eine echte Prognose-Bilanz entsteht nur mit **Zeit**: Eine Monatsprognose kann erst nach
20 Handelstagen bewertet werden. Deshalb startet das Prognose-Ledger **so früh wie möglich**
(Phase 4) – zunächst mit einfachen Referenzmodellen für alle drei Horizonte. Die ML-Modelle kommen
später dazu. So läuft die Uhr für die Erfolgsmessung bereits, während wir weiterentwickeln.

## Phasen (aktualisiert 18.11.2026: Quantitative Forecasting + Dependency Engine)

| Phase | Inhalt | Ergebnis, das du prüfen kannst | Grobe Dauer* |
|---|---|---|---|
| ✅ **0 Fundament** | Projektstruktur, PostgreSQL, Schema, Tests | Datenbank mit 8 Währungen und 28 Paaren | erledigt |
| ✅ **1a Kursdaten FRED + EZB** | Tageskurse aller 28 Paare, Qualitätsprüfungen | Kursdiagramme, Befundliste | erledigt |
| ✅ **Architektur-Erweiterung** | Horizonte Tag/Woche/Monat, quantitative Felder, Forecast-Tracker, Dependency Engine, Wissensbasis | Dokumente 08/09, Migration 0003, 28 Hypothesen | erledigt |
| ✅ **Erste lauffähige Version** | Engine Tag/Woche/Monat (4 Modelle), Ledger, Tracker, Dependency-Tests, Website, täglicher Check | siehe `10_stand_und_bedienung.md` | erledigt 18.11.2026 |
| **1b Dukascopy** | Hoch/Tief/Schluss 17:00 New York für alle 28 Paare | **Pflicht für die Tagesprognose und die Handelsspanne** | 1–2 Wochen |
| **2 Makro- und Rohstoffdaten point-in-time** | Leitzinsen, Renditen, Inflation, COT, VIX, DXY, Zentralbank-Termine; Rohstoffe von FRED; Quellen für Milch, Gold, China | „Was wusste man am Tag X?“ – getestet | 3–5 Wochen |
| **3 Features & Validierungsrahmen** | Merkmale, Zielgrößen je Horizont, Walk-Forward mit Purging/Embargo, alle Kennzahlen | Bericht: Wie gut sind Referenzprognosen je Horizont? | 2–3 Wochen |
| **4 Prognose-Ledger live** | täglicher Lauf: Referenzmodelle für 1D/1W/1M inkl. Volatilität und Spanne; Auswertung; Server | erste echte Prognosen, Forecast-Tracker füllt sich | 1–2 Wochen |
| **5 Machine Learning** | je Horizont: Volatilität/Spanne (GARCH, HAR, LightGBM), Rendite (Ridge, LightGBM, XGBoost), Richtung (LogReg, LightGBM, XGBoost), Quantile + konforme Kalibrierung, SHAP, Konfidenz | Vergleichstabelle aller Modelle je Horizont/Währung/Regime | 4–6 Wochen |
| ✅ **Signal-Prüfung und Abstimmung** | 43 Signale × 8 Währungen, Entdeckung/Bestätigung/Schlusstest, Abstimmung je Paar; Dependency Engine entfernt (kein Vorlauf) | [12_signal_abstimmung.md](12_signal_abstimmung.md) | erledigt 18.11.2026 |
| **7 Historische Analogien & Regime** | vergleichbare Situationen ohne Zukunftsdaten; Regime-Kennzeichnung | „Was passierte mit EUR/USD, wenn …?“ | 2–3 Wochen |
| **8 Wochenbericht** | „What changed?“ inkl. Tracker („wird das System besser?“) und Wirkungsketten | erster vollständiger Wochenbericht | 1–2 Wochen |
| **9 Website WorlᗡDriver** | FastAPI + Next.js, Weltkarte, AI Predictions, Tracker, Macro Center, Historical Intelligence | alles im iPhone-Browser | 4–6 Wochen |
| **10 A+-Regel-Engine** | deine 6 Kriterien als getestete Regeln | A+-Setups nur, wenn alle 6 erfüllt sind | 1–3 Wochen |
| **11 Optimierung** | kostenpflichtige Daten prüfen (Konsens, tägliche Rohstoff-Futures, Nachrichten), Challenger-Zyklen | messbar bessere Modelle – oder der Nachweis, dass es keine gibt | laufend |

\* Grobe Kalenderdauer bei regelmäßiger gemeinsamer Arbeit. Abhängig davon, wie viel Zeit
du für Prüfen und Entscheiden hast. Phase 2 ist erfahrungsgemäß der aufwendigste Teil,
weil jede Zentralbank und jedes Statistikamt Daten anders bereitstellt.

## Meilensteine

1. **M1 – Datenbasis vertrauenswürdig** (Ende Phase 2): Alle Daten point-in-time abrufbar.
2. **M2 – Uhr läuft** (Ende Phase 4): Tägliche Live-Prognosen im unveränderlichen Ledger.
3. **M3 – Erste ehrliche Modellbewertung** (Ende Phase 5): Wissen wir, ob ML die einfachen Regeln schlägt?
4. **M4 – Volles Analysewerkzeug** (Ende Phase 9).
5. **M5 – Erste belastbare Live-Bilanz:** frühestens ca. 6–12 Monate nach M2.

## Entscheidungen, die ich von dir brauche

| Wann | Entscheidung |
|---|---|
| ~~vor Phase 0~~ | ~~Freigabe dieser Planung~~ – erledigt 18.11.2026 |
| ~~vor Phase 0~~ | ~~Wo läuft das System?~~ – Entwicklung in der Cloud, Bedienung per iPhone; ab Phase 4 kleiner Server (ca. 5–15 €/Monat) |
| vor Phase 4 | Server-Anbieter auswählen und Konto anlegen (Claude unterstützt Schritt für Schritt) |
| Phase 3 | Definition „neutral“ (Startwert k = 0,5) bestätigen |
| Phase 5 | Schwellen für „kalibriert“ bestätigen |
| vor Phase 10 | Deine sechs A+-Kriterien möglichst genau beschreiben |
| laufend | Freigabe neuer Modellversionen |

## Phase 0 – erledigt

* Python-Projekt mit Ordnerstruktur aus `03_architektur.md`
* Migrations-Mechanismus (`db/migrations/`, Prüfsummen-Schutz)
* 16 automatische Tests, laufen bei jedem Upload auf GitHub (Reiter „Actions“)
* `docker-compose.yml` für den späteren Server (noch nicht auf einem Server erprobt)
* [Anleitung für iPhone-Nutzung](ANLEITUNG.md)

## Phase 1a – erledigt (18.11.2026)

* FRED H.10: 7 Dollar-Paare ab 1971, daraus 21 Kreuzkurse → alle 28 Paare
* EZB-Referenzkurse: 7 Euro-Paare ab 1999 als unabhängige Kontrolle
* Qualitätsprüfungen: Lücken, extreme Bewegungen vs. Datenfehler-Verdacht (Spike), Quellenvergleich, Aktualität
* Kurse werden nie überschrieben; abweichende Neulieferungen werden als Befund gespeichert
* Ergebnis: [reports/phase1/README.md](../reports/phase1/README.md), Auswertung: [07_phase1_ergebnisse.md](07_phase1_ergebnisse.md)

## Nächster Schritt: Phase 1b – Dukascopy (Hoch/Tief/Schluss 17:00 New York)

Durch die neue Tagesprognose ist Phase 1b jetzt Pflicht: Ohne tägliche Hoch-/Tiefkurse gibt es
keine verlässliche Handelsspanne und keinen marktüblichen Schlusskurs.

1. Nutzungsbedingungen von Dukascopy prüfen (persönliche Nutzung).
2. Stundenkerzen aller 28 Paare laden (langsam, wegen Abrufbegrenzung), Schluss 17:00 New York bilden.
3. Vergleich mit FRED und EZB; Hauptquelle für die Modelle festlegen.

Danach Phase 2 – Makro- und Rohstoffdaten point-in-time.