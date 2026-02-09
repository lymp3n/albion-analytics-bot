import os
import sys
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import yaml
from database import Database
from utils.permissions import Permissions
from commands.auth import AuthCommands
from commands.stats import StatsCommands
from commands.tickets import TicketsCommands
from commands.payroll import PayrollCommands

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('albion-bot')

class AlbionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # Загрузка конфигурации
        load_dotenv()
        self.token = os.getenv('DISCORD_TOKEN')
        self.database_url = os.getenv('DATABASE_URL')
        
        # Load YAML config
        with open('config.yaml', 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.guild_id = int(os.getenv('GUILD_ID', '0'))
        self.tickets_category_id = int(os.getenv('TICKETS_CATEGORY_ID', '0'))
        
        # Инициализация компонентов
        self.db = Database(self.database_url)
        self.permissions = None
        
        if not self.token:
            logger.error("❌ DISCORD_TOKEN not found in environment variables!")
            sys.exit(1)
        
        if not self.database_url:
            logger.error("❌ DATABASE_URL not found in environment variables!")
            sys.exit(1)
    
    async def setup_hook(self):
        """Асинхронная инициализация бота"""
        # Подключение к БД
        await self.db.connect()
        logger.info("✓ Database connected")
        
        # Инициализация системы прав
        self.permissions = Permissions(self)
        
        # Регистрация команд
        await self.add_cog(AuthCommands(self, self.db, self.permissions))
        await self.add_cog(StatsCommands(self, self.db, self.permissions))
        await self.add_cog(TicketsCommands(self, self.db, self.permissions))
        await self.add_cog(PayrollCommands(self, self.db, self.permissions))
        logger.info("✓ Command cogs loaded")
        
        # Синхронизация слэш-команд
        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"✓ Slash commands synced to guild {self.guild_id}")
        else:
            await self.tree.sync()
            logger.info("✓ Global slash commands synced")
    
    async def on_ready(self):
        """Обработчик готовности бота"""
        logger.info(f"✓ Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"✓ Connected to {len(self.guilds)} guild(s)")
        
        # Установка статуса
        await self.change_presence(
            activity=discord.Game(name="Albion Analytics"),
            status=discord.Status.online
        )
    
    async def close(self):
        """Корректное завершение работы"""
        logger.info(" Shutting down bot...")
        await self.db.close()
        await super().close()
        logger.info("✓ Bot shutdown complete")

async def main():
    """Точка входа приложения"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Albion Analytics Discord Bot")
    logger.info("=" * 50)
    
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