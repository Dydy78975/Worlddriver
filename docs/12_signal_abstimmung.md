# 12 – Modelle je Währung, Kombi-Modell und Prüfung

Stand: 19.11.2026 · Code: `forex_nexus/signals/` · Bericht: [reports/signals/README.md](../reports/signals/README.md)
· Befehl: `python -m forex_nexus signals`

## Aktueller Aufbau (seit 19.11.2026)

**Wunsch des Nutzers:** je Währung viele Modelle aus dem, was diese Währung wirklich bewegt (z. B. Milch für NZD,
Rohstoffe für AUD, Leitzins und Renditen für alle); nichts als Füllmaterial; schwache Einzelsignale (COT, Saison …)
kombinieren, um eine Richtung zu sehen; Ziel mindestens 70 % Aussagekraft; Tag, Woche (und Monat).

* **410 Modelle** (`library.py`), 43–65 je Währung, jedes Modell genau einmal mit seiner ökonomisch erwarteten Richtung:
  * Makro, jeweils eigener Wert gegen den Durchschnitt der anderen 7: Leitzins (BIS/Fed/EZB), Leitzins-Kurs 3/6/12 M.,
    Rendite 10 J. und Anstieg 1/3/6 M., **Rendite 2 J.** (EZB, Bank of Canada, RBA, Finanzministerium Japan,
    Bank of England [5 J.], FRED) mit Anstieg 1/3/6 M. und Abstand zum Leitzins, Zinskurve, Realzins, Inflation (BIS),
    Arbeitslosigkeit.
  * Positionierung (COT): Commercials, Extreme, Spekulanten-Zufluss, Kleinanleger. Saison. Risikostimmung (nur Risiko-
    und Fluchtwährungen). Kursverlauf (kurz Gegenbewegung, mittel Trend).
  * Eigene Treiber über 3 Zeitfenster: NZD Milchprodukte und Trinkmilch (US-Erzeugerpreise als Ersatz für Global
    Dairy Trade, die es auf keiner frei zugänglichen Schnittstelle gibt), Rind, Lamm, Wolle, Holz; AUD Eisenerz,
    Kohle, LNG, Kupfer, Aluminium, Weizen, Wolle, Rind; CAD Öl, Gas, Holz, Aluminium, Nickel; JPY Öl und LNG
    (Importeur, negativ), VIX, US-Rendite; CHF VIX, US-Rendite; EUR/GBP Gas und Öl (Importeure, negativ); USD VIX,
    US-Rendite.
  * Bewusst weggelassen: Spiegelbild-Modelle, zusätzliche Zeitfenster, schwach begründete Rohstoffe (Blei, Uran,
    Zink, Gerste …). Für CHF und NZD gibt es keine aktuelle 2-J.-Rendite (SNB-Reihen enden 07/2025, RBNZ sperrt
    automatische Abrufe) – dort keine 2-J.-Modelle statt wirkungsloser.
* **Gemessen** wird die Stärke der Währung gegen den Durchschnitt der anderen 7 (Tag, Woche, Monat), nach 0,03 % Kosten.
* **Einzelmodelle:** Entdeckung 1999–2012 mit Benjamini-Hochberg über alle 410, Bestätigung 2013–2019 (t > 1).
* **Kombi-Modell je Währung:** logistische Regression über alle Modelle der Währung, stark regularisiert.
  Bestätigung: Training bis 2012, Prüfung 2013–2019. Schlusstest: Training bis 2019 (eingefroren), Prüfung ab 2020.
  Dieses eingefrorene Modell liefert die aktuelle Einschätzung. **Bestätigt** heißt: untere Grenze des 95-%-Bereichs
  der Trefferquote 2013–2019 über 50 %. Offenlegung: Diese Schwelle wurde festgelegt, nachdem die Bestätigungszahlen
  einmal angesehen worden waren; am Schlusstest ändert sie nichts.
* **Aussagekraft:** Trefferquote insgesamt und je Sicherheitsstufe (nur Fälle, in denen das Modell mindestens
  55/60/65/70 % sicher ist), jeweils mit 95-%-Bereich und Anteil der Fälle.

### Ergebnis 19.11.2026 (Details im Bericht)

* Kein Einzelmodell besteht die strenge Prüfung (Tag, Woche, Monat).
* Kombi-Modelle: meist um 50 %. Bestätigt ist bisher nur **CHF auf Wochensicht** (Bestätigung 57 %, Schlusstest 54 %).
  Auf Monatssicht liegen JPY und NZD in Bestätigung und Schlusstest bei 57–60 %, aber mit nur ~80 Monaten je Zeitraum
  noch nicht von Zufall unterscheidbar.
* **70 % Trefferquote werden nicht verlässlich erreicht.** Wo einzelne Sicherheitsstufen 70 % oder mehr zeigen, beruht
  das auf wenigen Fällen und ist nicht belastbar. Die Website zeigt deshalb immer den 95-%-Bereich mit.

## Verlauf bis 18.11.2026 (Abstimmung je Paar)

### Wunsch

Für jedes Paar möglichst viele Signale (z. B. Arbeitslosenquote, Zinserwartung, Spekulanten-Positionierung),
nur geprüfte Signale mit echter positiver Rendite, und daraus ein Punkte-System: „von 25 Signalen sind
17 long und 8 short = 68 % long“ – für die Tages- und die Wochenansicht. Alles Unnötige entfernen.

## Was gebaut wurde

* **43 Einzelsignale** in 8 Familien (`signals/library.py`): Kursverlauf (Trend und Gegenbewegung über
  1 Tag bis 1 Jahr), Zinsen (Carry, 10-J.-Rendite, Realzins), Zinserwartung (Leitzinsänderung 3/6/12 Monate,
  Renditeanstieg 1/3 Monate, Zinskurve), Inflation, Arbeitsmarkt (Quote und Änderung 3/6/12 Monate, **neu:
  Arbeitslosenquoten aller 8 Währungsräume**, Eurozone von der EZB), Positionierung (COT: Spekulanten,
  Commercials, Kleinanleger, Extreme), Saisonalität, Risikostimmung (VIX, AUD/JPY), Rohstoffe (CAD: Öl;
  AUD: Eisenerz, Kupfer, Kohle; NZD: Rindfleisch, Holz).
* **Keine Zukunftsdaten:** Entscheidung täglich 12:00 New York; jeder Makrowert erst ab Veröffentlichung;
  ein Wert, dessen Nachfolger überfällig ist (Periodenlänge + 45 Tage nach Veröffentlichung), wird verworfen.
* **Prüfung** (`signals/validate.py`) je Signal × Währung, Tag und Woche, nach 0,03 % Kosten je neuem Trade:
  1. Entdeckung 1999–2012, Benjamini-Hochberg-Korrektur (10 %) über alle 344 Kombinationen.
  2. Bestätigung 2013–2019, t-Wert > 1.
  3. Schlusstest ab 2020 – für keine Entscheidung genutzt, nur berichtet.
* **Zwei Abstimmungen je Paar:** die *geprüfte* (nur bestandene Signale) und die *Fundamental-Abstimmung*
  (25 Signale in ihrer ökonomisch erwarteten Richtung, ohne Auswahl nach Ergebnis). Stufen: klar long
  (≥ 70 %), eher long (55–70 %), unentschieden, eher short, klar short. Neben jeder Stufe steht, wie oft sie
  im Schlusstest richtig lag – mit 95-%-Bereich.
* Ein Test pflanzt ein echtes Signal in Zufallsdaten: Die Prüfung findet es, reinen Zufall nicht
  (`tests/test_signals.py`). Die Prüfung *kann* also Signale finden.

## Ergebnis (ehrlich)

| | Tag | Woche |
|---|---|---|
| geprüfte Kombinationen | 344 | 344 |
| bestanden | **0** | **0** |
| Fundamental-Mehrheit richtig seit 2020 | 50,9 % (95 %: 48–53 %) | 50,7 % (95 %: 46–56 %) |
| Stufe „klar long“ richtig seit 2020 | 52,7 % (50–55 %) | 54,3 % (49–60 %) |

* Kein Signal hält die Prüfung. Die stärkste Kombination (t = 2,3) liegt unter dem, was bei 344 Versuchen
  allein durch Zufall zu erwarten ist.
* Am beständigsten – in allen drei Zeiträumen leicht positiv, aber nicht signifikant: **Inflation aus
  Notenbank-Sicht** (EUR, USD) und **Arbeitslosigkeit über 6–12 Monate** (EUR, CAD).
* Die Fundamental-Mehrheit ist von Zufall nicht zu unterscheiden. Sie wird deshalb als **Lagebild** gezeigt,
  nicht als Vorhersage.
* Was nachweislich funktioniert: die **erwartete Spanne** (80-%-Bereich trifft in 80 % der Fälle).

### Wie es zu diesem Aufbau kam (offengelegt)

1. Erste Fassung: Prüfung über alle 28 Paare gemittelt → 0 bestanden.
2. Zweite Fassung: je Paar (1.372 Tests) → 0 bestanden. Dabei fiel auf, dass Kurs-Regeln nur in einer
   Richtung im Katalog standen; seitdem stehen Trend **und** Gegenbewegung für jedes Fenster darin
   (das wurde nach Sicht auf die Daten ergänzt; die Mehrfachtest-Korrektur zählt beide Richtungen).
3. Dritte Fassung (jetzt): je Währung, weil das dem Wunsch „was funktioniert bei USD?“ entspricht und mehr
   Aussagekraft hat → 0 bestanden.
4. Zur Einordnung wurden einmalig mildere Regeln angesehen (ohne Korrektur; „Beobachtungsliste“ Entdeckung
   t ≥ 1, Bestätigung t ≥ 0,5). Ihre Kandidaten trafen im Schlusstest 50,4 % (Tag) bzw. 52,1 % (Woche).
   Diese Regeln wurden **nicht** übernommen. Weil dabei der Schlusstest angesehen wurde, ist er für
   künftige Regeländerungen nicht mehr unberührt – die gültigen Regeln oben bleiben deshalb fest.

## Was entfernt wurde – und warum

| Entfernt | Beleg |
|---|---|
| Logistische Regression, LightGBM (Richtung) | Walk-Forward 2006–2021: in allen 3 Horizonten schlechter als die Schwankungs-Referenz |
| Ridge-Renditemodell | Out-of-Sample-R² in allen Horizonten negativ |
| „Einflussfaktoren“ je Prognose | erklärten ein Modell ohne Vorhersagekraft |
| Momentum-, Wochentags-, Monatsende-, Risiko-Merkmale | nur von den entfernten Modellen genutzt |
| Konfluenz (COT + Trend + Saison), Währungs-Scores | historisch ≈ Zufall; ersetzt durch die geprüfte Signal-Abstimmung |
| Saison-Screener, Saisonverläufe | Saison-Signale bestehen die Prüfung nicht |
| Dependency-Engine und Wissensbasis | nur gleichzeitige Zusammenhänge, kein Vorlauf; Vorlauf prüfen jetzt die Rohstoff-Signale |
| Website: Cockpit, Heute, Währungen, Paar-Matrix, COT, Saison, Prognosen, Tracker, Zinsen, Makro, Weltkarte | ersetzt durch 5 Seiten: Übersicht, Paar, Signal-Prüfung, Kalender, Datenstand (+ Rechner) |
| Datenreihen Brent, Erdgas (USA/Europa/Asien), Aluminium, Weizen, breiter Dollar-Index | speisten nur die Dependency-Engine; Abruf abgeschaltet (Migration 0008), Daten bleiben gespeichert |
| Python-Pakete lightgbm, statsmodels, pyyaml | nicht mehr benötigt |

Alles ist in Git nachvollziehbar und kann zurückgeholt werden.

## Offene Punkte

* ~~Inflation für GBP, JPY, CHF, CAD, AUD, NZD veraltet~~ – **erledigt 18.11.2026**: Verbraucherpreise und
  offizielle Leitzinsen (BoE, BoJ, SNB, BoC, RBA, RBNZ) kommen jetzt von der BIS (Migration 0010). Alle
  Datenreihen sind aktuell. Neue Prüfung mit unveränderten Regeln: weiterhin 0 von 344 Kombinationen
  (Tag und Woche); Fundamental-Mehrheit seit 2020: 50,9 % (Tag), 50,7 % (Woche).
* Weitere Datenquellen, die Signale tragen könnten: 2-jährige Renditen aller Länder (bessere Zinserwartung),
  Konsens vs. Ist bei Wirtschaftsdaten (Überraschungen), Dukascopy Hoch/Tief (nur vom eigenen Server).
* Neue Signale kommen automatisch in die geprüfte Abstimmung, sobald sie Entdeckung und Bestätigung bestehen.
