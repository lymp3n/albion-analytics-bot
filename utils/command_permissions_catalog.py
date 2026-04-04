"""
Reference: which slash commands / UI actions need which bot permission tier.
Keep in sync with checks in commands/*.py (require_member / require_mentor / require_founder).
"""
from __future__ import annotations

from typing import Any, Dict, List

from utils.shotcaller_role_ids import SHOTCALLER_ROLE_IDS


def get_role_assist_catalog() -> Dict[str, Any]:
    """One compact table for the dashboard (tier → what they can use)."""
    table: List[Dict[str, str]] = [
        {"tier": "Everyone", "commands": "`/register`"},
        {
            "tier": "Basic",
            "commands": "`/menu` · `/ticket` create/list · `/event` create · event Join/Leave · `/stats` self",
        },
        {
            "tier": "Staff",
            "commands": "`/stats` others · `/ticket` claim/rate/unclaim/info · `/event` roster* · event Close/Manage · shotcaller roles (IDs in bot code)",
        },
        {"tier": "Admin", "commands": "`/guild` · `/payroll` · `/stats_seed_test`"},
    ]
    return {"table": table, "shotcaller_role_ids": sorted(SHOTCALLER_ROLE_IDS)}
