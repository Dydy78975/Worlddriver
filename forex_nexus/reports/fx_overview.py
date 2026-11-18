"""Phase-1-Bericht: Kursdiagramme aller 28 Paare + Datenqualität als Markdown."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from forex_nexus.fx.crosses import ALL_PAIRS  # noqa: E402

SURFACE, INK, INK_2, GRID, LINE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
CHECK_LABEL = {"gap": "Lücke (≥ 4 Werktage)", "spike": "Spike – Verdacht auf Datenfehler",
               "extreme_move": "Extreme Marktbewegung (Info)", "source_mismatch": "Abweichung FRED/EZB",
               "stale": "Veraltet", "source_revision": "Nachträglich geänderter Wert"}


def plot_pairs(closes: pd.DataFrame, path: Path, start: str = "1999-01-01") -> None:
    data = closes.loc[pd.Timestamp(start).date():]
    fig, axes = plt.subplots(7, 4, figsize=(12, 17), facecolor=SURFACE)
    for ax, sym in zip(axes.flat, ALL_PAIRS):
        s = data[sym].dropna()
        ax.set_facecolor(SURFACE)
        ax.plot(pd.to_datetime(s.index), s.values, color=LINE, linewidth=1.0)
        ax.set_title(f"{sym[:3]}/{sym[3:]}", loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.grid(True, color=GRID, linewidth=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK_2, labelsize=7, length=0)
        ax.xaxis.set_major_locator(mdates.YearLocator(10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(f"28 Währungspaare – Tageskurse FRED H.10 (Mittag New York), {start[:4]} bis {data.index.max():%d.%m.%Y}",
                 x=0.02, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def write_markdown(result: dict, path: Path, chart_name: str, today: date) -> None:
    fred, ecb, findings = result["fred"], result["ecb"], result["findings"]
    counts = Counter(f.check for f in findings)
    lines = [
        "# Phase 1 – Kursdaten und Datenqualität", "",
        f"Erstellt am {today:%d.%m.%Y} · automatisch erzeugt von `python -m forex_nexus report-fx`", "",
        "## Datenbestand", "",
        "| Quelle | Paare | von | bis | Tageswerte |", "|---|---|---|---|---|",
        f"| FRED H.10 + Kreuzkurse | {fred.shape[1]} | {fred.index.min():%d.%m.%Y} | {fred.index.max():%d.%m.%Y} | {int(fred.count().sum()):,} |".replace(",", "."),
        f"| EZB-Referenzkurse | {ecb.shape[1]} | {ecb.index.min():%d.%m.%Y} | {ecb.index.max():%d.%m.%Y} | {int(ecb.count().sum()):,} |".replace(",", "."),
        "", f"![Kursdiagramme]({chart_name})", "",
        "## Befunde der Qualitätsprüfung (ab 04.01.1999)", "",
        "Geprüft wird der Zeitraum seit Einführung des Euro. Ältere FRED-Daten (ab 1971) bleiben gespeichert,",
        "werden aber vorerst nicht für Modelle verwendet (u. a. feste Wechselkurse bis 1973).", "",
        "| Prüfung | Anzahl |", "|---|---|",
        *[f"| {CHECK_LABEL.get(k, k)} | {v} |" for k, v in sorted(counts.items())],
        "" if counts else "Keine Befunde.", "",
        "## Kontrolle FRED gegen EZB (gleiche Tage, EUR-Paare)", "",
        "FRED misst um 12:00 New York, die EZB um 14:15 MEZ – also ca. 4 Stunden früher.",
        "Kleine Unterschiede sind daher normal; große Unterschiede deuten auf Datenfehler oder sehr bewegte Tage hin.", "",
        "| Paar | gemeinsame Tage | mittlere Abweichung | 99-%-Abweichung | Tage > 2 % |", "|---|---|---|---|---|",
        *[f"| {r.symbol} | {r.days} | {r.median_abs_diff_pct:.3f} % | {r.p99_abs_diff_pct:.3f} % | {r.flagged} |"
          for r in result["mismatch_stats"].itertuples()],
        "", "## Einzelbefunde", "",
    ]
    # Extreme Bewegungen je Tag zusammenfassen: meist betrifft ein Ereignis viele Paare gleichzeitig
    moves = [f for f in findings if f.check == "extreme_move"]
    by_day: dict = {}
    for f in moves:
        by_day.setdefault(f.day, []).append(f.symbol)
    lines += ["### Tage mit extremen Marktbewegungen", "",
              "Echte Marktereignisse (die Bewegung bleibt bestehen). Kein Datenfehler, aber wichtig für die Modelle.", "",
              "| Datum | Paare |", "|---|---|"]
    lines += [f"| {d} | {len(s)}: {', '.join(sorted(s))} |" for d, s in sorted(by_day.items())]
    lines += ["", "### Weitere Befunde", ""]
    detail = [f for f in findings if f.check not in ("source_mismatch", "extreme_move")] + [f for f in findings if f.check == "source_mismatch"][:30]
    lines += ["| Prüfung | Paar | Datum | Details |", "|---|---|---|---|"]
    lines += [f"| {CHECK_LABEL.get(f.check, f.check)} | {f.symbol or '–'} | {f.day} | "
              + ", ".join(f"{k}: {v}" for k, v in f.details.items()) + " |"
              for f in sorted(detail, key=lambda f: (f.check, str(f.day)))]
    if counts.get("source_mismatch", 0) > 30:
        lines += ["", f"(Nur die ersten 30 von {counts['source_mismatch']} Abweichungen gezeigt; alle stehen in der Datenbank.)"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
