from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
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


def _parse_iso_utc(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        # Albion data dates are UTC strings.
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


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


def get_item_price_24h_trimmed_mean(item_id: str) -> Tuple[Optional[dict], Optional[str], bool]:
    """
    Returns robust market price over 24h across all cities.
    Keeps only city prices >= 50% of median city price to remove outliers.
    """
    item_id = (item_id or "").strip()
    if not item_id:
        return None, "item_id is required", False

    key = f"trimmed24h|{item_id}"
    now = time.time()
    ttl = _cache_ttl()
    hit = _CACHE.get(key)
    if hit and (now - hit[0]) <= ttl:
        return hit[1], None, False

    endpoint = f"{_base_url()}/api/v2/stats/prices/{item_id}"
    # Read all cities, default quality 1.
    query = urlencode({"qualities": 1})
    req = Request(f"{endpoint}?{query}", headers={"Accept": "application/json", "User-Agent": "albion-analytics-bot/1.0"})

    try:
        with urlopen(req, timeout=_timeout()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            if hit:
                return hit[1], "No market data, returned stale cache", True
            return None, "No market data for item", False

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        by_city: Dict[str, int] = {}
        for row in payload:
            city = str(row.get("city") or "").strip()
            if not city:
                continue
            dt_sell = _parse_iso_utc(row.get("sell_price_min_date"))
            dt_buy = _parse_iso_utc(row.get("buy_price_max_date"))
            price = int(row.get("sell_price_min") or row.get("buy_price_max") or 0)
            if price <= 0:
                continue
            # Keep only records with recent sell/buy snapshot.
            if ((dt_sell and dt_sell >= cutoff) or (dt_buy and dt_buy >= cutoff)) is False:
                continue
            # Keep max recent price per city (avoids stale tiny values within same city).
            prev = by_city.get(city, 0)
            if price > prev:
                by_city[city] = price

        values = [v for v in by_city.values() if v > 0]
        if not values:
            if hit:
                return hit[1], "No 24h city prices, returned stale cache", True
            return None, "No valid 24h city prices", False
        ordered = sorted(values)
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else int(round((ordered[mid - 1] + ordered[mid]) / 2.0))
        floor = max(1, int(round(median * 0.5)))
        filtered = [v for v in values if v >= floor]
        if not filtered:
            filtered = values
        unit_price = int(round(sum(filtered) / float(len(filtered))))

        out = {
            "item_id": item_id,
            "quality": 1,
            "method": "24h_trimmed_mean_all_cities",
            "city_count": len(values),
            "median_price": median,
            "trim_floor_50pct": floor,
            "used_city_count": len(filtered),
            "market_unit_price": unit_price,
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


def search_item_ids(query: str, limit: int = 20) -> Tuple[list[str], Optional[str]]:
    q = str(query or "").strip()
    if len(q) < 2:
        return [], None
    lim = max(1, min(int(limit), 50))
    endpoint = f"{_base_url()}/api/v2/search"
    req = Request(
        f"{endpoint}?{urlencode({'q': q})}",
        headers={"Accept": "application/json", "User-Agent": "albion-analytics-bot/1.0"},
    )
    try:
        with urlopen(req, timeout=_timeout()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, list):
            return [], "Invalid search response"
        out: list[str] = []
        for row in payload:
            val = str(row.get("ItemTypeId") or row.get("UniqueName") or "").strip()
            if not val:
                continue
            out.append(val)
            if len(out) >= lim:
                break
        return out, None
    except Exception as e:
        return [], str(e)
