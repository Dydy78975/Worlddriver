# 12 – Signal-Abstimmung und Aufräumen

Stand: 18.11.2026 · Code: `forex_nexus/signals/` · Bericht: [reports/signals/README.md](../reports/signals/README.md)
· Befehl: `python -m forex_nexus signals`

## Wunsch

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
| Fundamental-Mehrheit richtig seit 2020 | 50,8 % (95 %: 48–53 %) | 50,9 % (95 %: 46–56 %) |
| Stufe „klar long“ richtig seit 2020 | 52,9 % (50–55 %) | 54,2 % (49–60 %) |

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

* **Inflation ist für GBP, JPY, CHF, CAD, AUD, NZD veraltet** (OECD-Reihen auf FRED eingestellt, Japan seit
  2021). Diese Inflationssignale stehen deshalb auf neutral. Lösung: BIS-Statistik (`stats.bis.org`) mit
  Verbraucherpreisen und offiziellen Leitzinsen aller 8 Notenbanken. Der Host ist in der Umgebung
  „worlddriver“ freigegeben; der erste Abruf wurde in der Sitzung vom 18.11.2026 von der automatischen
  Freigabe-Prüfung abgelehnt und muss vom Nutzer erlaubt werden.
* Weitere Datenquellen, die Signale tragen könnten: 2-jährige Renditen aller Länder (bessere Zinserwartung),
  Konsens vs. Ist bei Wirtschaftsdaten (Überraschungen), Dukascopy Hoch/Tief (nur vom eigenen Server).
* Neue Signale kommen automatisch in die geprüfte Abstimmung, sobald sie Entdeckung und Bestätigung bestehen.
