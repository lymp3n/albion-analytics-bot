"""
Reference: which slash commands / UI actions need which bot permission tier.
Keep in sync with checks in commands/*.py (require_member / require_mentor / require_founder).
"""
from __future__ import annotations

from typing import Any, Dict, List

from utils.shotcaller_role_ids import SHOTCALLER_ROLE_IDS


def get_role_assist_catalog() -> Dict[str, Any]:
    """Table for the dashboard: tier, short command list, extra detail."""
    shot = ", ".join(str(x) for x in sorted(SHOTCALLER_ROLE_IDS))
    table: List[Dict[str, str]] = [
        {
            "tier": "Everyone",
            "commands": "`/register`",
            "details": "Join with a guild invite code. No bot role tier required yet.",
        },
        {
            "tier": "Basic",
            "commands": "`/menu` · `/ticket` create & list · `/event` create · event Join/Leave · `/stats` (self)",
            "details": "Needs member-level access (`require_member`). `/ticket list` shows your tickets; mentors see the queue. Event buttons need a player profile.",
        },
        {
            "tier": "Staff",
            "commands": "`/stats` (other player) · `/ticket` claim, rate, unclaim, info · `/event` close & roster · event Close/Manage",
            "details": "Mentor tier (`require_mentor`); founders count too. Event roster = add/remove/swap/extra. Shotcaller Discord role IDs act like staff for events: "
            + shot
            + ".",
        },
        {
            "tier": "Admin",
            "commands": "`/guild` · `/payroll` · `/stats_seed_test`",
            "details": "Founder-only (`require_founder`): roster management, mentor payout split, test data seed.",
        },
        {
            "tier": "Economy",
            "commands": "Economy dashboard page (`/dashboard/economy`) + journal / guild bonus operations",
            "details": "Optional dedicated role tier for financial operations; founders/admin still have access.",
        },
    ]
    return {"table": table, "shotcaller_role_ids": sorted(SHOTCALLER_ROLE_IDS)}
