"""Einfacher HTTP-Abruf mit Wiederholung bei Netzwerkfehlern."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request

class NotFound(Exception):
    """Die Datei existiert bei der Quelle nicht (HTTP 404)."""


def fetch_bytes(url: str, retries: int = 8, timeout: int = 90, base_wait: float = 5.0,
                sleep=time.sleep) -> bytes:
    """Binärdaten laden. 404 -> NotFound. 429/5xx/Verbindungsabbruch -> warten und wiederholen
    (Wartezeit verdoppelt sich, max. 5 Minuten)."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(url) from exc
            if exc.code < 500 and exc.code != 429:
                raise
            last = exc
        except (OSError, http.client.HTTPException) as exc:
            last = exc
        sleep(min(300.0, base_wait * 2 ** attempt))
    raise RuntimeError(f"Abruf fehlgeschlagen nach {retries} Versuchen: {url}") from last


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
