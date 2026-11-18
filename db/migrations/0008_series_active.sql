-- Migration 0008: Datenreihen ohne Nutzen nicht mehr abrufen.
-- Grundlage: Signal-Prüfung vom 18.11.2026 (docs/12_signal_abstimmung.md). Diese Reihen speisten nur die
-- entfernte Dependency-Engine (gleichzeitige Zusammenhänge ohne Vorlauf) und kein Signal. Gespeicherte
-- Werte bleiben erhalten; active = TRUE setzt eine Reihe jederzeit wieder in Betrieb.

ALTER TABLE ref.series ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE;

UPDATE ref.series SET active = FALSE
WHERE source_code IN ('DCOILBRENTEU', 'DHHNGSP', 'PNGASEUUSDM', 'PNGASJPUSDM', 'PALUMUSDM', 'PWHEAMTUSDM', 'DTWEXBGS');
