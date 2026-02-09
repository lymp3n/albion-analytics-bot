import discord
from discord import ui
from discord.ext import commands
from utils.permissions import Permissions


class MainMenuView(ui.View):
    """Главное меню бота с кнопками"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @ui.button(label="📝 Создать тикет", style=discord.ButtonStyle.primary, row=0)
    async def create_ticket(self, button: ui.Button, interaction: discord.Interaction):
        from commands.tickets import TicketModal
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            await interaction.response.send_message("❌ Сначала зарегистрируйтесь: `/register <код>`", ephemeral=True)
            return
        modal = TicketModal(self.bot, player['id'], player['guild_id'])
        await interaction.response.send_modal(modal)
    
    @ui.button(label="📊 Моя статистика", style=discord.ButtonStyle.secondary, row=0)
    async def my_stats(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Trigger stats command for self
        stats_cog = self.bot.get_cog('StatsCommands')
        if stats_cog:
            # Create a fake context-like object or just send embed directly
            player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
            if not player:
                await interaction.followup.send("❌ Вы не зарегистрированы.", ephemeral=True)
                return
            stats = await stats_cog._get_player_stats(player['id'], 30)
            if not stats['session_count']:
                await interaction.followup.send("📭 У вас пока нет сессий.", ephemeral=True)
                return
            embed = discord.Embed(
                title=f"📊 Ваша статистика",
                color=discord.Color.green()
            )
            embed.add_field(name="Средний балл", value=f"{stats['avg_score']:.2f}/10", inline=True)
            embed.add_field(name="Всего сессий", value=stats['session_count'], inline=True)
            embed.add_field(name="Лучшая роль", value=stats['best_role'] or "N/A", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Модуль статистики недоступен.", ephemeral=True)
    
    @ui.button(label="🎫 Мои тикеты", style=discord.ButtonStyle.secondary, row=0)
    async def my_tickets(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tickets = await self.bot.db.fetch("""
            SELECT t.id, t.status, t.role, t.created_at
            FROM tickets t JOIN players p ON p.id = t.player_id
            WHERE p.discord_id = $1 AND t.status != 'closed'
            ORDER BY t.created_at DESC LIMIT 5
        """, interaction.user.id)
        
        if not tickets:
            await interaction.followup.send("📭 У вас нет активных тикетов.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🎫 Ваши активные тикеты", color=discord.Color.blue())
        for t in tickets:
            status_emoji = "⏳" if t['status'] == 'available' else "🔍"
            embed.add_field(
                name=f"{status_emoji} #{t['id']} — {t['role']}",
                value=f"Статус: {t['status']}",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @ui.button(label="🏆 Топ игроков", style=discord.ButtonStyle.success, row=1)
    async def top_players(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats_cog = self.bot.get_cog('StatsCommands')
        if stats_cog:
            from datetime import datetime, timedelta
            start_date = datetime.utcnow() - timedelta(days=30)
            top = await self.bot.db.fetch("""
                SELECT p.nickname, AVG(s.score) as avg_score, COUNT(s.id) as cnt
                FROM players p JOIN sessions s ON s.player_id = p.id
                WHERE s.session_date >= $1
                GROUP BY p.id HAVING COUNT(s.id) >= 3
                ORDER BY avg_score DESC LIMIT 5
            """, start_date)
            
            if not top:
                await interaction.followup.send("❌ Недостаточно данных для рейтинга.", ephemeral=True)
                return
            
            embed = discord.Embed(title="🏆 Топ-5 игроков (30 дней)", color=discord.Color.gold())
            for i, p in enumerate(top, 1):
                embed.add_field(name=f"{i}. {p['nickname']}", value=f"Балл: {float(p['avg_score']):.2f} | Сессий: {p['cnt']}", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Модуль статистики недоступен.", ephemeral=True)


class MentorMenuView(ui.View):
    """Меню для менторов"""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
    
    @ui.button(label="📋 Доступные тикеты", style=discord.ButtonStyle.primary, row=0)
    async def available_tickets(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get mentor's guild
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            await interaction.followup.send("❌ Вы не зарегистрированы.", ephemeral=True)
            return
        
        tickets = await self.bot.db.fetch("""
            SELECT t.id, t.role, p.nickname, t.created_at
            FROM tickets t JOIN players p ON p.id = t.player_id
            WHERE p.guild_id = $1 AND t.status = 'available'
            ORDER BY t.created_at ASC LIMIT 10
        """, player['guild_id'])
        
        if not tickets:
            await interaction.followup.send("📭 Нет доступных тикетов для оценки.", ephemeral=True)
            return
        
        embed = discord.Embed(title="📋 Доступные тикеты", color=discord.Color.orange())
        for t in tickets:
            embed.add_field(
                name=f"#{t['id']} — {t['nickname']} ({t['role']})",
                value=f"Используйте `/ticket claim {t['id']}` чтобы взять",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @ui.button(label="🔍 Мои тикеты в работе", style=discord.ButtonStyle.secondary, row=0)
    async def my_claimed_tickets(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        tickets = await self.bot.db.fetch("""
            SELECT t.id, t.role, p.nickname, t.discord_channel_id
            FROM tickets t 
            JOIN players p ON p.id = t.player_id
            JOIN players m ON m.id = t.mentor_id
            WHERE m.discord_id = $1 AND t.status = 'in_progress'
        """, interaction.user.id)
        
        if not tickets:
            await interaction.followup.send("📭 У вас нет тикетов в работе.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🔍 Ваши тикеты в работе", color=discord.Color.blue())
        for t in tickets:
            channel_link = f"<#{t['discord_channel_id']}>" if t['discord_channel_id'] else "N/A"
            embed.add_field(
                name=f"#{t['id']} — {t['nickname']} ({t['role']})",
                value=f"Канал: {channel_link}",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


class MenuCommands(commands.Cog):
    """Команды меню"""
    
    def __init__(self, bot, db, permissions: Permissions):
        self.bot = bot
        self.db = db
        self.permissions = permissions
        print("✓ MenuCommands initialized")

def setup(bot):
    pass
    
    @discord.slash_command(name="menu", description="Открыть главное меню бота")
    async def menu(self, ctx: discord.ApplicationContext):
        """Показывает главное меню с кнопками"""
        is_mentor = await self.permissions.require_mentor(ctx.author)
        
        embed = discord.Embed(
            title="🎮 Albion Analytics Bot",
            description="Выберите действие:",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="📝 Создать тикет", 
            value="Отправить реплей на оценку ментору", 
            inline=False
        )
        embed.add_field(
            name="📊 Моя статистика", 
            value="Посмотреть свой прогресс и оценки", 
            inline=False
        )
        embed.add_field(
            name="🎫 Мои тикеты", 
            value="Список ваших активных тикетов", 
            inline=False
        )
        embed.set_footer(text="Используйте кнопки ниже для быстрого доступа")
        
        await ctx.respond(embed=embed, view=MainMenuView(self.bot), ephemeral=True)
        
        # If mentor, also show mentor menu
        if is_mentor:
            mentor_embed = discord.Embed(
                title="👨‍🏫 Меню ментора",
                description="Дополнительные функции для менторов:",
                color=discord.Color.green()
            )
            await ctx.followup.send(embed=mentor_embed, view=MentorMenuView(self.bot), ephemeral=True)
    
    @discord.slash_command(name="help", description="Показать справку по командам")
    async def help_command(self, ctx: discord.ApplicationContext):
        """Справка по командам бота"""
        embed = discord.Embed(
            title="📚 Справка по командам",
            description="Основные команды Albion Analytics Bot",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎫 Тикеты",
            value=(
                "`/menu` — Главное меню с кнопками\n"
                "`/ticket create` — Создать тикет\n"
                "`/ticket list` — Список тикетов\n"
                "`/ticket claim <id>` — Взять тикет (ментор)"
            ),
            inline=False
        )
        embed.add_field(
            name="📊 Статистика",
            value=(
                "`/stats` — Ваша статистика\n"
                "`/stats @игрок` — Статистика игрока (ментор)\n"
                "`/stats_top` — Топ-10 игроков"
            ),
            inline=False
        )
        embed.add_field(
            name="👥 Гильдия",
            value=(
                "`/register <код>` — Регистрация\n"
                "`/guild info` — Информация о гильдии (фаундер)\n"
                "`/payroll <сумма>` — Расчёт выплат (фаундер)"
            ),
            inline=False
        )
        embed.set_footer(text="💡 Совет: используйте /menu для быстрого доступа через кнопки!")
        
        await ctx.respond(embed=embed, ephemeral=True)
