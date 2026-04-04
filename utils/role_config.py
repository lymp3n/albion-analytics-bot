"""
Discord role ID lists for permission tiers (member / mentor / founder).
Used by Permissions and the dashboard; pure helpers are easy to unit-test.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

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
