import discord
from discord import option
from discord.ext import commands
from datetime import datetime, timedelta
from services.chart_generator import ChartGenerator
from utils.permissions import Permissions

class StatsCommands(commands.Cog):
    """Команды для просмотра статистики"""
    
    def __init__(self, bot, db, permissions: Permissions):
        self.bot = bot
        self.db = db
        self.permissions = permissions
        self.chart_generator = ChartGenerator()
        print("✓ StatsCommands initialized")

def setup(bot):
    pass
    
    @discord.slash_command(name="stats", description="View player statistics")
    @option("target", description="Player to view stats for (leave empty for yourself)", required=False)
    @option("period", choices=["7 days", "30 days", "all time"], default="30 days")
    async def stats(self, ctx: discord.ApplicationContext, target: discord.Member = None, period: str = "30 days"):
        """Просмотр статистики игрока"""
        # Определяем целевого игрока
        if target is None:
            target = ctx.author
        
        # Проверяем права доступа
        is_self = target.id == ctx.author.id
        is_mentor = await self.permissions.require_mentor(ctx.author)
        
        if not is_self and not is_mentor:
            await ctx.respond("❌ Only mentors and founders can view other players' statistics.", ephemeral=True)
            return
        
        # Получаем данные игрока
        player = await self.db.get_player_by_discord_id(target.id)
        if not player:
            await ctx.respond(f"❌ Player {target.mention} is not registered in the system.", ephemeral=True)
            return
        
        # Определяем период
        days = 7 if "7" in period else 30 if "30" in period else None
        
        # Получаем статистику
        stats = await self._get_player_stats(player['id'], days)
        if not stats['sessions']:
            await ctx.respond(f"📊 {target.mention} has no recorded sessions yet.", ephemeral=True)
            return
        
        # Генерируем графики
        await ctx.defer()  # Для долгих операций
        
        # 1. Тренд очков
        trend_chart = self.chart_generator.generate_score_trend(
            stats['trend_weeks'], 
            stats['trend_scores'], 
            target.display_name
        )
        
        # 2. Очки по ролям
        role_chart = self.chart_generator.generate_role_scores(
            stats['role_names'],
            stats['role_scores'],
            target.display_name
        )
        
        # Отправляем результаты
        embed = discord.Embed(
            title=f"📊 Statistics for {target.display_name}",
            description=f"Period: {period}",
            color=discord.Color.green()
        )
        embed.add_field(name="Average Score", value=f"{stats['avg_score']:.2f}/10", inline=True)
        embed.add_field(name="Total Sessions", value=stats['session_count'], inline=True)
        embed.add_field(name="Best Role", value=stats['best_role'] or "N/A", inline=True)
        embed.add_field(name="Most Played Content", value=stats['top_content'] or "N/A", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"Data updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        
        # Отправляем графики как вложения
        files = [
            discord.File(trend_chart, filename="score_trend.png"),
            discord.File(role_chart, filename="role_scores.png")
        ]
        
        await ctx.respond(embed=embed, files=files)
    
    @discord.slash_command(name="stats_top", description="View top 10 players in the alliance")
    async def stats_top(self, ctx: discord.ApplicationContext):
        """Просмотр топ-10 игроков альянса"""
        await ctx.defer()
        
        # Получаем топ-10 за последние 30 дней
        start_date = datetime.utcnow() - timedelta(days=30)
        
        top_players = await self.db.fetch("""
            SELECT 
                p.discord_id,
                p.nickname,
                AVG(s.score) as avg_score,
                COUNT(s.id) as session_count
            FROM players p
            JOIN sessions s ON s.player_id = p.id
            WHERE s.session_date >= $1
            GROUP BY p.id, p.discord_id, p.nickname
            HAVING COUNT(s.id) >= 3  -- Минимум 3 сессии для объективности
            ORDER BY avg_score DESC
            LIMIT 10
        """, start_date)
        
        if not top_players:
            await ctx.respond("❌ Not enough data to generate top players list (minimum 3 sessions required).", ephemeral=True)
            return
        
        # Подготавливаем данные для графика
        players = [p['nickname'] for p in top_players]
        scores = [float(p['avg_score']) for p in top_players]
        
        # Генерируем график
        chart = self.chart_generator.generate_top_players(players, scores)
        
        # Создаём embed с таблицей
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
        embed.set_image(url="attachment://top_players.png")
        embed.set_footer(text="Minimum 3 sessions required for ranking")
        
        await ctx.respond(embed=embed, file=discord.File(chart, filename="top_players.png"))
    
    async def _get_player_stats(self, player_id: int, days: int = None):
        """Получение статистики игрока из БД"""
        # Базовый фильтр по периоду
        where_clauses = ["s.player_id = $1"]
        params = [player_id]
        
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            where_clauses.append("s.session_date >= $2")
            params.append(start_date)
            
        where_str = " AND ".join(where_clauses)
        
        # Основная статистика
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
        stats = await self.db.fetchrow(stats_query, *params)
        
        if not stats or not stats['session_count']:
            return {'sessions': [], 'avg_score': 0, 'session_count': 0}
        
        # Тренд по неделям (Note: to_char is Postgres specific, SQLite uses strftime)
        # We need a cross-db way. Usually best to fetch date and aggregate in python if DB agnostic.
        # But for now let's use SQLite syntax as default if we assume local dev is SQLite?
        # Or better: just select date and score and aggregate in python.
        trend_query = f"""
            SELECT s.session_date, s.score
            FROM sessions s
            WHERE {where_str}
            ORDER BY s.session_date ASC
        """
        raw_trend_data = await self.db.fetch(trend_query, *params)
        
        # Aggregate in Python for portability
        from collections import defaultdict
        week_scores = defaultdict(list)
        for row in raw_trend_data:
            # Parse date if string, else assume date obj
            d = row['session_date']
            if isinstance(d, str):
                d = datetime.strptime(d, '%Y-%m-%d').date()
            week_key = d.strftime('%Y-%W')
            week_scores[week_key].append(row['score'])
            
        trend_data = [{'week': k, 'avg_score': sum(v)/len(v)} for k, v in week_scores.items()]
        
        # Статистика по ролям
        role_query = f"""
            SELECT 
                s.role,
                AVG(s.score) as avg_score
            FROM sessions s
            WHERE {where_str}
            GROUP BY s.role
            ORDER BY avg_score DESC
        """
        role_data = await self.db.fetch(role_query, *params)
        
        return {
            'avg_score': float(stats['avg_score']) if stats['avg_score'] else 0,
            'session_count': stats['session_count'],
            'last_session': stats['last_session'],
            'best_role': stats['best_role'],
            'top_content': stats['top_content'],
            'sessions': [],  # Для будущего использования
            'trend_weeks': [r['week'] for r in trend_data],
            'trend_scores': [float(r['avg_score']) for r in trend_data],
            'role_names': [r['role'] for r in role_data],
            'role_scores': [float(r['avg_score']) for r in role_data]
        }