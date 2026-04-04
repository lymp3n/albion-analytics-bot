import logging
import os
import time
from threading import Thread
from typing import Optional

from flask import Flask
from waitress import serve

logger = logging.getLogger("keep_alive")

_bot_meta: dict = {}


def set_bot_ready(**kwargs):
    """Called from Discord bot on_ready — surfaced on dashboard System tab."""
    from datetime import datetime

    global _bot_meta
    _bot_meta = {
        **_bot_meta,
        "last_ready_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        **kwargs,
    }


def get_bot_meta() -> dict:
    return dict(_bot_meta)


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


def run():
    global _http_started
    _http_started = time.time()
    port = int(os.environ.get("PORT", 8080))
    logger.info("Starting HTTP server on port %s (health + dashboard)", port)
    serve(app, host="0.0.0.0", port=port, _quiet=True)


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
