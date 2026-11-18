# 10 – Stand der Software und Bedienung

Stand: 18.11.2026

## Was jetzt funktioniert

| Baustein | Stand |
|---|---|
| Kursdaten FRED + EZB, alle 28 Paare | läuft, mit Qualitätsprüfung |
| Rohstoffe und VIX (14 Reihen von FRED) | läuft, Veröffentlichungsverzögerung berücksichtigt |
| Prognose-Engine Tag / Woche / Monat | läuft: 4 Modelle je Horizont, Walk-Forward 2006–heute |
| Prognose-Ledger (unveränderlich) | läuft: 336 Prognosen pro Handelstag (84 angezeigt, 252 im Schattenbetrieb) |
| Auswertung fälliger Prognosen | läuft, sobald die Kurse des Zieltags vorliegen |
| Forecast-Tracker | läuft: Backtest je Jahr, Hold-out, je Währung, je Regime, Live-Bilanz |
| Dependency Engine | läuft: 21 von 28 Beziehungen statistisch geprüft, 7 warten auf Daten |
| Website WorlᗡDriver | läuft: Cockpit, Währungen, Paare (Woche + Tage), Kalender, COT, Saisonalität, Prognosen, Tracker, Makro, Weltkarte, Daten |
| COT (CFTC) und Wirtschaftskalender | läuft, siehe `11_fundamentale_wochenansicht.md` |
| Täglicher Fehler-Check 6:00 Uhr | eingerichtet (siehe unten) |
| Dukascopy (Hoch/Tief, 17:00 New York) | Code fertig; Abruf aus der Cloud-Umgebung blockiert → eigener Server nötig |
| Zinsen, Inflation | nächste Phase |
| A+-Regel-Engine | wartet auf deine 6 Kriterien |

## Wichtigste Ergebnisse (ehrlich)

* **Die Schwankungsbreite ist gut vorhersagbar.** Die 80-%-Intervalle trafen in allen drei Horizonten
  in 79–81 % der Fälle, auch im Hold-out ab 2022.
* **Die Richtung ist mit den bisherigen Daten nicht besser vorhersagbar als durch Referenzen.**
  Logistische Regression und LightGBM schlagen die Referenzen nicht belastbar. Das System zeigt deshalb
  Referenzwahrscheinlichkeiten an und kennzeichnet das klar.
* **Ein wichtiger Fehlschluss wurde abgefangen:** Zunächst schien die Tagesprognose besser als die
  Referenz. Ein Test mit reinen Zufallsdaten zeigte, dass dieser „Vorteil“ nur aus der Korrektur der
  Schwankungsschätzung stammt. Seitdem gibt es die **Schwankungs-Referenz**; ein Modell muss beide
  Referenzen schlagen, bevor es einen Richtungsvorteil beanspruchen darf.
* **Wirtschaftsbeziehungen:** Belegt als gleichzeitige Zusammenhänge sind u. a. AUD–Eisenerz, AUD–Kohle,
  AUD–Kupfer, CAD–Öl sowie JPY und CHF als sichere Häfen. Keine Beziehung hat bisher einen nachweisbaren
  Vorlauf – die Information ist sofort im Kurs. Nicht belegt: EUR/GBP–Erdgas, NZD–Rindfleisch/Holz.

## Täglicher Ablauf

```
python -m forex_nexus daily      # Kurse + Rohstoffe laden, prüfen, prognostizieren, auswerten, Website bauen
```

Neue Modellversionen entstehen nur über `train` und werden nur über `promote` (mit Namen) eingesetzt.
Der tägliche Lauf verändert keine Modellparameter.

## Wichtige Einschränkung bis zum eigenen Server

Die Cloud-Umgebung ist nicht dauerhaft: Die Datenbank wird nach jeder Sitzung gelöscht. Code, Berichte
und die Website bleiben auf GitHub erhalten, aber eine **echte, über Monate wachsende Live-Bilanz**
braucht eine dauerhafte Datenbank (eigener kleiner Server oder verwaltete Datenbank).
