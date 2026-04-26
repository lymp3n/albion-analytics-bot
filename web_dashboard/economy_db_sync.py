import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, List, Optional, Tuple


def _pg_dollar_to_psycopg(sql: str, params: tuple) -> Tuple[str, tuple]:
    expanded: List[Any] = []
    pattern = re.compile(r"\$(\d+)")

    def repl(match):
        idx = int(match.group(1)) - 1
        if idx < 0 or idx >= len(params):
            raise IndexError(f"SQL placeholder {match.group(0)} out of range for {len(params)} params")
        expanded.append(params[idx])
        return "%s"

    return pattern.sub(repl, sql), tuple(expanded)


def _normalize_postgres_url(url: str) -> str:
    return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url


def _economy_db_url() -> str:
    # Economy DB is intended to be separate. Do NOT fall back to DATABASE_URL
    # (it can be read-only / missing CREATE TABLE privileges in managed deployments).
    url = (os.environ.get("ECON_DATABASE_URL") or "").strip()
    if url:
        return url
    # Safe default for deployments (e.g. Render) where env var might be missing.
    # Prefer a local writable sqlite file under ./data; fall back to /tmp.
    data_dir = os.path.abspath(os.path.join(os.getcwd(), "data"))
    try:
        os.makedirs(data_dir, exist_ok=True)
        test_path = os.path.join(data_dir, "economy.db")
        with open(test_path, "a", encoding="utf-8"):
            pass
        return f"sqlite:///{test_path}"
    except Exception:
        tmp_path = os.path.join(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp", "economy.db")
        return f"sqlite:///{tmp_path}"


@contextmanager
def get_economy_sync_connection() -> Generator[Tuple[Any, str], None, None]:
    url = _economy_db_url()

    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        # Normalize relative paths to absolute, and ensure parent dir exists.
        path = os.path.abspath(path)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn, "sqlite"
        finally:
            conn.close()
        return

    import psycopg2
    import psycopg2.extras

    dsn = _normalize_postgres_url(url)
    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        yield conn, "postgres"
    finally:
        conn.close()


def fetch_all(conn, backend: str, sql: str, params: Optional[tuple] = None) -> List[dict]:
    if backend == "postgres":
        import psycopg2.extras

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    p = params or ()
    if backend == "sqlite":
        q = re.sub(r"\$\d+", "?", sql)
        cur.execute(q, p)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    q, bind = _pg_dollar_to_psycopg(sql, p)
    cur.execute(q, bind)
    return [dict(r) for r in cur.fetchall()]


def fetch_one(conn, backend: str, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
    if backend == "postgres":
        import psycopg2.extras

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    p = params or ()
    if backend == "sqlite":
        q = re.sub(r"\$\d+", "?", sql)
        cur.execute(q, p)
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description] if cur.description else []
        return dict(zip(cols, row))
    q, bind = _pg_dollar_to_psycopg(sql, p)
    cur.execute(q, bind)
    row = cur.fetchone()
    return dict(row) if row else None
