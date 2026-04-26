from __future__ import annotations

import csv
import io
import json
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from services.pricing_client import get_item_price, get_item_price_24h_trimmed_mean, search_item_ids
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_audit_log (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mutation_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                actor TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_import_discrepancies (
                id SERIAL PRIMARY KEY,
                import_id INTEGER REFERENCES econ_game_log_imports(id) ON DELETE CASCADE,
                row_ref TEXT,
                raw_name TEXT,
                matched_name TEXT,
                expected_amount BIGINT,
                actual_amount BIGINT,
                tolerance BIGINT,
                score NUMERIC(5,4),
                status TEXT DEFAULT 'open',
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_alerts (
                id SERIAL PRIMARY KEY,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                threshold_value BIGINT,
                current_value BIGINT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_loot_buyback_requests (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seller_name TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                location TEXT NOT NULL,
                quality INTEGER NOT NULL,
                market_unit_price BIGINT NOT NULL,
                discount_percent INTEGER NOT NULL DEFAULT 20,
                payout_total BIGINT NOT NULL,
                auto_approve_limit BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approved_by TEXT,
                journal_entry_id INTEGER,
                note TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_regear_requests (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                player_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost BIGINT NOT NULL,
                screenshot_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                checked_by TEXT,
                issued_by TEXT,
                journal_entry_id INTEGER,
                note TEXT
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mutation_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                actor TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_import_discrepancies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER,
                row_ref TEXT,
                raw_name TEXT,
                matched_name TEXT,
                expected_amount INTEGER,
                actual_amount INTEGER,
                tolerance INTEGER,
                score REAL,
                status TEXT DEFAULT 'open',
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (import_id) REFERENCES econ_game_log_imports(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                threshold_value INTEGER,
                current_value INTEGER,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_loot_buyback_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seller_name TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                location TEXT NOT NULL,
                quality INTEGER NOT NULL,
                market_unit_price INTEGER NOT NULL,
                discount_percent INTEGER NOT NULL DEFAULT 20,
                payout_total INTEGER NOT NULL,
                auto_approve_limit INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                approved_by TEXT,
                journal_entry_id INTEGER,
                note TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS econ_regear_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                player_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost INTEGER NOT NULL,
                screenshot_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                checked_by TEXT,
                issued_by TEXT,
                journal_entry_id INTEGER,
                note TEXT
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
        ("1210", "Regear Chest", "asset"),
        ("1300", "Receivables", "asset"),
        ("2000", "Payables", "liability"),
        ("3000", "Guild Capital", "equity"),
        ("3100", "Energy Capital", "equity"),
        ("4000", "Content Revenue", "income"),
        ("4100", "Gear Sale Revenue", "income"),
        ("4200", "Rent Revenue", "income"),
        ("4300", "Tax Revenue", "income"),
        ("4400", "Penalty Revenue", "income"),
        ("4500", "Donations", "income"),
        ("5000", "COGS", "expense"),
        ("5100", "Rent Expense", "expense"),
        ("5200", "Rewards Expense", "expense"),
        ("5210", "Regear Expense", "expense"),
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
        ("loot_buyback", "1200", "1000", True, "buyback"),
        ("regear_issue", "5210", "1210", True, "regear"),
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
    config_defaults = {
        "alert_low_cash_threshold": "2000000",
        "alert_high_expense_30d_threshold": "25000000",
        "alert_unmatched_records_threshold": "0",
        "treasury_cash_current": "295531023",
        "treasury_energy_current": "379",
    }
    for k, v in config_defaults.items():
        if backend == "postgres":
            cur.execute(
                """
                INSERT INTO econ_config (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING
                """,
                (k, v),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO econ_config (key, value) VALUES (?, ?)",
                (k, v),
            )
    conn.commit()

    _seed_opening_balances_from_config(conn, backend)


def _seed_opening_balances_from_config(conn, backend: str) -> None:
    """
    Variant A:
    - treat treasury_* config values as initial balances only
    - write them into the journal as opening posted entries (idempotent)
    - KPI balance is then derived from posted journal lines
    """
    cfg = get_config(conn, backend)
    cash_s = str(cfg.get("treasury_cash_current") or "").strip()
    energy_s = str(cfg.get("treasury_energy_current") or "").strip()

    def _to_pos_int(s: str) -> int:
        return int(s) if s and s.lstrip("-").isdigit() and int(s) > 0 else 0

    cash_amt = _to_pos_int(cash_s)
    energy_amt = _to_pos_int(energy_s)

    if cash_amt > 0:
        _seed_opening_entry(conn, backend, category="opening_cash", amount=cash_amt, asset_code="1000", equity_code="3000")
    if energy_amt > 0:
        _seed_opening_entry(conn, backend, category="opening_energy", amount=energy_amt, asset_code="1100", equity_code="3100")


def _seed_opening_entry(conn, backend: str, *, category: str, amount: int, asset_code: str, equity_code: str) -> None:
    exists = fetch_one(conn, backend, "SELECT id FROM econ_journal_entries WHERE category=$1 LIMIT 1", (category,))
    if exists:
        return
    entry_id = _insert_entry(
        conn,
        backend,
        category,
        int(amount),
        f"Opening balance seed for account {asset_code}.",
        "system_seed",
        "economy_seed",
        "posted",
    )
    lines = [(asset_code, "debit", int(amount)), (equity_code, "credit", int(amount))]
    _validate_double_entry(lines)
    for acc, side, a in lines:
        _insert_line(conn, backend, entry_id, acc, side, a)
    _log_audit(
        conn,
        backend,
        mutation_type="seed_opening_balance",
        entity_type="journal_entry",
        entity_id=str(entry_id),
        actor="system_seed",
        payload={"category": category, "amount": int(amount), "asset_code": asset_code, "equity_code": equity_code},
    )
    conn.commit()


def get_config(conn, backend: str) -> dict:
    rows = fetch_all(conn, backend, "SELECT key, value FROM econ_config", ())
    return {str(r.get("key")): str(r.get("value")) for r in rows if r.get("key") is not None}


def set_config_values(conn, backend: str, values: dict, actor: str = "dashboard_admin") -> None:
    if not isinstance(values, dict):
        raise ValueError("values must be an object")
    cur = conn.cursor()
    for k, raw in values.items():
        key = str(k or "").strip()
        if not key.startswith("alert_"):
            continue
        val = str(raw or "").strip()
        if not val or (not val.lstrip("-").isdigit()):
            raise ValueError(f"Invalid numeric value for {key}")
        if backend == "postgres":
            cur.execute(
                """
                INSERT INTO econ_config (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=CURRENT_TIMESTAMP
                """,
                (key, val),
            )
        else:
            cur.execute(
                """
                INSERT INTO econ_config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                (key, val),
            )
    _log_audit(
        conn,
        backend,
        mutation_type="set_config",
        entity_type="econ_config",
        entity_id="alerts",
        actor=actor,
        payload={"values": values},
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


def _log_audit(conn, backend: str, *, mutation_type: str, entity_type: str, entity_id: str, actor: str, payload: dict) -> None:
    data = json.dumps(payload or {}, default=str)
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_audit_log (mutation_type, entity_type, entity_id, actor, payload_json)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (mutation_type, entity_type, str(entity_id or ""), actor or "", data),
        )
    else:
        cur.execute(
            """
            INSERT INTO econ_audit_log (mutation_type, entity_type, entity_id, actor, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (mutation_type, entity_type, str(entity_id or ""), actor or "", data),
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
    _log_audit(
        conn,
        backend,
        mutation_type="create_routed_operation",
        entity_type="journal_entry",
        entity_id=str(entry_id),
        actor=actor,
        payload={"category": category, "amount": amount, "source": source, "status": status},
    )
    conn.commit()
    return {"entry_id": entry_id, "status": status, "category": category, "amount": amount}


def list_recent_entries(
    conn,
    backend: str,
    limit: int = 120,
    *,
    status: str = "",
    category_like: str = "",
    source_like: str = "",
) -> List[dict]:
    lim = max(10, min(int(limit), 500))
    where = []
    params: List[object] = []
    if status in ("posted", "pending", "rejected"):
        where.append("e.status = $1")
        params.append(status)
    if category_like.strip():
        idx = len(params) + 1
        where.append(f"LOWER(e.category) LIKE LOWER(${idx})")
        params.append(f"%{category_like.strip()}%")
    if source_like.strip():
        idx = len(params) + 1
        where.append(f"LOWER(COALESCE(e.source,'')) LIKE LOWER(${idx})")
        params.append(f"%{source_like.strip()}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = fetch_all(
        conn,
        backend,
        f"""
        SELECT e.id, e.created_at, e.category, e.amount, e.description, e.actor, e.source, e.status,
               SUM(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END) AS debit_sum,
               SUM(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END) AS credit_sum
        FROM econ_journal_entries e
        LEFT JOIN econ_journal_lines l ON l.entry_id = e.id
        {where_sql}
        GROUP BY e.id
        ORDER BY e.id DESC
        LIMIT {lim}
        """,
        tuple(params),
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
        _log_audit(
            conn,
            backend,
            mutation_type="update_task",
            entity_type="guild_bonus_task",
            entity_id=str(int(task_id)),
            actor="dashboard_admin",
            payload={"title": title.strip(), "reward_amount": reward_amount, "active": bool(active)},
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
    _log_audit(
        conn,
        backend,
        mutation_type="create_task",
        entity_type="guild_bonus_task",
        entity_id=str(new_id),
        actor="dashboard_admin",
        payload={"title": title.strip(), "reward_amount": reward_amount, "active": bool(active)},
    )
    conn.commit()
    return {"id": new_id, "created": True}


def delete_task(conn, backend: str, task_id: int) -> int:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute("DELETE FROM econ_guild_bonus_tasks WHERE id=%s", (int(task_id),))
    else:
        cur.execute("DELETE FROM econ_guild_bonus_tasks WHERE id=?", (int(task_id),))
    if int(cur.rowcount or 0) > 0:
        _log_audit(
            conn,
            backend,
            mutation_type="delete_task",
            entity_type="guild_bonus_task",
            entity_id=str(int(task_id)),
            actor="dashboard_admin",
            payload={"task_id": int(task_id)},
        )
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
    if not bool(task.get("active")):
        raise ValueError("Task is inactive")
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
    _log_audit(
        conn,
        backend,
        mutation_type="award_task_completion",
        entity_type="guild_bonus_award",
        entity_id=str(award_id),
        actor=approved_by.strip(),
        payload={"task_id": int(task_id), "entry_id": entry_id, "reward_total": reward_total},
    )
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


def create_loot_buyback_request(
    conn,
    backend: str,
    *,
    seller_name: str,
    item_id: str,
    quantity: int,
    auto_approve_limit: int,
    approved_by: str = "",
    note: str = "",
) -> dict:
    seller_name = seller_name.strip()
    item_id = item_id.strip()
    quantity = int(quantity)
    auto_approve_limit = int(auto_approve_limit)
    if not seller_name:
        raise ValueError("seller_name is required")
    if not item_id:
        raise ValueError("item_id is required")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if auto_approve_limit < 0:
        raise ValueError("auto_approve_limit must be >= 0")

    price_obj, err, stale = get_item_price_24h_trimmed_mean(item_id=item_id)
    if not price_obj:
        raise ValueError(f"Failed to fetch market price: {err or 'unknown error'}")
    market_unit = int(price_obj.get("market_unit_price") or 0)
    if market_unit <= 0:
        raise ValueError("Market price is missing/zero for selected item")
    payout_total = int(round(market_unit * quantity * 0.8))
    status = "approved" if payout_total <= auto_approve_limit else "pending"

    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_loot_buyback_requests (
                seller_name, item_id, quantity, location, quality,
                market_unit_price, discount_percent, payout_total,
                auto_approve_limit, status, approved_by, note
            ) VALUES (%s, %s, %s, %s, %s, %s, 20, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                seller_name,
                item_id,
                quantity,
                "ALL_CITIES_24H",
                1,
                market_unit,
                payout_total,
                auto_approve_limit,
                status,
                approved_by.strip() or None,
                note.strip() or None,
            ),
        )
        req_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            """
            INSERT INTO econ_loot_buyback_requests (
                seller_name, item_id, quantity, location, quality,
                market_unit_price, discount_percent, payout_total,
                auto_approve_limit, status, approved_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, 20, ?, ?, ?, ?, ?)
            """,
            (
                seller_name,
                item_id,
                quantity,
                "ALL_CITIES_24H",
                1,
                market_unit,
                payout_total,
                auto_approve_limit,
                status,
                approved_by.strip() or None,
                note.strip() or None,
            ),
        )
        req_id = int(cur.lastrowid)

    entry_id = None
    if status == "approved":
        entry_id = _insert_entry(
            conn,
            backend,
            "loot_buyback",
            payout_total,
            f"Loot buyback {item_id} x{quantity} from {seller_name}. {note}".strip(),
            approved_by.strip() or "system_auto",
            "loot_buyback",
            "posted",
        )
        lines = [("1200", "debit", payout_total), ("1000", "credit", payout_total)]
        _validate_double_entry(lines)
        for acc, side, amt in lines:
            _insert_line(conn, backend, entry_id, acc, side, amt)
        if backend == "postgres":
            cur.execute("UPDATE econ_loot_buyback_requests SET journal_entry_id=%s WHERE id=%s", (entry_id, req_id))
        else:
            cur.execute("UPDATE econ_loot_buyback_requests SET journal_entry_id=? WHERE id=?", (entry_id, req_id))

    _log_audit(
        conn,
        backend,
        mutation_type="create_loot_buyback_request",
        entity_type="loot_buyback_request",
        entity_id=str(req_id),
        actor=approved_by.strip() or "dashboard_admin",
        payload={
            "seller_name": seller_name,
            "item_id": item_id,
            "quantity": quantity,
            "location": "ALL_CITIES_24H",
            "quality": 1,
            "market_unit_price": market_unit,
            "discount_percent": 20,
            "payout_total": payout_total,
            "auto_approve_limit": auto_approve_limit,
            "status": status,
            "stale_price": bool(stale),
            "journal_entry_id": entry_id,
        },
    )
    conn.commit()
    return {
        "request_id": req_id,
        "status": status,
        "journal_entry_id": entry_id,
        "market_unit_price": market_unit,
        "discount_percent": 20,
        "payout_total": payout_total,
        "stale_price": bool(stale),
        "price_error": err,
    }


def create_manual_loot_buyback_from_price(
    conn,
    backend: str,
    *,
    buyback_price: int,
    actor: str = "",
) -> dict:
    """
    Manual loot buyback input flow:
    - user provides buyback paid amount
    - market equivalent for stats is computed as +20%
    """
    payout_total = int(buyback_price)
    if payout_total <= 0:
        raise ValueError("buyback_price must be positive")
    market_total = int(round(payout_total * 1.2))
    market_unit = market_total  # quantity=1 synthetic record

    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_loot_buyback_requests (
                seller_name, item_id, quantity, location, quality,
                market_unit_price, discount_percent, payout_total,
                auto_approve_limit, status, approved_by, note
            ) VALUES (%s, %s, %s, %s, %s, %s, 20, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                actor.strip() or "manual",
                "MANUAL_LOOT_BUYBACK",
                1,
                "MANUAL",
                1,
                market_unit,
                payout_total,
                payout_total,
                "approved",
                actor.strip() or "manual",
                "manual_buyback_price_input",
            ),
        )
        req_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            """
            INSERT INTO econ_loot_buyback_requests (
                seller_name, item_id, quantity, location, quality,
                market_unit_price, discount_percent, payout_total,
                auto_approve_limit, status, approved_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, 20, ?, ?, ?, ?, ?)
            """,
            (
                actor.strip() or "manual",
                "MANUAL_LOOT_BUYBACK",
                1,
                "MANUAL",
                1,
                market_unit,
                payout_total,
                payout_total,
                "approved",
                actor.strip() or "manual",
                "manual_buyback_price_input",
            ),
        )
        req_id = int(cur.lastrowid)

    entry_id = _insert_entry(
        conn,
        backend,
        "loot_buyback",
        payout_total,
        f"Manual loot buyback by price: payout={payout_total}, market_eq={market_total}",
        actor.strip() or "manual",
        "loot_buyback_manual",
        "posted",
    )
    lines = [("1200", "debit", payout_total), ("1000", "credit", payout_total)]
    _validate_double_entry(lines)
    for acc, side, amt in lines:
        _insert_line(conn, backend, entry_id, acc, side, amt)
    if backend == "postgres":
        cur.execute("UPDATE econ_loot_buyback_requests SET journal_entry_id=%s WHERE id=%s", (entry_id, req_id))
    else:
        cur.execute("UPDATE econ_loot_buyback_requests SET journal_entry_id=? WHERE id=?", (entry_id, req_id))

    _log_audit(
        conn,
        backend,
        mutation_type="create_manual_loot_buyback_from_price",
        entity_type="loot_buyback_request",
        entity_id=str(req_id),
        actor=actor.strip() or "manual",
        payload={
            "payout_total": payout_total,
            "market_total_plus_20_pct": market_total,
            "discount_percent": 20,
            "journal_entry_id": entry_id,
        },
    )
    conn.commit()
    return {
        "request_id": req_id,
        "status": "approved",
        "journal_entry_id": entry_id,
        "payout_total": payout_total,
        "market_total_plus_20_pct": market_total,
        "discount_percent": 20,
    }


def create_regear_request(
    conn,
    backend: str,
    *,
    player_name: str,
    content_type: str,
    item_id: str,
    quantity: int,
    unit_cost: int,
    screenshot_url: str,
    note: str = "",
) -> dict:
    player_name = player_name.strip()
    content_type = content_type.strip()
    item_id = item_id.strip()
    screenshot_url = screenshot_url.strip()
    quantity = int(quantity)
    unit_cost = int(unit_cost)
    if not player_name:
        raise ValueError("player_name is required")
    if not content_type:
        raise ValueError("content_type is required")
    if not item_id:
        raise ValueError("item_id is required")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if unit_cost <= 0:
        raise ValueError("unit_cost must be positive")
    if not screenshot_url:
        raise ValueError("screenshot_url is required")

    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO econ_regear_requests (
                player_name, content_type, item_id, quantity, unit_cost, screenshot_url, status, note
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
            RETURNING id
            """,
            (player_name, content_type, item_id, quantity, unit_cost, screenshot_url, note.strip() or None),
        )
        req_id = int(cur.fetchone()[0])
    else:
        cur.execute(
            """
            INSERT INTO econ_regear_requests (
                player_name, content_type, item_id, quantity, unit_cost, screenshot_url, status, note
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (player_name, content_type, item_id, quantity, unit_cost, screenshot_url, note.strip() or None),
        )
        req_id = int(cur.lastrowid)
    _log_audit(
        conn,
        backend,
        mutation_type="create_regear_request",
        entity_type="regear_request",
        entity_id=str(req_id),
        actor=player_name,
        payload={
            "content_type": content_type,
            "item_id": item_id,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "screenshot_url": screenshot_url,
        },
    )
    conn.commit()
    return {"request_id": req_id, "status": "pending"}


def issue_regear_request(
    conn,
    backend: str,
    *,
    request_id: int,
    checked_by: str,
    issued_by: str,
    note: str = "",
) -> dict:
    req = fetch_one(
        conn,
        backend,
        """
        SELECT id, player_name, content_type, item_id, quantity, unit_cost, screenshot_url, status
        FROM econ_regear_requests
        WHERE id=$1
        """,
        (int(request_id),),
    )
    if not req:
        raise ValueError("Regear request not found")
    if str(req.get("status") or "").lower() == "issued":
        raise ValueError("Regear request is already issued")
    total_cost = int(req.get("quantity") or 0) * int(req.get("unit_cost") or 0)
    if total_cost <= 0:
        raise ValueError("Invalid total cost for regear request")

    entry_id = _insert_entry(
        conn,
        backend,
        "regear_issue",
        total_cost,
        f"Regear issue for {req.get('player_name')} ({req.get('item_id')} x{req.get('quantity')}). {note}".strip(),
        issued_by.strip() or "dashboard_admin",
        "regear_issue",
        "posted",
    )
    lines = [("5210", "debit", total_cost), ("1210", "credit", total_cost)]
    _validate_double_entry(lines)
    for acc, side, amt in lines:
        _insert_line(conn, backend, entry_id, acc, side, amt)
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            UPDATE econ_regear_requests
            SET status='issued', checked_by=%s, issued_by=%s, journal_entry_id=%s, note=%s
            WHERE id=%s
            """,
            (
                checked_by.strip() or None,
                issued_by.strip() or None,
                entry_id,
                note.strip() or None,
                int(request_id),
            ),
        )
    else:
        cur.execute(
            """
            UPDATE econ_regear_requests
            SET status='issued', checked_by=?, issued_by=?, journal_entry_id=?, note=?
            WHERE id=?
            """,
            (
                checked_by.strip() or None,
                issued_by.strip() or None,
                entry_id,
                note.strip() or None,
                int(request_id),
            ),
        )
    _log_audit(
        conn,
        backend,
        mutation_type="issue_regear_request",
        entity_type="regear_request",
        entity_id=str(int(request_id)),
        actor=issued_by.strip() or "dashboard_admin",
        payload={"entry_id": entry_id, "checked_by": checked_by.strip(), "total_cost": total_cost},
    )
    conn.commit()
    return {"request_id": int(request_id), "status": "issued", "entry_id": entry_id, "total_cost": total_cost}


def list_loot_buyback_requests(conn, backend: str, limit: int = 80) -> List[dict]:
    lim = max(10, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT id, created_at, seller_name, item_id, quantity, location, quality,
               market_unit_price, discount_percent, payout_total, auto_approve_limit,
               status, approved_by, journal_entry_id, note
        FROM econ_loot_buyback_requests
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )


def list_regear_requests(conn, backend: str, limit: int = 80) -> List[dict]:
    lim = max(10, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT id, created_at, player_name, content_type, item_id, quantity, unit_cost,
               screenshot_url, status, checked_by, issued_by, journal_entry_id, note
        FROM econ_regear_requests
        ORDER BY id DESC
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
    _log_audit(
        conn,
        backend,
        mutation_type="upsert_routing_rule",
        entity_type="routing_rule",
        entity_id=category.strip(),
        actor="dashboard_admin",
        payload={
            "debit_account": debit_account.strip(),
            "credit_account": credit_account.strip(),
            "require_approval": bool(require_approval),
            "tag": tag.strip() or "",
        },
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
    discrepancies = _build_import_discrepancies(conn, backend, import_id=import_id, rows=rows)
    summary["discrepancies"] = discrepancies
    _log_audit(
        conn,
        backend,
        mutation_type="import_game_log_csv",
        entity_type="game_log_import",
        entity_id=str(import_id),
        actor="dashboard_admin",
        payload=summary,
    )
    conn.commit()
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
    pending = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_journal_entries WHERE status='pending'", ())
    unresolved_discrepancies = fetch_one(
        conn, backend, "SELECT COUNT(*) AS c FROM econ_import_discrepancies WHERE status='open'", ()
    )
    open_alerts = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_alerts WHERE status='open'", ())
    return {
        "accounts_count": len(accounts),
        "entries_count": int((total_entries or {}).get("c") or 0),
        "pending_entries": int((pending or {}).get("c") or 0),
        "unresolved_discrepancies": int((unresolved_discrepancies or {}).get("c") or 0),
        "open_alerts": int((open_alerts or {}).get("c") or 0),
    }


def list_pending_approvals(conn, backend: str, limit: int = 100) -> List[dict]:
    lim = max(1, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT id, created_at, category, amount, description, actor, source, status
        FROM econ_journal_entries
        WHERE status = 'pending'
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )


def review_pending_entry(conn, backend: str, *, entry_id: int, action: str, reviewed_by: str, note: str = "") -> dict:
    action_norm = str(action or "").strip().lower()
    if action_norm not in ("approve", "reject"):
        raise ValueError("action must be approve or reject")
    entry = fetch_one(
        conn,
        backend,
        "SELECT id, status, category, amount FROM econ_journal_entries WHERE id=$1",
        (int(entry_id),),
    )
    if not entry:
        raise ValueError("Entry not found")
    if str(entry.get("status") or "") != "pending":
        raise ValueError("Entry is not pending")
    new_status = "posted" if action_norm == "approve" else "rejected"
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute("UPDATE econ_journal_entries SET status=%s WHERE id=%s", (new_status, int(entry_id)))
    else:
        cur.execute("UPDATE econ_journal_entries SET status=? WHERE id=?", (new_status, int(entry_id)))
    _log_audit(
        conn,
        backend,
        mutation_type="review_pending_entry",
        entity_type="journal_entry",
        entity_id=str(int(entry_id)),
        actor=reviewed_by.strip() or "dashboard_admin",
        payload={"action": action_norm, "new_status": new_status, "note": note.strip()},
    )
    conn.commit()
    return {"entry_id": int(entry_id), "status": new_status}


def list_audit_trail(conn, backend: str, limit: int = 250) -> List[dict]:
    lim = max(1, min(int(limit), 1000))
    rows = fetch_all(
        conn,
        backend,
        f"""
        SELECT id, created_at, mutation_type, entity_type, entity_id, actor, payload_json
        FROM econ_audit_log
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )
    out: List[dict] = []
    for row in rows:
        rec = dict(row)
        try:
            rec["payload"] = json.loads(rec.get("payload_json") or "{}")
        except Exception:
            rec["payload"] = {}
        out.append(rec)
    return out


def _guess_name(row: dict) -> str:
    for key in ("Player", "Name", "Nickname", "Character", "player", "name", "nickname"):
        if key in row and str(row.get(key) or "").strip():
            return str(row.get(key)).strip()
    return ""


def _to_int_amount(val: object) -> int:
    try:
        return int(float(str(val or "0").strip().replace(",", "")))
    except ValueError:
        return 0


def _build_import_discrepancies(conn, backend: str, *, import_id: int, rows: List[dict]) -> int:
    known = fetch_all(
        conn,
        backend,
        """
        SELECT player_nickname, SUM(reward_total) AS total
        FROM econ_guild_bonus_awards
        GROUP BY player_nickname
        """,
        (),
    )
    known_names = [(str(r.get("player_nickname") or "").strip(), int(r.get("total") or 0)) for r in known if r.get("player_nickname")]
    cur = conn.cursor()
    count = 0
    for idx, row in enumerate(rows, start=1):
        raw_name = _guess_name(row)
        actual = abs(_to_int_amount(row.get("Amount")))
        expected_hint = _to_int_amount(row.get("ExpectedAmount"))
        best_name = ""
        best_score = 0.0
        best_expected = expected_hint
        if raw_name and known_names:
            for candidate_name, candidate_total in known_names:
                score = SequenceMatcher(None, raw_name.lower(), candidate_name.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_name = candidate_name
                    best_expected = expected_hint or candidate_total
        tolerance = max(5000, int(abs(best_expected) * 0.05)) if best_expected else 5000
        unmatched = bool(raw_name and not best_name)
        low_confidence = bool(raw_name and best_name and best_score < 0.75)
        amount_mismatch = bool(best_expected and abs(actual - best_expected) > tolerance)
        if unmatched or low_confidence or amount_mismatch:
            note = "unmatched record" if unmatched else ("low fuzzy confidence" if low_confidence else "amount outside tolerance")
            if backend == "postgres":
                cur.execute(
                    """
                    INSERT INTO econ_import_discrepancies
                    (import_id, row_ref, raw_name, matched_name, expected_amount, actual_amount, tolerance, score, status, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open', %s)
                    """,
                    (
                        int(import_id),
                        f"row_{idx}",
                        raw_name or None,
                        best_name or None,
                        int(best_expected or 0),
                        int(actual or 0),
                        int(tolerance),
                        float(best_score),
                        note,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO econ_import_discrepancies
                    (import_id, row_ref, raw_name, matched_name, expected_amount, actual_amount, tolerance, score, status, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
                    """,
                    (
                        int(import_id),
                        f"row_{idx}",
                        raw_name or None,
                        best_name or None,
                        int(best_expected or 0),
                        int(actual or 0),
                        int(tolerance),
                        float(best_score),
                        note,
                    ),
                )
            count += 1
    return count


def list_discrepancy_queue(conn, backend: str, limit: int = 200) -> List[dict]:
    lim = max(1, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT id, import_id, row_ref, raw_name, matched_name, expected_amount, actual_amount, tolerance, score, status, note, created_at
        FROM econ_import_discrepancies
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )


def resolve_discrepancy(conn, backend: str, discrepancy_id: int, resolved_by: str, note: str = "") -> int:
    did = int(discrepancy_id)
    if did < 1:
        raise ValueError("Invalid discrepancy id")
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            "UPDATE econ_import_discrepancies SET status='resolved', note=%s WHERE id=%s",
            ((note or "").strip()[:500] or "resolved manually", did),
        )
    else:
        cur.execute(
            "UPDATE econ_import_discrepancies SET status='resolved', note=? WHERE id=?",
            ((note or "").strip()[:500] or "resolved manually", did),
        )
    _log_audit(
        conn,
        backend,
        mutation_type="resolve_discrepancy",
        entity_type="import_discrepancy",
        entity_id=str(did),
        actor=resolved_by or "dashboard_admin",
        payload={"note": (note or "").strip()[:500]},
    )
    conn.commit()
    return int(cur.rowcount or 0)


def list_alerts(conn, backend: str, limit: int = 100) -> List[dict]:
    lim = max(1, min(int(limit), 500))
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT id, alert_type, severity, message, threshold_value, current_value, status, created_at, resolved_at
        FROM econ_alerts
        ORDER BY id DESC
        LIMIT {lim}
        """,
        (),
    )


def acknowledge_alert(conn, backend: str, alert_id: int, acknowledged_by: str, note: str = "") -> int:
    aid = int(alert_id)
    if aid < 1:
        raise ValueError("Invalid alert id")
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            "UPDATE econ_alerts SET status='resolved', resolved_at=CURRENT_TIMESTAMP, message=message || %s WHERE id=%s",
            (f" [ack:{(note or '').strip()[:200]}]" if (note or "").strip() else "", aid),
        )
    else:
        cur.execute(
            "UPDATE econ_alerts SET status='resolved', resolved_at=CURRENT_TIMESTAMP, message=message || ? WHERE id=?",
            (f" [ack:{(note or '').strip()[:200]}]" if (note or "").strip() else "", aid),
        )
    _log_audit(
        conn,
        backend,
        mutation_type="ack_alert",
        entity_type="alert",
        entity_id=str(aid),
        actor=acknowledged_by or "dashboard_admin",
        payload={"note": (note or "").strip()[:200]},
    )
    conn.commit()
    return int(cur.rowcount or 0)


def _set_alert_state(
    conn, backend: str, *, alert_type: str, severity: str, message: str, threshold_value: int, current_value: int, should_open: bool
) -> None:
    existing = fetch_one(
        conn,
        backend,
        "SELECT id, status FROM econ_alerts WHERE alert_type=$1 AND message=$2 AND status='open' ORDER BY id DESC LIMIT 1",
        (alert_type, message),
    )
    cur = conn.cursor()
    if should_open and not existing:
        if backend == "postgres":
            cur.execute(
                """
                INSERT INTO econ_alerts (alert_type, severity, message, threshold_value, current_value, status)
                VALUES (%s, %s, %s, %s, %s, 'open')
                """,
                (alert_type, severity, message, int(threshold_value), int(current_value)),
            )
        else:
            cur.execute(
                """
                INSERT INTO econ_alerts (alert_type, severity, message, threshold_value, current_value, status)
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (alert_type, severity, message, int(threshold_value), int(current_value)),
            )
    if (not should_open) and existing:
        if backend == "postgres":
            cur.execute(
                "UPDATE econ_alerts SET status='resolved', resolved_at=CURRENT_TIMESTAMP WHERE id=%s",
                (int(existing["id"]),),
            )
        else:
            cur.execute(
                "UPDATE econ_alerts SET status='resolved', resolved_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(existing["id"]),),
            )


def run_alert_threshold_checks(conn, backend: str) -> dict:
    cfg = get_config(conn, backend)
    low_cash_threshold = int(cfg.get("alert_low_cash_threshold") or 2_000_000)
    high_expense_threshold = int(cfg.get("alert_high_expense_30d_threshold") or 25_000_000)
    unmatched_threshold = int(cfg.get("alert_unmatched_records_threshold") or 0)
    balance = balance_snapshot(conn, backend)
    cash = int(balance.get("cash_balance") or 0)
    pnl = pnl_summary(conn, backend, days=30)
    expense_30 = int(pnl.get("expense_total") or 0)
    unmatched = fetch_one(conn, backend, "SELECT COUNT(*) AS c FROM econ_import_discrepancies WHERE status='open'", ())
    unmatched_count = int((unmatched or {}).get("c") or 0)

    _set_alert_state(
        conn,
        backend,
        alert_type="low_cash",
        severity="high",
        message="Cash balance below threshold",
        threshold_value=low_cash_threshold,
        current_value=cash,
        should_open=cash < low_cash_threshold,
    )
    _set_alert_state(
        conn,
        backend,
        alert_type="high_expense",
        severity="medium",
        message="30-day expense above threshold",
        threshold_value=high_expense_threshold,
        current_value=expense_30,
        should_open=expense_30 > high_expense_threshold,
    )
    _set_alert_state(
        conn,
        backend,
        alert_type="unmatched_records",
        severity="medium",
        message="Unmatched import records detected",
        threshold_value=unmatched_threshold,
        current_value=unmatched_count,
        should_open=unmatched_count > unmatched_threshold,
    )
    _log_audit(
        conn,
        backend,
        mutation_type="run_alert_threshold_checks",
        entity_type="alerts",
        entity_id="threshold_check",
        actor="dashboard_system",
        payload={"cash_balance": cash, "expense_30d": expense_30, "unmatched_records": unmatched_count},
    )
    conn.commit()
    return {
        "cash_balance": cash,
        "expense_30d": expense_30,
        "unmatched_records": unmatched_count,
        "thresholds": {
            "low_cash": low_cash_threshold,
            "high_expense_30d": high_expense_threshold,
            "unmatched_records": unmatched_threshold,
        },
    }


def balance_snapshot(conn, backend: str) -> dict:
    rows = fetch_all(
        conn,
        backend,
        """
        SELECT a.code, a.name, a.kind,
               COALESCE(SUM(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END),0) AS debit_total,
               COALESCE(SUM(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END),0) AS credit_total
        FROM econ_accounts a
        LEFT JOIN econ_journal_lines l ON l.account_code = a.code
        LEFT JOIN econ_journal_entries e ON e.id = l.entry_id AND e.status='posted'
        GROUP BY a.code, a.name, a.kind
        ORDER BY a.code
        """,
        (),
    )
    items: List[dict] = []
    for r in rows:
        debit_total = int(r.get("debit_total") or 0)
        credit_total = int(r.get("credit_total") or 0)
        kind = str(r.get("kind") or "")
        balance = debit_total - credit_total if kind in ("asset", "expense") else credit_total - debit_total
        rec = dict(r)
        rec["balance"] = int(balance)
        items.append(rec)
    cash_balance = next((int(i.get("balance") or 0) for i in items if str(i.get("code")) == "1000"), 0)
    energy_balance = next((int(i.get("balance") or 0) for i in items if str(i.get("code")) == "1100"), 0)
    return {
        "as_of_utc": _utc_now(),
        "cash_balance": cash_balance,
        "energy_balance": energy_balance,
        "accounts": items,
    }


def pnl_summary(conn, backend: str, days: int = 30) -> dict:
    ndays = max(1, min(int(days), 365))
    if backend == "sqlite":
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT a.kind,
                   COALESCE(SUM(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END),0) AS debit_total,
                   COALESCE(SUM(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END),0) AS credit_total
            FROM econ_journal_lines l
            JOIN econ_journal_entries e ON e.id = l.entry_id
            JOIN econ_accounts a ON a.code = l.account_code
            WHERE e.status='posted' AND e.created_at >= datetime('now', '-' || $1 || ' day')
            GROUP BY a.kind
            """,
            (ndays,),
        )
    else:
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT a.kind,
                   COALESCE(SUM(CASE WHEN l.side='debit' THEN l.amount ELSE 0 END),0) AS debit_total,
                   COALESCE(SUM(CASE WHEN l.side='credit' THEN l.amount ELSE 0 END),0) AS credit_total
            FROM econ_journal_lines l
            JOIN econ_journal_entries e ON e.id = l.entry_id
            JOIN econ_accounts a ON a.code = l.account_code
            WHERE e.status='posted' AND e.created_at >= (CURRENT_TIMESTAMP - ($1 * INTERVAL '1 day'))
            GROUP BY a.kind
            """,
            (ndays,),
        )
    income_total = 0
    expense_total = 0
    for row in rows:
        kind = str(row.get("kind") or "")
        debit_total = int(row.get("debit_total") or 0)
        credit_total = int(row.get("credit_total") or 0)
        if kind == "income":
            income_total += credit_total - debit_total
        if kind == "expense":
            expense_total += debit_total - credit_total
    return {"days": ndays, "income_total": income_total, "expense_total": expense_total, "net_profit": income_total - expense_total}


def cashflow_summary(conn, backend: str, days: int = 30) -> dict:
    ndays = max(1, min(int(days), 365))
    row = None
    if backend == "postgres":
        row = fetch_one(
            conn,
            backend,
            """
            SELECT COALESCE(SUM(CASE WHEN l.side='debit' THEN l.amount ELSE -l.amount END),0) AS net_cash
            FROM econ_journal_lines l
            JOIN econ_journal_entries e ON e.id = l.entry_id
            WHERE l.account_code='1000' AND e.status='posted' AND e.created_at >= (CURRENT_TIMESTAMP - ($1 * INTERVAL '1 day'))
            """,
            (ndays,),
        )
    else:
        row = fetch_one(
            conn,
            backend,
            """
            SELECT COALESCE(SUM(CASE WHEN l.side='debit' THEN l.amount ELSE -l.amount END),0) AS net_cash
            FROM econ_journal_lines l
            JOIN econ_journal_entries e ON e.id = l.entry_id
            WHERE l.account_code='1000' AND e.status='posted' AND e.created_at >= datetime('now', '-' || $1 || ' day')
            """,
            (ndays,),
        )
    net_cash = int((row or {}).get("net_cash") or 0)
    return {"days": ndays, "net_cash": net_cash, "avg_daily_cashflow": round(net_cash / float(ndays), 2)}


def forecast_summary(conn, backend: str) -> dict:
    cash_now = int(balance_snapshot(conn, backend).get("cash_balance") or 0)
    cf7 = cashflow_summary(conn, backend, days=7)
    cf30 = cashflow_summary(conn, backend, days=30)
    return {
        "cash_now": cash_now,
        "forecast_7d": int(round(cash_now + (float(cf7.get("avg_daily_cashflow") or 0) * 7))),
        "forecast_30d": int(round(cash_now + (float(cf30.get("avg_daily_cashflow") or 0) * 30))),
        "basis": {"avg_daily_7d": cf7.get("avg_daily_cashflow"), "avg_daily_30d": cf30.get("avg_daily_cashflow")},
    }


def fetch_market_price(item_id: str, location: str, quality: int) -> dict:
    data, err, stale = get_item_price(item_id=item_id, location=location, quality=quality)
    return {"ok": bool(data), "data": data, "error": err, "stale": bool(stale)}


def suggest_item_ids(query: str, limit: int = 20) -> dict:
    items, err = search_item_ids(query, limit=limit)
    return {"ok": err is None, "items": items, "error": err}
