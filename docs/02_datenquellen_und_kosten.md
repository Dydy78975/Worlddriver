# 02 – Datenquellen und Kosten

Stand: 18.11.2026 · Preise **vor Abschluss eines Abos immer auf der Anbieterseite prüfen**.
Mehrere Anbieter veröffentlichen ihre Preise nicht vollständig oder ändern sie häufig.
Die Angaben unten sind mit ihrer Verlässlichkeit gekennzeichnet.

## Ergebnis vorab

**Phase 1 bis 5 lassen sich mit 0 € Datenkosten umsetzen.** Die einzigen laufenden
Kosten sind ein kleiner Server (ca. 5–15 €/Monat) – und auch der ist anfangs optional.
Kostenpflichtige Daten lohnen sich erst, wenn messbar ist, dass sie die Prognosen
verbessern.

## Die 8 Währungen und ihre Zentralbanken

USD (Fed) · EUR (EZB) · JPY (BoJ) · GBP (BoE) · CHF (SNB) · CAD (BoC) · AUD (RBA) · NZD (RBNZ)

## Kostenlose Quellen (empfohlen für den Start)

| Datenart | Quelle | Abdeckung | Hinweis |
|---|---|---|---|
| Wechselkurse täglich | **FRED** (Fed H.10-Reihen, z. B. DEXUSEU, DEXJPUS) | alle 7 USD-Paare, ab 1971/1999 | Mittagskurse New York; Kreuzkurse berechnen wir selbst |
| Wechselkurse täglich | **EZB-Referenzkurse** | EUR gegen alle anderen, ab 1999 | 14:15 MEZ, zweite Quelle zur Kontrolle |
| Wechselkurse OHLC/Tick | **Dukascopy** Historical Data Export | alle 28 Paare, ab ca. 2003 | kostenlos; Nutzungsbedingungen beachten; liefert Hoch/Tief für Volatilität und Ungültigkeits-Level |
| Leitzinsen | **BIS** Central Bank Policy Rates (SDMX-API) | alle 8 Zentralbanken | kostenlos, ohne API-Schlüssel |
| Anleiherenditen USA | **FRED** (DGS2, DGS10 u. a.) | täglich, lange Historie | |
| Anleiherenditen Eurozone | **EZB Data Portal**, Bundesbank | täglich | |
| Renditen GB/JP/CH/CA/AU/NZ | BoE Database, japanisches Finanzministerium, SNB Data Portal, Bank of Canada Valet-API, RBA-Tabellen, RBNZ-Tabellen | täglich, Umfang je Land unterschiedlich | aufwendigste Datenarbeit des Projekts |
| Kurz-/Langfristzinsen einheitlich | **OECD** Data Explorer | monatlich, alle 8 Länder | gute einheitliche Rückfallebene |
| Inflation (CPI) | FRED/**ALFRED** (USA, mit historischen Datenständen), OECD, nationale Statistikämter | monatlich (AU/NZ quartalsweise bzw. teils monatlich) | ALFRED verhindert Revisions-Leakage für US-Daten |
| COT-Positionierung | **CFTC** (Legacy ab 1986, Traders in Financial Futures ab 2006) | EUR, JPY, GBP, CHF, CAD, AUD, NZD, USD-Index | Daten vom Dienstag, Veröffentlichung Freitag 15:30 New York → Verfügbarkeit korrekt abbilden |
| DXY | selbst berechnet aus der offiziellen ICE-Formel (6 Kurse) | täglich | Original-DXY ist ICE-Eigentum; Alternative: Fed Broad Dollar Index (FRED: DTWEXBGS) |
| VIX | FRED (VIXCLS) oder Cboe-CSV | täglich ab 1990 | |
| Zentralbank-Termine | Webseiten der 8 Zentralbanken | Sitzungskalender | halbautomatisch gepflegt |
| Saisonalität | aus den Kursdaten selbst berechnet | – | keine externe Quelle nötig |

## Was kostenlos fehlt (ehrliche Lücken)

1. **Markterwartungen für Zinspfade** (OIS-Kurven, Fed-Funds-Futures historisch).
   Ersatz: Veränderung der 2-Jahres-Rendite. Sie spiegelt die erwarteten Zinsen der
   nächsten zwei Jahre recht gut wider.
2. **Konsensprognosen für Wirtschaftsdaten** („Überraschungen“).
   Ersatz zunächst: Veränderung der Daten selbst statt Abweichung von der Erwartung.
3. **Saubere historische Datenstände (Vintages) außerhalb der USA.**
   Ersatz: Veröffentlichungstermine plus Sicherheitsabstand. Wird im System als
   Einschränkung dokumentiert.

## Kostenpflichtige Anbieter (nur bei nachgewiesenem Mehrwert)

| Anbieter | Was | Preis | Verlässlichkeit der Preisangabe |
|---|---|---|---|
| **Twelve Data** | Forex-Kurse per API | Free: 800 Anfragen/Tag, 8/Minute; bezahlte Pläne laut Drittseiten ab ca. 29 $/Monat | Free-Tarif offiziell bestätigt; bezahlte Preise **nicht offiziell bestätigt** |
| **Massive** (ehemals Polygon.io, seit 10/2025 umbenannt) | Forex + Krypto, 10+ Jahre Historie | „Currencies Business“ offiziell 999 $/Monat; günstigere Forex-Tarife laut Drittseiten ab ca. 29 $/Monat | widersprüchlich, prüfen |
| **Trading Economics** | Makrodaten, Wirtschaftskalender **mit Konsens** | kein Gratis-Tarif; Drittseiten nennen 149–199 $/Monat (Standard) und ~299 $/Monat (Professional) | **nicht offiziell bestätigt**, Preise widersprechen sich |
| Bloomberg / LSEG (Refinitiv) | alles inkl. OIS, Konsens, Vintages | jährlich im fünfstelligen Bereich | nicht relevant für dieses Projekt |

Hinweis: Die offiziellen Preisseiten von Twelve Data, Massive und Trading Economics
konnten aus der aktuellen Entwicklungsumgebung nicht direkt abgerufen werden
(Netzwerkfreigabe fehlt). Die Zahlen stammen aus Suchergebnissen.

**Empfehlung:** Erst ab Phase 6 prüfen, ob ein Wirtschaftskalender mit Konsensdaten
(z. B. Trading Economics) die Prognosen messbar verbessert. Das testen wir mit einer
Probephase, bevor ein Abo dauerhaft läuft.

## Infrastrukturkosten

| Posten | Kosten | Wann nötig |
|---|---|---|
| Entwicklung auf deinem eigenen PC | 0 € | ab sofort |
| Kleiner Linux-Server (z. B. 2–4 CPU, 4–8 GB RAM) bei einem europäischen Hoster | ca. 5–15 €/Monat | sobald das Prognose-Ledger täglich laufen soll (Phase 5) |
| Datenbank PostgreSQL, Python, LightGBM, XGBoost, MLflow | 0 € (Open Source) | – |
| Backup-Speicher | ca. 1–3 €/Monat | ab Phase 5 |
| Optional: KI-Formulierung des Wochenberichts per API | wenige € pro Monat | Phase 8, optional |

## Quellen der Recherche

* [Twelve Data – Pricing](https://twelvedata.com/pricing.md), [Twelve Data – Forex API v2](https://intercom.help/twelvedata/en/articles/12520817-forex-api-v2)
* [Massive – Business Currencies](https://massive.com/business-currencies), [Polygon → Massive Rebrand](https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html), [apis.io – Polygon Plans](https://apis.io/plans/polygon/polygon-plans-pricing/)
* [Trading Economics – API Pricing](https://tradingeconomics.com/api/pricing.aspx), [apis.io – Trading Economics Plans](https://apis.io/plans/tradingeconomics/tradingeconomics-plans-pricing/), [Business Quant – Macro Data Providers](https://businessquant.com/resources/best-macroeconomic-data-providers)
* [Dukascopy – Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/)
* [FRED – Real-Time Periods (ALFRED)](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
* [BIS-Paket-Vignette (Policy Rates Dataset)](https://cran.r-project.org/web/packages/BIS/vignettes/BIS.html)
