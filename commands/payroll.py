import discord
from discord import option
from discord.ext import commands
from datetime import datetime, timedelta
from utils.permissions import Permissions

class PayrollCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✓ PayrollCommands initialized")

    @discord.slash_command(name="payroll", description="Calculate mentor payroll")
    @option("total_amount", description="Total amount to distribute", min_value=1)
    @option("days", description="Number of days to look back (default 14)", default=14, min_value=1, max_value=365)
    async def payroll(self, ctx: discord.ApplicationContext, total_amount: int, days: int = 14):
        """Calculate payroll for mentors based on sessions closed in the last N days."""
        await ctx.defer()
        
        # Check permissions (Founder only)
        if not await self.bot.permissions.require_founder(ctx.author):
            await ctx.respond("❌ Only Founders can calculate payroll.", ephemeral=True)
            return

        # Calculate date ranges
        now = datetime.utcnow()
        date_7d = now - timedelta(days=7)
        date_14d = now - timedelta(days=14)
        
        # Fetch session counts per mentor with multiple time windows
        rows = await self.bot.db.fetch("""
            SELECT 
                p.discord_id,
                p.nickname,
                COUNT(s.id) as total_sessions,
                COUNT(CASE WHEN s.session_date >= $1 THEN 1 END) as sessions_14d,
                COUNT(CASE WHEN s.session_date >= $2 THEN 1 END) as sessions_7d
            FROM players p
            JOIN sessions s ON s.mentor_id = p.id
            GROUP BY p.id, p.discord_id, p.nickname
            ORDER BY sessions_14d DESC
        """, date_14d, date_7d)
        
        if not rows:
            await ctx.respond("📉 No sessions found in the database.", ephemeral=True)
            return
            
        # We calculate payout based on the 14-day window as the standard
        # but the user can see other stats.
        total_sessions_14d = sum(row['sessions_14d'] for row in rows)
        
        if total_sessions_14d == 0:
            await ctx.respond("📉 No sessions found in the last 14 days to calculate payout.", ephemeral=True)
            return
            
        # Generate Report
        embed = discord.Embed(
            title="💰 Mentor Payroll Dashboard",
            description=f"Budget: **{total_amount:,} Silver** (Distributed by last 14 days activity)",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Total Sessions (14d)", value=str(total_sessions_14d), inline=True)
        embed.add_field(name="Active Mentors", value=str(len([r for r in rows if r['sessions_14d'] > 0])), inline=True)
        
        report_lines = []
        for row in rows:
            count_14d = row['sessions_14d']
            if count_14d == 0 and row['total_sessions'] == 0:
                continue
                
            share_percent = count_14d / total_sessions_14d if total_sessions_14d > 0 else 0
            payout = int(total_amount * share_percent)
            
            # Format: Nickname | 7d: X | 14d: Y | All: Z | Payout
            report_lines.append(
                f"**{row['nickname']}** (<@{row['discord_id']}>)\n"
                f"└ 7d: `{row['sessions_7d']}` | 14d: `{count_14d}` | All: `{row['total_sessions']}`\n"
                f"└ Share: `{share_percent:.1%}` → **{payout:,} Silver**"
            )
            
        # Split report into multiple fields if it's too long
        full_report = "\n".join(report_lines)
        if len(full_report) > 1024:
            # Simple split for now, could be more robust
            embed.add_field(name="Payout Breakdown (Part 1)", value="\n".join(report_lines[:len(report_lines)//2]), inline=False)
            embed.add_field(name="Payout Breakdown (Part 2)", value="\n".join(report_lines[len(report_lines)//2:]), inline=False)
        else:
            embed.add_field(name="Payout Breakdown", value=full_report, inline=False)
            
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(PayrollCommands(bot))
