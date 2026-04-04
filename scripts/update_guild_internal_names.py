#!/usr/bin/env python3
"""
One-off: set guilds.name (internal name) for DB ids 1 and 2.

  id 1 → Only Greens
  id 2 → Take a Break,

Run from repo root with DATABASE_URL set (same as bot), e.g.:

  python scripts/update_guild_internal_names.py

Or execute SQL on your host:

  UPDATE guilds SET name = 'Only Greens' WHERE id = 1;
  UPDATE guilds SET name = 'Take a Break,' WHERE id = 2;
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print("DATABASE_URL is not set. Run these on your database:", file=sys.stderr)
        print("  UPDATE guilds SET name = 'Only Greens' WHERE id = 1;", file=sys.stderr)
        print("  UPDATE guilds SET name = 'Take a Break,' WHERE id = 2;", file=sys.stderr)
        return 1

    n1, n2 = "Only Greens", "Take a Break,"

    if url.startswith("sqlite"):
        import sqlite3

        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE guilds SET name = ? WHERE id = 1", (n1,))
        conn.execute("UPDATE guilds SET name = ? WHERE id = 2", (n2,))
        conn.commit()
        for row in conn.execute("SELECT id, name FROM guilds WHERE id IN (1, 2) ORDER BY id"):
            print(row)
        conn.close()
    else:
        import psycopg2

        dsn = url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("UPDATE guilds SET name = %s WHERE id = 1", (n1,))
        cur.execute("UPDATE guilds SET name = %s WHERE id = 2", (n2,))
        conn.commit()
        cur.execute("SELECT id, name FROM guilds WHERE id IN (1, 2) ORDER BY id")
        for row in cur.fetchall():
            print(row)
        conn.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
