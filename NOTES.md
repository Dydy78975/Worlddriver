# Übergabe-Notiz – WorlᗡDriver / FOREX NEXUS AI

Stand: 20.11.2026 · Branch `claude/forex-nexus-ai-platform-6ez50s` · Forex-Website: https://claude.ai/artifact/HbAihgkuZ3q8qsu7xAWUBj · Krypto-Website: https://claude.ai/artifact/7RnuArdUCSafvvU8t11fSJ (beide privat)

## Ziel
- Fundamentales Trading-Tool + Prognose-Plattform **nur** für USD, EUR, JPY, GBP, CHF, CAD, AUD, NZD und ihre 28 Paare.
- Prognosen Tag (1) / Woche (5) / Monat (20 Handelstage), je **eigenes** Modell, unveränderlich gespeichert, später gegen die Realität gemessen.
- Fundamentale Wochen- und Tagesansicht: COT, Saisonalität, Kalender (rote Ordner), Zinsen, Währungsstärke, Konfluenz je Paar.
- Nutzer: Deutsch, keine Programmierkenntnisse, nutzt iPhone/iPad. Design-Vorbild: lenvra.de/Primeedge (nur Anregung, nicht kopieren).

## Fertig
- PostgreSQL-Schema (Migrationen 0001–0006): bitemporale Rohdaten (`available_at`), unveränderliches Ledger (Trigger), Modell-Registry, Dependency-Engine, COT, Kalender, Zinsen.
- Daten: FRED H.10 + Kreuzkurse (28 Paare ab 1999), EZB-Kurse, 14 Rohstoff-/Risikoreihen, VIX, CFTC-COT ab 2005, Forex-Factory-Wochenkalender, Zinsen/Renditen/CPI (FRED).
- Engine: Referenz, Schwankungs-Referenz, LogReg, LightGBM; Walk-Forward 2006–heute mit Purging/Embargo, Hold-out ab 2022; Quantile/Intervalle; Ledger, Auswertung.
- Dependency-Engine: 28 Hypothesen (`knowledge/relationships.yaml`), HAC-Tests, Teilperioden, OOS, Benjamini-Hochberg.
- Fundamentals: COT-Index (Commercials/Spekulanten/Kleinanleger), Saisonalität + Jahresverlauf + Screener (Binomialtest, Bonferroni), Konfluenz je Paar, Wochenaussage, Marktstimmung, Zinsen & Carry; alle Signale historisch geprüft.
- Website (eine HTML-Datei): Cockpit, Heute, Währungen, Paare (Matrix + Checkliste), Paar-Seite (Woche/Tage), Kalender (Countdown), COT, Saisonalität, Prognosen, Tracker, Zinsen, Makro, Rechner, Weltkarte, Daten. iPad: feste Seitenleiste.
- 96 Tests grün (lokal + GitHub Actions). Täglicher Check: geplante Aufgabe `trig_017cgKCoLFTF76c2subGa5aC`, 5:36 Europe/Berlin, läuft in dieser Sitzung.

## Krypto (neu, 20.11.2026)
- Wunsch des Nutzers: wenn Forex wenig hergibt, Krypto-Website. `forex_nexus/crypto/` (data, analysis, site), Vorlage `site/crypto_template.html`, Befehl `crypto-site [--offline]`, Doku `docs/12_krypto.md`, Tests `tests/test_crypto.py`.
- Ergebnis: Schwankungsspanne hält; Trendregeln begrenzen vor allem Verluste; Fear & Greed, COT, Saisonalität ohne Vorteil.
- Netz: `data-api.binance.vision`, `api.alternative.me` freigegeben.

## Gerade in Arbeit
- Warten auf Design-Feedback des Nutzers zu Version 7 der Website (Ziel: „so sauber wie die Fotos“).

## Offen / bekannte Probleme
- **Kein dauerhafter Betrieb:** Cloud-DB ist temporär (`/var/tmp/fnxw`, Port 5495, DB `fnx_check`) → echte Live-Bilanz braucht Server oder verwaltete DB.
- Kurse = FRED-Mittagskurse, nur wöchentlich aktualisiert; Dukascopy (Hoch/Tief, 17:00 NY) blockiert die Cloud-IP → auf eigenem Server laden (`download-dukascopy`).
- Inflation nur für USA/Eurozone aktuell; GB/JP/CH/CA/AU/NZ veraltet (OECD auf FRED endet) → nationale Statistikämter anbinden.
- Modelle wurden von Claude zur Inbetriebnahme eingesetzt → Bestätigung durch Nutzer ausstehend.
- Fehlende Treiberdaten: Milchpreise (GDT), Gold, China-Aktivität.
- A+-Regel-Engine: wartet auf die 6 Kriterien des Nutzers.
- Richtungsmodelle schlagen die Referenzen nicht; COT/Saison/Konfluenz historisch ≈ Zufall (wird offen angezeigt).
- Aufräumen: `site/template.html` enthält ungenutzte alte Funktionen (z. B. `viewOverview`, `renderStrength`).
- Geplante Aufgabe hat keine Connectors; läuft deshalb an diese Sitzung gebunden.

## Wichtige Dateien
- `db/migrations/000X_*.sql` – Schema; nie ändern, nur neue Datei anlegen (Prüfsummenschutz).
- `forex_nexus/__main__.py` – CLI: `migrate`, `ingest-fx`, `ingest-fred-series`, `ingest-cot`, `ingest-calendar`, `load-knowledge`, `train`, `promote`, `forecast`, `evaluate`, `validate-dependencies`, `build-site`, `daily`.
- `forex_nexus/ingestion/` – Abrufe (FRED, EZB, Dukascopy, CFTC, Kalender, HTTP mit Retry).
- `forex_nexus/models/` – Merkmale (point-in-time) und Engine (Walk-Forward, Kennzahlen).
- `forex_nexus/ledger/pipeline.py` – train/promote/forecast/evaluate.
- `forex_nexus/fundamentals/` – COT, Saison, Konfluenz (`analysis.py`), Screener/Stimmung (`extras.py`), Zinsen (`rates.py`), Export (`export.py`).
- `forex_nexus/dependencies/` – Wissensbasis laden, statistische Prüfung.
- `forex_nexus/reports/site_export.py` – sammelt Daten → `site/index.html` aus `site/template.html`.
- `knowledge/relationships.yaml` – Wirtschaftsbeziehungen (für Nutzer lesbar).
- `docs/01–11*.md`, `docs/ANLEITUNG.md` – Planung, Methodik, Ergebnisse, iPhone-Anleitung.
- `tests/` – pytest; `conftest.py` startet temporäres PostgreSQL 16 (als root via `runuser postgres`).

## Regeln und Entscheidungen
- Sprache: Python 3.12+ (lokal 3.13), PostgreSQL 16, psycopg 3, pandas, scikit-learn, LightGBM, statsmodels; Website = Vanilla JS/SVG in einer Datei (keine Frameworks), Schriften Inter / Inter Tight / JetBrains Mono.
- Alle Texte für den Nutzer auf Deutsch, verständlich, deutsches Zahlenformat.
- Keine Zukunftsdaten: jeder Wert mit `available_at`; COT erst ab Freitag 15:30 NY; VIX vom Vortag; Saison nur Vorjahre.
- Ehrlichkeit: Signale nur mit historischer Trefferquote zeigen; nie Modelle/Schwellen/Tests ändern, damit Ergebnisse besser aussehen; Schwankungs-Referenz gegen Scheinvorteile.
- Kein automatisches Umstellen im Live-Betrieb: neue Modelle nur über `train` + `promote` (mit Namen); täglicher Lauf nutzt eingefrorenen `train_end`.
- „Validiert“ bei Wirtschaftsbeziehungen nur durch eine Person mit bestandenem Test (DB-Trigger).
- Repo ist **öffentlich**: `site/index.html` und Dukascopy-Daten (`data/`) nicht committen (Lizenz: nur privat).
- Abrufe mit ehrlicher Programmkennung, nie als Browser tarnen.
- Netzwerk-Umgebung „worlddriver“: FRED, EZB, Dukascopy, CFTC, nfs.faireconomy.media freigegeben.
- Nie auf `main` pushen; PRs nur auf Wunsch; Commits mit Co-Authored-By-Zeile.
