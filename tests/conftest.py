"""Test-Datenbank.

* Ist FNX_TEST_DATABASE_URL gesetzt (z. B. auf GitHub), wird diese Datenbank genutzt.
* Sonst startet der Test eine temporäre PostgreSQL-Instanz und löscht sie danach.

Jeder Test bekommt eine frisch migrierte, leere Datenbank.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest

from forex_nexus.db.migrate import migrate


def _pg_bin() -> Path:
    found = shutil.which("initdb")
    if found:
        return Path(found).parent
    candidates = sorted(Path("/usr/lib/postgresql").glob("*/bin/initdb"), reverse=True)
    if not candidates:
        pytest.skip("Keine PostgreSQL-Installation gefunden und FNX_TEST_DATABASE_URL nicht gesetzt")
    return candidates[0].parent


def _run(cmd: list[str]) -> None:
    # PostgreSQL verweigert den Start als root -> dann als Benutzer 'postgres'.
    if os.geteuid() == 0:
        cmd = ["runuser", "-u", "postgres", "--", *cmd]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} fehlgeschlagen:\n{result.stderr}")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def admin_url():
    external = os.environ.get("FNX_TEST_DATABASE_URL")
    if external:
        yield external
        return

    bindir = _pg_bin()
    tmp = Path(tempfile.mkdtemp(prefix="fnx-pg-", dir="/var/tmp" if Path("/var/tmp").exists() else None))
    if os.geteuid() == 0:
        shutil.chown(tmp, "postgres", "postgres")
    data = tmp / "data"
    port = _free_port()
    _run([str(bindir / "initdb"), "-D", str(data), "-E", "UTF8", "-A", "trust", "-U", "postgres"])
    _run([str(bindir / "pg_ctl"), "-D", str(data), "-w", "-l", str(tmp / "log"),
          "-o", f"-p {port} -k {tmp} -c listen_addresses=''", "start"])
    try:
        yield f"postgresql://postgres@/postgres?host={tmp}&port={port}"
    finally:
        _run([str(bindir / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"])
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def db_url(admin_url):
    """Eigene, frisch migrierte Datenbank pro Test."""
    name = f"fnx_test_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = psycopg.conninfo.make_conninfo(admin_url, dbname=name)
    migrate(url)
    try:
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def conn(db_url):
    with psycopg.connect(db_url, autocommit=True) as c:
        yield c
