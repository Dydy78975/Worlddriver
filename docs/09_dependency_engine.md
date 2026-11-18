# 09 – Global Economic Dependency Engine

Stand: 18.11.2026 · Status: Architektur festgelegt, Datenbank umgesetzt (Migration 0003),
Wissensbasis mit 28 Hypothesen geladen, statistische Tests folgen

## 1. Ziel

Die Engine erklärt, **wie** Rohstoffpreise, Handelsströme, Industrienachfrage, Lieferketten und
Geopolitik die 8 Hauptwährungen beeinflussen. Sie prüft, **ob** diese Zusammenhänge historisch
belegbar sind, und erkennt, **wann** sie sich abschwächen oder brechen.

**Grundsatz:** Ein steigender Rohstoffpreis stärkt eine Währung nicht automatisch. Jede
Beziehung ist zuerst eine Hypothese und muss sich in Daten beweisen.

## 2. Bausteine

```
 knowledge/relationships.yaml  (Wissensbasis: 17 Treiber, 28 Beziehungen, Wirkungsketten)
          │ load-knowledge (prüft Format, startet alles als Hypothese)
          ▼
 dep.economy · dep.driver · dep.trade_exposure · dep.relationship
          │
          ▼
 ┌──────────────── Analyse-Läufe (dep.analysis_run) ─────────────────┐
 │ Validierung     – Hypothesen statistisch prüfen                     │
 │ Überwachung     – validierte Beziehungen auf Abschwächung prüfen    │
 │ Entdeckung      – neue Kandidaten in den Daten suchen               │
 └──────────────────────────┬──────────────────────────────────────────┘
                            ▼
 dep.relationship_test (unveränderlich) → dep.relationship_status_log (unveränderlich)
                            │
          ┌─────────────────┴──────────────────┐
          ▼                                    ▼
 Merkmale für die Prognosemodelle      Erklärungen (Wirkungsketten) in
 (nur validierte, vorauslaufende       Prognosen, Wochenbericht, Dashboard
 Beziehungen)                          (ml.forecast_driver)
```

## 3. Was „Währungsstärke“ heißt

Für Beziehungen auf Währungsebene (z. B. „Eisenerz → AUD“) wird die Währung gegen einen
**gleich gewichteten Korb der anderen 7 Hauptwährungen** gemessen. Sonst wäre „AUD steigt“ oft
nur „USD fällt“. Für Paarprognosen werden die Effekte beider Währungen kombiniert.

## 4. Statistische Prüfung

### 4.1 Gleichzeitig vs. vorauslaufend – der wichtigste Unterschied

| Art | Beispiel | Nutzen |
|---|---|---|
| **Gleichzeitig** (Lag 0) | AUD und Eisenerz bewegen sich am selben Tag gemeinsam | **Erklärt** Bewegungen, sagt aber nichts voraus – die Information ist sofort im Kurs |
| **Vorauslaufend** (Lag > 0) | Eisenerz von heute erklärt AUD von morgen | Kann in **Prognosen** einfließen – nur wenn Out-of-Sample bestätigt |

Nur vorauslaufende, validierte Beziehungen werden zu Merkmalen der Prognosemodelle.
Gleichzeitige Beziehungen dienen der Erklärung und der Frage „schon eingepreist?“.

### 4.2 Testverfahren

1. **Zeitliche Ausrichtung:** Jede Reihe nur ab ihrem `available_at`. Monatliche IMF-Rohstoffpreise
   erscheinen ca. 45 Tage nach Monatsende – genau so werden sie behandelt.
2. **Regression der Renditen** (Veränderungen, nicht Niveaus – Niveaus erzeugen Scheinzusammenhänge)
   mit Newey-West-Standardfehlern (robust gegen Autokorrelation), für Lags 0 bis L.
3. **Stabilität:** rollierende Betas (3 Jahre), Teilperioden (z. B. 2000–08, 2009–15, 2016–heute),
   Vorzeichenwechsel, Strukturbruch-Tests (CUSUM, Chow).
4. **Regime-Abhängigkeit:** getrennt nach Risikostimmung (VIX hoch/niedrig), Dollar-Trend,
   Rohstoffboom/-baisse, Zinszyklus.
5. **Out-of-Sample:** Walk-Forward-Vorhersage gegen Referenz 0; Out-of-Sample-R², Trefferquote.
6. **Mehrfachtest-Korrektur:** Bei vielen getesteten Kombinationen entstehen Zufallstreffer.
   Darum Benjamini-Hochberg-Korrektur (`q_value`) und Speicherung der Anzahl Tests je Lauf (`n_tests`).

### 4.3 Status einer Beziehung

| Status | Bedeutung | Kriterium (Startwerte, versioniert) |
|---|---|---|
| `hypothesis` | wirtschaftlich plausibel, noch nicht geprüft | Startzustand |
| `testing` | Prüfung läuft oder ist nötig | z. B. nach Änderung des erwarteten Vorzeichens |
| `validated` | belegt | erwartetes Vorzeichen; HAC-p < 0,05 (Entdeckungen: q < 0,10); in ≥ 2 von 3 Teilperioden gleiches Vorzeichen; Out-of-Sample bestätigt (bei Prognose-Nutzung); **Freigabe durch dich** |
| `weakening` | lässt nach | rollierendes Beta halbiert oder Konfidenzintervall schließt 0 ein; CUSUM-Signal |
| `broken` | gebrochen | signifikanter Vorzeichenwechsel oder zwei Überprüfungen in Folge nicht bestanden |
| `rejected` | verworfen | Hypothese hält Tests nicht stand |

**Sicherheitsregeln in der Datenbank:**
* Der Status lässt sich nur über das Protokoll `dep.relationship_status_log` ändern (mit Begründung).
* „Validiert“ kann **nur eine Person** setzen, und nur mit Verweis auf einen **bestandenen** Test.
* Das System darf Beziehungen eigenständig herabstufen (z. B. auf `weakening`), aber nie aufwerten.
* Tests und Statusprotokoll sind unveränderlich.

### 4.4 Automatische Entdeckung neuer Beziehungen

* Durchsucht alle Kombinationen aus Treiber × Währung × Lag.
* Treffer werden nur **Kandidaten** (`origin = 'discovered'`, Status `hypothesis`) – nie direkt validiert.
* Bedingungen für einen Kandidaten: Signifikanz nach Mehrfachtest-Korrektur, Bestätigung im
  Hold-out-Zeitraum und eine wirtschaftlich plausible Erklärung, die du prüfst.

## 5. „Schon eingepreist?“

Drei Messungen:
1. **Vorlauf:** Hat der Treiber überhaupt einen messbaren Vorlauf? Wenn nicht, ist die Information
   bereits beim Erscheinen im Kurs.
2. **Erklärungslücke:** Erwartete Währungsbewegung (β × Treiberbewegung) im Vergleich zur
   tatsächlichen Bewegung im selben Zeitraum. Hat die Währung schon mehr als erklärt reagiert, gilt
   das Signal als eingepreist.
3. **Überraschung** (später, sobald Konsensdaten verfügbar sind): Nur der unerwartete Teil einer
   Veröffentlichung bewegt Kurse.

Ergebnisse stehen in `dep.relationship_test.priced_in`.

## 6. Verbindung zu den Prognosen

* Validierte, vorauslaufende Beziehungen liefern Merkmale (z. B. „Eisenerz-Rendite 20 Tage“) für
  die Modelle aller drei Horizonte. Für jeden Horizont wird separat getestet, ob das Merkmal hilft.
* Nach jeder Prognose werden die SHAP-Beiträge in `ml.forecast_driver` gespeichert und – wenn das
  Merkmal zu einer Beziehung gehört – mit `relationship_id` verknüpft.
* **Beispiel einer erzeugten Erklärung:**

  > **AUD/USD · Woche · leicht bärisch (Konfidenz: niedrig)**
  > Eisenerz ist in 20 Tagen um 8 % gefallen. Wirkungskette: China kauft weniger Eisenerz →
  > Australiens Exporterlöse sinken → Terms of Trade verschlechtern sich → weniger Nachfrage nach AUD.
  > Status der Beziehung: *validiert seit 03/2027, derzeit stabil*. Bereits eingepreist: zu etwa 60 %.

## 7. Geopolitik

* Ereignisse (Sanktionen, Konflikte, Wahlen, Handelszölle) werden in `ref.event` erfasst.
* Wirkung wird über **Ereignisstudien** gemessen: ungewöhnliche Währungsbewegung um das Ereignis
  mit Konfidenzintervall, verglichen mit normalen Tagen.
* Geopolitische Zusammenhänge bleiben Hypothesen, bis genügend vergleichbare Ereignisse vorliegen.
  Es gibt keine automatische Prognose aus einzelnen Nachrichten.

## 8. Datenlage (geprüft am 18.11.2026)

| Treiber | Quelle | Frequenz | Status |
|---|---|---|---|
| Öl WTI, Öl Brent, Erdgas USA | FRED (EIA) | täglich, ca. 1 Woche Verzögerung | verfügbar |
| Erdgas Europa, LNG Asien, Kohle Australien, Eisenerz, Kupfer, Aluminium, Weizen, Rindfleisch, Holz | FRED (IMF) | monatlich, ca. 45 Tage Verzögerung | verfügbar |
| VIX, breiter Dollar-Index | FRED | täglich | verfügbar |
| **Milchpreise** (Global Dairy Trade) | offen | alle 2 Wochen | **fehlt** |
| **Gold** | offen (z. B. Weltbank) | monatlich/täglich | **fehlt** |
| **Industrieaktivität China** | offen | monatlich | **fehlt** |
| Handelsstruktur (Export-/Importanteile) | UN Comtrade (API mit Registrierung), nationale Statistikämter | jährlich | **offen** |
| Tagesaktuelle Rohstoffe (Futures) | meist kostenpflichtig | täglich | später prüfen |

**Folge für die Tagesprognose:** Monatliche Rohstoffdaten mit 45 Tagen Verzögerung helfen kaum für
`1D`. Für Tag und Woche zählen vor allem tägliche Reihen (Öl, Gas, VIX). Monatsdaten sind für `1M`
und die Erklärungen relevant.

## 9. Wissensbasis bearbeiten

Die Datei [`knowledge/relationships.yaml`](../knowledge/relationships.yaml) ist bewusst lesbar
geschrieben. Änderungen laufen über Git (nachvollziehbar) und werden mit
`python -m forex_nexus load-knowledge` geladen. Dabei gilt:
* neue Beziehungen → `hypothesis`,
* geändertes erwartetes Vorzeichen bei geprüften Beziehungen → zurück auf `testing`,
* nichts wird gelöscht.
