from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from services.pricing_client import get_item_price
from web_dashboard.economy_db_sync import fetch_all, fetch_one


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_economy_schema(conn, backend: str) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_accounts (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_routing_rules (
                category TEXT PRIMARY KEY,
                debit_account TEXT NOT NULL,
                credit_account TEXT NOT NULL,
                require_approval BOOLEAN DEFAULT FALSE,
                tag TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_journal_entries (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT NOT NULL,
                amount BIGINT NOT NULL,
                description TEXT,
                actor TEXT,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'posted'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_journal_lines (
                id SERIAL PRIMARY KEY,
                entry_id INTEGER NOT NULL REFERENCES econ_journal_entries(id) ON DELETE CASCADE,
                account_code TEXT NOT NULL,
                side TEXT NOT NULL,
                amount BIGINT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_guild_bonus_tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                reward_amount BIGINT NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_guild_bonus_awards (
                id SERIAL PRIMARY KEY,
                task_id INTEGER REFERENCES econ_guild_bonus_tasks(id) ON DELETE SET NULL,
                player_nickname TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reward_total BIGINT NOT NULL,
                approved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_game_log_imports (
                id SERIAL PRIMARY KEY,
                log_type TEXT NOT NULL,
                rows_count INTEGER NOT NULL,
                summary_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_accounts (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_routing_rules (
                category TEXT PRIMARY KEY,
                debit_account TEXT NOT NULL,
                credit_account TEXT NOT NULL,
                require_approval INTEGER DEFAULT 0,
                tag TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                actor TEXT,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'posted'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_journal_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                account_code TEXT NOT NULL,
                side TEXT NOT NULL,
                amount INTEGER NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES econ_journal_entries(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_guild_bonus_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                reward_amount INTEGER NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_guild_bonus_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                player_nickname TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reward_total INTEGER NOT NULL,
                approved_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES econ_guild_bonus_tasks(id) ON DELETE SET NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_game_log_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_type TEXT NOT NULL,
                rows_count INTEGER NOT NULL,
                summary_json TEXT NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    conn.commit()
    _seed_defaults(conn, backend)


def _seed_defaults(conn, backend: str) -> None:
    cur = conn.cursor()
    accounts = [
        ("1000", "Guild Cash (silver)", "asset"),
        ("1100", "Guild Energy", "asset"),
        ("1200", "Inventory / Gear", "asset"),
        ("1300", "Receivables", "asset"),
        ("2000", "Payables", "liability"),
        ("3000", "Guild Capital", "equity"),
        ("4000", "Content Revenue", "income"),
        ("4100", "Gear Sale Revenue", "income"),
        ("4200", "Rent Revenue", "income"),
        ("4300", "Tax Revenue", "income"),
        ("4400", "Penalty Revenue", "income"),
        ("4500", "Donations", "income"),
        ("5000", "COGS", "expense"),
        ("5100", "Rent Expense", "expense"),
        ("5200", "Rewards Expense", "expense"),
        ("5300", "Consumables/Repairs", "expense"),
        ("6000", "Rounding / Reconciliation", "expense"),
    ]
    for code, name, kind in accounts:
        if backend == "postgres":
            cur.execute(
                """
                INSERT INTO econ_accounts (code, name, kind) VALUES (%s, %s, %s)
                ON CONFLICT (code) DO NOTHING
                """,
                (code, name, kind),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO econ_accounts (code, name, kind) VALUES (?, ?, ?)",
                (code, name, kind),
            )

    rules = [
        ("deposit", "1000", "3000", False, "capital_in"),
        ("withdrawal", "3000", "1000", True, "capital_out"),
        ("content_income", "1000", "4000", False, "content"),
        ("buy_gear", "1200", "1000", False, "gear"),
        ("reward_payout", "5200", "1000", True, "rewards"),
    ]
    for category, dt, kt, need_approval, tag in rules:
        if backend == "postgres":
            cur.execute(
                """
                INSERT INTO econ_routing_rules (category, debit_account, credit_account, require_approval, tag)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (category) DO NOTHING
                """,
                (category, dt, kt, need_approval, tag),
            )
        else:
            cur.execute(
                """
                INSERT OR IGNORE INTO econ_routing_rules (category, debit_account, credit_account, require_approval, tag)
                VALUES (?, ?, ?, ?, ?)
                """,
                (category, dt, kt, 1 if need_approval else 0, tag),
            )
    conn.commit()


def _insert_entry(conn, backend: str, category: str, amount: int, description: str, actor: str, source: str, status: str) -> int:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_journal_entries (category, amount, description, actor, source, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (category, amount, description, actor, source, status),
        )
        return int(cur.fetchone()[0])
    cur.execute(
        """
        INSERT INTO econ_journal_entries (category, amount, description, actor, source, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (category, amount, description, actor, source, status),
    )
    return int(cur.lastrowid)


def _insert_line(conn, backend: str, entry_id: int, account_code: str, side: str, amount: int) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            "INSERT INTO econ_journal_lines (entry_id, account_code, side, amount) VALUES (%s, %s, %s, %s)",
            (entry_id, account_code, side, amount),
        )
    else:
        cur.execute(
            "INSERT INTO econ_journal_lines (entry_id, account_code, side, amount) VALUES (?, ?, ?, ?)",
            (entry_id, account_code, side, amount),
        )


def _validate_double_entry(lines: List[Tuple[str, str, int]]) -> None:
    debit = sum(int(a) for _, side, a in lines if side == "debit")
    credit = sum(int(a) for _, side, a in lines if side == "credit")
    if debit != credit:
        raise ValueError("ERR_UNBALANCED: debit and credit sums must match")


def create_routed_operation(
    conn,
    backend: str,
    *,
    category: str,
    amount: int,
    description: str = "",
    actor: str = "",
    source: str = "manual",
) -> dict:
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Amount must be positive")
    rule = fetch_one(
        conn,
        backend,
        "SELECT category, debit_account, credit_account, require_approval, tag FROM econ_routing_rules WHERE category = $1",
        (category,),
    )
    if not rule:
        raise ValueError(f"Unknown category: {category}")
    status = "pending" if bool(rule.get("require_approval")) else "posted"
    entry_id = _insert_entry(conn, backend, category, amount, description, actor, source, status)
    lines = [(rule["debit_account"], "debit", amount), (rule["credit_account"], "credit", amount)]
    _validate_double_entry(lines)
    for acc, side, a in lines:
        _insert_line(conn, backend, entry_id, acc, side, a)
    conn.commit()
    return {"entry_id": entry_id, "status": status, "category": category, "amount": amount}


def list_recent_entries(conn, backend: str, limit: int = 120) -> List[dict]:
    lim = max(10, min(int(limit), 500))
    rows = fetch_all(
        conn,
        backend,
        f"""
        SELECT e.id, e.created_at, e.category, e.amount, e.description, e.actor, e.source, e.status,
               SUM(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END) AS debit_sum,
               SUM(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END) AS credit_sum
        FROM econ_journal_entries e
        LEFT JOIN econ_journal_lines l ON l.entry_id = e.id
        GROUP BY e.id
        ORDER BY e.id DESC
        LIMIT {lim}
        """,
        (),
    )
    return rows


def list_tasks(conn, backend: str) -> List[dict]:
    return fetch_all(
        conn,
        backend,
        """
        SELECT id, title, description, reward_amount, active, created_at
        FROM econ_guild_bonus_tasks
        ORDER BY id DESC
        """,
        (),
    )


def upsert_task(conn, backend: str, *, task_id: Optional[int], title: str, description: str, reward_amount: int, active: bool) -> dict:
    cur = conn.cursor()
    reward_amount = int(reward_amount)
    if reward_amount <= 0:
        raise ValueError("reward_amount must be positive")
    if not title.strip():
        raise ValueError("title is required")
    if task_id:
        if backend == "postgres":
            cur.execute(
                """
                UPDATE econ_guild_bonus_tasks
                SET title=%s, description=%s, reward_amount=%s, active=%s
                WHERE id=%s
                """,
                (title.strip(), description.strip(), reward_amount, bool(active), int(task_id)),
            )
        else:
            cur.execute(
                """
                UPDATE econ_guild_bonus_tasks
                SET title=?, description=?, reward_amount=?, active=?
                WHERE id=?
                """,
                (title.strip(), description.strip(), reward_amount, 1 if active else 0, int(task_id)),
            )
        conn.commit()
        return {"id": int(task_id), "updated": True}

    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_guild_bonus_tasks (title, description, reward_amount, active)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (title.strip(), description.strip(), reward_amount, bool(active)),
        )
        new_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            """
            INSERT INTO econ_guild_bonus_tasks (title, description, reward_amount, active)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), description.strip(), reward_amount, 1 if active else 0),
        )
        new_id = int(cur.lastrowid)
    conn.commit()
    return {"id": new_id, "created": True}


def delete_task(conn, backend: str, task_id: int) -> int:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute("DELETE FROM econ_guild_bonus_tasks WHERE id=%s", (int(task_id),))
    else:
        cur.execute("DELETE FROM econ_guild_bonus_tasks WHERE id=?", (int(task_id),))
    conn.commit()
    return int(cur.rowcount or 0)


def award_task_completion(
    conn,
    backend: str,
    *,
    task_id: int,
    player_nickname: str,
    quantity: int,
    approved_by: str,
    note: str = "",
) -> dict:
    task = fetch_one(
        conn,
        backend,
        "SELECT id, title, reward_amount, active FROM econ_guild_bonus_tasks WHERE id=$1",
        (int(task_id),),
    )
    if not task:
        raise ValueError("Task not found")
    if int(quantity) <= 0:
        raise ValueError("quantity must be positive")
    if not player_nickname.strip():
        raise ValueError("player_nickname is required")
    reward_total = int(task["reward_amount"]) * int(quantity)

    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_guild_bonus_awards (task_id, player_nickname, quantity, reward_total, approved_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (int(task_id), player_nickname.strip(), int(quantity), reward_total, approved_by.strip()),
        )
        award_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            """
            INSERT INTO econ_guild_bonus_awards (task_id, player_nickname, quantity, reward_total, approved_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(task_id), player_nickname.strip(), int(quantity), reward_total, approved_by.strip()),
        )
        award_id = int(cur.lastrowid)

    # Accrual: expense + payable.
    entry_id = _insert_entry(
        conn,
        backend,
        "guild_bonus_reward",
        reward_total,
        f"Task #{task_id} x{quantity} for {player_nickname}. {note}".strip(),
        approved_by.strip(),
        "dashboard_admin",
        "posted",
    )
    lines = [("5200", "debit", reward_total), ("2000", "credit", reward_total)]
    _validate_double_entry(lines)
    for acc, side, amt in lines:
        _insert_line(conn, backend, entry_id, acc, side, amt)
    conn.commit()
    return {"award_id": award_id, "entry_id": entry_id, "reward_total": reward_total}


def list_bonus_awards(conn, backend: str, limit: int = 120) -> List[dict]:
    lim = max(10, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT a.id, a.task_id, t.title AS task_title, a.player_nickname, a.quantity, a.reward_total, a.approved_by, a.created_at
        FROM econ_guild_bonus_awards a
        LEFT JOIN econ_guild_bonus_tasks t ON t.id = a.task_id
        ORDER BY a.id DESC
        LIMIT {lim}
        """,
        (),
    )


def list_routing_rules(conn, backend: str) -> List[dict]:
    return fetch_all(
        conn,
        backend,
        """
        SELECT category, debit_account, credit_account, require_approval, tag
        FROM econ_routing_rules
        ORDER BY category
        """,
        (),
    )


def upsert_routing_rule(
    conn,
    backend: str,
    *,
    category: str,
    debit_account: str,
    credit_account: str,
    require_approval: bool = False,
    tag: str = "",
) -> None:
    if not category.strip() or not debit_account.strip() or not credit_account.strip():
        raise ValueError("category, debit_account, credit_account are required")
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_routing_rules (category, debit_account, credit_account, require_approval, tag)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (category) DO UPDATE
            SET debit_account=EXCLUDED.debit_account,
                credit_account=EXCLUDED.credit_account,
                require_approval=EXCLUDED.require_approval,
                tag=EXCLUDED.tag
            """,
            (category.strip(), debit_account.strip(), credit_account.strip(), bool(require_approval), tag.strip() or None),
        )
    else:
        cur.execute(
            """
            INSERT INTO econ_routing_rules (category, debit_account, credit_account, require_approval, tag)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category) DO UPDATE SET
                debit_account=excluded.debit_account,
                credit_account=excluded.credit_account,
                require_approval=excluded.require_approval,
                tag=excluded.tag
            """,
            (category.strip(), debit_account.strip(), credit_account.strip(), 1 if require_approval else 0, tag.strip() or None),
        )
    conn.commit()


def import_game_log_csv(conn, backend: str, *, log_type: str, content: str) -> dict:
    if log_type not in ("silver", "energy"):
        raise ValueError("log_type must be silver or energy")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("CSV content is required")

    rdr = csv.DictReader(io.StringIO(content))
    rows = [r for r in rdr]
    deposits = 0
    withdrawals = 0
    dep_sum = 0
    wd_sum = 0
    for r in rows:
        try:
            amt = int(float(str(r.get("Amount", "0")).strip().replace(",", "")))
        except ValueError:
            continue
        if amt >= 0:
            deposits += 1
            dep_sum += amt
        else:
            withdrawals += 1
            wd_sum += abs(amt)
    summary = {
        "log_type": log_type,
        "rows": len(rows),
        "deposits_count": deposits,
        "withdrawals_count": withdrawals,
        "deposits_sum": dep_sum,
        "withdrawals_sum": wd_sum,
        "imported_at_utc": _utc_now(),
    }
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_game_log_imports (log_type, rows_count, summary_json)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (log_type, len(rows), json.dumps(summary)),
        )
        import_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            "INSERT INTO econ_game_log_imports (log_type, rows_count, summary_json) VALUES (?, ?, ?)",
            (log_type, len(rows), json.dumps(summary)),
        )
        import_id = int(cur.lastrowid)
    conn.commit()
    summary["import_id"] = import_id
    return summary


def list_game_log_imports(conn, backend: str, limit: int = 30) -> List[dict]:
    lim = max(1, min(int(limit), 200))
    rows = fetch_all(
        conn,
        backend,
        f"""
        SELECT id, log_type, rows_count, summary_json, imported_at
        FROM econ_game_log_imports
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )
    out = []
    for r in rows:
        rec = dict(r)
        try:
            rec["summary"] = json.loads(rec.get("summary_json") or "{}")
        except Exception:
            rec["summary"] = {}
        out.append(rec)
    return out


def economy_kpis(conn, backend: str) -> dict:
    accounts = fetch_all(conn, backend, "SELECT code, name, kind FROM econ_accounts ORDER BY code", ())
    total_entries = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_journal_entries", ())
    total_tasks = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_guild_bonus_tasks", ())
    total_awards = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_guild_bonus_awards", ())
    pending = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_journal_entries WHERE status='pending'", ())
    rewards_sum = fetch_one(conn, backend, "SELECT COALESCE(SUM(reward_total),0) AS s FROM econ_guild_bonus_awards", ())
    return {
        "accounts_count": len(accounts),
        "entries_count": int((total_entries or {}).get("c") or 0),
        "tasks_count": int((total_tasks or {}).get("c") or 0),
        "awards_count": int((total_awards or {}).get("c") or 0),
        "pending_entries": int((pending or {}).get("c") or 0),
        "awards_total": int((rewards_sum or {}).get("s") or 0),
    }


def fetch_market_price(item_id: str, location: str, quality: int) -> dict:
    data, err, stale = get_item_price(item_id=item_id, location=location, quality=quality)
    return {"ok": bool(data), "data": data, "error": err, "stale": bool(stale)}
