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

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('albion-bot')

class AlbionBot(commands.Bot):
    def __init__(self):
        # Load configuration first to get GUILD_ID
        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')
        self.database_url = os.getenv('DATABASE_URL')
        self.guild_id = int(os.getenv('GUILD_ID', '0'))
        self.tickets_category_id = int(os.getenv('TICKETS_CATEGORY_ID', '0'))
        
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        # debug_guilds - instant command synchronization for specified servers
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            debug_guilds=[self.guild_id] if self.guild_id else None
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
            logger.info(f"✓ Command cogs loaded: {', '.join(self.cogs.keys())}")
            logger.info(f"✓ Found {len(self.application_commands)} application commands")
        except Exception as e:
            logger.error(f"❌ Failed to load cogs: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
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
            if self.guild_id:
                logger.info(f"⏳ Syncing to guild {self.guild_id}")
                await self.sync_commands(guild_ids=[self.guild_id], force=True)
                logger.info(f"✓ Slash commands synced to guild {self.guild_id}")
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
