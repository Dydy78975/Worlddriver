# Krypto-Seite (WorlᗡDriver Krypto)

Bauen: `python -m forex_nexus crypto-site` (lädt frisch) bzw. `crypto-site --offline` (Zwischenspeicher `data/crypto/raw.pkl`).
Ergebnis: `site/crypto/index.html` + `data.json` (nicht im Repository – Daten Dritter, nur privat).

## Daten (kostenlos, ohne Schlüssel)
- Tageskerzen BTC, ETH, BNB, SOL, XRP, DOGE, ADA, LINK gegen USDT: `data-api.binance.vision` (Schluss 00:00 UTC; laufende Kerze wird verworfen).
- Fear & Greed Index: `api.alternative.me` (ab Feb. 2018).
- CFTC-COT für CME-Bitcoin (133741) und CME-Ether (146021): `publicreporting.cftc.gov`.
- US-Termine: Forex-Factory-Wochenfeed (nur USD, hohe/mittlere Wichtigkeit).

## Prüfungen und Ergebnisse (Stand 19.11.2026)
| Regel | Prüfung | Ergebnis |
|---|---|---|
| 80-%-Spanne (EWMA-Schwankung) | Walk-Forward, Quantile nur aus Vergangenheit | trifft 78–82 % → **hält** |
| Trend: Kurs über 200-Tage-Linie / 30-Tage-Momentum | Umsetzung am Folgetag, 0,1 % Gebühr; 5 Längen je Regel, 8 Coins, zwei Zeithälften | kleinerer Maximalverlust 60/80, besserer Sharpe 48/80, in der jüngeren Hälfte schwächer → **teilweise** |
| Fear & Greed < 20 / > 80 | BTC 30 Tage danach, nicht überlappend, Binomialtest | 52 % vs. 54 % Basis → **kein Vorteil** |
| COT-Spekulanten-Index > 80 / < 20 | 4 Wochen ab Veröffentlichungs-Freitag, nicht überlappend | p ≥ 0,21 → **kein Vorteil** |
| Saisonalität Monate / Wochentage | 9 Jahre; Bonferroni über 7 Wochentage | Monate Zufall; ETH-Samstag auffällig (57 %), aber ohne größere Durchschnittsrendite → **kein nutzbarer Vorteil** |

Grenzen: nur heute existierende Coins (Überlebens-Verzerrung), keine Steuern/Slippage, Vergangenheit ≠ Zukunft.
