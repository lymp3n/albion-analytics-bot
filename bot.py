import os
import sys

# Monkeypatch audioop for Python 3.13+ compatibility
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop
        sys.modules["audioop"] = audioop
    except ImportError:
        print("Warning: audioop not found. Voice features may fail.")

import asyncio
import hashlib
import json
import logging
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yaml
from database import Database
from utils.permissions import Permissions
from typing import List, Set

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('albion-bot')

SLASH_SYNC_FP_KV = "slash_sync_fingerprint"


def _discord_response_looks_like_cf1015_ip_ban(message: str) -> bool:
    """Cloudflare error 1015 = Discord temporarily blocks the hosting egress IP (HTML body, not JSON API 429)."""
    if not message or "1015" not in message:
        return False
    low = message.lower()
    return (
        "cloudflare" in low
        or "discord.com" in low
        or "errorcode: 1015" in low.replace(" ", "")
        or "you are being rate limited" in low
    )


def _discord_cf1015_retry_wait_seconds() -> int:
    raw = (os.getenv("DISCORD_CF1015_RETRY_AFTER_SEC") or "3600").strip()
    try:
        base = max(300, int(float(raw)))
    except ValueError:
        base = 3600
    return base + random.randint(0, 180)


def _discord_startup_reconnect_delay_seconds(attempt: int, err_text: str) -> int:
    """Avoid hammering Discord when the IP is banned (short retries only make logs noisy and may extend blocks)."""
    if _discord_response_looks_like_cf1015_ip_ban(err_text):
        return _discord_cf1015_retry_wait_seconds()
    base_backoff = 30
    max_backoff = 900
    wait_seconds = min(max_backoff, base_backoff * (2 ** min(attempt - 1, 5)))
    return wait_seconds + random.randint(0, 20)


def _slash_command_tree_fingerprint(
    bot: commands.Bot, sync_mode: str, target_guild_ids: List[int]
) -> str:
    """Stable hash of slash tree + sync scope; used to skip redundant Discord command API sync."""

    def walk_options(opts):
        if not opts:
            return []
        out = []
        for o in sorted(
            opts, key=lambda x: (getattr(x, "name", ""), int(getattr(x, "type", 0)))
        ):
            nested = getattr(o, "options", None) or []
            out.append(
                [
                    getattr(o, "name", ""),
                    int(getattr(o, "type", 0)),
                    walk_options(nested),
                ]
            )
        return out

    cmds = []
    for c in sorted(
        bot.application_commands,
        key=lambda x: (x.name, int(getattr(x, "type", 1))),
    ):
        top = getattr(c, "options", None) or []
        cmds.append([c.name, int(getattr(c, "type", 1)), walk_options(top)])

    payload = {"m": sync_mode, "g": sorted(target_guild_ids), "c": cmds}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class AlbionBot(commands.Bot):
    def __init__(self):
        # Load configuration first
        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')
        self.database_url = os.getenv('DATABASE_URL')
        self.guild_id = int(os.getenv('GUILD_ID', '0'))
        self.guild_id2 = int(os.getenv('GUILD_ID2', '0'))
        self.tickets_category_id = int(os.getenv('TICKETS_CATEGORY_ID', '0'))
        
        # Collect all configured guild IDs (for instant command sync)
        # Supports legacy GUILD_ID/GUILD_ID2 and a new comma/space separated GUILD_IDS.
        self.guild_ids = self._parse_guild_ids()
        
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        # Register commands globally (works on all servers)
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            # Default True runs sync_commands on every on_connect; we sync once in on_ready with controlled guild scope.
            auto_sync_commands=False,
        )
        
        # Load YAML config
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize components
        self.db = Database(self.database_url)
        self.permissions = None
        
        if not self.token:
            logger.error("❌ DISCORD_TOKEN not found in environment variables!")
            sys.exit(1)
        
        if not self.database_url:
            logger.error("❌ DATABASE_URL not found in environment variables!")
            sys.exit(1)
        
        # CRITICAL: Load cogs BEFORE connecting to Discord!
        # This allows py-cord to discover slash commands
        logger.info("Loading command cogs...")
        try:
            self.load_extension("commands.auth")
            self.load_extension("commands.stats")
            self.load_extension("commands.tickets")
            self.load_extension("commands.payroll")
            self.load_extension("commands.menu")
            self.load_extension("commands.events")  # Event management
            logger.info(f"✓ Command cogs loaded: {', '.join(self.cogs.keys())}")
            logger.info("✓ Slash commands will appear after Discord sync in on_ready")
        except Exception as e:
            logger.error(f"❌ Failed to load cogs: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _parse_guild_ids(self) -> List[int]:
        raw = os.getenv("GUILD_IDS", "") or ""
        parsed: List[int] = []

        # legacy single/dual vars
        for v in (self.guild_id, self.guild_id2):
            if v:
                parsed.append(v)

        # new list var
        for part in raw.replace(";", ",").replace(" ", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                gid = int(part)
                if gid:
                    parsed.append(gid)
            except ValueError:
                logger.warning(f"⚠️ Invalid guild id in GUILD_IDS: {part!r}")

        # de-dup while keeping order
        seen: Set[int] = set()
        out: List[int] = []
        for gid in parsed:
            if gid not in seen:
                seen.add(gid)
                out.append(gid)
        return out

    def _database_ready(self) -> bool:
        if self.db.is_sqlite:
            return self.db.conn is not None
        return self.db.pool is not None

    async def _dashboard_discord_heartbeat(self):
        """Lets the dashboard see recent Discord activity even if on_ready does not repeat after reconnects."""
        from datetime import datetime, timezone

        while not self.is_closed():
            try:
                from keep_alive import set_bot_ready

                set_bot_ready(
                    last_discord_heartbeat_utc=datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    )
                )
            except Exception:
                pass
            try:
                await asyncio.sleep(45)
            except asyncio.CancelledError:
                break

    async def on_resumed(self):
        """Discord gateway RESUME succeeded — same session, not a disconnect. This is normal."""
        logger.info(
            "✓ Gateway RESUMED — websocket session continued; slash commands should work. "
            "If commands still fail, check for a second bot process using the same token."
        )

    async def on_ready(self):
        """First ready: DB, permissions, slash sync, heartbeat task. Later ready: refresh presence + dashboard meta."""
        try:
            from keep_alive import set_discord_api_blocked

            set_discord_api_blocked(False)
        except Exception:
            pass

        first = not getattr(self, "_albion_initial_ready_done", False)
        database_connected = self._database_ready()

        if first:
            self._albion_initial_ready_done = True
            self.ready_check = True

            logger.info(f"✓ Logged in as {self.user.name} (ID: {self.user.id})")
            logger.info(f"✓ Connected to {len(self.guilds)} guild(s)")

            self.permissions = Permissions(self)

            try:
                if not self._database_ready():
                    await self.db.connect()
                    logger.info("✓ Database connected")
                database_connected = self._database_ready()
            except Exception as e:
                logger.error(f"❌ Database connection failed: {e}")
                logger.error("Check DATABASE_URL in Render Environment Variables.")
                database_connected = False

            skip_sync = (os.getenv("DISCORD_SKIP_COMMAND_SYNC", "") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            force_command_sync = (os.getenv("DISCORD_FORCE_COMMAND_SYNC", "") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            if skip_sync:
                logger.warning(
                    "⚠️ DISCORD_SKIP_COMMAND_SYNC is set — slash commands will NOT be registered this run. "
                    "Unset for production or run `/` sync manually when needed."
                )
            else:
                logger.info("⏳ Syncing slash commands (first connection this process)...")

            try:
                if not skip_sync:
                    defer = float(os.getenv("DISCORD_COMMAND_SYNC_DEFER_SEC", "0") or "0")
                    if defer > 0:
                        logger.info(
                            "⏳ DISCORD_COMMAND_SYNC_DEFER_SEC=%.1f — waiting before command sync to ease API bursts",
                            defer,
                        )
                        await asyncio.sleep(defer)

                    jitter_max = float(os.getenv("DISCORD_COMMAND_SYNC_JITTER_SEC", "0") or "0")
                    if jitter_max > 0:
                        j = random.uniform(0.0, jitter_max)
                        logger.info(
                            "⏳ Random pre-sync delay %.2fs (DISCORD_COMMAND_SYNC_JITTER_SEC=%.1f) to stagger parallel deploys",
                            j,
                            jitter_max,
                        )
                        await asyncio.sleep(j)

                    connected_guild_ids = {g.id for g in self.guilds}
                    configured_guild_ids = set(self.guild_ids)

                    if configured_guild_ids:
                        target_guild_ids = sorted(connected_guild_ids & configured_guild_ids)
                        missing = sorted(configured_guild_ids - connected_guild_ids)
                        if missing:
                            logger.warning(
                                "⚠️ Bot is not in configured guild id(s) (no command sync there until invited): "
                                f"{missing}"
                            )
                    else:
                        target_guild_ids = sorted(connected_guild_ids)
                        if len(target_guild_ids) > 1:
                            logger.warning(
                                "⚠️ No GUILD_IDS / GUILD_ID in env — syncing slash commands to all "
                                f"{len(target_guild_ids)} connected guild(s). Set GUILD_IDS to your guild id(s) to reduce "
                                "API load and avoid application-command rate limits."
                            )

                    sync_mode = "guild" if target_guild_ids else "global"
                    fp_ids = sorted(target_guild_ids) if target_guild_ids else []
                    fp = _slash_command_tree_fingerprint(self, sync_mode, fp_ids)

                    stored_fp = None
                    if database_connected and not force_command_sync:
                        try:
                            stored_fp = await self.db.get_bot_kv(SLASH_SYNC_FP_KV)
                        except Exception as ex:
                            logger.warning("Slash fingerprint read failed (%s); syncing commands.", ex)

                    skip_redundant_sync = (
                        stored_fp is not None
                        and stored_fp == fp
                        and database_connected
                        and not force_command_sync
                    )

                    # Fingerprint skip avoids HTTP sync, but in a new process py-cord often leaves
                    # `application_commands` empty until sync — slash interactions then do not dispatch.
                    if skip_redundant_sync and len(self.application_commands) == 0:
                        logger.warning(
                            "Slash sync: DB fingerprint matches but application_commands is empty — "
                            "forcing sync this run (required so this process registers command handlers)."
                        )
                        skip_redundant_sync = False

                    if skip_redundant_sync:
                        logger.info(
                            "✓ Slash command sync skipped — same tree as last successful sync (stored in DB). "
                            "Set DISCORD_FORCE_COMMAND_SYNC=1 for one run after you change commands or if Discord is stale."
                        )
                    elif target_guild_ids:
                        try:
                            await self.sync_commands(guild_ids=target_guild_ids, force=False)
                            logger.info(f"✓ Commands synced to guild(s): {target_guild_ids}")
                            if database_connected:
                                await self.db.set_bot_kv(SLASH_SYNC_FP_KV, fp)
                        except discord.Forbidden as e:
                            logger.error(f"❌ Guild command sync forbidden: {e}")
                            fp_global = _slash_command_tree_fingerprint(self, "global", [])
                            await self.sync_commands(force=False)
                            logger.info("✓ Fallback: global slash commands synced")
                            if database_connected:
                                await self.db.set_bot_kv(SLASH_SYNC_FP_KV, fp_global)
                    else:
                        if configured_guild_ids:
                            logger.warning(
                                "⚠️ No overlap between connected guilds and env guild list — registering commands globally."
                            )
                        await self.sync_commands(force=False)
                        logger.info("✓ Global slash commands synced")
                        if database_connected:
                            await self.db.set_bot_kv(SLASH_SYNC_FP_KV, fp)
            except Exception as e:
                logger.error(f"❌ Command sync failed: {e}")

            cmds = self.application_commands
            logger.info(f"✓ Registered {len(cmds)} commands: {', '.join([c.name for c in cmds])}")

            if not getattr(self, "_dashboard_heartbeat_started", False):
                self._dashboard_heartbeat_started = True
                try:
                    self.loop.create_task(self._dashboard_discord_heartbeat())
                except Exception:
                    pass
        else:
            logger.info(
                "✓ on_ready fired again (%s guild(s)) — refreshing presence and dashboard telemetry (no re-sync)",
                len(self.guilds),
            )

        try:
            await self.change_presence(
                activity=discord.Game(name="Albion Analytics | !ping"),
                status=discord.Status.online,
            )
        except Exception as e:
            logger.warning("change_presence after ready failed: %s", e)

        try:
            from keep_alive import set_bot_ready

            set_bot_ready(
                touch_ready=first,
                bot_username=str(self.user),
                bot_user_id=self.user.id,
                guilds_connected=len(self.guilds),
                database_connected=database_connected,
            )
        except Exception:
            pass

    async def on_application_command_error(self, ctx, error):
        logger.exception("Application command error: %s", error)
        try:
            if hasattr(ctx, "response") and not ctx.response.is_done():
                await ctx.respond("❌ Internal error while executing command.", ephemeral=True)
            else:
                await ctx.followup.send("❌ Internal error while executing command.", ephemeral=True)
        except Exception:
            pass

    async def on_error(self, event_method, *args, **kwargs):
        logger.exception("Discord event error in %s", event_method)

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong! Bot is alive.")
    
    async def close(self):
        """Graceful shutdown"""
        logger.info(" Shutting down bot...")
        await self.db.close()
        await super().close()
        logger.info("✓ Bot shutdown complete")

async def main():
    """Application entry point (call keep_alive() from __main__ before asyncio.run)."""
    logger.info("=" * 50)
    logger.info("🚀 Starting Albion Analytics Discord Bot")
    logger.info("=" * 50)

    await asyncio.sleep(0.15)

    attempt = 0

    while True:
        bot = AlbionBot()
        try:
            await bot.start(bot.token)
            # Normal stop (rare in production) => break gracefully
            break
        except KeyboardInterrupt:
            logger.info("\n⚠️  Shutdown requested by user")
            break
        except discord.GatewayNotFound as e:
            try:
                from keep_alive import set_discord_api_blocked

                set_discord_api_blocked(True, f"GatewayNotFound: {e}")
            except Exception:
                pass
            attempt += 1
            err_text = str(e)
            wait_seconds = _discord_startup_reconnect_delay_seconds(attempt, err_text)
            if _discord_response_looks_like_cf1015_ip_ban(err_text):
                logger.error(
                    "❌ Discord gateway unreachable; response looks like Cloudflare 1015 / IP block on discord.com. "
                    "This is not fixable in application code: wait (often hours–24h), move the service to another "
                    "region or host, or use a different egress IP. Use exactly one bot instance per token."
                )
            else:
                logger.error(
                    "❌ Discord gateway unavailable (temporary outage or rate limit): %s",
                    e,
                )
            logger.warning(
                "⏳ Reconnect attempt #%s in %ss (longer waits if CF 1015; DISCORD_CF1015_RETRY_AFTER_SEC)",
                attempt,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
        except discord.HTTPException as e:
            # Handle startup-level 429/Cloudflare responses without crash loops.
            err_text = str(e)
            if e.status == 429 or "1015" in err_text:
                try:
                    from keep_alive import set_discord_api_blocked

                    set_discord_api_blocked(True, err_text)
                except Exception:
                    pass
                attempt += 1
                wait_seconds = _discord_startup_reconnect_delay_seconds(attempt, err_text)
                if _discord_response_looks_like_cf1015_ip_ban(err_text):
                    logger.error(
                        "❌ Discord returned HTTP %s with Cloudflare 1015 / datacenter IP ban HTML. "
                        "Short reconnect intervals do not help. Next try in %ss (default 1h; env DISCORD_CF1015_RETRY_AFTER_SEC). "
                        "Practical fixes: another Render region, another provider, wait out the ban, single bot process.",
                        e.status,
                        wait_seconds,
                    )
                else:
                    logger.error("❌ Discord HTTP rate limit during startup: %s", e)
                logger.warning("⏳ Reconnect attempt #%s in %ss", attempt, wait_seconds)
                await asyncio.sleep(wait_seconds)
            else:
                logger.exception(f"❌ Fatal HTTP error: {e}")
                break
        except Exception as e:
            logger.exception(f"❌ Fatal error: {e}")
            break
        finally:
            try:
                await bot.close()
            except Exception:
                pass

if __name__ == "__main__":
    from keep_alive import keep_alive

    keep_alive()
    asyncio.run(main())
