# Prüfung der Modelle je Währung – Stand 19.11.2026

Automatisch erzeugt von `python -m forex_nexus signals`. 410 Modelle (EUR 47, GBP 44, AUD 65, NZD 55, USD 47, CAD 56, CHF 43, JPY 53). Regeln: [docs/12_signal_abstimmung.md](../../docs/12_signal_abstimmung.md).

## Tag (1D)

**Gültige Einzelmodelle: 0 von 410.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 48,9 % / 54,1 % (15 %) | 52,0 % / 57,1 % (11 %) | nein | 51 % |
| GBP | 50,9 % / 59,5 % (5 %) | 51,5 % / 52,1 % (6 %) | nein | 45 % |
| AUD | 49,5 % / 46,3 % (24 %) | 50,6 % / 51,3 % (9 %) | nein | 50 % |
| NZD | 50,5 % / 49,3 % (39 %) | 51,6 % / 49,0 % (9 %) | nein | 57 % |
| USD | 49,7 % / 46,4 % (7 %) | 50,6 % / 47,0 % (4 %) | nein | 53 % |
| CAD | 50,8 % / 49,7 % (19 %) | 51,3 % / 52,9 % (14 %) | nein | 40 % |
| CHF | 49,5 % / 50,9 % (16 %) | 51,3 % / 47,8 % (3 %) | nein | 48 % |
| JPY | 49,3 % / 52,6 % (13 %) | 51,3 % / 57,6 % (13 %) | nein | 35 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Rendite 10 J. | EUR | +4,9 % (t 2,2) | -0,5 % (t -0,2) | -1,0 % (t -0,6) | nein |
| Arbeitslosigkeit 6 M. | EUR | +4,1 % (t 2,1) | +0,8 % (t 0,3) | +1,3 % (t 0,7) | nein |
| US-Rendite 2 J. 1 Monat | JPY | +7,5 % (t 2,0) | -12,3 % (t -2,9) | +0,1 % (t 0,0) | nein |
| Gegen Kleinanleger | AUD | +13,9 % (t 2,0) | +1,5 % (t 0,3) | +2,1 % (t 0,5) | nein |
| Inflationsanstieg 12 M. | USD | +4,3 % (t 1,9) | -2,4 % (t -0,9) | +3,3 % (t 1,2) | nein |
| Rendite 2 J. 6 M. | EUR | +4,1 % (t 1,8) | -2,9 % (t -1,3) | +3,3 % (t 1,7) | nein |
| Arbeitslosigkeit 6 M. | CAD | +4,5 % (t 1,8) | -0,5 % (t -0,2) | +2,2 % (t 1,0) | nein |
| Rendite 2 J. 3 M. | USD | +4,1 % (t 1,8) | +0,9 % (t 0,4) | +1,4 % (t 0,4) | nein |
| Zinskurve 6 M. | NZD | +5,4 % (t 1,7) | +3,4 % (t 1,0) | +1,6 % (t 0,6) | nein |
| Inflation | NZD | +5,2 % (t 1,7) | +2,2 % (t 0,6) | -0,7 % (t -0,2) | nein |

## Woche (1W)

**Gültige Einzelmodelle: 0 von 410.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 52,1 % / 50,0 % (35 %) | 48,6 % / 49,4 % (45 %) | nein | 40 % |
| GBP | 47,7 % / 50,4 % (36 %) | 55,6 % / 52,8 % (25 %) | nein | 49 % |
| AUD | 50,1 % / 49,7 % (52 %) | 52,5 % / 53,2 % (35 %) | nein | 27 % |
| NZD | 47,1 % / 51,2 % (44 %) | 49,7 % / 50,3 % (49 %) | nein | 52 % |
| USD | 49,0 % / 50,7 % (37 %) | 49,7 % / 57,0 % (28 %) | nein | 73 % |
| CAD | 51,8 % / 52,6 % (48 %) | 48,9 % / 46,3 % (41 %) | nein | 30 % |
| CHF | 57,3 % / 57,1 % (19 %) | 53,9 % / 59,1 % (38 %) | ja | 41 % |
| JPY | 48,8 % / 49,7 % (45 %) | 53,4 % / 55,3 % (39 %) | nein | 36 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Rendite 2 J. 3 M. | USD | +5,5 % (t 2,4) | -0,7 % (t -0,3) | +1,0 % (t 0,3) | nein |
| Arbeitslosigkeit 6 M. | EUR | +4,6 % (t 2,3) | +0,9 % (t 0,4) | +1,2 % (t 0,7) | nein |
| Trend 1 Monat | USD | +4,3 % (t 2,0) | -1,5 % (t -0,6) | +0,4 % (t 0,2) | nein |
| Rendite 10 J. | EUR | +4,7 % (t 2,0) | -0,5 % (t -0,3) | -1,0 % (t -0,6) | nein |
| Inflation | NZD | +6,1 % (t 2,0) | +1,2 % (t 0,3) | -1,5 % (t -0,5) | nein |
| US-Rendite 2 J. 1 Monat | JPY | +7,6 % (t 2,0) | -10,7 % (t -2,6) | +1,0 % (t 0,3) | nein |
| Inflationsanstieg 12 M. | USD | +4,0 % (t 1,8) | -2,6 % (t -1,0) | +2,8 % (t 1,0) | nein |
| US-Rendite 2 J. 1 Woche | USD | +4,9 % (t 1,8) | +0,2 % (t 0,1) | +0,2 % (t 0,0) | nein |
| Eisenerz 3 Monate | AUD | +6,2 % (t 1,8) | -3,3 % (t -1,2) | +5,5 % (t 2,0) | nein |
| Arbeitslosigkeit 6 M. | CAD | +4,3 % (t 1,8) | -0,7 % (t -0,2) | +2,3 % (t 1,2) | nein |

## Monat (1M)

**Gültige Einzelmodelle: 0 von 410.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 56,0 % / 51,4 % (44 %) | 48,8 % / 57,5 % (49 %) | nein | 43 % |
| GBP | 48,8 % / 51,4 % (44 %) | 63,4 % / 70,0 % (37 %) | nein | 51 % |
| AUD | 40,5 % / 44,1 % (70 %) | 52,4 % / 53,1 % (60 %) | nein | 30 % |
| NZD | 57,1 % / 65,8 % (45 %) | 59,8 % / 57,6 % (40 %) | nein | 41 % |
| USD | 46,4 % / 37,9 % (35 %) | 47,6 % / 40,6 % (39 %) | nein | 60 % |
| CAD | 47,6 % / 44,0 % (60 %) | 52,4 % / 49,0 % (62 %) | nein | 51 % |
| CHF | 56,0 % / 48,3 % (35 %) | 42,7 % / 43,2 % (54 %) | nein | 65 % |
| JPY | 56,0 % / 54,1 % (44 %) | 58,5 % / 60,0 % (43 %) | nein | 53 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Gegenbewegung 1 Woche | GBP | +4,4 % (t 2,5) | -2,1 % (t -0,7) | -0,1 % (t -0,0) | nein |
| Arbeitslosigkeit 3 M. | CAD | +5,9 % (t 2,4) | -4,4 % (t -1,4) | +2,0 % (t 1,1) | nein |
| Inflationsanstieg 3 M. | CAD | +4,5 % (t 2,1) | -1,4 % (t -0,5) | -0,6 % (t -0,4) | nein |
| US-Rendite 2 J. 3 Monate | CHF | +4,6 % (t 2,1) | -2,5 % (t -0,8) | -0,1 % (t -0,1) | nein |
| Rendite 2 J. 3 M. | USD | +4,5 % (t 1,9) | +2,6 % (t 1,0) | +3,5 % (t 1,0) | nein |
| Eisenerz 1 Monat | AUD | +7,3 % (t 1,9) | +1,3 % (t 0,5) | +1,1 % (t 0,4) | nein |
| Arbeitslosigkeit 6 M. | EUR | +3,5 % (t 1,8) | +1,8 % (t 0,9) | +1,9 % (t 1,1) | nein |
| Trend 1 Monat | NZD | +4,4 % (t 1,7) | -4,6 % (t -1,5) | -4,0 % (t -1,6) | nein |
| Arbeitslosigkeit 6 M. | CAD | +3,9 % (t 1,7) | -0,2 % (t -0,1) | +2,9 % (t 1,9) | nein |
| Gegenbewegung 1 Tag | CHF | +3,5 % (t 1,7) | +1,6 % (t 0,7) | -2,4 % (t -1,4) | nein |

## Datenstand und Nutzen

| Reihe | Währung | letzter Wert | aktuell | speist Modelle |
|---|---|---|---|---|
| Rindfleisch | – | 2026-09-01 | ja | 6 |
| Erzeugerpreise Trinkmilch (USA, BLS) | – | 2026-10-01 | ja | 3 |
| Lammfleisch | – | 2026-09-01 | ja | 3 |
| Rundholz (Weichholz) | – | 2026-09-01 | ja | 3 |
| Weizen | – | 2026-09-01 | ja | 3 |
| Wolle grob | – | 2026-09-01 | ja | 3 |
| Wolle fein | – | 2026-09-01 | ja | 3 |
| Erzeugerpreise Milchprodukte (USA, BLS) | – | 2026-10-01 | ja | 3 |
| Erzeugerpreise Schnittholz (USA, BLS) | – | 2026-10-01 | ja | 3 |
| Verbraucherpreise Australien (BIS, Quartal) | AUD | 2026-06-01 | ja | 56 |
| Verbraucherpreise Kanada (BIS) | CAD | 2026-09-01 | ja | 56 |
| Verbraucherpreise Schweiz (BIS) | CHF | 2026-09-01 | ja | 56 |
| HICP Eurozone (Index) | EUR | 2026-09-01 | ja | 56 |
| Verbraucherpreise Großbritannien (BIS) | GBP | 2026-09-01 | ja | 56 |
| Verbraucherpreise Japan (BIS) | JPY | 2026-09-01 | ja | 56 |
| Verbraucherpreise Neuseeland (BIS, Quartal) | NZD | 2026-09-01 | ja | 56 |
| Verbraucherpreisindex USA | USD | 2026-10-01 | ja | 56 |
| Rohöl Brent (Nordsee) | – | 2026-11-11 | ja | 6 |
| Rohöl WTI (USA) | – | 2026-11-11 | ja | 6 |
| Erdgas Henry Hub (USA) | – | 2026-11-11 | ja | 3 |
| Kraftwerkskohle Australien | – | 2026-09-01 | ja | 3 |
| Erdgas Europa | – | 2026-09-01 | ja | 6 |
| Flüssiggas (LNG) Japan/Asien | – | 2026-09-01 | ja | 6 |
| Aluminium | – | 2026-09-01 | ja | 6 |
| Kupfer | – | 2026-09-01 | ja | 3 |
| Eisenerz | – | 2026-09-01 | ja | 3 |
| Nickel | – | 2026-09-01 | ja | 3 |
| Volatilitätsindex VIX (Risikostimmung) | – | 2026-11-16 | ja | 27 |
| Leitzins Reserve Bank of Australia (BIS) | AUD | 2026-11-05 | ja | 86 |
| Leitzins Bank of Canada (BIS) | CAD | 2026-11-09 | ja | 86 |
| Leitzins Schweizerische Nationalbank (BIS) | CHF | 2026-11-10 | ja | 86 |
| EZB-Einlagesatz | EUR | 2026-11-18 | ja | 86 |
| Leitzins Bank of England (BIS) | GBP | 2026-11-09 | ja | 86 |
| Leitzins Bank of Japan (BIS) | JPY | 2026-11-10 | ja | 86 |
| Leitzins Reserve Bank of New Zealand (BIS) | NZD | 2026-11-06 | ja | 86 |
| Effektiver Leitzins USA (Fed Funds) | USD | 2026-11-16 | ja | 86 |
| Arbeitslosenquote Australien (OECD) | AUD | 2026-09-01 | ja | 32 |
| Arbeitslosenquote Kanada (OECD) | CAD | 2026-10-01 | ja | 32 |
| Arbeitslosenquote Schweiz (OECD, Quartal) | CHF | 2026-04-01 | ja | 32 |
| Arbeitslosenquote Eurozone (EZB/Eurostat) | EUR | 2026-09-01 | ja | 32 |
| Arbeitslosenquote Großbritannien (OECD) | GBP | 2026-07-01 | ja | 32 |
| Arbeitslosenquote Japan (OECD) | JPY | 2026-09-01 | ja | 32 |
| Arbeitslosenquote Neuseeland (OECD, Quartal) | NZD | 2026-07-01 | ja | 32 |
| Arbeitslosenquote USA (BLS) | USD | 2026-10-01 | ja | 32 |
| Rendite 10-jährige australische Staatsanleihe | AUD | 2026-10-01 | ja | 56 |
| Rendite 10-jährige kanadische Staatsanleihe | CAD | 2026-10-01 | ja | 56 |
| Rendite 10-jährige Schweizer Bundesobligation | CHF | 2026-10-01 | ja | 56 |
| Rendite 10-jährige Bundesanleihe (Proxy Eurozone) | EUR | 2026-10-01 | ja | 56 |
| Rendite 10-jährige britische Staatsanleihe | GBP | 2026-10-01 | ja | 56 |
| Rendite 10-jährige japanische Staatsanleihe | JPY | 2026-10-01 | ja | 56 |
| Rendite 10-jährige neuseeländische Staatsanleihe | NZD | 2026-10-01 | ja | 56 |
| Rendite 10-jährige US-Staatsanleihe | USD | 2026-11-16 | ja | 56 |
| Rendite 2 J. Australien (RBA) | AUD | 2026-11-11 | ja | 24 |
| Rendite 2 J. Kanada (Bank of Canada) | CAD | 2026-11-17 | ja | 24 |
| Rendite 2 J. Euroraum (EZB-Zinsstrukturkurve) | EUR | 2026-11-17 | ja | 24 |
| Rendite 5 J. Großbritannien (Bank of England; kürzeste verfügbare Reihe) | GBP | – | **nein** | 24 |
| Rendite 2 J. Japan (Finanzministerium) | JPY | 2026-11-18 | ja | 24 |
| Rendite 2-jährige US-Staatsanleihe | USD | 2026-11-16 | ja | 36 |
