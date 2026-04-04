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
            logger.info(f"✓ Found {len(self.application_commands)} application commands")
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

    async def _dashboard_discord_heartbeat(self):
        """Lets the dashboard see recent Discord activity even if on_ready does not repeat after reconnects."""
        from datetime import datetime

        while not self.is_closed():
            try:
                from keep_alive import set_bot_ready

                set_bot_ready(
                    last_discord_heartbeat_utc=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                )
            except Exception:
                pass
            try:
                await asyncio.sleep(45)
            except asyncio.CancelledError:
                break
    
    async def on_ready(self):
        """Bot readiness handler"""
        if getattr(self, 'ready_check', False):
            return
        self.ready_check = True

        try:
            from keep_alive import set_discord_api_blocked

            set_discord_api_blocked(False)
        except Exception:
            pass

        logger.info(f"✓ Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"✓ Connected to {len(self.guilds)} guild(s)")
        
        # 1. Initialize permissions system
        self.permissions = Permissions(self)

        # 2. Connect to DB (with error handling)
        database_connected = False
        try:
            await self.db.connect()
            logger.info("✓ Database connected")
            database_connected = True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            logger.error("Check DATABASE_URL in Render Environment Variables.")
            # Don't crash completely so the bot can at least respond to ping
        
        # 3. Sync slash commands (single pass; see auto_sync_commands=False above).
        skip_sync = (os.getenv("DISCORD_SKIP_COMMAND_SYNC", "") or "").strip().lower() in (
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
            logger.info(f"⏳ Syncing commands... (Found {len(self.application_commands)} app commands)")

        try:
            if skip_sync:
                pass
            else:
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
                    # Only sync guilds listed in GUILD_ID / GUILD_ID2 / GUILD_IDS — avoids work for every invite.
                    target_guild_ids = sorted(connected_guild_ids & configured_guild_ids)
                    missing = sorted(configured_guild_ids - connected_guild_ids)
                    if missing:
                        logger.warning(
                            "⚠️ Bot is not in configured guild id(s) (no command sync there until invited): "
                            f"{missing}"
                        )
                else:
                    # Legacy: env had no guild list — sync all connected (heavy if the bot is in many servers).
                    target_guild_ids = sorted(connected_guild_ids)
                    if len(target_guild_ids) > 1:
                        logger.warning(
                            "⚠️ No GUILD_IDS / GUILD_ID in env — syncing slash commands to all "
                            f"{len(target_guild_ids)} connected guild(s). Set GUILD_IDS to your guild id(s) to reduce "
                            "API load and avoid application-command rate limits."
                        )

                # One sync_commands() for all target guilds. A per-guild loop made py-cord repeat the internal
                # "global commands" pass (GET /applications/.../commands) once per iteration, multiplying load on
                # the same rate-limit bucket.
                if target_guild_ids:
                    try:
                        await self.sync_commands(guild_ids=target_guild_ids, force=False)
                        logger.info(f"✓ Commands synced to guild(s): {target_guild_ids}")
                    except discord.Forbidden as e:
                        logger.error(f"❌ Guild command sync forbidden: {e}")
                        await self.sync_commands(force=False)
                        logger.info("✓ Fallback: global slash commands synced")
                else:
                    if configured_guild_ids:
                        logger.warning(
                            "⚠️ No overlap between connected guilds and env guild list — registering commands globally."
                        )
                    await self.sync_commands(force=False)
                    logger.info("✓ Global slash commands synced")
        except Exception as e:
            logger.error(f"❌ Command sync failed: {e}")
        
        # Final logging
        cmds = self.application_commands
        logger.info(f"✓ Registered {len(cmds)} commands: {', '.join([c.name for c in cmds])}")
        
        # Set status
        await self.change_presence(
            activity=discord.Game(name="Albion Analytics | !ping"),
            status=discord.Status.online
        )

        try:
            from keep_alive import set_bot_ready

            set_bot_ready(
                touch_ready=True,
                bot_username=str(self.user),
                bot_user_id=self.user.id,
                guilds_connected=len(self.guilds),
                database_connected=database_connected,
            )
        except Exception:
            pass

        try:
            self.loop.create_task(self._dashboard_discord_heartbeat())
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

from keep_alive import keep_alive

async def main():
    """Application entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Albion Analytics Discord Bot")
    logger.info("=" * 50)
    
    keep_alive()
    attempt = 0
    base_backoff = 30
    max_backoff = 900

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
            wait_seconds = min(max_backoff, base_backoff * (2 ** min(attempt - 1, 5)))
            wait_seconds += random.randint(0, 20)
            logger.error(
                "❌ Discord gateway unavailable (likely temporary rate limit / Cloudflare 1015): %s",
                e,
            )
            logger.warning("⏳ Reconnect attempt #%s in %ss", attempt, wait_seconds)
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
                wait_seconds = min(max_backoff, base_backoff * (2 ** min(attempt - 1, 5)))
                wait_seconds += random.randint(0, 20)
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
    asyncio.run(main())
