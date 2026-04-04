from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from utils.role_config import assignment_rows_from_legacy_override

from web_dashboard.db_sync import fetch_all, fetch_one

# Dashboard analytics: only closed events count (open / test posts are excluded).


def _since(days: int) -> str:
    dt = datetime.utcnow() - timedelta(days=max(1, min(days, 730)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def ensure_guilds_dashboard_columns(conn, backend: str) -> None:
    cur = conn.cursor()
    try:
        if backend == "postgres":
            cur.execute("ALTER TABLE guilds ADD COLUMN IF NOT EXISTS dashboard_label TEXT")
        else:
            cur.execute("ALTER TABLE guilds ADD COLUMN dashboard_label TEXT")
        conn.commit()
    except Exception:
        conn.rollback()


def list_guilds(conn, backend: str) -> List[dict]:
    ensure_guilds_dashboard_columns(conn, backend)
    if backend == "postgres":
        return fetch_all(
            conn,
            backend,
            """
            SELECT id, name, discord_id, dashboard_label,
              COALESCE(NULLIF(TRIM(COALESCE(dashboard_label, '')), ''), name) AS display_name
            FROM guilds
            ORDER BY COALESCE(NULLIF(TRIM(COALESCE(dashboard_label, '')), ''), name) NULLS LAST
            """,
            (),
        )
    return fetch_all(
        conn,
        backend,
        """
        SELECT id, name, discord_id, dashboard_label,
          COALESCE(NULLIF(TRIM(COALESCE(dashboard_label, '')), ''), name) AS display_name
        FROM guilds
        ORDER BY COALESCE(NULLIF(TRIM(COALESCE(dashboard_label, '')), ''), name)
        """,
        (),
    )


def ensure_guild_role_overrides_table(conn, backend: str) -> None:
    """Create table if missing (e.g. dashboard opened before bot ran migrations)."""
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_role_overrides (
                guild_id INTEGER PRIMARY KEY REFERENCES guilds(id) ON DELETE CASCADE,
                member_role_ids TEXT,
                mentor_role_ids TEXT,
                founder_role_ids TEXT
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_role_overrides (
                guild_id INTEGER PRIMARY KEY,
                member_role_ids TEXT,
                mentor_role_ids TEXT,
                founder_role_ids TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
            """
        )
    conn.commit()


_MISSING = object()


def ensure_guild_role_assignments_table(conn, backend: str) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_role_assignments (
                guild_id INTEGER NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                discord_role_id BIGINT NOT NULL,
                tier TEXT NOT NULL,
                role_label TEXT,
                PRIMARY KEY (guild_id, discord_role_id)
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_role_assignments (
                guild_id INTEGER NOT NULL,
                discord_role_id INTEGER NOT NULL,
                tier TEXT NOT NULL,
                role_label TEXT,
                PRIMARY KEY (guild_id, discord_role_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
            """
        )
    ensure_guild_role_assignments_role_label_column(conn, backend)


def ensure_guild_role_assignments_role_label_column(conn, backend: str) -> None:
    cur = conn.cursor()
    try:
        if backend == "postgres":
            cur.execute("ALTER TABLE guild_role_assignments ADD COLUMN IF NOT EXISTS role_label TEXT")
        else:
            cur.execute("ALTER TABLE guild_role_assignments ADD COLUMN role_label TEXT")
    except Exception:
        pass
    conn.commit()


def list_guild_roles_dashboard(conn, backend: str) -> List[dict]:
    ensure_guilds_dashboard_columns(conn, backend)
    ensure_guild_role_overrides_table(conn, backend)
    ensure_guild_role_assignments_table(conn, backend)
    ensure_guild_role_assignments_role_label_column(conn, backend)
    guilds = list_guilds(conn, backend)
    assigns = fetch_all(
        conn,
        backend,
        "SELECT guild_id, discord_role_id, tier, role_label FROM guild_role_assignments",
        (),
    )
    overrides = fetch_all(
        conn,
        backend,
        "SELECT guild_id, member_role_ids, mentor_role_ids, founder_role_ids FROM guild_role_overrides",
        (),
    )
    ov_by: Dict[int, dict] = {int(o["guild_id"]): dict(o) for o in overrides}
    by_guild: Dict[int, List[dict]] = defaultdict(list)
    for a in assigns:
        lbl = a.get("role_label")
        if lbl is not None and isinstance(lbl, str):
            lbl = lbl.strip() or None
        else:
            lbl = None
        by_guild[int(a["guild_id"])].append(
            {
                "discord_role_id": int(a["discord_role_id"]),
                "tier": str(a["tier"]),
                "role_label": lbl,
            }
        )
    out: List[dict] = []
    for g in guilds:
        gid = int(g["id"])
        row = dict(g)
        row["assignments"] = sorted(by_guild.get(gid, []), key=lambda x: (x["tier"], x["discord_role_id"]))
        row["legacy_override"] = ov_by.get(gid)
        row["has_explicit_assignments"] = len(row["assignments"]) > 0
        row["suggested_from_legacy"] = (
            assignment_rows_from_legacy_override(row["legacy_override"])
            if not row["assignments"]
            else []
        )
        out.append(row)
    return out


def replace_guild_role_assignments_rows(
    conn,
    backend: str,
    guild_db_id: int,
    pairs: List[Tuple[int, str, Optional[str]]],
) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute("DELETE FROM guild_role_assignments WHERE guild_id = %s", (guild_db_id,))
        for rid, tier, label in pairs:
            cur.execute(
                "INSERT INTO guild_role_assignments (guild_id, discord_role_id, tier, role_label) VALUES (%s, %s, %s, %s)",
                (guild_db_id, rid, tier, label),
            )
    else:
        cur.execute("DELETE FROM guild_role_assignments WHERE guild_id = ?", (guild_db_id,))
        for rid, tier, label in pairs:
            cur.execute(
                "INSERT INTO guild_role_assignments (guild_id, discord_role_id, tier, role_label) VALUES (?, ?, ?, ?)",
                (guild_db_id, rid, tier, label),
            )
    conn.commit()


def fetch_guild_discord_id(conn, backend: str, guild_db_id: int) -> int:
    if backend == "postgres":
        row = fetch_one(conn, backend, "SELECT discord_id FROM guilds WHERE id = $1::int", (guild_db_id,))
    else:
        row = fetch_one(conn, backend, "SELECT discord_id FROM guilds WHERE id = ?", (guild_db_id,))
    if not row or row.get("discord_id") is None:
        return 0
    try:
        return int(row["discord_id"])
    except (TypeError, ValueError):
        return 0


def count_other_guilds_with_discord_id(conn, backend: str, guild_db_id: int, discord_id: int) -> int:
    if backend == "postgres":
        row = fetch_one(
            conn,
            backend,
            "SELECT COUNT(*) AS c FROM guilds WHERE discord_id = $1::bigint AND id <> $2::int",
            (discord_id, guild_db_id),
        )
    else:
        row = fetch_one(
            conn,
            backend,
            "SELECT COUNT(*) AS c FROM guilds WHERE discord_id = ? AND id <> ?",
            (discord_id, guild_db_id),
        )
    return int(row["c"]) if row and row.get("c") is not None else 0


def update_guild_dashboard_meta(
    conn,
    backend: str,
    guild_db_id: int,
    *,
    dashboard_label=_MISSING,
    discord_id=_MISSING,
) -> None:
    cur = conn.cursor()
    if dashboard_label is not _MISSING:
        val = dashboard_label if dashboard_label is not None else None
        if isinstance(val, str) and not val.strip():
            val = None
        elif isinstance(val, str):
            val = val.strip()
        if backend == "postgres":
            cur.execute("UPDATE guilds SET dashboard_label = %s WHERE id = %s", (val, guild_db_id))
        else:
            cur.execute("UPDATE guilds SET dashboard_label = ? WHERE id = ?", (val, guild_db_id))
    if discord_id is not _MISSING:
        did = int(discord_id)
        if backend == "postgres":
            cur.execute("UPDATE guilds SET discord_id = %s WHERE id = %s", (did, guild_db_id))
        else:
            cur.execute("UPDATE guilds SET discord_id = ? WHERE id = ?", (did, guild_db_id))
    conn.commit()


def delete_guild_role_overrides_row(conn, backend: str, guild_db_id: int) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute("DELETE FROM guild_role_overrides WHERE guild_id = %s", (guild_db_id,))
    else:
        cur.execute("DELETE FROM guild_role_overrides WHERE guild_id = ?", (guild_db_id,))
    conn.commit()


def upsert_guild_role_overrides_row(
    conn,
    backend: str,
    guild_db_id: int,
    member_s: Optional[str],
    mentor_s: Optional[str],
    founder_s: Optional[str],
) -> None:
    cur = conn.cursor()
    if backend == "postgres":
        cur.execute(
            """
            INSERT INTO guild_role_overrides (guild_id, member_role_ids, mentor_role_ids, founder_role_ids)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (guild_id) DO UPDATE SET
                member_role_ids = EXCLUDED.member_role_ids,
                mentor_role_ids = EXCLUDED.mentor_role_ids,
                founder_role_ids = EXCLUDED.founder_role_ids
            """,
            (guild_db_id, member_s, mentor_s, founder_s),
        )
    else:
        cur.execute(
            """
            INSERT INTO guild_role_overrides (guild_id, member_role_ids, mentor_role_ids, founder_role_ids)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                member_role_ids = excluded.member_role_ids,
                mentor_role_ids = excluded.mentor_role_ids,
                founder_role_ids = excluded.founder_role_ids
            """,
            (guild_db_id, member_s, mentor_s, founder_s),
        )
    conn.commit()


def guild_exists(conn, backend: str, guild_db_id: int) -> bool:
    if backend == "postgres":
        row = fetch_one(conn, backend, "SELECT 1 AS o FROM guilds WHERE id = $1::int", (guild_db_id,))
    else:
        row = fetch_one(conn, backend, "SELECT 1 AS o FROM guilds WHERE id = ?", (guild_db_id,))
    return bool(row)


def get_active_players_count(conn, backend: str, guild_db_id: Optional[int]) -> int:
    if guild_db_id:
        row = fetch_one(
            conn,
            backend,
            "SELECT COUNT(*) AS c FROM players WHERE guild_id = $1 AND status = 'active'",
            (guild_db_id,),
        )
    else:
        row = fetch_one(
            conn,
            backend,
            "SELECT COUNT(*) AS c FROM players WHERE status = 'active'",
            (),
        )
    return int(row["c"]) if row and row.get("c") is not None else 0


def get_overview(conn, backend: str, guild_db_id: Optional[int], days: int) -> dict:
    since = _since(days)

    if backend == "postgres":
        t_open = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE t.status != 'closed' AND ($1::int IS NULL OR p.guild_id = $1::int)
            """,
            (guild_db_id,),
        )
        t_closed_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE t.status = 'closed' AND t.closed_at IS NOT NULL AND t.closed_at >= $2::timestamp
            AND ($1::int IS NULL OR p.guild_id = $1::int)
            """,
            (guild_db_id, since),
        )
        sess_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM sessions s
            JOIN players pl ON pl.id = s.player_id
            WHERE s.session_date >= $2::timestamp AND ($1::int IS NULL OR pl.guild_id = $1::int)
            """,
            (guild_db_id, since),
        )
        ev_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM events e
            WHERE e.created_at >= $2::timestamp AND ($1::int IS NULL OR e.guild_id = $1::int)
              AND e.status = 'closed'
            """,
            (guild_db_id, since),
        )
    else:
        t_open = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE t.status != 'closed' AND (? IS NULL OR p.guild_id = ?)
            """,
            (guild_db_id, guild_db_id),
        )
        t_closed_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE t.status = 'closed' AND t.closed_at IS NOT NULL AND t.closed_at >= ?
            AND (? IS NULL OR p.guild_id = ?)
            """,
            (since, guild_db_id, guild_db_id),
        )
        sess_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM sessions s
            JOIN players pl ON pl.id = s.player_id
            WHERE s.session_date >= ? AND (? IS NULL OR pl.guild_id = ?)
            """,
            (since, guild_db_id, guild_db_id),
        )
        ev_period = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM events e
            WHERE e.created_at >= ? AND (? IS NULL OR e.guild_id = ?)
              AND e.status = 'closed'
            """,
            (since, guild_db_id, guild_db_id),
        )

    return {
        "tickets_open": int(t_open["c"]) if t_open else 0,
        "tickets_closed_period": int(t_closed_period["c"]) if t_closed_period else 0,
        "sessions_period": int(sess_period["c"]) if sess_period else 0,
        "events_period": int(ev_period["c"]) if ev_period else 0,
        "period_days": days,
        "since_utc": since,
    }


def get_players_table(conn, backend: str, guild_db_id: Optional[int], days: int, limit: int = 200) -> List[dict]:
    since = _since(days)
    lim = max(10, min(limit, 500))
    if backend == "postgres":
        return fetch_all(
            conn,
            backend,
            f"""
            SELECT
                p.id,
                p.nickname,
                p.status,
                p.guild_id,
                g.name AS guild_name,
                (SELECT COUNT(*) FROM sessions s WHERE s.player_id = p.id AND s.session_date >= $2::timestamp) AS sessions_count,
                COALESCE(
                    (SELECT AVG(s.score) FROM sessions s WHERE s.player_id = p.id AND s.session_date >= $2::timestamp),
                    0
                )::float AS avg_score,
                (SELECT COUNT(*) FROM tickets t WHERE t.player_id = p.id AND t.status != 'closed') AS tickets_open
            FROM players p
            LEFT JOIN guilds g ON g.id = p.guild_id
            WHERE ($1::int IS NULL OR p.guild_id = $1::int)
            ORDER BY sessions_count DESC NULLS LAST
            LIMIT {lim}
            """,
            (guild_db_id, since),
        )
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT
            p.id,
            p.nickname,
            p.status,
            p.guild_id,
            g.name AS guild_name,
            (SELECT COUNT(*) FROM sessions s WHERE s.player_id = p.id AND s.session_date >= ?) AS sessions_count,
            COALESCE(
                (SELECT AVG(s.score) FROM sessions s WHERE s.player_id = p.id AND s.session_date >= ?),
                0
            ) AS avg_score,
            (SELECT COUNT(*) FROM tickets t WHERE t.player_id = p.id AND t.status != 'closed') AS tickets_open
        FROM players p
        LEFT JOIN guilds g ON g.id = p.guild_id
        WHERE (? IS NULL OR p.guild_id = ?)
        ORDER BY sessions_count DESC
        LIMIT {lim}
        """,
        (since, since, guild_db_id, guild_db_id),
    )


def get_tickets_breakdown(conn, backend: str, guild_db_id: Optional[int], days: int) -> dict:
    since = _since(days)
    if backend == "postgres":
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT t.status, COUNT(*) AS c
            FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE ($1::int IS NULL OR p.guild_id = $1::int)
            GROUP BY t.status
            """,
            (guild_db_id,),
        )
        recent = fetch_all(
            conn,
            backend,
            """
            SELECT t.id, t.status, t.created_at, p.nickname AS player_nick,
                   m.nickname AS mentor_nick, t.replay_link
            FROM tickets t
            JOIN players p ON p.id = t.player_id
            LEFT JOIN players m ON m.id = t.mentor_id
            WHERE t.created_at >= $2::timestamp
              AND ($1::int IS NULL OR p.guild_id = $1::int)
            ORDER BY t.created_at DESC
            LIMIT 40
            """,
            (guild_db_id, since),
        )
    else:
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT t.status, COUNT(*) AS c
            FROM tickets t
            JOIN players p ON p.id = t.player_id
            WHERE (? IS NULL OR p.guild_id = ?)
            GROUP BY t.status
            """,
            (guild_db_id, guild_db_id),
        )
        recent = fetch_all(
            conn,
            backend,
            """
            SELECT t.id, t.status, t.created_at, p.nickname AS player_nick,
                   m.nickname AS mentor_nick, t.replay_link
            FROM tickets t
            JOIN players p ON p.id = t.player_id
            LEFT JOIN players m ON m.id = t.mentor_id
            WHERE t.created_at >= ?
              AND (? IS NULL OR p.guild_id = ?)
            ORDER BY t.created_at DESC
            LIMIT 40
            """,
            (since, guild_db_id, guild_db_id),
        )
    return {"by_status": rows, "recent": recent}


def get_events_analytics(conn, backend: str, guild_db_id: Optional[int], days: int) -> dict:
    since = _since(days)
    active_roster = get_active_players_count(conn, backend, guild_db_id)
    fill_rows = None

    if backend == "postgres":
        unique_participants = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(DISTINCT es.player_id) AS c
            FROM event_signups es
            JOIN events e ON e.id = es.event_id
            WHERE es.player_id IS NOT NULL
              AND e.created_at >= $2::timestamp
              AND ($1::int IS NULL OR e.guild_id = $1::int)
              AND e.status = 'closed'
            """,
            (guild_db_id, since),
        )
        total_events = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM events e
            WHERE e.created_at >= $2::timestamp
              AND ($1::int IS NULL OR e.guild_id = $1::int)
              AND e.status = 'closed'
            """,
            (guild_db_id, since),
        )
        per_content = fetch_all(
            conn,
            backend,
            """
            WITH ev_fill AS (
                SELECT
                    e.id AS event_id,
                    e.content_name,
                    COUNT(DISTINCT CASE WHEN es.player_id IS NOT NULL THEN es.player_id END) AS players_in_event,
                    COUNT(*) AS slot_count
                FROM events e
                LEFT JOIN event_signups es ON es.event_id = e.id
                WHERE e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
                GROUP BY e.id, e.content_name
            ),
            content_uniq AS (
                SELECT e.content_name, COUNT(DISTINCT es.player_id) AS uniq_players
                FROM events e
                JOIN event_signups es ON es.event_id = e.id AND es.player_id IS NOT NULL
                WHERE e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
                GROUP BY e.content_name
            )
            SELECT
                f.content_name,
                COUNT(*)::int AS events_count,
                ROUND(AVG(f.players_in_event)::numeric, 2) AS avg_players_per_event,
                ROUND(MAX(f.slot_count)::numeric, 0) AS max_slots_seen,
                COALESCE(u.uniq_players, 0)::int AS unique_players_on_content
            FROM ev_fill f
            LEFT JOIN content_uniq u ON u.content_name = f.content_name
            GROUP BY f.content_name, u.uniq_players
            ORDER BY events_count DESC
            """,
            (guild_db_id, since),
        )
        never_rows = fetch_all(
            conn,
            backend,
            """
            SELECT p.nickname, p.id
            FROM players p
            WHERE p.status = 'active'
              AND ($1::int IS NULL OR p.guild_id = $1::int)
              AND NOT EXISTS (
                SELECT 1 FROM event_signups es
                JOIN events e ON e.id = es.event_id
                WHERE es.player_id = p.id
                  AND e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
              )
            ORDER BY p.nickname
            LIMIT 200
            """,
            (guild_db_id, since),
        )
        attendance = fetch_all(
            conn,
            backend,
            """
            WITH ev AS (
                SELECT id FROM events e
                WHERE e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
            ),
            total AS (SELECT COUNT(*)::int AS tc FROM ev),
            att AS (
                SELECT es.player_id, COUNT(DISTINCT es.event_id) AS events_attended
                FROM event_signups es
                WHERE es.event_id IN (SELECT id FROM ev) AND es.player_id IS NOT NULL
                GROUP BY es.player_id
            )
            SELECT p.nickname,
                   a.events_attended,
                   (SELECT tc FROM total) AS total_events,
                   CASE WHEN (SELECT tc FROM total) > 0
                        THEN ROUND(100.0 * a.events_attended / (SELECT tc FROM total), 1)
                        ELSE 0 END AS attendance_pct
            FROM att a
            JOIN players p ON p.id = a.player_id
            ORDER BY events_attended ASC, p.nickname
            LIMIT 80
            """,
            (guild_db_id, since),
        )
        stable = fetch_all(
            conn,
            backend,
            """
            WITH ev AS (
                SELECT id FROM events e
                WHERE e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
            ),
            total AS (SELECT COUNT(*)::int AS tc FROM ev),
            att AS (
                SELECT es.player_id, COUNT(DISTINCT es.event_id) AS events_attended
                FROM event_signups es
                WHERE es.event_id IN (SELECT id FROM ev) AND es.player_id IS NOT NULL
                GROUP BY es.player_id
            )
            SELECT p.nickname,
                   a.events_attended,
                   (SELECT tc FROM total) AS total_events,
                   CASE WHEN (SELECT tc FROM total) > 0
                        THEN ROUND(100.0 * a.events_attended / (SELECT tc FROM total), 1)
                        ELSE 0 END AS attendance_pct
            FROM att a
            JOIN players p ON p.id = a.player_id
            WHERE (SELECT tc FROM total) > 0
              AND a.events_attended >= GREATEST(1, (SELECT tc FROM total) / 3)
            ORDER BY attendance_pct DESC, events_attended DESC
            LIMIT 40
            """,
            (guild_db_id, since),
        )
    else:
        unique_participants = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(DISTINCT es.player_id) AS c
            FROM event_signups es
            JOIN events e ON e.id = es.event_id
            WHERE es.player_id IS NOT NULL
              AND e.created_at >= ?
              AND (? IS NULL OR e.guild_id = ?)
              AND e.status = 'closed'
            """,
            (since, guild_db_id, guild_db_id),
        )
        total_events = fetch_one(
            conn,
            backend,
            """
            SELECT COUNT(*) AS c FROM events e
            WHERE e.created_at >= ?
              AND (? IS NULL OR e.guild_id = ?)
              AND e.status = 'closed'
            """,
            (since, guild_db_id, guild_db_id),
        )
        fill_rows = fetch_all(
            conn,
            backend,
            """
            SELECT
                e.id AS event_id,
                e.content_name,
                COUNT(DISTINCT CASE WHEN es.player_id IS NOT NULL THEN es.player_id END) AS players_in_event,
                COUNT(*) AS slot_count
            FROM events e
            LEFT JOIN event_signups es ON es.event_id = e.id
            WHERE e.created_at >= ?
              AND (? IS NULL OR e.guild_id = ?)
              AND e.status = 'closed'
            GROUP BY e.id, e.content_name
            """,
            (since, guild_db_id, guild_db_id),
        )
        uniq_rows = fetch_all(
            conn,
            backend,
            """
            SELECT DISTINCT e.content_name, es.player_id
            FROM events e
            JOIN event_signups es ON es.event_id = e.id AND es.player_id IS NOT NULL
            WHERE e.created_at >= ?
              AND (? IS NULL OR e.guild_id = ?)
              AND e.status = 'closed'
            """,
            (since, guild_db_id, guild_db_id),
        )
        uniq_by_content: dict = defaultdict(set)
        for ur in uniq_rows:
            uniq_by_content[ur["content_name"]].add(ur["player_id"])

        agg: dict = defaultdict(lambda: {"events": 0, "sum_players": 0, "max_slots": 0})
        for fr in fill_rows:
            cn = fr["content_name"]
            agg[cn]["events"] += 1
            agg[cn]["sum_players"] += int(fr["players_in_event"] or 0)
            agg[cn]["max_slots"] = max(agg[cn]["max_slots"], int(fr["slot_count"] or 0))

        per_content = []
        for cn, v in sorted(agg.items(), key=lambda x: -x[1]["events"]):
            ec = v["events"]
            per_content.append(
                {
                    "content_name": cn,
                    "events_count": ec,
                    "avg_players_per_event": round(v["sum_players"] / ec, 2) if ec else 0,
                    "max_slots_seen": v["max_slots"],
                    "unique_players_on_content": len(uniq_by_content.get(cn, set())),
                }
            )

        never_rows = fetch_all(
            conn,
            backend,
            """
            SELECT p.nickname, p.id
            FROM players p
            WHERE p.status = 'active'
              AND (? IS NULL OR p.guild_id = ?)
              AND NOT EXISTS (
                SELECT 1 FROM event_signups es
                JOIN events e ON e.id = es.event_id
                WHERE es.player_id = p.id
                  AND e.created_at >= ?
                  AND (? IS NULL OR e.guild_id = ?)
                  AND e.status = 'closed'
              )
            ORDER BY p.nickname
            LIMIT 200
            """,
            (guild_db_id, guild_db_id, since, guild_db_id, guild_db_id),
        )
        attendance = fetch_all(
            conn,
            backend,
            """
            WITH ev AS (
                SELECT id FROM events e
                WHERE e.created_at >= ? AND (? IS NULL OR e.guild_id = ?)
                  AND e.status = 'closed'
            ),
            tc AS (SELECT COUNT(*) AS total FROM ev)
            SELECT p.nickname,
                   COUNT(DISTINCT es.event_id) AS events_attended,
                   (SELECT total FROM tc) AS total_events,
                   CASE WHEN (SELECT total FROM tc) > 0
                        THEN ROUND(1.0 * COUNT(DISTINCT es.event_id) / (SELECT total FROM tc) * 100, 1)
                        ELSE 0 END AS attendance_pct
            FROM event_signups es
            JOIN ev ON ev.id = es.event_id
            JOIN players p ON p.id = es.player_id
            WHERE es.player_id IS NOT NULL
            GROUP BY p.id, p.nickname
            ORDER BY events_attended ASC, p.nickname
            LIMIT 80
            """,
            (since, guild_db_id, guild_db_id),
        )
        stable = fetch_all(
            conn,
            backend,
            """
            WITH ev AS (
                SELECT id FROM events e
                WHERE e.created_at >= ? AND (? IS NULL OR e.guild_id = ?)
                  AND e.status = 'closed'
            ),
            tc AS (SELECT COUNT(*) AS total FROM ev),
            agg AS (
                SELECT p.nickname,
                       COUNT(DISTINCT es.event_id) AS events_attended,
                       (SELECT total FROM tc) AS total_events,
                       CASE WHEN (SELECT total FROM tc) > 0
                            THEN ROUND(1.0 * COUNT(DISTINCT es.event_id) / (SELECT total FROM tc) * 100, 1)
                            ELSE 0 END AS attendance_pct
                FROM event_signups es
                JOIN ev ON ev.id = es.event_id
                JOIN players p ON p.id = es.player_id
                WHERE es.player_id IS NOT NULL
                GROUP BY p.id, p.nickname
            )
            SELECT * FROM agg
            WHERE total_events > 0 AND events_attended * 3 >= total_events
            ORDER BY attendance_pct DESC, events_attended DESC
            LIMIT 40
            """,
            (since, guild_db_id, guild_db_id),
        )

    uc = int(unique_participants["c"]) if unique_participants and unique_participants.get("c") is not None else 0
    te = int(total_events["c"]) if total_events and total_events.get("c") is not None else 0
    part_pct = round(100.0 * uc / active_roster, 1) if active_roster > 0 else 0.0
    avg_players_overall = None
    if te > 0 and backend == "postgres":
        r = fetch_one(
            conn,
            backend,
            """
            SELECT ROUND(AVG(cnt)::numeric, 2) AS a FROM (
                SELECT COUNT(DISTINCT CASE WHEN es.player_id IS NOT NULL THEN es.player_id END) AS cnt
                FROM events e
                LEFT JOIN event_signups es ON es.event_id = e.id
                WHERE e.created_at >= $2::timestamp
                  AND ($1::int IS NULL OR e.guild_id = $1::int)
                  AND e.status = 'closed'
                GROUP BY e.id
            ) x
            """,
            (guild_db_id, since),
        )
        avg_players_overall = float(r["a"]) if r and r.get("a") is not None else None
    elif te > 0 and backend == "sqlite":
        if fill_rows:
            s = sum(int(r["players_in_event"] or 0) for r in fill_rows)
            avg_players_overall = round(s / len(fill_rows), 2)

    return {
        "active_roster_count": active_roster,
        "unique_participants_period": uc,
        "events_in_period": te,
        "participation_pct_of_roster": part_pct,
        "avg_players_per_event_overall": avg_players_overall,
        "per_content": per_content,
        "never_attended": never_rows,
        "low_attendance": attendance,
        "stable_attendance": stable,
        "ratio_avg_to_unique": (
            round((avg_players_overall or 0) / uc, 3) if uc and avg_players_overall else None
        ),
        "only_closed_events": True,
    }


def list_events_catalog(conn, backend: str, guild_db_id: Optional[int], limit: int = 100) -> List[dict]:
    lim = max(1, min(int(limit), 200))
    if backend == "postgres":
        return fetch_all(
            conn,
            backend,
            f"""
            SELECT e.id, e.content_name, e.event_time, e.status, e.created_at, e.guild_id, g.name AS guild_name
            FROM events e
            LEFT JOIN guilds g ON g.id = e.guild_id
            WHERE ($1::int IS NULL OR e.guild_id = $1::int)
            ORDER BY e.id DESC
            LIMIT {lim}
            """,
            (guild_db_id,),
        )
    return fetch_all(
        conn,
        backend,
        f"""
        SELECT e.id, e.content_name, e.event_time, e.status, e.created_at, e.guild_id, g.name AS guild_name
        FROM events e
        LEFT JOIN guilds g ON g.id = e.guild_id
        WHERE (? IS NULL OR e.guild_id = ?)
        ORDER BY e.id DESC
        LIMIT {lim}
        """,
        (guild_db_id, guild_db_id),
    )


def delete_events_by_ids(conn, backend: str, ids: List[int]) -> int:
    clean: List[int] = []
    for x in ids:
        try:
            i = int(x)
            if i > 0:
                clean.append(i)
        except (TypeError, ValueError):
            continue
    clean = clean[:50]
    if not clean:
        return 0
    cur = conn.cursor()
    if backend == "postgres":
        ph = ",".join(["%s"] * len(clean))
        cur.execute(f"DELETE FROM events WHERE id IN ({ph})", tuple(clean))
    else:
        ph = ",".join(["?"] * len(clean))
        cur.execute(f"DELETE FROM events WHERE id IN ({ph})", tuple(clean))
    conn.commit()
    try:
        return int(cur.rowcount) if cur.rowcount is not None else 0
    except Exception:
        return 0


def get_database_storage(conn, backend: str) -> dict:
    quota = int(os.environ.get("DASHBOARD_DB_QUOTA_BYTES", str(512 * 1024 * 1024)))
    bytes_used: Optional[int] = None
    if backend == "postgres":
        row = fetch_one(conn, backend, "SELECT pg_database_size(current_database())::bigint AS b", ())
        if row and row.get("b") is not None:
            bytes_used = int(row["b"])
    else:
        cur = conn.cursor()
        cur.execute("PRAGMA page_count")
        r1 = cur.fetchone()
        cur.execute("PRAGMA page_size")
        r2 = cur.fetchone()
        if r1 is not None and r2 is not None:
            bytes_used = int(r1[0] or 0) * int(r2[0] or 0)
    free_est = (quota - bytes_used) if bytes_used is not None else None
    pct = round(100.0 * bytes_used / quota, 2) if bytes_used is not None and quota > 0 else None
    return {
        "db_quota_bytes": quota,
        "db_quota_gb": round(quota / (1024**3), 4),
        "db_used_bytes": bytes_used,
        "db_used_mb": round(bytes_used / (1024 * 1024), 2) if bytes_used is not None else None,
        "db_free_bytes_estimate": free_est,
        "db_free_mb_estimate": round(free_est / (1024 * 1024), 2) if free_est is not None else None,
        "db_used_pct_of_quota": pct,
    }


def get_mentors_payroll(conn, backend: str, guild_db_id: Optional[int], days: int, fund: int) -> dict:
    since = _since(days)
    fund = max(0, int(fund))
    if backend == "postgres":
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT
                p.id,
                p.discord_id,
                p.nickname,
                COUNT(s.id) AS total_sessions,
                COUNT(s.id) FILTER (WHERE s.session_date >= $2::timestamp) AS sessions_window
            FROM players p
            JOIN sessions s ON s.mentor_id = p.id
            WHERE ($1::int IS NULL OR p.guild_id = $1::int)
            GROUP BY p.id, p.discord_id, p.nickname
            HAVING COUNT(s.id) FILTER (WHERE s.session_date >= $2::timestamp) > 0
            ORDER BY sessions_window DESC
            """,
            (guild_db_id, since),
        )
    else:
        rows = fetch_all(
            conn,
            backend,
            """
            SELECT
                p.id,
                p.discord_id,
                p.nickname,
                COUNT(s.id) AS total_sessions,
                SUM(CASE WHEN s.session_date >= ? THEN 1 ELSE 0 END) AS sessions_window
            FROM players p
            JOIN sessions s ON s.mentor_id = p.id
            WHERE (? IS NULL OR p.guild_id = ?)
            GROUP BY p.id, p.discord_id, p.nickname
            HAVING SUM(CASE WHEN s.session_date >= ? THEN 1 ELSE 0 END) > 0
            ORDER BY sessions_window DESC
            """,
            (since, guild_db_id, guild_db_id, since),
        )

    total_w = sum(int(r["sessions_window"] or 0) for r in rows)
    mentors = []
    for r in rows:
        w = int(r["sessions_window"] or 0)
        share = (w / total_w) if total_w > 0 else 0
        payout = int(fund * share)
        mentors.append(
            {
                "nickname": r["nickname"],
                "discord_id": r.get("discord_id"),
                "sessions_window": w,
                "total_sessions": int(r.get("total_sessions") or 0),
                "share_pct": round(100 * share, 2),
                "payout": payout,
            }
        )
    return {"fund": fund, "window_days": days, "total_sessions_window": total_w, "mentors": mentors}


def get_system_snapshot(bot_meta: Optional[dict] = None) -> dict:
    import platform
    import sys
    import threading

    du = os.environ.get("DATABASE_URL") or ""
    db_host = None
    try:
        if du:
            pu = urlparse(du.replace("postgres://", "postgresql://", 1))
            db_host = pu.hostname
    except Exception:
        db_host = None
    snap = {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "platform_machine": platform.machine(),
        "cwd": os.getcwd(),
        "database_url_set": bool(du),
        "database_host": db_host,
        "discord_token_set": bool(os.environ.get("DISCORD_TOKEN")),
        "guild_id_env": os.environ.get("GUILD_ID"),
        "guild_ids_env": os.environ.get("GUILD_IDS"),
        "render_service_id": os.environ.get("RENDER_SERVICE_ID"),
        "render_instance_id": os.environ.get("RENDER_INSTANCE_ID"),
        "render_external_url": os.environ.get("RENDER_EXTERNAL_URL"),
        "render_git_commit": os.environ.get("RENDER_GIT_COMMIT"),
        "render_branch": os.environ.get("RENDER_GIT_BRANCH"),
        "port": os.environ.get("PORT"),
        "thread_count": threading.active_count(),
        "render_env_subset": {
            k: v for k, v in os.environ.items() if k.startswith("RENDER_") and "KEY" not in k and "SECRET" not in k
        },
        "utc_now": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    try:
        import psutil

        proc = psutil.Process()
        snap["process_memory_mb"] = round(proc.memory_info().rss / 1024 / 1024, 1)
        snap["process_cpu_pct"] = proc.cpu_percent(interval=0.1)
        snap["open_files"] = len(proc.open_files())
    except Exception as e:
        snap["psutil"] = f"unavailable: {e}"

    if bot_meta:
        snap.update(bot_meta)
    return snap
