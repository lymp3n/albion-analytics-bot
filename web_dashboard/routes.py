import json
import os
import time
from functools import wraps

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from web_dashboard.data_service import (
    delete_events_by_ids,
    get_database_storage,
    get_events_analytics,
    get_mentors_payroll,
    get_overview,
    get_players_table,
    get_system_snapshot,
    get_tickets_breakdown,
    list_events_catalog,
    list_guilds,
)
from web_dashboard.db_sync import get_sync_connection

from event_templates_store import read_raw_text, save_raw_text, templates_file_path


def register_dashboard(app: Flask) -> None:
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("DASHBOARD_SECRET") or "change-me-in-production"

    def dashboard_secret() -> str:
        return (os.environ.get("DASHBOARD_SECRET") or "").strip()

    def require_secret_configured():
        if not dashboard_secret():
            return False
        return True

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not require_secret_configured():
                return (
                    render_template(
                        "dashboard_login.html",
                        error="Set DASHBOARD_SECRET in environment (Render env vars).",
                    ),
                    503,
                )
            if not session.get("dash_ok"):
                return redirect(url_for("dashboard_login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    @app.route("/dashboard/login", methods=["GET", "POST"])
    def dashboard_login():
        if not require_secret_configured():
            return (
                render_template(
                    "dashboard_login.html",
                    error="Set DASHBOARD_SECRET in environment to enable the dashboard.",
                ),
                503,
            )
        err = None
        if request.method == "POST":
            token = (request.form.get("token") or "").strip()
            if token == dashboard_secret():
                session["dash_ok"] = True
                session.permanent = True
                nxt = request.args.get("next") or url_for("dashboard_app")
                return redirect(nxt)
            err = "Invalid access token."
        return render_template("dashboard_login.html", error=err)

    @app.route("/dashboard/logout", methods=["POST"])
    def dashboard_logout():
        session.pop("dash_ok", None)
        return redirect(url_for("dashboard_login"))

    @app.route("/dashboard")
    @login_required
    def dashboard_app():
        return render_template("dashboard.html")

    @app.route("/dashboard/api/data")
    @login_required
    def dashboard_api_data():
        try:
            days = int(request.args.get("days", 30))
        except ValueError:
            days = 30
        days = max(1, min(days, 730))

        guild_raw = request.args.get("guild_id", "").strip()
        guild_db_id = None
        if guild_raw:
            try:
                guild_db_id = int(guild_raw)
            except ValueError:
                guild_db_id = None

        try:
            fund = int(request.args.get("fund", 1_000_000))
        except ValueError:
            fund = 1_000_000
        fund = max(0, min(fund, 10_000_000_000))

        t0 = time.perf_counter()
        try:
            with get_sync_connection() as (conn, backend):
                guilds = list_guilds(conn, backend)
                overview = get_overview(conn, backend, guild_db_id, days)
                players = get_players_table(conn, backend, guild_db_id, days)
                tickets = get_tickets_breakdown(conn, backend, guild_db_id, days)
                events = get_events_analytics(conn, backend, guild_db_id, days)
                mentors = get_mentors_payroll(conn, backend, guild_db_id, days, fund)
                events_catalog = list_events_catalog(conn, backend, guild_db_id, 120)
                db_storage = get_database_storage(conn, backend)
        except Exception as e:
            payload = {"ok": False, "error": str(e)}
            return app.response_class(
                response=json.dumps(payload, default=str),
                status=500,
                mimetype="application/json",
            )

        try:
            from keep_alive import get_bot_meta

            bot_meta = get_bot_meta()
        except Exception:
            bot_meta = {}

        system = get_system_snapshot(bot_meta)
        system.update(db_storage)
        system["db_query_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        try:
            from keep_alive import get_http_uptime_s

            system["http_server_uptime_s"] = get_http_uptime_s()
        except Exception:
            pass
        try:
            from keep_alive import get_bot_health

            system["bot_health"] = get_bot_health()
        except Exception:
            system["bot_health"] = {
                "signal_status": "unknown",
                "title": "Discord bot",
                "summary": "Status could not be loaded.",
                "database_ok": None,
                "hint": None,
            }

        payload = {
            "ok": True,
            "guilds": guilds,
            "filters": {"days": days, "guild_id": guild_db_id, "fund": fund},
            "overview": overview,
            "players": players,
            "tickets": tickets,
            "events": events,
            "events_catalog": events_catalog,
            "mentors": mentors,
            "system": system,
        }
        return app.response_class(
            response=json.dumps(payload, default=str),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/events/delete", methods=["POST"])
    @login_required
    def dashboard_events_delete():
        body = request.get_json(silent=True) or {}
        raw_ids = body.get("ids")
        if not isinstance(raw_ids, list):
            return app.response_class(
                response=json.dumps({"ok": False, "error": "Expected JSON body { \"ids\": [1,2,3] }"}),
                status=400,
                mimetype="application/json",
            )
        try:
            with get_sync_connection() as (conn, backend):
                deleted = delete_events_by_ids(conn, backend, raw_ids)
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps({"ok": True, "deleted": deleted}, default=str),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/event-templates", methods=["GET"])
    @login_required
    def dashboard_event_templates_get():
        try:
            content = read_raw_text()
            path = str(templates_file_path())
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps({"ok": True, "content": content, "path": path}, default=str),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/event-templates", methods=["POST"])
    @login_required
    def dashboard_event_templates_post():
        body = request.get_json(silent=True) or {}
        content = body.get("content")
        if not isinstance(content, str):
            return app.response_class(
                response=json.dumps({"ok": False, "error": 'Send JSON { "content": "..." }'}), status=400, mimetype="application/json"
            )
        try:
            save_raw_text(content)
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except OSError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps({"ok": True, "message": "Saved. /event create uses this file immediately (same process)."}),
            mimetype="application/json",
        )
