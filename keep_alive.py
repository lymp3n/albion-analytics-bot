import base64
import logging
import os
import time
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Dict, Optional

from flask import Flask, Response, send_file
from waitress import serve

logger = logging.getLogger("keep_alive")

_bot_meta: dict = {}


def set_bot_ready(*, touch_ready: bool = False, **kwargs: Any) -> None:
    """
    Merge telemetry for the dashboard. Use touch_ready=True only from on_ready
    so last_ready_utc stays the connect time; heartbeats pass last_discord_heartbeat_utc only.
    """
    global _bot_meta
    _bot_meta = {**_bot_meta, **kwargs}
    if touch_ready:
        _bot_meta["last_ready_utc"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def get_bot_meta() -> dict:
    return dict(_bot_meta)


def set_discord_api_blocked(active: bool, detail: Optional[str] = None) -> None:
    """Set when startup hits Discord 429 / Cloudflare-style blocks; cleared from on_ready."""
    global _bot_meta
    _bot_meta = {**_bot_meta}
    if active:
        _bot_meta["discord_api_blocked"] = True
        if detail:
            _bot_meta["discord_api_blocked_detail"] = str(detail)[:2000]
        _bot_meta["discord_api_blocked_utc"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    else:
        _bot_meta.pop("discord_api_blocked", None)
        _bot_meta.pop("discord_api_blocked_detail", None)
        _bot_meta.pop("discord_api_blocked_utc", None)


def _parse_meta_utc(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    s = s.replace(" UTC", "").strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def get_bot_health() -> Dict[str, Any]:
    """
    Short, non-technical summary for the System tab: is the Discord side likely up?
    """
    meta = get_bot_meta()
    now = datetime.now(timezone.utc)
    hb = _parse_meta_utc(meta.get("last_discord_heartbeat_utc"))
    rd = _parse_meta_utc(meta.get("last_ready_utc"))
    db_ok = meta.get("database_connected")

    if meta.get("discord_api_blocked"):
        return {
            "signal_status": "discord_blocked",
            "discord_api_blocked": True,
            "title": "Discord API",
            "summary": (
                "Временная блокировка или глобальный лимит запросов со стороны Discord (HTTP 429 / Cloudflare). "
                "Бот переподключается с увеличивающейся задержкой."
            ),
            "seconds_since_signal": None,
            "database_ok": db_ok,
            "hint": meta.get("discord_api_blocked_detail"),
            "discord_api_blocked_detail": meta.get("discord_api_blocked_detail"),
            "discord_api_blocked_utc": meta.get("discord_api_blocked_utc"),
        }

    if hb is None and rd is None:
        return {
            "signal_status": "unknown",
            "title": "Discord bot",
            "summary": (
                "No recent signal from the bot yet. If the service just started, wait about a minute. "
                "If this stays here, the bot may not be running or cannot reach Discord."
            ),
            "seconds_since_signal": None,
            "database_ok": db_ok,
            "hint": "Slash commands show “The application did not respond” when the bot is offline or too slow to answer.",
        }

    # Without heartbeat (older deploy), last_ready only fires once — never show “down” from that alone.
    if hb is None and rd is not None:
        age = max(0.0, (now - rd).total_seconds())
        if age < 300:
            status = "ok"
            summary = (
                "The bot signed in to Discord recently. "
                "(Deploy the latest code for a live heartbeat and clearer status.)"
            )
        else:
            status = "warn"
            summary = (
                "This run only reports the last Discord login time, not live activity. "
                f"That login was {int(age // 60)}+ minutes ago — redeploy the latest bot for a reliable online check, "
                "or confirm in Discord whether the bot is green."
            )
        out = {
            "signal_status": status,
            "title": "Discord bot",
            "summary": summary,
            "seconds_since_signal": int(age),
            "database_ok": db_ok,
            "hint": None,
        }
        if db_ok is False:
            out["hint"] = "Database did not connect at startup — check DATABASE_URL and provider status."
        return out

    last = max(t for t in (hb, rd) if t is not None)
    age = max(0.0, (now - last).total_seconds())
    if age < 120:
        status = "ok"
        summary = f"Last activity from the bot was {int(age)} seconds ago — looks online."
    elif age < 600:
        status = "warn"
        summary = f"Last activity was {int(age // 60)} minutes ago. It may be reconnecting or overloaded."
    else:
        status = "down"
        summary = (
            f"No activity for {int(age // 60)}+ minutes. This page still loads (web server is up), "
            "but Discord commands may not work until the bot reconnects."
        )

    out = {
        "signal_status": status,
        "title": "Discord bot",
        "summary": summary,
        "seconds_since_signal": int(age),
        "database_ok": db_ok,
        "hint": None,
    }
    if db_ok is False:
        out["hint"] = "Database did not connect at startup — check DATABASE_URL and provider status."
    return out


_http_started: Optional[float] = None


def get_http_uptime_s():
    if _http_started is None:
        return None
    return round(time.time() - _http_started, 1)


_ROOT = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_ROOT, "web_dashboard", "templates"),
    static_folder=os.path.join(_ROOT, "web_dashboard", "static"),
    static_url_path="/dash-static",
)

from web_dashboard.routes import register_dashboard

register_dashboard(app)


@app.route("/")
def home():
    return "I'm alive!"


@app.route("/video/ban.gif")
def serve_ban_gif():
    """Dashboard ban-screen animation; replace video/ban.gif in the repo with your asset."""
    path = os.path.join(_ROOT, "video", "ban.gif")
    if os.path.isfile(path):
        return send_file(path, mimetype="image/gif")
    data = base64.b64decode(
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    )
    return Response(data, mimetype="image/gif")


def run():
    global _http_started
    _http_started = time.time()
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting HTTP server on port %s (health + dashboard)", port)
    serve(app, host="0.0.0.0", port=port, _quiet=True)


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
