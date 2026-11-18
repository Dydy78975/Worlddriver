# 10 – Stand der Software und Bedienung

Stand: 18.11.2026

## Was jetzt funktioniert

| Baustein | Stand |
|---|---|
| Kursdaten FRED + EZB, alle 28 Paare | läuft, mit Qualitätsprüfung |
| Zinsen (offizielle Leitzinsen via BIS), Renditen, Inflation (BIS), **Arbeitslosenquoten** (alle 8 Währungsräume) | läuft, alle Reihen aktuell |
| COT (CFTC), VIX, Rohstoffe der Rohstoffwährungen | läuft |
| Wirtschaftskalender (Forex Factory) | läuft, Woche |
| **Signal-Prüfung** (43 Signale × 8 Währungen, Tag + Woche) | läuft, siehe [12_signal_abstimmung.md](12_signal_abstimmung.md) |
| **Signal-Abstimmung je Paar** | läuft: geprüfte Abstimmung (derzeit leer) + Fundamental-Abstimmung (25 Signale) |
| Spannen-Prognose (80 %) Tag / Woche / Monat | läuft, trifft im Test in 80 % der Fälle |
| Prognose-Ledger (unveränderlich) + Auswertung | läuft: 168 Prognosen pro Lauf (84 angezeigt, 84 Schattenbetrieb) |
| Website WorlᗡDriver | 5 Seiten: Übersicht, Paar, Signal-Prüfung, Kalender, Datenstand, dazu Rechner |
| Dukascopy (Hoch/Tief, 17:00 New York) | Code fertig; aus der Cloud blockiert → eigener Server nötig |
| A+-Regel-Engine | wartet auf deine 6 Kriterien |

## Wichtigste Ergebnisse (ehrlich)

* **Die Spanne ist gut vorhersagbar:** Die 80-%-Bereiche trafen in allen Horizonten in 80 % der Fälle.
* **Die Richtung nicht:** Kein einziges der 43 Signale besteht die Prüfung für irgendeine Währung,
  weder für den Tag noch für die Woche. Die Mehrheit der Fundamental-Signale lag seit 2020 in 51 % der
  Fälle richtig – Zufall wären 50 %.

## Täglicher Ablauf

```
python -m forex_nexus daily      # Daten laden, prüfen, Spannen prognostizieren, auswerten, Signale prüfen, Website bauen
python -m forex_nexus signals    # nur die Signal-Prüfung (Bericht: reports/signals/README.md)
```

Neue Modellversionen entstehen nur über `train` und werden nur über `promote` (mit Namen) eingesetzt.

## Wichtige Einschränkung bis zum eigenen Server

Die Cloud-Datenbank ist nicht dauerhaft. Code, Berichte und die Website-Vorlage bleiben auf GitHub, aber eine
über Monate wachsende Live-Bilanz braucht eine dauerhafte Datenbank (kleiner Server oder verwaltete Datenbank).
