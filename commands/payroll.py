import discord
from discord import option
from discord.ext import commands
from datetime import datetime, timedelta
from utils.permissions import Permissions

class PayrollCommands(commands.Cog):
    def __init__(self, bot, db, permissions: Permissions):
        self.bot = bot
        self.db = db
        self.permissions = permissions
        print("✓ PayrollCommands initialized")

def setup(bot):
    pass

    @discord.slash_command(name="payroll", description="Calculate mentor payroll")
    @option("total_amount", description="Total amount to distribute", min_value=1)
    @option("days", description="Number of days to look back (default 14)", default=14, min_value=1, max_value=365)
    async def payroll(self, ctx: discord.ApplicationContext, total_amount: int, days: int = 14):
        """Calculate payroll for mentors based on sessions closed in the last N days."""
        
        # Check permissions (Founder only)
        if not await self.permissions.require_founder(ctx.author):
            await ctx.respond("❌ Only Founders can calculate payroll.", ephemeral=True)
            return

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Fetch session counts per mentor
        # We join with players to get nicknames
        # We count sessions table entries which represent evaluated tickets
        rows = await self.db.fetch("""
            SELECT 
                p.discord_id,
                p.nickname,
                COUNT(s.id) as session_count
            FROM sessions s
            JOIN players p ON p.id = s.mentor_id
            WHERE s.session_date >= $1
            GROUP BY p.id, p.discord_id, p.nickname
            ORDER BY session_count DESC
        """, start_date)
        
        if not rows:
            await ctx.respond(f"📉 No sessions found in the last {days} days.", ephemeral=True)
            return
            
        total_sessions = sum(row['session_count'] for row in rows)
        
        if total_sessions == 0:
            await ctx.respond("📉 Total sessions is 0.", ephemeral=True)
            return
            
        # Generate Report
        embed = discord.Embed(
            title="💰 Payroll Calculation",
            description=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days} days)\nTotal Budget: {total_amount:,} Silver",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Total Sessions", value=str(total_sessions), inline=False)
        
        report_lines = []
        for row in rows:
            count = row['session_count']
            share_percent = count / total_sessions
            payout = int(total_amount * share_percent)
            
            report_lines.append(
                f"**{row['nickname']}** (<@{row['discord_id']}>): "
                f"{count} sessions ({share_percent:.1%}) -> **{payout:,}**"
            )
            
        embed.add_field(name="Payout Breakdown", value="\n".join(report_lines), inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.respond(embed=embed)

def setup(bot):
    # This setup function is not strictly needed if we add cog manually in bot.py 
    # but good for extension loading if we switched to extensions.
    pass
