# Test script to verify command registration locally
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

import discord
from discord.ext import commands

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✓ TestCog initialized")
    
    @discord.slash_command(name="test", description="Test command")
    async def test_cmd(self, ctx):
        await ctx.respond("Test works!")

def setup(bot):
    bot.add_cog(TestCog(bot))

async def main():
    bot = discord.Bot(
        command_prefix="!",
        intents=discord.Intents.default(),
        debug_guilds=[int(os.getenv('GUILD_ID', '0'))] if os.getenv('GUILD_ID') else None
    )
    
    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")
        print(f"Application commands: {len(bot.application_commands)}")
        for cmd in bot.application_commands:
            print(f"  - {cmd.name}: {cmd.description}")
        await bot.close()
    
    # Test 1: Manual add_cog
    print("\n=== Test 1: Manual add_cog ===")
    bot.add_cog(TestCog(bot))
    print(f"Commands after add_cog: {len(bot.application_commands)}")
    
    # Test 2: load_extension
    print("\n=== Test 2: load_extension ===")
    bot.remove_cog("TestCog")
    bot.load_extension("test_commands")
    print(f"Commands after load_extension: {len(bot.application_commands)}")
    
    print("\n=== Starting bot ===")
    try:
        await bot.start(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    asyncio.run(main())
