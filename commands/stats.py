import discord
from discord import option
from discord.ext import commands
from datetime import datetime, timedelta
from services.chart_generator import ChartGenerator

class StatsCommands(commands.Cog):
    """Команды для просмотра статистики"""
    
    def __init__(self, bot):
        self.bot = bot
        self.chart_generator = ChartGenerator()
        print("✓ StatsCommands initialized")
    
    @discord.slash_command(name="stats", description="View player statistics")
    @option("target", description="Player to view stats for (leave empty for yourself)", required=False)
    @option("period", choices=["7 days", "30 days", "all time"], default="30 days")
    async def stats(self, ctx: discord.ApplicationContext, target: discord.Member = None, period: str = "30 days"):
        """Просмотр статистики игрока"""
        await ctx.defer()  # Сразу деферим, так как работа с БД и графиками долгая
        
        # Определяем целевого игрока
        if target is None:
            target = ctx.author
        
        # Проверяем права доступа
        is_self = target.id == ctx.author.id
        is_mentor = await self.bot.permissions.require_mentor(ctx.author)
        
        if not is_self and not is_mentor:
            await ctx.respond("❌ Only mentors and founders can view other players' statistics.", ephemeral=True)
            return
        
        # Получаем данные игрока
        player = await self.bot.db.get_player_by_discord_id(target.id)
        if not player:
            await ctx.respond(f"❌ Player {target.mention} is not registered in the system.", ephemeral=True)
            return
        
        # Определяем период
        days = 7 if "7" in period else 30 if "30" in period else None
        
        # Получаем статистику
        stats = await self._get_player_stats(player['id'], days)
        if not stats or stats['session_count'] == 0:
            await ctx.respond(f"📊 {target.mention} has no recorded sessions yet.", ephemeral=True)
            return
        
        # Генерируем графики
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
        
        # 1. Отправляем Embed с основной инфой
        await ctx.respond(embed=embed)
        
        # 2. Отправляем графики по одному
        await ctx.send(file=discord.File(trend_chart, filename="score_trend.png"))
        await ctx.send(file=discord.File(role_chart, filename="role_scores.png"))
    
    @discord.slash_command(name="stats_top", description="View top 10 players in the alliance")
    async def stats_top(self, ctx: discord.ApplicationContext):
        """Просмотр топ-10 игроков альянса"""
        await ctx.defer()
        
        # Получаем топ-10 за последние 30 дней
        start_date = datetime.utcnow() - timedelta(days=30)
        
        top_players = await self.bot.db.fetch("""
            SELECT 
                p.discord_id,
                p.nickname,
                AVG(s.score) as avg_score,
                COUNT(s.id) as session_count
            FROM players p
            JOIN sessions s ON s.player_id = p.id
            WHERE s.session_date >= $1
            GROUP BY p.id, p.discord_id, p.nickname
            HAVING COUNT(s.id) >= 1  -- Изменили с 3 на 1 для более легкого тестирования
            ORDER BY avg_score DESC
            LIMIT 10
        """, start_date)
        
        if not top_players:
            await ctx.respond("❌ Not enough data to generate top players list.", ephemeral=True)
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
        # embed.set_image(url="attachment://top_players.png") # Убираем картинку из эмбеда
        embed.set_footer(text="Top 10 players by average score")
        
        await ctx.respond(embed=embed)
        await ctx.send(file=discord.File(chart, filename="top_players.png"))

    @discord.slash_command(name="stats_seed_test", description="Seed database with test session data (Founder only)")
    async def stats_seed_test(self, ctx: discord.ApplicationContext):
        """Команда для генерации тестовых данных статистики"""
        await ctx.defer(ephemeral=True)
        
        if not await self.bot.permissions.require_founder(ctx.author):
            await ctx.respond("❌ Только основатели могут использовать эту команду.", ephemeral=True)
            return
            
        import random
        from datetime import datetime, timedelta
        
        # Получаем всех игроков
        players = await self.bot.db.fetch("SELECT id FROM players")
        if not players:
            await ctx.respond("❌ Нет игроков для заполнения статистики.", ephemeral=True)
            return
            
        # Получаем типы контента
        content_types = await self.bot.db.fetch("SELECT id FROM content")
        if not content_types:
            await ctx.respond("❌ Таблица контента пуста.", ephemeral=True)
            return
            
        # Добавляем по 5 случайных сессий для каждого игрока
        sessions_added = 0
        roles = ['Tank', 'Healer', 'DPS', 'Support']
        
        for player in players:
            for _ in range(5):
                # Случайная дата за последние 30 дней
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
                
        await ctx.respond(f"✅ Добавлено {sessions_added} тестовых сессий для {len(players)} игроков!", ephemeral=True)
    
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
        stats = await self.bot.db.fetchrow(stats_query, *params)
        
        if not stats or not stats['session_count']:
            return {'sessions': [], 'avg_score': 0, 'session_count': 0}
        
        # Тренд по неделям
        trend_query = f"""
            SELECT s.session_date, s.score
            FROM sessions s
            WHERE {where_str}
            ORDER BY s.session_date ASC
        """
        raw_trend_data = await self.bot.db.fetch(trend_query, *params)
        
        # Aggregate in Python for portability
        from collections import defaultdict
        week_scores = defaultdict(list)
        for row in raw_trend_data:
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
        role_data = await self.bot.db.fetch(role_query, *params)
        
        return {
            'avg_score': float(stats['avg_score']) if stats['avg_score'] else 0,
            'session_count': stats['session_count'],
            'last_session': stats['last_session'],
            'best_role': stats['best_role'],
            'top_content': stats['top_content'],
            'sessions': [],
            'trend_weeks': [r['week'] for r in trend_data],
            'trend_scores': [float(r['avg_score']) for r in trend_data],
            'role_names': [r['role'] for r in role_data],
            'role_scores': [float(r['avg_score']) for r in role_data]
        }

def setup(bot):
    bot.add_cog(StatsCommands(bot))