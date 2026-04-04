"""
Discord role ID lists for permission tiers (member / mentor / founder).
Used by Permissions and the dashboard; pure helpers are easy to unit-test.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Discord snowflakes are < 2^63; keep a generous upper bound.
_MIN_SNOWFLAKE = 1
_MAX_SNOWFLAKE = 2**63 - 1


def parse_discord_role_ids(text: Optional[str]) -> List[int]:
    """Split comma / whitespace / semicolon separated IDs. Raises ValueError on bad input."""
    if text is None:
        return []
    s = str(text).strip()
    if not s:
        return []
    out: List[int] = []
    for part in re.split(r"[\s,;]+", s):
        part = part.strip()
        if not part:
            continue
        try:
            n = int(part)
        except ValueError as e:
            raise ValueError(f"Not a valid role ID: {part!r}") from e
        if n < _MIN_SNOWFLAKE or n > _MAX_SNOWFLAKE:
            raise ValueError(f"Role ID out of range: {n}")
        out.append(n)
    return out


def tier_set_from_db_value(raw: Optional[str], default_set: Set[int]) -> Set[int]:
    """None or blank DB field => use default_set copy."""
    if raw is None:
        return set(default_set)
    if isinstance(raw, str) and not raw.strip():
        return set(default_set)
    ids = parse_discord_role_ids(str(raw))
    return set(ids)


def effective_sets_from_override_row(
    row: Optional[Dict],
    default_members: Set[int],
    default_mentors: Set[int],
    default_founders: Set[int],
) -> Tuple[Set[int], Set[int], Set[int]]:
    """Compute effective role ID sets given an optional guild_role_overrides row."""
    if not row:
        return set(default_members), set(default_mentors), set(default_founders)
    m = tier_set_from_db_value(row.get("member_role_ids"), default_members)
    ment = tier_set_from_db_value(row.get("mentor_role_ids"), default_mentors)
    f = tier_set_from_db_value(row.get("founder_role_ids"), default_founders)
    return m, ment, f


def parse_single_snowflake(text: Optional[str]) -> Optional[int]:
    """Parse one Discord snowflake; empty -> None. Raises ValueError if invalid."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    try:
        n = int(s)
    except ValueError as e:
        raise ValueError(f"Not a valid ID: {s!r}") from e
    if n < _MIN_SNOWFLAKE or n > _MAX_SNOWFLAKE:
        raise ValueError(f"ID out of range: {n}")
    return n


def sets_from_assignment_rows(
    rows: List[Dict[str, Any]],
) -> Tuple[Set[int], Set[int], Set[int]]:
    """Build member / mentor / founder sets from guild_role_assignments rows."""
    m: Set[int] = set()
    ment: Set[int] = set()
    f: Set[int] = set()
    for row in rows:
        rid = int(row["discord_role_id"])
        t = str(row.get("tier") or "").strip().lower()
        if t == "member":
            m.add(rid)
        elif t == "mentor":
            ment.add(rid)
        elif t == "founder":
            f.add(rid)
    return m, ment, f


def assignment_rows_from_legacy_override(legacy: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten legacy three-string overrides into per-role rows (highest tier wins)."""
    if not legacy:
        return []
    f_raw = legacy.get("founder_role_ids")
    m_raw = legacy.get("mentor_role_ids")
    mem_raw = legacy.get("member_role_ids")
    f_ids = set(parse_discord_role_ids(str(f_raw))) if f_raw and str(f_raw).strip() else set()
    m_ids = set(parse_discord_role_ids(str(m_raw))) if m_raw and str(m_raw).strip() else set()
    mem_ids = set(parse_discord_role_ids(str(mem_raw))) if mem_raw and str(mem_raw).strip() else set()
    out: List[Dict[str, Any]] = []
    for rid in sorted(f_ids):
        out.append({"discord_role_id": rid, "tier": "founder"})
    for rid in sorted(m_ids - f_ids):
        out.append({"discord_role_id": rid, "tier": "mentor"})
    for rid in sorted(mem_ids - f_ids - m_ids):
        out.append({"discord_role_id": rid, "tier": "member"})
    return out


def normalize_ids_for_storage(text: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a user-entered list for DB storage.
    Returns None for blank (inherit default). Raises ValueError if invalid.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    ids = parse_discord_role_ids(s)
    if not ids:
        return None
    # Stable unique order for diff-friendly storage
    unique = sorted(set(ids))
    return ", ".join(str(x) for x in unique)
