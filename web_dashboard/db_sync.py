import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, List, Optional, Tuple


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


@contextmanager
def get_sync_connection() -> Generator[Tuple[Any, str], None, None]:
    """
    Yields (connection, backend) where backend is 'postgres' or 'sqlite'.
    """
    url = os.environ.get("DATABASE_URL", "") or ""
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn, "sqlite"
        finally:
            conn.close()
        return

    import psycopg2
    import psycopg2.extras

    dsn = _normalize_postgres_url(url)
    conn = psycopg2.connect(dsn, connect_timeout=10)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn, "postgres"
    finally:
        conn.close()


def rows_to_dicts(rows: List[Any]) -> List[dict]:
    out = []
    for r in rows:
        if hasattr(r, "keys"):
            out.append(dict(r))
        else:
            out.append(dict(r))
    return out


def _sql_for_backend(sql: str, backend: str) -> str:
    if backend != "sqlite":
        return sql
    return re.sub(r"\$\d+", "?", sql)


def fetch_all(conn, backend: str, sql: str, params: Optional[tuple] = None) -> List[dict]:
    cur = conn.cursor()
    q = _sql_for_backend(sql, backend)
    cur.execute(q, params or ())
    if backend == "sqlite":
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return rows_to_dicts(cur.fetchall())


def fetch_one(conn, backend: str, sql: str, params: Optional[tuple] = None) -> Optional[dict]:
    cur = conn.cursor()
    q = _sql_for_backend(sql, backend)
    cur.execute(q, params or ())
    row = cur.fetchone()
    if not row:
        return None
    if backend == "sqlite":
        cols = [d[0] for d in cur.description] if cur.description else []
        return dict(zip(cols, row))
    return dict(row)
