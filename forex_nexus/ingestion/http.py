"""Einfacher HTTP-Abruf mit Wiederholung bei Netzwerkfehlern."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request

def fetch_text(url: str, retries: int = 4, timeout: int = 90) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            # Bewusst die Standard-Kennung von Python: FRED blockiert unbekannte User-Agents.
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise                      # z. B. 404: Wiederholen hilft nicht
            last = exc
        except (OSError, http.client.HTTPException) as exc:   # Abbruch, Zeitüberschreitung, Reset
            last = exc
        time.sleep(3 * 2 ** attempt)
    raise RuntimeError(f"Abruf fehlgeschlagen nach {retries} Versuchen: {url}") from last
