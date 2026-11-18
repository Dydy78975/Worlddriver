# 01 – Technische Machbarkeit

Stand: 18.11.2026 · Status: Entwurf zur Freigabe

## Kurzfazit

**Machbar – mit einer klaren Einschränkung:** Das System lässt sich vollständig mit
kostenlosen Daten und Open-Source-Software bauen. Ob es **gute** Prognosen liefert,
wissen wir vorher nicht. Wechselkurse gehören zu den am schwersten vorhersagbaren
Zeitreihen überhaupt. Der eigentliche Wert der Plattform ist deshalb, dass sie
**ehrlich misst**, wie gut ihre Prognosen sind, und schwache Prognosen auch als
schwach ausweist.

| Baustein | Machbarkeit | Hauptrisiko |
|---|---|---|
| 1 Predictive Engine (28 Paare × 3 Horizonte) | Hoch | Geringe Vorhersagekraft, v. a. bei 1 Woche |
| 2 Historische Mustererkennung | Hoch | Kleine Stichproben bei seltenen Situationen |
| 3 Self-Learning (Prognose-Ledger, Champion/Challenger) | Hoch | Braucht Zeit: echte 3-Monats-Bilanz erst nach Monaten |
| 4 Machine Learning (LogReg, LightGBM, XGBoost) | Hoch | Overfitting, Datenleck (Leakage) |
| 5 Makro-Beziehungen (stabile vs. brechende Korrelationen) | Hoch | Instabile Zusammenhänge, Fehlalarme |
| 6 „What changed?“-Wochenbericht | Hoch | Gering |
| 7 A+-Regel-Engine | Hoch | Hängt von der genauen Formulierung deiner 6 Kriterien ab |
| Zinspfad-Erwartungen (OIS / Futures) | **Eingeschränkt** | Gute Daten kosten viel Geld → wir nutzen 2-Jahres-Renditen als Ersatz |
| Konsens-Erwartungen / Daten-Überraschungen | **Eingeschränkt** | Kostenlos kaum historisch verfügbar |

## Realistische Erwartung an die Prognosequalität

Aus Forschung und Praxis ist bekannt:

* Auf **1 Woche** sind Wechselkurse nahe an einem Zufallspfad. Eine Trefferquote von
  52–54 % bei der Richtung wäre bereits ein gutes Ergebnis.
* Auf **1–3 Monate** gibt es schwache, aber dokumentierte Effekte: Zinsdifferenz
  (Carry), Momentum, Bewertung, Risikostimmung (VIX) und extreme Positionierung (COT).
* Zusammenhänge **ändern sich** je nach Marktregime. Eine Korrelation, die zehn Jahre
  stabil war, kann plötzlich brechen.

Daraus folgen drei Grundregeln für das System:

1. **Jedes Modell muss einfache Referenzprognosen schlagen**, zum Beispiel
   „immer die historische Häufigkeit“ oder „Momentum der letzten 3 Monate“. Ein Modell,
   das das nicht schafft, wird nicht verwendet.
2. **Wahrscheinlichkeiten werden nur angezeigt, wenn sie kalibriert sind.** Sonst
   zeigt das System nur Richtung und Unsicherheit und kennzeichnet die Prognose als
   „nicht kalibriert“.
3. **Kein Ergebnis wird geschönt.** Schlechte Modellleistung bleibt im Wochenbericht
   sichtbar.

## Statistische Stolperfallen und wie wir sie lösen

### 1. Zu wenige unabhängige Beobachtungen

Mit Tagesdaten ab etwa 2000 gibt es pro Paar ungefähr 100 **nicht überlappende**
3-Monats-Zeiträume. Das ist wenig. Außerdem sind die 28 Paare nicht unabhängig: Sie
bestehen aus nur 8 Währungen, also 7 unabhängigen Kursbewegungen.

**Lösung:**
* Ein gemeinsames Modell für alle Paare (Panel-Modell) statt 28 Einzelmodelle.
  Merkmale wie „Zinsdifferenz Basis minus Quote“ sind für alle Paare gleich aufgebaut.
* Zusätzlich ein **Währungsstärke-Modell** für die 8 Einzelwährungen. Daraus lassen
  sich Paarprognosen ableiten und auf Widersprüche prüfen
  (z. B. EUR/USD bullisch, USD/CHF bullisch, EUR/CHF bärisch passt nicht zusammen).
* Unsicherheit wird immer mit der Stichprobengröße angezeigt.

### 2. Überlappende Zielwerte

Wenn jeden Tag eine 3-Monats-Prognose erstellt wird, überschneiden sich die
Prognosezeiträume stark. Normale Kreuzvalidierung würde dann die Zukunft „sehen“.

**Lösung:** Walk-Forward-Validierung mit **Purging** und **Embargo**: Zwischen
Trainings- und Testdaten wird eine Lücke von mindestens der Länge des
Prognosehorizonts gelassen.

### 3. Look-ahead Bias (Zukunftsdaten)

Beispiele für versteckte Zukunftsdaten:

* Die US-Inflation für Oktober wird erst Mitte November veröffentlicht.
* COT-Daten beziehen sich auf Dienstag, werden aber erst am Freitag veröffentlicht.
* Wirtschaftsdaten werden **nachträglich revidiert**. Die heutige Zahl für das
  BIP 2019 ist nicht die Zahl, die man 2019 kannte.

**Lösung:** Jeder Datenpunkt bekommt in der Datenbank zwei Zeitangaben:
* `period_date` – worauf sich der Wert bezieht (z. B. Oktober 2026),
* `available_at` – ab wann er öffentlich bekannt war.

Das System darf für eine Prognose zum Zeitpunkt T **nur** Daten mit
`available_at ≤ T` verwenden. Für US-Daten gibt es mit ALFRED (St. Louis Fed)
echte historische Datenstände („Vintages“). Für andere Länder nutzen wir
Veröffentlichungskalender oder einen vorsichtigen Sicherheitsabstand.

### 4. Datenqualität der Kurse

Kostenlose Kursquellen unterscheiden sich in Uhrzeit des Tagesschlusses und
Feiertagen. **Lösung:** Eine feste Referenzquelle mit fester Schlusszeit
(17:00 New York) und automatische Plausibilitätsprüfung gegen eine zweite Quelle.

## Was das System bewusst **nicht** tut

* Keine automatische Änderung von Modellen im Live-Betrieb.
* Keine Kauf- oder Verkaufsempfehlungen aus der statistischen Prognose.
  Ein Trading-Setup entsteht ausschließlich in der getrennten A+-Regel-Engine.
* Keine Intraday-Prognosen (andere Datenanforderungen, anderes Projekt).
* Keine Anlageberatung. Das System ist ein persönliches Analysewerkzeug.

## Technische Rahmenbedingungen

* Datenmenge: klein. 28 Paare × ~7.000 Handelstage plus einige hundert
  Makro-Zeitreihen ergeben wenige Millionen Zeilen. Ein normaler PC oder ein
  kleiner Server reicht.
* Rechenzeit: Ein vollständiger Walk-Forward-Test aller Modelle dauert auf einem
  normalen Rechner voraussichtlich Minuten bis wenige Stunden.
* Betrieb: Das System muss täglich automatisch laufen, damit das Prognose-Ledger
  lückenlos ist. Dafür empfiehlt sich ein kleiner Server (siehe Kosten in
  `02_datenquellen_und_kosten.md`).
