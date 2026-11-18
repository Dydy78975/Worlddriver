# 11 – Fundamentale Wochenansicht (Cockpit, Paare, Kalender, COT, Saisonalität)

Stand: 18.11.2026

## Was die Website jetzt zeigt

| Seite | Inhalt |
|---|---|
| **Cockpit** | Die Aussage der Woche („Diese Woche: Neuseeland-Dollar stark, Yen schwach.“), Kurzfassung mit Quellen-Verweisen [1]–[4], rote Ordner der Woche, Paare mit der höchsten Übereinstimmung, Währungs-Ranking |
| **Währungen** | Bias 0–100 je Währung aus COT, Trend und Saison; Stärke-Verlauf |
| **Paare** | alle 28 Paare: Richtung (LONG/SHORT/NEUTRAL), Konfluenz 0–3, COT-Differenz, typische Tagesbewegung |
| **Paar-Seite** | Woche Tag für Tag mit Terminen beider Währungen, Faktoren mit Begründung, Kurs mit Wochenfächer, Saisonalität des Paares, COT beider Währungen |
| **Kalender** | Termine der Woche mit Ordner-Farben (rot = hoch, orange = mittel, gelb = niedrig, grau = Feiertag), Prognose, Vorwert, Ist-Wert; Filter nach Wichtigkeit und Währung |
| **Positionierung (COT)** | Commercials- und Spekulanten-Index (0–100, 3 Jahre), Netto-Positionen, 4-Wochen-Veränderung, Verlauf, Extremzonen |
| **Saisonalität** | Monatsrenditen je Paar oder Währung seit 1999, Anteil positiver Jahre, deutlichste Muster des Monats |

## Regeln (versioniert in `forex_nexus/fundamentals/analysis.py`)

* **COT-Faktor:** Commercials-Index der Basis- minus der Quotewährung; Signal ab ±20 Punkten.
  Ein Bericht zählt erst ab Veröffentlichung (Freitag 15:30 New York).
* **Trend-Faktor:** Stärke gegen den Korb der anderen 7 über 20 Handelstage; Signal ab ±0,5 %.
* **Saison-Faktor:** Anteil der Vorjahre, in denen das Paar im Monat stieg; Signal ab 60 % bzw. unter 40 %
  (mindestens 8 Jahre). Für ein Jahr werden nur frühere Jahre verwendet.
* **Richtung:** Mehrheit der Faktoren; **Konfluenz:** Anzahl der Faktoren in diese Richtung.
* **Bias einer Währung:** Mittel der drei Faktoren, skaliert auf 0–100.

## Ehrliche Prüfung (gleiche Regeln, nur damals verfügbare Daten)

| Signal | Ergebnis | Bewertung |
|---|---|---|
| Saisonalität (Richtung des Monats) | 50,4 % Treffer, n = 2.818 | keine verlässliche Vorhersagekraft |
| COT Commercials > 80 → Währung 4 Wochen stärker | 52,6 % Treffer, n = 1.668 | kleiner, knapp messbarer Vorteil |
| COT Commercials < 20 → Währung 4 Wochen schwächer | 52,1 % Treffer, n = 1.452 | nicht belegt |
| Konfluenz 3/3 → Richtung der Folgewoche | 48,3 % Treffer, n = 1.276 | keine verlässliche Vorhersagekraft |

Die Website zeigt diese Ergebnisse neben den Signalen. Die fundamentale Wochenansicht ist ein
**Überblick über die Lage**, kein Handelssignal.

## Datenquellen

* COT: CFTC Public Reporting (Legacy, Futures Only), kostenlos, ab 2005.
* Kalender: Forex Factory Wochen-Feed. **Nur zur persönlichen Nutzung** – deshalb wird die fertige
  Website (`site/index.html`) nicht im öffentlichen Repository gespeichert, sondern als private Seite
  bereitgestellt. Das Programm meldet sich beim Abruf ehrlich als „WorlDDriver“.

## Version 2 (18.11.2026)

| Neu | Beschreibung |
|---|---|
| Seitenleiste | auf iPad und Desktop fest sichtbar; Umschalter Woche (Swing) / Heute (Intraday) |
| Paar-Matrix | Bias-Abstand jeder Währung gegen jede andere; Antippen öffnet die Konfluenz-Checkliste mit Bias-Abstand, Faktoren, Event-Lage und Gegenargumenten |
| Währungsstärke | Rangliste für 1 Tag, 1 Woche, 1 Monat (gegen den Korb) und Bias-Rangliste |
| COT | Pegel je Währung (Commercials-Index, Kleinanleger-Strich, Extremlinien) und Verlauf der Netto-Positionen von Commercials, Spekulanten und Kleinanlegern über 1–3 Jahre mit markierten Extremphasen |
| Saisonalität | Jahresverlauf (Basis 100) für 5/10/15/20 Jahre oder alle Jahre; **Saison-Screener** mit exaktem Binomialtest und Bonferroni-Korrektur über alle durchsuchten Fenster (aktuell besteht kein Paar die Korrektur) |
| Makro | Marktstimmung Risk-on/Risk-off (VIX gegen Jahresmittel, AUD/JPY-Trend, US-Dollar), Quadrant Trend × Positionierung, Stärke-Heatmap |
| Rechner | Positionsgröße aus Risiko, Pip-Wert in Kontowährung, Chance-Risiko-Verhältnis, Warnung bei zu engem Stop im Verhältnis zur typischen Tagesbewegung |
| Kalender | Countdown zum nächsten roten Ordner |
