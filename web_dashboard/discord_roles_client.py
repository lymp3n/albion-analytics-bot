"""Fetch Discord guild roles for the dashboard (Bot token + REST)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def fetch_discord_guild_roles(discord_guild_id: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Returns (roles, error_message). Each role: {"id": str, "name": str}.
    error_message is None on success.
    """
    token = (os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if not token:
        return [], "DISCORD_TOKEN is not set on the server; cannot load role names."

    if discord_guild_id < 1:
        return [], "Guild has no Discord server ID — set it above and save."

    url = f"https://discord.com/api/v10/guilds/{discord_guild_id}/roles"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "AlbionAnalyticsDashboard (urllib)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        return [], f"Discord API HTTP {e.code}: {body or e.reason}"
    except urllib.error.URLError as e:
        return [], f"Discord API error: {e.reason!s}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], "Invalid JSON from Discord API."

    if not isinstance(data, list):
        return [], "Unexpected Discord API response."

    out: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        rid = item.get("id")
        name = item.get("name")
        if rid is None or name is None:
            continue
        out.append({"id": str(rid), "name": str(name)})

    out.sort(key=lambda x: (x["name"].casefold() != "@everyone", x["name"].casefold()))
    return out, None
