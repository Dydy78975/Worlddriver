# 06 – Entwicklungsplan

Stand: 18.11.2026 · Status: **freigegeben** · Phase 0 abgeschlossen

## Arbeitsweise

* Kleine Schritte. Jeder Schritt endet mit etwas, das du **selbst sehen und prüfen** kannst
  (eine Tabelle, ein Diagramm, ein Testergebnis).
* Ich erkläre vor jedem Schritt, was gebaut wird und warum, und danach, wie du es prüfst.
* Jeder Schritt wird in Git gespeichert, damit nichts verloren geht und jede Änderung nachvollziehbar ist.
* Du triffst die fachlichen Entscheidungen (z. B. Freigabe eines Modells). Ich setze technisch um.

## Wichtigster Planungsgrundsatz

Eine echte Prognose-Bilanz entsteht nur mit **Zeit**: Eine 3-Monats-Prognose kann erst
nach 3 Monaten bewertet werden. Deshalb startet das Prognose-Ledger **so früh wie möglich**
(Phase 4) – zunächst mit einfachen Referenzmodellen. Die ML-Modelle kommen später dazu.
So läuft die Uhr für die Erfolgsmessung bereits, während wir weiterentwickeln.

## Phasen

| Phase | Inhalt | Ergebnis, das du prüfen kannst | Grobe Dauer* |
|---|---|---|---|
| **0 Fundament** | Projektstruktur, Docker, PostgreSQL, Schema einspielen, Tests einrichten | Datenbank mit 8 Währungen und 28 Paaren läuft | 1 Woche |
| **1 Kursdaten** | Tageskurse aller 28 Paare (FRED + EZB, Kreuzkurse, Dukascopy für OHLC), Qualitätsprüfungen | Diagramm jedes Paares, Liste gefundener Datenfehler | 1–2 Wochen |
| **2 Makrodaten point-in-time** | Leitzinsen (BIS), Renditen, Inflation (ALFRED/OECD), COT (CFTC), VIX, DXY-Berechnung, Zentralbank-Termine | Abfrage „Was wusste man am Tag X?“ funktioniert und ist getestet | 3–4 Wochen |
| **3 Features & Validierungsrahmen** | Feature-Engine, Zielgrößen, Walk-Forward mit Purging/Embargo, Kennzahlen, Leakage-Tests | Bericht: Wie gut sind die Referenzprognosen historisch? | 2–3 Wochen |
| **4 Prognose-Ledger live** | täglicher automatischer Lauf mit Referenzmodellen, Auswertung fälliger Prognosen, Server-Betrieb | Erste echte, unveränderliche Prognosen mit Zeitstempel | 1–2 Wochen |
| **5 Machine Learning** | Logistische Regression, LightGBM, XGBoost, Kalibrierung, SHAP, Modell-Registry, Freigabeprozess | Vergleichstabelle aller Modelle je Währung/Horizont/Regime | 3–5 Wochen |
| **6 Historische Analogien** | Regel-Abfragen und Ähnlichkeitssuche ohne Zukunftsdaten | Antwort auf Fragen wie „Was passierte mit EUR/USD, wenn …?“ | 2–3 Wochen |
| **7 Makro-Beziehungen & Regime** | rollierende Korrelationen, Strukturbrüche, Regime-Kennzeichnung | Übersicht: welche Zusammenhänge sind gerade stabil oder brechen | 2–3 Wochen |
| **8 Wochenbericht** | „What changed?“ automatisch aus der Datenbank | Erster vollständiger Wochenbericht | 1–2 Wochen |
| **9 Dashboard** | Streamlit-Oberfläche: Prognosen, Szenarien, Unsicherheit, Bilanz | Alles im Browser ansehen | 2–3 Wochen |
| **10 A+-Regel-Engine** | deine 6 Kriterien als getestete Regeln, eigene Ansicht | A+-Setups nur, wenn alle 6 erfüllt sind | 1–3 Wochen |
| **11 Optimierung** | Prüfung kostenpflichtiger Daten (z. B. Konsens), neue Merkmale, Challenger-Zyklen | messbar bessere Modelle – oder der Nachweis, dass es keine gibt | laufend |

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

## Nächster Schritt: Phase 1 – Kursdaten

1. Tageskurse der 7 USD-Paare von FRED laden, Kreuzkurse für die übrigen 21 Paare berechnen.
2. EZB-Referenzkurse als zweite Quelle zur Kontrolle.
3. Qualitätsprüfungen (Lücken, Ausreißer, Abweichung zwischen Quellen).
4. Ergebnis für dich: Kursdiagramme aller 28 Paare und eine Liste gefundener Datenprobleme.
