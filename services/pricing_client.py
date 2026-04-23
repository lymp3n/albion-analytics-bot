from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_CACHE: Dict[str, Tuple[float, dict]] = {}


def _base_url() -> str:
    # Prefer Albion Data Project for real-time market pricing.
    return (os.environ.get("ALBION_PRICING_BASE_URL") or "https://west.albion-online-data.com").rstrip("/")


def _timeout() -> float:
    try:
        return max(2.0, float(os.environ.get("ALBION_PRICING_TIMEOUT_SEC", "7")))
    except ValueError:
        return 7.0


def _cache_ttl() -> int:
    try:
        return max(20, int(os.environ.get("ALBION_PRICING_CACHE_TTL_SEC", "90")))
    except ValueError:
        return 90


def _cache_key(item_id: str, location: str, quality: int) -> str:
    return f"{item_id}|{location}|{quality}"


def get_item_price(item_id: str, location: str, quality: int = 1) -> Tuple[Optional[dict], Optional[str], bool]:
    """
    Returns (price_obj, error, stale).
    price_obj example: {"item_id": "...", "location": "...", "quality": 1, "sell_price_min": 12345, ...}
    """
    item_id = (item_id or "").strip()
    location = (location or "").strip()
    if not item_id or not location:
        return None, "item_id and location are required", False

    key = _cache_key(item_id, location, quality)
    now = time.time()
    ttl = _cache_ttl()
    hit = _CACHE.get(key)
    if hit and (now - hit[0]) <= ttl:
        return hit[1], None, False

    endpoint = f"{_base_url()}/api/v2/stats/prices/{item_id}"
    query = urlencode({"locations": location, "qualities": quality})
    req = Request(f"{endpoint}?{query}", headers={"Accept": "application/json", "User-Agent": "albion-analytics-bot/1.0"})

    try:
        with urlopen(req, timeout=_timeout()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            if hit:
                return hit[1], "No market data, returned stale cache", True
            return None, "No market data for item/location", False
        first = payload[0]
        out = {
            "item_id": first.get("item_id") or item_id,
            "city": first.get("city") or location,
            "quality": int(first.get("quality") or quality),
            "sell_price_min": first.get("sell_price_min"),
            "buy_price_max": first.get("buy_price_max"),
            "sell_price_min_date": first.get("sell_price_min_date"),
            "buy_price_max_date": first.get("buy_price_max_date"),
            "source": "albion-online-data",
            "fetched_at_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }
        _CACHE[key] = (now, out)
        return out, None, False
    except HTTPError as e:
        if hit:
            return hit[1], f"HTTP {e.code}, returned stale cache", True
        return None, f"HTTP {e.code}", False
    except URLError as e:
        if hit:
            return hit[1], f"Network error, returned stale cache: {e.reason}", True
        return None, f"Network error: {e.reason}", False
    except Exception as e:
        if hit:
            return hit[1], f"Unexpected error, returned stale cache: {e}", True
        return None, str(e), False
