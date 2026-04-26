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

from utils.command_permissions_catalog import get_role_assist_catalog
from utils.role_config import parse_discord_snowflake_string, parse_single_snowflake

from web_dashboard.data_service import (
    count_other_guilds_with_discord_id,
    delete_events_by_ids,
    delete_guild_role_overrides_row,
    ensure_guild_role_assignments_table,
    ensure_guild_role_overrides_table,
    fetch_guild_discord_id,
    get_database_storage,
    get_events_analytics,
    get_mentors_payroll,
    get_overview,
    get_players_table,
    guild_exists,
    get_system_snapshot,
    get_tickets_breakdown,
    list_events_catalog,
    list_guild_roles_dashboard,
    list_guilds,
    replace_guild_role_assignments_rows,
    update_guild_dashboard_meta,
)
from web_dashboard.db_sync import fetch_all, get_sync_connection
from web_dashboard.discord_roles_client import fetch_discord_guild_roles
from web_dashboard.economy_db_sync import get_economy_sync_connection
from web_dashboard.economy_service import (
    create_manual_loot_buyback_from_price,
    create_regear_request,
    issue_regear_request,
    balance_snapshot,
    cashflow_summary,
    create_routed_operation,
    economy_kpis,
    ensure_economy_schema,
    fetch_market_price,
    suggest_item_ids,
    forecast_summary,
    import_game_log_csv,
    get_config,
    set_config_values,
    list_alerts,
    list_audit_trail,
    list_discrepancy_queue,
    list_pending_approvals,
    list_game_log_imports,
    list_recent_entries,
    list_routing_rules,
    list_loot_buyback_requests,
    list_regear_requests,
    resolve_discrepancy,
    acknowledge_alert,
    pnl_summary,
    review_pending_entry,
    run_alert_threshold_checks,
    upsert_routing_rule,
)

from event_templates_store import read_raw_text, save_raw_text, templates_file_path


def register_dashboard(app: Flask) -> None:
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("DASHBOARD_SECRET") or "change-me-in-production"

    def _econ_err(e: Exception) -> str:
        return f"{type(e).__name__}: {e}"

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

    @app.route("/dashboard/economy")
    @login_required
    def dashboard_economy_app():
        return render_template("economy_dashboard.html")

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

    _VALID_TIERS = frozenset({"member", "mentor", "founder", "economy"})

    @app.route("/dashboard/api/role-assist-catalog", methods=["GET"])
    @login_required
    def dashboard_role_assist_catalog():
        try:
            payload = {"ok": True, **get_role_assist_catalog()}
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps(payload, default=str), mimetype="application/json")

    @app.route("/dashboard/api/discord-guild-roles", methods=["GET"])
    @login_required
    def dashboard_discord_guild_roles():
        guild_db_id = request.args.get("guild_id", type=int) or 0
        if guild_db_id < 1:
            return app.response_class(
                response=json.dumps({"ok": False, "error": "Invalid guild_id"}),
                status=400,
                mimetype="application/json",
            )
        try:
            with get_sync_connection() as (conn, backend):
                if not guild_exists(conn, backend, guild_db_id):
                    return app.response_class(
                        response=json.dumps({"ok": False, "error": "Guild not found"}),
                        status=404,
                        mimetype="application/json",
                    )
                discord_gid = fetch_guild_discord_id(conn, backend, guild_db_id)
            roles, err = fetch_discord_guild_roles(discord_gid)
            if err:
                return app.response_class(
                    response=json.dumps({"ok": False, "error": err, "roles": []}, default=str),
                    status=502,
                    mimetype="application/json",
                )
            # Force string ids so the browser JSON parser never rounds snowflakes.
            roles_out = [{"id": str(r["id"]), "name": str(r["name"])} for r in roles]
            return app.response_class(
                response=json.dumps(
                    {"ok": True, "roles": roles_out, "discord_guild_id": str(int(discord_gid))},
                    default=str,
                ),
                mimetype="application/json",
            )
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )

    @app.route("/dashboard/api/guild-roles", methods=["GET"])
    @login_required
    def dashboard_guild_roles_get():
        try:
            with get_sync_connection() as (conn, backend):
                rows = list_guild_roles_dashboard(conn, backend)
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps({"ok": True, "guilds": rows}, default=str),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/guild-roles", methods=["POST"])
    @login_required
    def dashboard_guild_roles_post():
        body = request.get_json(silent=True) or {}
        try:
            guild_db_id = int(body.get("guild_id", 0))
        except (TypeError, ValueError):
            guild_db_id = 0
        if guild_db_id < 1:
            return app.response_class(
                response=json.dumps({"ok": False, "error": "Invalid guild_id"}),
                status=400,
                mimetype="application/json",
            )
        raw_assignments = body.get("assignments")
        if not isinstance(raw_assignments, list):
            return app.response_class(
                response=json.dumps({"ok": False, "error": 'Expected JSON { "guild_id": N, "assignments": [...] }'}),
                status=400,
                mimetype="application/json",
            )
        pairs = []
        seen: set = set()
        try:
            for item in raw_assignments:
                if not isinstance(item, dict):
                    continue
                rid_str = parse_discord_snowflake_string(item.get("discord_role_id"))
                if not rid_str:
                    continue
                tier = str(item.get("tier", "")).strip().lower()
                if tier not in _VALID_TIERS:
                    return app.response_class(
                        response=json.dumps({"ok": False, "error": f"Invalid tier: {tier!r}"}),
                        status=400,
                        mimetype="application/json",
                    )
                if rid_str in seen:
                    continue
                seen.add(rid_str)
                raw_lbl = item.get("role_label")
                if isinstance(raw_lbl, str):
                    lbl = raw_lbl.strip() or None
                else:
                    lbl = None
                pairs.append((rid_str, tier, lbl))
        except (TypeError, ValueError) as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        try:
            with get_sync_connection() as (conn, backend):
                ensure_guild_role_overrides_table(conn, backend)
                ensure_guild_role_assignments_table(conn, backend)
                if not guild_exists(conn, backend, guild_db_id):
                    return app.response_class(
                        response=json.dumps({"ok": False, "error": "Guild not found"}),
                        status=404,
                        mimetype="application/json",
                    )
                replace_guild_role_assignments_rows(conn, backend, guild_db_id, pairs)
                delete_guild_role_overrides_row(conn, backend, guild_db_id)
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps(
                {
                    "ok": True,
                    "message": "Saved. Role access is stored per role (like Discord). Empty list = use config.yaml defaults.",
                }
            ),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/guild-meta", methods=["POST"])
    @login_required
    def dashboard_guild_meta_post():
        body = request.get_json(silent=True) or {}
        try:
            guild_db_id = int(body.get("guild_id", 0))
        except (TypeError, ValueError):
            guild_db_id = 0
        if guild_db_id < 1:
            return app.response_class(
                response=json.dumps({"ok": False, "error": "Invalid guild_id"}),
                status=400,
                mimetype="application/json",
            )
        kwargs = {}
        if "dashboard_label" in body:
            label = body.get("dashboard_label")
            if label is not None and not isinstance(label, str):
                return app.response_class(
                    response=json.dumps({"ok": False, "error": "dashboard_label must be a string"}),
                    status=400,
                    mimetype="application/json",
                )
            kwargs["dashboard_label"] = label
        parsed_did = None
        if "discord_id" in body:
            raw_did = body.get("discord_id")
            if raw_did is None or str(raw_did).strip() == "":
                parsed_did = 0
            else:
                try:
                    parsed_did = parse_single_snowflake(str(raw_did).strip())
                except ValueError as e:
                    return app.response_class(
                        response=json.dumps({"ok": False, "error": str(e)}, default=str),
                        status=400,
                        mimetype="application/json",
                    )
                if parsed_did is None:
                    parsed_did = 0
            kwargs["discord_id"] = int(parsed_did)
        if not kwargs:
            return app.response_class(
                response=json.dumps({"ok": False, "error": "No fields to update"}),
                status=400,
                mimetype="application/json",
            )
        try:
            with get_sync_connection() as (conn, backend):
                ensure_guild_role_overrides_table(conn, backend)
                if not guild_exists(conn, backend, guild_db_id):
                    return app.response_class(
                        response=json.dumps({"ok": False, "error": "Guild not found"}),
                        status=404,
                        mimetype="application/json",
                    )
                if "discord_id" in kwargs and int(kwargs["discord_id"]) > 0:
                    if count_other_guilds_with_discord_id(
                        conn, backend, guild_db_id, int(kwargs["discord_id"])
                    ) > 0:
                        return app.response_class(
                            response=json.dumps(
                                {"ok": False, "error": "Another guild already uses this Discord server ID."}
                            ),
                            status=400,
                            mimetype="application/json",
                        )
                update_guild_dashboard_meta(conn, backend, guild_db_id, **kwargs)
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(
            response=json.dumps({"ok": True, "message": "Guild info updated."}),
            mimetype="application/json",
        )

    @app.route("/dashboard/api/economy/data", methods=["GET"])
    @login_required
    def dashboard_economy_data():
        try:
            days = int(request.args.get("days", 30))
        except ValueError:
            days = 30
        days = max(1, min(days, 365))
        entry_status = str(request.args.get("entry_status", "") or "").strip().lower()
        category_q = str(request.args.get("category", "") or "").strip()
        source_q = str(request.args.get("source", "") or "").strip()
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                alert_state = run_alert_threshold_checks(conn, backend)
                payload = {
                    "ok": True,
                    "filters": {
                        "days": days,
                        "entry_status": entry_status,
                        "category": category_q,
                        "source": source_q,
                    },
                    "kpis": economy_kpis(conn, backend),
                    "entries": list_recent_entries(
                        conn,
                        backend,
                        160,
                        status=entry_status,
                        category_like=category_q,
                        source_like=source_q,
                    ),
                    "routing_rules": list_routing_rules(conn, backend),
                    "loot_buybacks": list_loot_buyback_requests(conn, backend, 80),
                    "regear_requests": list_regear_requests(conn, backend, 80),
                    "imports": list_game_log_imports(conn, backend, 40),
                    "pending_approvals": list_pending_approvals(conn, backend, 120),
                    "audit_trail": list_audit_trail(conn, backend, 180),
                    "discrepancies": list_discrepancy_queue(conn, backend, 180),
                    "alerts": list_alerts(conn, backend, 100),
                    "alert_state": alert_state,
                    "config": get_config(conn, backend),
                    "reports": {
                        "balance_snapshot": balance_snapshot(conn, backend),
                        "pnl_summary": pnl_summary(conn, backend, days),
                        "cashflow_summary": cashflow_summary(conn, backend, days),
                    },
                    "forecast": forecast_summary(conn, backend),
                }
            # Player nickname suggestions come from the main bot DB.
            try:
                with get_sync_connection() as (main_conn, main_backend):
                    player_rows = fetch_all(
                        main_conn,
                        main_backend,
                        """
                        SELECT nickname
                        FROM players
                        WHERE nickname IS NOT NULL AND TRIM(nickname) <> ''
                        ORDER BY nickname
                        LIMIT 600
                        """,
                        (),
                    )
                    payload["player_suggestions"] = [
                        str(r.get("nickname") or "").strip() for r in player_rows if str(r.get("nickname") or "").strip()
                    ]
            except Exception:
                payload["player_suggestions"] = []
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps(payload, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/loot-buyback", methods=["POST"])
    @login_required
    def dashboard_economy_loot_buyback():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = create_manual_loot_buyback_from_price(
                    conn,
                    backend,
                    buyback_price=int(body.get("buyback_price") or 0),
                    actor=str(body.get("approved_by") or "dashboard_admin").strip(),
                )
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Economy loot-buyback failed")
            print("Economy loot-buyback failed:", _econ_err(e), flush=True)
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "result": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/regear", methods=["POST"])
    @login_required
    def dashboard_economy_regear():
        body = request.get_json(silent=True) or {}
        action = str(body.get("action") or "create").strip().lower()
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                if action == "issue":
                    out = issue_regear_request(
                        conn,
                        backend,
                        request_id=int(body.get("request_id") or 0),
                        checked_by=str(body.get("checked_by") or "dashboard_admin").strip(),
                        issued_by=str(body.get("issued_by") or "dashboard_admin").strip(),
                        note=str(body.get("note") or "").strip(),
                    )
                else:
                    screenshot_url = str(body.get("screenshot_url") or "").strip()
                    if not screenshot_url:
                        screenshot_file = body.get("screenshot_file")
                        if isinstance(screenshot_file, dict):
                            name = str(screenshot_file.get("name") or "screenshot").strip() or "screenshot"
                            mime = str(screenshot_file.get("type") or "application/octet-stream").strip() or "application/octet-stream"
                            data = str(screenshot_file.get("data") or "").strip()
                            if data:
                                screenshot_url = f"data:{mime};name={name};base64,{data}"
                    out = create_regear_request(
                        conn,
                        backend,
                        player_name=str(body.get("player_name") or "").strip(),
                        content_type=str(body.get("content_type") or "").strip(),
                        item_id="REGEAR_GENERIC",
                        quantity=1,
                        unit_cost=int(body.get("unit_cost") or 0),
                        screenshot_url=screenshot_url,
                        note=str(body.get("note") or "").strip(),
                    )
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Economy regear failed")
            print("Economy regear failed:", _econ_err(e), flush=True)
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "result": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/award", methods=["POST"])
    @login_required
    def dashboard_economy_award():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = create_routed_operation(
                    conn,
                    backend,
                    category="reward_payout",
                    amount=int(body.get("amount") or 0),
                    description=str(body.get("player_nickname") or "").strip(),
                    actor=str(body.get("approved_by") or "dashboard_admin").strip(),
                    source="economy_dashboard",
                )
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Economy award failed")
            print("Economy award failed:", _econ_err(e), flush=True)
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "result": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/route-op", methods=["POST"])
    @login_required
    def dashboard_economy_route_op():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = create_routed_operation(
                    conn,
                    backend,
                    category=str(body.get("category") or "").strip(),
                    amount=int(body.get("amount") or 0),
                    description=str(body.get("description") or "").strip(),
                    actor=str(body.get("actor") or "dashboard").strip(),
                    source=str(body.get("source") or "dashboard").strip(),
                )
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Economy route-op failed")
            print("Economy route-op failed:", _econ_err(e), flush=True)
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "result": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/review-entry", methods=["POST"])
    @login_required
    def dashboard_economy_review_entry():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = review_pending_entry(
                    conn,
                    backend,
                    entry_id=int(body.get("entry_id") or 0),
                    action=str(body.get("action") or "").strip().lower(),
                    reviewed_by=str(body.get("reviewed_by") or "dashboard_admin").strip(),
                    note=str(body.get("note") or "").strip(),
                )
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "result": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/discrepancy/resolve", methods=["POST"])
    @login_required
    def dashboard_economy_resolve_discrepancy():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                updated = resolve_discrepancy(
                    conn,
                    backend,
                    discrepancy_id=int(body.get("id") or 0),
                    resolved_by=str(body.get("resolved_by") or "dashboard_admin").strip(),
                    note=str(body.get("note") or "").strip(),
                )
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "updated": updated}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/config", methods=["POST"])
    @login_required
    def dashboard_economy_set_config():
        body = request.get_json(silent=True) or {}
        try:
            values = body.get("values")
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                set_config_values(
                    conn,
                    backend,
                    values=values,
                    actor=str(body.get("updated_by") or "dashboard_admin").strip(),
                )
                cfg = get_config(conn, backend)
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "config": cfg}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/alert/ack", methods=["POST"])
    @login_required
    def dashboard_economy_ack_alert():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                updated = acknowledge_alert(
                    conn,
                    backend,
                    alert_id=int(body.get("id") or 0),
                    acknowledged_by=str(body.get("acknowledged_by") or "dashboard_admin").strip(),
                    note=str(body.get("note") or "").strip(),
                )
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "updated": updated}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/routing-rule", methods=["POST"])
    @login_required
    def dashboard_economy_routing_rule():
        body = request.get_json(silent=True) or {}
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                upsert_routing_rule(
                    conn,
                    backend,
                    category=str(body.get("category") or "").strip(),
                    debit_account=str(body.get("debit_account") or "").strip(),
                    credit_account=str(body.get("credit_account") or "").strip(),
                    require_approval=bool(body.get("require_approval", False)),
                    tag=str(body.get("tag") or "").strip(),
                )
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True}), mimetype="application/json")

    @app.route("/dashboard/api/economy/import-log", methods=["POST"])
    @login_required
    def dashboard_economy_import_log():
        body = request.get_json(silent=True) or {}
        try:
            log_type = str(body.get("log_type") or "").strip().lower()
            content = str(body.get("content") or "")
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = import_game_log_csv(conn, backend, log_type=log_type, content=content)
        except ValueError as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=400,
                mimetype="application/json",
            )
        except Exception as e:
            app.logger.exception("Economy import-log failed")
            print("Economy import-log failed:", _econ_err(e), flush=True)
            return app.response_class(
                response=json.dumps({"ok": False, "error": _econ_err(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps({"ok": True, "summary": out}, default=str), mimetype="application/json")

    @app.route("/dashboard/api/economy/price", methods=["GET"])
    @login_required
    def dashboard_economy_price():
        item_id = str(request.args.get("item_id") or "").strip()
        location = str(request.args.get("location") or "Caerleon").strip() or "Caerleon"
        try:
            quality = int(request.args.get("quality", 1))
        except ValueError:
            quality = 1
        out = fetch_market_price(item_id=item_id, location=location, quality=quality)
        status = 200 if out.get("ok") else 502
        return app.response_class(
            response=json.dumps(out, default=str),
            status=status,
            mimetype="application/json",
        )

    @app.route("/dashboard/api/economy/item-suggest", methods=["GET"])
    @login_required
    def dashboard_economy_item_suggest():
        q = str(request.args.get("q") or "").strip()
        try:
            limit = int(request.args.get("limit", 20))
        except ValueError:
            limit = 20
        out = suggest_item_ids(q, limit=max(1, min(limit, 30)))
        status = 200 if out.get("ok") else 502
        return app.response_class(
            response=json.dumps(out, default=str),
            status=status,
            mimetype="application/json",
        )

    @app.route("/dashboard/api/economy/reports", methods=["GET"])
    @login_required
    def dashboard_economy_reports():
        try:
            days = int(request.args.get("days", 30))
        except ValueError:
            days = 30
        days = max(1, min(days, 365))
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = {
                    "ok": True,
                    "balance_snapshot": balance_snapshot(conn, backend),
                    "pnl_summary": pnl_summary(conn, backend, days),
                    "cashflow_summary": cashflow_summary(conn, backend, days),
                    "forecast": forecast_summary(conn, backend),
                }
        except Exception as e:
            return app.response_class(
                response=json.dumps({"ok": False, "error": str(e)}, default=str),
                status=500,
                mimetype="application/json",
            )
        return app.response_class(response=json.dumps(out, default=str), mimetype="application/json")
