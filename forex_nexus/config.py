"""Konfiguration über Umgebungsvariablen (keine Passwörter im Code)."""

import os

ENV_DATABASE_URL = "FNX_DATABASE_URL"


def database_url() -> str:
    url = os.environ.get(ENV_DATABASE_URL)
    if not url:
        raise RuntimeError(
            f"Umgebungsvariable {ENV_DATABASE_URL} fehlt, "
            "z. B. postgresql://fnx:passwort@localhost:5432/fnx"
        )
    return url
