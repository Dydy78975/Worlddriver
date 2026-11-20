# Prüfung der Modelle je Währung – Stand 20.11.2026

Automatisch erzeugt von `python -m forex_nexus signals`. 443 Modelle (EUR 50, GBP 50, AUD 68, NZD 58, USD 53, CAD 56, CHF 52, JPY 56). Regeln: [docs/12_signal_abstimmung.md](../../docs/12_signal_abstimmung.md).

## Tag (1D)

**Gültige Einzelmodelle: 0 von 443.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 49,2 % / 51,7 % (23 %) | 51,7 % / 52,8 % (10 %) | nein | 51 % |
| GBP | 49,4 % / 56,8 % (8 %) | 50,3 % / 45,3 % (8 %) | nein | 47 % |
| AUD | 49,9 % / 49,6 % (24 %) | 51,3 % / 50,7 % (16 %) | nein | 52 % |
| NZD | 50,2 % / 49,6 % (39 %) | 50,9 % / 53,5 % (11 %) | nein | 60 % |
| USD | 48,7 % / 52,4 % (14 %) | 50,6 % / 54,4 % (4 %) | nein | 45 % |
| CAD | 50,5 % / 49,3 % (19 %) | 51,5 % / 51,8 % (15 %) | nein | 44 % |
| CHF | 48,2 % / 48,8 % (25 %) | 50,8 % / 45,9 % (6 %) | nein | 47 % |
| JPY | 48,3 % / 51,5 % (14 %) | 51,5 % / 56,4 % (12 %) | nein | 38 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Rendite 2 J. 3 M. | USD | +6,2 % (t 2,6) | +0,9 % (t 0,3) | +0,9 % (t 0,3) | nein |
| Rendite 10 J. | EUR | +4,9 % (t 2,2) | -0,5 % (t -0,2) | -1,0 % (t -0,6) | nein |
| Arbeitslosigkeit 6 M. | EUR | +4,1 % (t 2,1) | +0,8 % (t 0,3) | +1,3 % (t 0,7) | nein |
| Rendite 2 J. 6 M. | EUR | +4,5 % (t 2,0) | -5,0 % (t -2,1) | +2,4 % (t 1,2) | nein |
| US-Rendite 2 J. 1 Monat | JPY | +7,5 % (t 2,0) | -12,3 % (t -2,9) | +0,1 % (t 0,0) | nein |
| Gegen Kleinanleger | AUD | +13,9 % (t 2,0) | +1,5 % (t 0,3) | +2,1 % (t 0,5) | nein |
| Inflationsanstieg 12 M. | USD | +4,3 % (t 1,9) | -2,4 % (t -0,9) | +3,3 % (t 1,2) | nein |
| Rendite 2 J. 6 M. | USD | +4,2 % (t 1,8) | +1,5 % (t 0,6) | -1,1 % (t -0,4) | nein |
| Kreditaufschlag 1 Monat | JPY | +7,3 % (t 1,8) | -7,4 % (t -1,9) | +1,3 % (t 0,3) | nein |
| Arbeitslosigkeit 6 M. | CAD | +4,5 % (t 1,8) | -0,5 % (t -0,2) | +2,2 % (t 1,0) | nein |

## Woche (1W)

**Gültige Einzelmodelle: 0 von 443.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 51,5 % / 46,6 % (52 %) | 49,4 % / 48,5 % (47 %) | nein | 42 % |
| GBP | 49,9 % / 52,0 % (48 %) | 54,2 % / 49,5 % (25 %) | nein | 45 % |
| AUD | 51,5 % / 51,9 % (51 %) | 51,1 % / 54,1 % (41 %) | nein | 34 % |
| NZD | 47,1 % / 52,5 % (44 %) | 50,6 % / 50,6 % (48 %) | nein | 55 % |
| USD | 50,4 % / 49,7 % (40 %) | 50,3 % / 49,5 % (29 %) | nein | 67 % |
| CAD | 50,7 % / 51,4 % (50 %) | 50,8 % / 49,7 % (41 %) | nein | 38 % |
| CHF | 58,4 % / 61,0 % (32 %) | 56,4 % / 59,4 % (47 %) | ja | 42 % |
| JPY | 47,1 % / 49,0 % (39 %) | 53,4 % / 56,1 % (41 %) | nein | 36 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Rendite 2 J. 3 M. | USD | +6,6 % (t 2,9) | +0,6 % (t 0,2) | +0,9 % (t 0,3) | nein |
| Arbeitslosigkeit 6 M. | EUR | +4,6 % (t 2,3) | +0,9 % (t 0,4) | +1,2 % (t 0,7) | nein |
| Rendite 2 J. über Leitzins | USD | +5,1 % (t 2,2) | +1,0 % (t 0,3) | -2,5 % (t -0,8) | nein |
| Rendite 2 J. 6 M. | USD | +4,6 % (t 2,1) | +0,6 % (t 0,2) | -1,9 % (t -0,6) | nein |
| Trend 1 Monat | USD | +4,3 % (t 2,0) | -1,5 % (t -0,6) | +0,4 % (t 0,2) | nein |
| Rendite 10 J. | EUR | +4,7 % (t 2,0) | -0,5 % (t -0,3) | -1,0 % (t -0,6) | nein |
| Inflation | NZD | +6,1 % (t 2,0) | +1,2 % (t 0,3) | -1,5 % (t -0,5) | nein |
| US-Rendite 2 J. 1 Monat | JPY | +7,6 % (t 2,0) | -10,7 % (t -2,6) | +1,0 % (t 0,3) | nein |
| Kreditaufschlag 1 Monat | JPY | +7,6 % (t 1,8) | -8,7 % (t -2,1) | +1,0 % (t 0,3) | nein |
| Inflationsanstieg 12 M. | USD | +4,0 % (t 1,8) | -2,6 % (t -1,0) | +2,8 % (t 1,0) | nein |

## Monat (1M)

**Gültige Einzelmodelle: 0 von 443.**

Kombi-Modell je Währung – Trefferquote (alle Fälle / nur Fälle mit ≥ 10 Prozentpunkten Sicherheit, Anteil dieser Fälle):

| Währung | Bestätigung 2013–2019 | Schlusstest ab 2020 | bestätigt | aktuell P(stärker) |
|---|---|---|---|---|
| EUR | 53,6 % / 51,3 % (46 %) | 52,4 % / 57,9 % (46 %) | nein | 43 % |
| GBP | 52,4 % / 50,0 % (55 %) | 59,8 % / 70,5 % (54 %) | nein | 47 % |
| AUD | 47,6 % / 44,3 % (73 %) | 46,3 % / 52,9 % (62 %) | nein | 33 % |
| NZD | 59,5 % / 59,5 % (44 %) | 52,4 % / 60,0 % (43 %) | nein | 44 % |
| USD | 41,7 % / 38,5 % (46 %) | 42,7 % / 38,7 % (38 %) | nein | 57 % |
| CAD | 45,2 % / 44,0 % (60 %) | 52,4 % / 47,7 % (54 %) | nein | 48 % |
| CHF | 56,0 % / 50,0 % (40 %) | 45,1 % / 47,7 % (54 %) | nein | 57 % |
| JPY | 51,2 % / 59,5 % (50 %) | 56,1 % / 59,5 % (51 %) | nein | 48 % |

Die 10 stärksten Einzelmodelle in der Entdeckung (Rendite pro Jahr nach Kosten, t-Wert):

| Modell | Währung | Entdeckung 1999–2012 | Bestätigung 2013–2019 | Schlusstest ab 2020 | gültig |
|---|---|---|---|---|---|
| Gegenbewegung 1 Woche | GBP | +4,4 % (t 2,5) | -2,1 % (t -0,7) | -0,1 % (t -0,0) | nein |
| Arbeitslosigkeit 3 M. | CAD | +5,9 % (t 2,4) | -4,4 % (t -1,4) | +2,0 % (t 1,1) | nein |
| Inflationsanstieg 3 M. | CAD | +4,5 % (t 2,1) | -1,4 % (t -0,5) | -0,6 % (t -0,4) | nein |
| US-Rendite 2 J. 3 Monate | CHF | +4,6 % (t 2,1) | -2,5 % (t -0,8) | -0,1 % (t -0,1) | nein |
| Rendite 2 J. 3 M. | USD | +4,7 % (t 2,1) | +1,5 % (t 0,6) | +2,6 % (t 0,8) | nein |
| Eisenerz 1 Monat | AUD | +7,3 % (t 1,9) | +1,3 % (t 0,5) | +1,1 % (t 0,4) | nein |
| Arbeitslosigkeit 6 M. | EUR | +3,5 % (t 1,8) | +1,8 % (t 0,9) | +1,9 % (t 1,1) | nein |
| Kreditaufschlag 3 Monate | CHF | +4,0 % (t 1,8) | +2,0 % (t 0,7) | +1,7 % (t 0,9) | nein |
| Trend 1 Monat | NZD | +4,4 % (t 1,7) | -4,6 % (t -1,5) | -4,0 % (t -1,6) | nein |
| Arbeitslosigkeit 6 M. | CAD | +3,9 % (t 1,7) | -0,2 % (t -0,1) | +2,9 % (t 1,9) | nein |

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
| Finanzstress-Index der Chicago Fed (NFCI) | – | 2026-11-13 | ja | 6 |
| Volatilitätsindex VIX (Risikostimmung) | – | 2026-11-16 | ja | 27 |
| Leitzins Reserve Bank of Australia (BIS) | AUD | 2026-11-05 | ja | 86 |
| Leitzins Bank of Canada (BIS) | CAD | 2026-11-09 | ja | 86 |
| Leitzins Schweizerische Nationalbank (BIS) | CHF | 2026-11-10 | ja | 86 |
| EZB-Einlagesatz | EUR | 2026-11-18 | ja | 86 |
| Leitzins Bank of England (BIS) | GBP | 2026-11-09 | ja | 86 |
| Leitzins Bank of Japan (BIS) | JPY | 2026-11-10 | ja | 86 |
| Leitzins Reserve Bank of New Zealand (BIS) | NZD | 2026-11-06 | ja | 86 |
| Effektiver Leitzins USA (Fed Funds) | USD | 2026-11-16 | ja | 86 |
| Kreditaufschlag Unternehmensanleihen BAA gegenüber US-Staatsanleihen | – | 2026-11-18 | ja | 18 |
| Rendite 10 J. Italien (für den Italien-Aufschlag) | – | 2026-10-01 | ja | 6 |
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
| Rendite 2 J. Australien (RBA) | AUD | 2026-11-18 | ja | 24 |
| Rendite 2 J. Kanada (Bank of Canada) | CAD | 2026-11-19 | ja | 24 |
| Rendite 2 J. Euroraum (EZB-Zinsstrukturkurve) | EUR | 2026-11-19 | ja | 24 |
| Rendite 5 J. Großbritannien (Bank of England; kürzeste verfügbare Reihe) | GBP | 2026-11-18 | ja | 24 |
| Rendite 2 J. Japan (Finanzministerium) | JPY | 2026-11-19 | ja | 24 |
| Rendite 2-jährige US-Staatsanleihe | USD | 2026-11-16 | ja | 39 |
