"""Fetch Discord guild roles for the dashboard (Bot token + REST)."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# In-process cache: fewer identical GET /guilds/{id}/roles (Discord global limits are strict).
_cache_lock = threading.Lock()
_cache: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}


def _cache_ttl_seconds() -> float:
    try:
        return max(30.0, float(os.environ.get("DISCORD_ROLES_CACHE_SECONDS", "120")))
    except ValueError:
        return 120.0


def _cache_get(guild_id: int) -> Optional[List[Dict[str, Any]]]:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(guild_id)
        if not entry:
            return None
        expires, roles = entry
        if now >= expires:
            del _cache[guild_id]
            return None
        return list(roles)


def _cache_set(guild_id: int, roles: List[Dict[str, Any]]) -> None:
    ttl = _cache_ttl_seconds()
    with _cache_lock:
        _cache[guild_id] = (time.monotonic() + ttl, roles)


def _parse_retry_after_seconds(headers: Any, body_txt: str) -> float:
    """Discord 429: Retry-After header (seconds) and/or JSON retry_after in body."""
    if headers:
        h = headers.get("Retry-After")
        if h:
            try:
                return max(0.5, float(h))
            except ValueError:
                pass
    try:
        if body_txt.strip().startswith("{"):
            j = json.loads(body_txt)
            ra = j.get("retry_after")
            if ra is not None:
                return max(0.5, float(ra))
    except Exception:
        pass
    return 2.0


def fetch_discord_guild_roles(discord_guild_id: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Returns (roles, error_message). Each role: {"id": str, "name": str}.
    Retries on HTTP 429 using Retry-After / JSON retry_after (capped per wait).
    """
    token = (os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    if not token:
        return [], "DISCORD_TOKEN is not set on the server; cannot load role names."

    if discord_guild_id < 1:
        return [], "Guild has no Discord server ID — set it above and save."

    cached = _cache_get(discord_guild_id)
    if cached is not None:
        return cached, None

    url = f"https://discord.com/api/v10/guilds/{discord_guild_id}/roles"
    max_attempts = int(os.environ.get("DISCORD_ROLES_MAX_RETRIES", "5"))
    try:
        cap_wait = float(os.environ.get("DISCORD_ROLES_RETRY_CAP_SEC", "60"))
    except ValueError:
        cap_wait = 60.0

    total_slept = 0.0
    last_429_snippet = ""

    for attempt in range(max_attempts):
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bot {token}",
                "User-Agent": "DiscordBot (https://github.com/lymp3n/albion-analytics-bot, 1.0)",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            body_txt = ""
            try:
                body_txt = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            snippet = body_txt[:800] if body_txt else ""

            if e.code != 429:
                return [], f"Discord API HTTP {e.code}: {snippet or e.reason}"

            last_429_snippet = snippet
            wait = min(_parse_retry_after_seconds(e.headers, body_txt), cap_wait)
            total_slept += wait
            if attempt + 1 >= max_attempts:
                break
            time.sleep(wait)
            continue
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
        _cache_set(discord_guild_id, out)
        return out, None

    msg = (
        "Discord rate limit (HTTP 429). Wait several minutes before using “Load names from Discord” again; "
        "avoid opening multiple dashboards or double-clicking. "
        f"Retried {max_attempts} time(s), waited ~{int(total_slept)}s total."
    )
    if last_429_snippet:
        msg += f" Detail: {last_429_snippet[:400]}"
    return [], msg
