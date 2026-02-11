import discord
from discord import option
from discord.ext import commands
from datetime import datetime, timedelta
from services.chart_generator import ChartGenerator

class StatsCommands(commands.Cog):
    """Commands for viewing statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.chart_generator = ChartGenerator()
        print("✓ StatsCommands initialized")
    
    @discord.slash_command(name="stats", description="View player statistics")
    @option("target", description="Player to view stats for (leave empty for yourself)", required=False)
    @option("period", choices=["7 days", "30 days", "all time"], default="30 days")
    async def stats(self, ctx: discord.ApplicationContext, target: discord.Member = None, period: str = "30 days"):
        """View player statistics"""
        await ctx.defer()  # Defer immediately as DB work and chart generation takes time
        
        # Determine target player
        if target is None:
            target = ctx.author
        
        # Check access permissions
        is_self = target.id == ctx.author.id
        is_mentor = await self.bot.permissions.require_mentor(ctx.author)
        
        if not is_self and not is_mentor:
            await ctx.respond("❌ Only mentors and founders can view other players' statistics.", ephemeral=True)
            return
        
        # Fetch player data
        player = await self.bot.db.get_player_by_discord_id(target.id)
        if not player:
            await ctx.respond(f"❌ Player {target.mention} is not registered in the system.", ephemeral=True)
            return
        
        # Determine period
        days = 7 if "7" in period else 30 if "30" in period else None
        
        # Fetch statistics
        stats = await self._get_player_stats(player['id'], days)
        if not stats or stats['session_count'] == 0:
            await ctx.respond(f"📊 {target.mention} has no recorded sessions yet.", ephemeral=True)
            return
            
        # Get Global Rank
        rank_data = await self.bot.db.fetchrow("""
            SELECT rank FROM (
                SELECT p.id, RANK() OVER (ORDER BY SUM(s.score) DESC) as rank
                FROM players p
                JOIN sessions s ON s.player_id = p.id
                GROUP BY p.id
            ) ranked WHERE id = $1
        """, player['id'])
        current_rank = rank_data['rank'] if rank_data else "N/A"
        
        # Prepare data for dashboard
        dashboard_data = {
            'avg_score': stats['avg_score'],
            'session_count': stats['session_count'],
            'trend_weeks': stats['trend_weeks'],
            'trend_scores': stats['trend_scores'],
            'role_names': stats['role_names'],
            'role_scores': stats['role_scores'],
            'content_names': stats['content_names'],
            'content_scores': stats['content_scores'],
            'error_names': stats['error_names'],
            'error_counts': stats['error_counts']
        }
        
        # Generate Dashboard Card
        dashboard_image = self.chart_generator.create_player_dashboard(
            dashboard_data,
            target.display_name,
            str(current_rank)
        )
        
        # Send Results
        embed = discord.Embed(
            title=f"📊 Player Statistics: {target.display_name}",
            description=f"Performance snapshot for the last **{period}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Global Rank", value=f"#{current_rank}", inline=True)
        embed.add_field(name="Average Score", value=f"{stats['avg_score']:.2f}", inline=True)
        embed.add_field(name="Total Sessions", value=f"{stats['session_count']}", inline=True)
        
        # Attach the dashboard image to the embed
        file = discord.File(dashboard_image, filename="dashboard.png")
        embed.set_image(url="attachment://dashboard.png")
        
        await ctx.respond(embed=embed, file=file)
    
    @discord.slash_command(name="stats_top", description="View top 10 players in the alliance")
    async def stats_top(self, ctx: discord.ApplicationContext):
        """View top 10 players in the alliance"""
        await ctx.defer()
        
        # Fetch top 10 for the last 30 days
        start_date = datetime.utcnow() - timedelta(days=30)
        
        top_players = await self.bot.db.fetch("""
            SELECT 
                p.discord_id,
                p.nickname,
                AVG(s.score) as avg_score,
                COUNT(s.id) as session_count,
                SUM(s.score) as total_points
            FROM players p
            JOIN sessions s ON s.player_id = p.id
            WHERE s.session_date >= $1
            GROUP BY p.id, p.discord_id, p.nickname
            HAVING COUNT(s.id) >= 1
            ORDER BY total_points DESC
            LIMIT 10
        """, start_date)
        
        if not top_players:
            await ctx.respond("❌ Not enough data to generate top players list.", ephemeral=True)
            return
        
        # Prepare data for chart
        players = [p['nickname'] for p in top_players]
        scores = [float(p['avg_score']) for p in top_players]
        
        # Generate chart
        chart = self.chart_generator.generate_top_players(players, scores)
        
        # Create embed with table
        embed = discord.Embed(
            title="🏆 Top 10 Alliance Players (Last 30 Days)",
            color=discord.Color.gold()
        )
        
        table_text = "```\n#  Player             Score  Sessions\n"
        table_text += "-" * 40 + "\n"
        for i, player in enumerate(top_players, 1):
            table_text += f"{i:2d}. {player['nickname'][:18]:18s} {float(player['avg_score']):5.2f}  {player['session_count']:8d}\n"
        table_text += "```"
        
        embed.description = table_text
        # embed.set_image(url="attachment://top_players.png") # Убираем картинку из эмбеда
        embed.set_footer(text="Ranking based on total score (Volume + Quality)")
        
        await ctx.respond(embed=embed)
        await ctx.send(file=discord.File(chart, filename="top_players.png"))

    @discord.slash_command(name="stats_seed_test", description="Seed database with test session data (Founder only)")
    async def stats_seed_test(self, ctx: discord.ApplicationContext):
        """Command to generate test statistics data"""
        await ctx.defer(ephemeral=True)
        
        if not await self.bot.permissions.require_founder(ctx.author):
            await ctx.respond("❌ Only founders can use this command.", ephemeral=True)
            return
            
        import random
        from datetime import datetime, timedelta
        
        # Get all players
        players = await self.bot.db.fetch("SELECT id FROM players")
        if not players:
            await ctx.respond("❌ No players found to seed stats for.", ephemeral=True)
            return
            
        # Get content types
        content_types = await self.bot.db.fetch("SELECT id FROM content")
        if not content_types:
            await ctx.respond("❌ Content table is empty.", ephemeral=True)
            return
            
        # Add 5 random sessions for each player
        sessions_added = 0
        roles = ['Tank', 'Healer', 'DPS', 'Support']
        
        for player in players:
            for _ in range(5):
                # Random date in the last 30 days
                random_days = random.randint(0, 30)
                session_date = datetime.utcnow() - timedelta(days=random_days)
                
                await self.bot.db.execute("""
                    INSERT INTO sessions (
                        ticket_id, player_id, content_id, score, role, 
                        error_types, work_on, comments, mentor_id, session_date
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, 
                0, # Fake ticket_id
                player['id'],
                random.choice(content_types)['id'],
                random.uniform(5.0, 10.0), # Score 5-10
                random.choice(roles),
                "Positioning", "Stay alive", "Good job",
                player['id'], # Self-reviewed for test
                session_date
                )
                sessions_added += 1
                
        await ctx.respond(f"✅ Added {sessions_added} test sessions for {len(players)} players!", ephemeral=True)
    
    async def _get_player_stats(self, player_id: int, days: int = None):
        """Fetches player statistics from the database"""
        # Base filter by period
        where_clauses = ["s.player_id = $1"]
        params = [player_id]
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            where_clauses.append("s.session_date >= $2")
            params.append(start_date)
            
        where_str = " AND ".join(where_clauses)
        
        # Main statistics
        stats_query = f"""
            SELECT 
                AVG(s.score) as avg_score,
                COUNT(s.id) as session_count,
                MAX(s.session_date) as last_session,
                (SELECT role FROM sessions s2
                 WHERE {where_str.replace('s.', 's2.')} 
                 GROUP BY role ORDER BY COUNT(*) DESC LIMIT 1) as best_role,
                (SELECT c.name FROM sessions s3 
                 JOIN content c ON c.id = s3.content_id 
                 WHERE {where_str.replace('s.', 's3.')} 
                 GROUP BY c.id ORDER BY COUNT(*) DESC LIMIT 1) as top_content
            FROM sessions s
            WHERE {where_str}
        """
        stats = await self.bot.db.fetchrow(stats_query, *params)
        
        if not stats or not stats['session_count']:
            return {'sessions': [], 'avg_score': 0, 'session_count': 0, 'error_names': []}
        
        # Weekly Trend
        trend_query = f"""
            SELECT s.session_date, s.score
            FROM sessions s
            WHERE {where_str}
            ORDER BY s.session_date ASC
        """
        raw_trend_data = await self.bot.db.fetch(trend_query, *params)
        
        from collections import defaultdict
        week_scores = defaultdict(list)
        for row in raw_trend_data:
            d = row['session_date']
            if isinstance(d, str):
                d = datetime.strptime(d, '%Y-%m-%d').date()
            week_key = d.strftime('%Y-%W')
            week_scores[week_key].append(row['score'])
            
        trend_data = [{'week': k, 'avg_score': sum(v)/len(v)} for k, v in week_scores.items()]
        trend_data.sort(key=lambda x: x['week'])
        
        # Stats by Role
        role_query = f"""
            SELECT 
                s.role,
                AVG(s.score) as avg_score
            FROM sessions s
            WHERE {where_str}
            GROUP BY s.role
            ORDER BY avg_score DESC
        """
        role_data = await self.bot.db.fetch(role_query, *params)

        # Content Performance
        content_perf_query = f"""
            SELECT c.name, AVG(s.score) as avg_score
            FROM sessions s
            JOIN content c ON c.id = s.content_id
            WHERE {where_str}
            GROUP BY c.name
            ORDER BY avg_score DESC
        """
        content_perf_data = await self.bot.db.fetch(content_perf_query, *params)

        # Error Frequency
        error_types_query = f"""
            SELECT error_types FROM sessions s
            WHERE {where_str} AND error_types IS NOT NULL
        """
        error_rows = await self.bot.db.fetch(error_types_query, *params)
        error_counts = defaultdict(int)
        for row in error_rows:
            if row['error_types']:
                for e in row['error_types'].split(','):
                    error_counts[e.strip()] += 1
        
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'avg_score': float(stats['avg_score']) if stats['avg_score'] else 0,
            'session_count': stats['session_count'],
            'last_session': stats['last_session'],
            'best_role': stats['best_role'],
            'top_content': stats['top_content'],
            'sessions': raw_trend_data,
            'trend_weeks': [r['week'] for r in trend_data],
            'trend_scores': [float(r['avg_score']) for r in trend_data],
            'role_names': [r['role'] for r in role_data],
            'role_scores': [float(r['avg_score']) for r in role_data],
            'content_names': [r['name'] for r in content_perf_data],
            'content_scores': [float(r['avg_score']) for r in content_perf_data],
            'error_names': [e[0] for e in sorted_errors],
            'error_counts': [e[1] for e in sorted_errors]
        }

def setup(bot):
    bot.add_cog(StatsCommands(bot))