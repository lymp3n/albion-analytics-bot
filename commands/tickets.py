import discord
import asyncio
from discord import option, ui
from discord.ext import commands
from datetime import datetime
from typing import Optional, List
import hashlib
from models import TicketStatus, ContentTypes, PlayerRoles
from utils.permissions import Permissions
from utils.validators import ReplayValidator, RoleValidator
from services.nlp import ErrorCategorizer

# --- Ticket Creation Modal ---

class TicketModal(ui.Modal):
    """Модальное окно создания тикета (Replay + Роль)"""
    def __init__(self, bot, player_id: int, guild_id: int):
        super().__init__(title="Create Session Ticket")
        self.bot = bot
        self.player_id = player_id
        self.guild_id = guild_id
        
        self.replay_url = ui.InputText(
            label="Albion Online Replay URL",
            placeholder="https://albiononline.com/en/replay/...",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=500
        )
        self.role = ui.InputText(
            label="Your Role in Session",
            placeholder="D-Tank, E-Tank, Healer, Support, DPS...",
            style=discord.InputTextStyle.short,
            required=True,
            max_length=30
        )
        self.description = ui.InputText(
            label="Brief Session Description (optional)",
            placeholder="e.g., 'Crystal League 5v5, lost first fight...'",
            style=discord.InputTextStyle.long,
            required=False,
            max_length=500
        )
        
        self.add_item(self.replay_url)
        self.add_item(self.role)
        self.add_item(self.description)
    
    async def callback(self, interaction: discord.Interaction):
        # Валидация роли
        normalized_role = RoleValidator.normalize_role(self.role.value)
        if not normalized_role:
            suggestions = RoleValidator.get_role_suggestions(self.role.value)
            suggestion_text = f"\nВозможно, вы имели в виду: {', '.join(suggestions)}?" if suggestions else ""
            await interaction.response.send_message(
                f"❌ Неизвестная роль '{self.role.value}'. Доступные: {', '.join(PlayerRoles.all())}{suggestion_text}",
                ephemeral=True
            )
            return
        
        # Получение категории для тикетов
        category_id = self.bot.tickets_category_id or self.bot.config.get('tickets_category_id')
        category = discord.utils.get(interaction.guild.categories, id=category_id)
        
        if not category:
            await interaction.response.send_message("❌ Категория тикетов не найдена. Свяжитесь с админом.", ephemeral=True)
            return
        
        # Создание канала
        channel_name = f"ticket-{interaction.user.name}-{hashlib.md5(str(datetime.utcnow()).encode()).hexdigest()[:4]}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        mentor_role = interaction.guild.get_role(self.bot.permissions.mentor_role_id)
        founder_role = interaction.guild.get_role(self.bot.permissions.founder_role_id)
        
        if mentor_role: overwrites[mentor_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if founder_role: overwrites[founder_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            
        channel = await interaction.guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
            
        # Запись в БД
        ticket_id = await self.bot.db.execute("""
            INSERT INTO tickets (
                discord_channel_id, player_id, replay_link, session_date, 
                role, description, status, guild_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, channel.id, self.player_id, self.replay_url.value.strip(), datetime.utcnow().date(),
           normalized_role, self.description.value.strip() if self.description.value else None,
           TicketStatus.AVAILABLE.value, self.guild_id)
           
        embed = discord.Embed(
            title="🎫 New Session Ticket Created",
            description="Ожидайте проверки ментором.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Replay", value=self.replay_url.value.strip(), inline=False)
        embed.add_field(name="Role", value=normalized_role, inline=True)
        embed.add_field(name="Status", value="⏳ Awaiting Mentor", inline=True)
        if self.description.value:
            embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.set_footer(text=f"ID: {ticket_id}")
        
        message = await channel.send(f"{interaction.user.mention}", embed=embed, view=TicketControlView(self.bot))
        await self.bot.db.execute("UPDATE tickets SET discord_message_id = $1 WHERE id = $2", message.id, ticket_id)
        
        await interaction.response.send_message(f"✅ Тикет создан: {channel.mention}", ephemeral=True)


# --- Rating Flow ---

class RatingSelectView(ui.View):
    """Выбор параметров при оценке сессии"""
    def __init__(self, bot, ticket_id: int, player_id: int, mentor_id: int, replay_link: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_id = ticket_id
        self.player_id = player_id
        self.mentor_id = mentor_id
        self.replay_link = replay_link
        self.selections = {"content": None, "role": None, "score": None, "errors": []}
        
        # Добавление селектов (Контент, Роль, Оценка)
        content_options = [discord.SelectOption(label=c) for c in ContentTypes.all()]
        self.add_item(ui.Select(placeholder="Тип контента", options=content_options, custom_id="sel_content"))
        
        role_options = [discord.SelectOption(label=r) for r in PlayerRoles.all()]
        self.add_item(ui.Select(placeholder="Ваша роль", options=role_options, custom_id="sel_role"))
        
        score_options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)]
        self.add_item(ui.Select(placeholder="Оценка (1-10)", options=score_options, custom_id="sel_score"))

    @ui.button(label="Продолжить", style=discord.ButtonStyle.primary, row=4)
    async def next_step(self, button, interaction: discord.Interaction):
        # Сбор данных из селектов
        for item in self.children:
            if isinstance(item, ui.Select):
                if not item.values:
                    await interaction.response.send_message("❌ Выберите все параметры!", ephemeral=True)
                    return
                key = item.custom_id.replace("sel_", "")
                self.selections[key] = item.values[0]
        
        await interaction.response.send_modal(FeedbackModal(self.bot, self.ticket_id, self.player_id, self.mentor_id, self.selections))

class FeedbackModal(ui.Modal):
    """Финальный этап оценки (Ошибки + Рекомендации)"""
    def __init__(self, bot, ticket_id, player_id, mentor_id, data):
        super().__init__(title="Session Feedback")
        self.bot, self.ticket_id, self.player_id, self.mentor_id, self.data = bot, ticket_id, player_id, mentor_id, data
        
        self.errors = ui.InputText(label="Ошибки (через запятую)", style=discord.InputTextStyle.long, required=True)
        self.work_on = ui.InputText(label="Над чем работать?", style=discord.InputTextStyle.long, required=True)
        self.add_item(self.errors)
        self.add_item(self.work_on)

    async def callback(self, interaction: discord.Interaction):
        # Сохранение сессии и закрытие тикета
        error_list = [e.strip() for e in self.errors.value.split(',')]
        await self.bot.db.execute("""
            INSERT INTO sessions (ticket_id, player_id, mentor_id, content_type, role, score, errors, work_on, session_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, self.ticket_id, self.player_id, self.mentor_id, self.data['content'], self.data['role'], 
           int(self.data['score']), ",".join(error_list), self.work_on.value, datetime.utcnow())
        
        await self.bot.db.execute("UPDATE tickets SET status = $1, closed_at = $2 WHERE id = $3", 
                                  TicketStatus.CLOSED.value, datetime.utcnow(), self.ticket_id)
        
        await interaction.response.send_message("✅ Сессия успешно оценена и тикет закрыт!")
        # Логика уведомления игрока...

# --- UI Controls ---

class TicketControlView(ui.View):
    """Кнопки управления внутри канала тикета"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✅")
    async def claim_callback(self, button, interaction: discord.Interaction):
        if not await self.bot.permissions.require_mentor(interaction.user):
            return await interaction.response.send_message("❌ Только менторы!", ephemeral=True)
            
        mentor = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        ticket = await self.bot.db.fetchrow("SELECT * FROM tickets WHERE discord_channel_id = $1", interaction.channel_id)
        
        if ticket['status'] == TicketStatus.AVAILABLE.value:
            await self.bot.db.execute("UPDATE tickets SET status = $1, mentor_id = $2 WHERE id = $3", 
                                      TicketStatus.IN_PROGRESS.value, mentor['id'], ticket['id'])
            # Обновление Embed...
            await interaction.response.send_message(f"✅ Взято ментором {interaction.user.mention}")
        else:
            await interaction.response.send_message("❌ Тикет уже занят или закрыт.", ephemeral=True)

# --- Slash Commands ---

class TicketsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✓ TicketsCommands initialized")

    ticket_group = discord.SlashCommandGroup("ticket", "Management of session tickets")

    @ticket_group.command(name="unclaim", description="Отменить захват тикета и вернуть его в очередь")
    @option("ticket_id", description="ID тикета", required=True)
    async def ticket_unclaim(self, ctx: discord.ApplicationContext, ticket_id: int):
        """Возвращает тикет в статус AVAILABLE"""
        await ctx.defer(ephemeral=True)
        
        if not await self.bot.permissions.require_mentor(ctx.author):
            return await ctx.respond("❌ Недостаточно прав.", ephemeral=True)

        mentor = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        ticket = await self.bot.db.fetchrow("SELECT * FROM tickets WHERE id = $1", ticket_id)
        
        if not ticket:
            return await ctx.respond(f"❌ Тикет #{ticket_id} не найден.", ephemeral=True)

        if ticket['status'] != TicketStatus.IN_PROGRESS.value:
            return await ctx.respond("❌ Этот тикет не находится в работе.", ephemeral=True)

        # Проверка прав: свой тикет или Founder
        is_founder = await self.bot.permissions.require_founder(ctx.author)
        if ticket['mentor_id'] != mentor['id'] and not is_founder:
            return await ctx.respond("❌ Вы можете освободить только свой тикет.", ephemeral=True)

        # Обновление БД
        await self.bot.db.execute("""
            UPDATE tickets SET status = $1, mentor_id = NULL, updated_at = $2 WHERE id = $3
        """, TicketStatus.AVAILABLE.value, datetime.utcnow(), ticket_id)

        # Обновление сообщения в канале тикета
        try:
            channel = self.bot.get_channel(ticket['discord_channel_id'])
            if channel:
                msg = await channel.fetch_message(ticket['discord_message_id'])
                embed = msg.embeds[0]
                for i, field in enumerate(embed.fields):
                    if field.name == "Status":
                        embed.set_field_at(i, name="Status", value="⏳ Awaiting Mentor", inline=True)
                embed.color = discord.Color.blue()
                await msg.edit(embed=embed, view=TicketControlView(self.bot))
                await channel.send(f"🔄 Ментор {ctx.author.mention} освободил тикет. Он снова доступен.")
        except: pass

        await ctx.respond(f"✅ Тикет #{ticket_id} возвращен в очередь.")

    @ticket_group.command(name="details")
    @option("ticket_id", required=True)
    async def ticket_details(self, ctx, ticket_id: int):
        ticket = await self.bot.db.fetchrow("""
            SELECT t.*, p.nickname as player_nickname, p.discord_id as player_discord_id
            FROM tickets t JOIN players p ON t.player_id = p.id WHERE t.id = $1
        """, ticket_id)
        # Логика отображения деталей...
        await ctx.respond(f"Детали тикета #{ticket_id}")

def setup(bot):
    bot.add_cog(TicketsCommands(bot))
