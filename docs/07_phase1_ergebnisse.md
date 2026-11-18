# 07 – Phase 1a: Ergebnisse und Einordnung

Stand: 18.11.2026 · Automatischer Bericht: [reports/phase1/README.md](../reports/phase1/README.md)

## Datenbestand

| Quelle | Inhalt | Zeitraum | Werte |
|---|---|---|---|
| FRED H.10 | 7 Dollar-Paare, Mittagskurs New York | 1971 – 13.11.2026 | 91.019 |
| FRED-Kreuzkurse | 21 berechnete Paare | ab 1999 (Euro) bzw. früher | 251.925 |
| EZB | 7 Euro-Paare, 14:15 MEZ | 1999 – 17.11.2026 | 49.966 |

## Was die Qualitätsprüfung gefunden hat (Zeitraum ab 1999)

**Kein einziger Verdacht auf Datenfehler.** Alle extremen Bewegungen werden von der
unabhängigen EZB-Quelle bestätigt.

**100 extreme Marktbewegungen (Info)** – das sind echte Ereignisse, keine Fehler. Die Prüfung
erkennt sie selbstständig, darunter:

| Datum | Ereignis |
|---|---|
| 16.08.2007 | Auflösung von Carry-Trades (AUD, NZD stürzen gegen JPY) |
| Okt. 2008 | Finanzkrise nach Lehman-Pleite |
| 06.09.2011 | SNB führt Mindestkurs EUR/CHF 1,20 ein |
| 15.01.2015 | SNB hebt Mindestkurs auf |
| 24.06.2016 | Brexit-Abstimmung |
| März 2020 | Corona-Schock |
| 04.04.2025 | Zoll-Turbulenzen |

**37 Tage mit > 2 % Abweichung zwischen FRED und EZB.** Sie fallen auf Tage, an denen zwischen
14:15 MEZ (EZB) und 12:00 New York (FRED) ein großes Ereignis lag, z. B. die EZB-Pressekonferenzen
am 03.12.2015 und 10.03.2016, die Yen-Intervention am 21.10.2022 oder US-Inflationsdaten am 10.11.2022.
Im Normalfall liegen beide Quellen im Mittel nur 0,09–0,21 % auseinander.

## Wichtige Erkenntnisse für die nächsten Phasen

1. **Extreme Ereignisse sind selten, aber prägend.** Modelle müssen mit solchen Tagen umgehen;
   die Liste wird später für die Regime-Analyse (Phase 7) genutzt.
2. **Zeitpunkt der Messung ist entscheidend.** Ein Kurs um 14:15 MEZ und einer um 12:00 New York
   können an Ereignistagen mehrere Prozent auseinanderliegen. Für Prognosen muss klar sein, welcher
   Schlusskurs gilt – deshalb Phase 1b (Dukascopy, Schluss 17:00 New York).
3. **FRED erscheint nur wöchentlich.** Für tägliche Live-Prognosen reicht FRED allein nicht.
4. **Daten vor 1999** bleiben gespeichert, werden aber vorerst nicht genutzt (feste Kurse bis 1973,
   kein Euro).

## Technische Erkenntnisse

* FRED blockiert unbekannte Programmkennungen (User-Agent); das System nutzt die Standardkennung.
* Abbrüche durch die Gegenseite werden automatisch bis zu 4-mal wiederholt.
