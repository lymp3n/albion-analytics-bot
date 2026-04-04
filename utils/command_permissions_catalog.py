"""
Reference: which slash commands / UI actions need which bot permission tier.
Keep in sync with checks in commands/*.py (require_member / require_mentor / require_founder).
"""
from __future__ import annotations

from typing import Any, Dict, List

from utils.shotcaller_role_ids import SHOTCALLER_ROLE_IDS


def get_role_assist_catalog() -> Dict[str, Any]:
    """
    Sections ordered from open to strict. Each row: command (slash or UI), description (EN).
    """
    shot_ids = ", ".join(str(x) for x in sorted(SHOTCALLER_ROLE_IDS))
    sections: List[Dict[str, Any]] = [
        {
            "id": "public",
            "title": "Everyone",
            "subtitle": "No Basic/Staff/Admin role required from this bot (still need server access).",
            "rows": [
                {"command": "`/register`", "description": "Join a guild with an invite code."},
            ],
        },
        {
            "id": "member",
            "title": "Basic (member)",
            "subtitle": "Needs the bot to treat the user as a member (your Basic tier roles, or defaults).",
            "rows": [
                {"command": "`/menu`", "description": "Main menu (ticket / own stats / tickets — registration still required)."},
                {"command": "`/ticket create`", "description": "Open a new session ticket."},
                {"command": "`/ticket list`", "description": "List tickets (members see their own; Staff see queue in their guild)."},
                {"command": "`/event create`", "description": "Post a new event in the current channel/thread."},
                {"command": "Event · **Join** / **Leave**", "description": "Buttons on the event message (registered player profile)."},
                {"command": "`/stats` (yourself)", "description": "View your own statistics and chart."},
            ],
        },
        {
            "id": "mentor",
            "title": "Staff (mentor)",
            "subtitle": "Mentors and founders pass these checks; founders inherit Staff access.",
            "rows": [
                {"command": "`/stats` (other player)", "description": "Target another member — Staff or Admin only."},
                {"command": "`/ticket claim`", "description": "Take an available ticket from the queue."},
                {"command": "`/ticket rate`", "description": "Submit evaluation in the ticket channel (after claim)."},
                {"command": "`/ticket unclaim`", "description": "Return a ticket to the queue (own ticket; Admin can override)."},
                {"command": "`/ticket info`", "description": "Detailed ticket view."},
                {"command": "`/event close`", "description": "Close an event by ID (locks roster)."},
                {"command": "`/event add_player` · `remove_player` · `swap_players` · `add_extra`", "description": "Roster management commands."},
                {"command": "Event · **Close Event** · **Manage**", "description": "Buttons on the event post (same as slash roster tools)."},
                {
                    "command": "Shotcaller Discord roles",
                    "description": f"Users with these role IDs can manage/close events like Staff: `{shot_ids}` (configured in bot code).",
                },
            ],
        },
        {
            "id": "founder",
            "title": "Admin (founder)",
            "subtitle": "Guild administration and sensitive tools.",
            "rows": [
                {"command": "`/guild`", "description": "approve / promote / demote / info — founders only."},
                {"command": "`/payroll`", "description": "Split mentor fund from session data."},
                {"command": "`/stats_seed_test`", "description": "Seed fake sessions (testing) — founders only."},
            ],
        },
    ]
    return {"sections": sections, "shotcaller_role_ids": sorted(SHOTCALLER_ROLE_IDS)}
