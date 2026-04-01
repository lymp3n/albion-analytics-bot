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
    
    async def on_ready(self):
        """Bot readiness handler"""
        if getattr(self, 'ready_check', False):
            return
        self.ready_check = True

        logger.info(f"✓ Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"✓ Connected to {len(self.guilds)} guild(s)")
        
        # 1. Initialize permissions system
        self.permissions = Permissions(self)

        # 2. Connect to DB (with error handling)
        try:
            await self.db.connect()
            logger.info("✓ Database connected")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            logger.error("Check DATABASE_URL in Render Environment Variables.")
            # Don't crash completely so the bot can at least respond to ping
        
        # 3. Sync slash commands
        logger.info(f"⏳ Syncing commands... (Found {len(self.application_commands)} app commands)")
        
        try:
            connected_guild_ids = {g.id for g in self.guilds}
            target_guild_ids = [gid for gid in self.guild_ids if gid in connected_guild_ids]
            skipped_guild_ids = [gid for gid in self.guild_ids if gid not in connected_guild_ids]

            if skipped_guild_ids:
                logger.warning(
                    "⚠️ Skipping command sync for guild(s) the bot is not in: "
                    f"{skipped_guild_ids}. Invite the bot first or remove them from env."
                )

            # Step 1: wipe stale guild-specific commands ONLY where bot has access
            for gid in target_guild_ids:
                try:
                    await self.http.bulk_upsert_guild_commands(self.user.id, gid, [])
                    logger.info(f"✓ Cleared stale guild commands from guild {gid}")
                except discord.Forbidden as e:
                    logger.warning(f"⚠️ No access to clear guild commands for {gid}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed clearing guild commands for {gid}: {e}")

            # Step 2: sync commands (prefer guild sync for instant propagation)
            if target_guild_ids:
                try:
                    await self.sync_commands(guild_ids=target_guild_ids, force=True)
                    logger.info(f"✓ Commands synced to guilds: {target_guild_ids}")
                except discord.Forbidden as e:
                    logger.error(f"❌ Guild command sync forbidden: {e}")
                    # fallback to global sync so at least commands exist
                    await self.sync_commands(force=True)
                    logger.info("✓ Fallback: global slash commands synced")
            else:
                await self.sync_commands(force=True)
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
    
    bot = AlbionBot()

    try:
        await bot.start(bot.token)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Shutdown requested by user")
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
