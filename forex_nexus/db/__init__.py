"""Datenbankzugriff und Migrationen."""

import psycopg


def connect(conninfo: str, **kwargs) -> psycopg.Connection:
    """Einheitliche Verbindung: immer UTF-8, unabhängig von der Server-Einstellung."""
    kwargs.setdefault("client_encoding", "utf8")
    return psycopg.connect(conninfo, **kwargs)
