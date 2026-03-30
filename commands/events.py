import os
import re
import discord
from discord import ui, option
from discord.ext import commands
from datetime import datetime

def get_templates():
    """Читает шаблоны из event_templates.txt."""
    templates = {}
    filepath = "event_templates.txt"
    
    if not os.path.exists(filepath):
        # Создаем дефолтный файл, если его нет
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("[Castle]\n1. Caller\n2. Healer\n3. DPS\n\n[Open World]\n1. Tank\n2. DPS\n")
            
    with open(filepath, "r", encoding="utf-8") as f:
        current_template = None
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith('[') and line.endswith(']'):
                current_template = line[1:-1]
                templates[current_template] = []
            elif current_template:
                role_name = re.sub(r'^\d+\.\s*', '', line)
                templates[current_template].append(role_name)
                
    return templates

async def build_event_embed(bot, event_id: int):
    """Генерирует красивый Embed для поста события"""
    event = await bot.db.fetchrow("SELECT content_name, event_time FROM events WHERE id = $1", event_id)
    if not event:
        return discord.Embed(description="❌ Событие не найдено."), None
        
    signups = await bot.db.fetch("""
        SELECT s.slot_number, s.role_name, p.nickname, p.discord_id 
        FROM event_signups s 
        LEFT JOIN players p ON p.id = s.player_id 
        WHERE s.event_id = $1 
        ORDER BY s.slot_number
    """, event_id)
    
    embed = discord.Embed(
        title=f"📅 Сбор: {event['content_name']}",
        description=f"🕒 **Время:** {event['event_time']}\n\n**Состав группы:**",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    
    roster_text = ""
    for s in signups:
        mention = f" — <@{s['discord_id']}> ({s['nickname']})" if s['discord_id'] else " — *Свободно*"
        roster_text += f"`{s['slot_number']}.` **{s['role_name']}**{mention}\n"
    
    embed.description += f"\n{roster_text}"
    embed.set_footer(text="Нажмите 'Участвовать', чтобы выбрать номер слота")
    
    return embed

class SlotSelectView(ui.View):
    """Меню выбора конкретного номера слота"""
    def __init__(self, bot, event_id: int, player_id: int, available_slots: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.player_id = player_id
        
        options = [
            discord.SelectOption(
                label=f"Слот {s['slot_number']}: {s['role_name']}", 
                value=str(s['slot_number'])
            ) for s in available_slots[:25] # Лимит Discord - 25 позиций
        ]
        
        select = ui.Select(placeholder="Выберите номер вашей роли...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        slot_num = int(interaction.data['values'][0])
        
        # Проверка: не заняли ли слот, пока юзер выбирал
        check = await self.bot.db.fetchrow(
            "SELECT player_id FROM event_signups WHERE event_id = $1 AND slot_number = $2",
            self.event_id, slot_num
        )
        
        if check and check['player_id'] is not None:
            return await interaction.followup.send("❌ Этот слот уже заняли!", ephemeral=True)
            
        # Обновляем базу
        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3",
            self.player_id, self.event_id, slot_num
        )
        
        # Обновляем основное сообщение
        embed = await build_event_embed(self.bot, self.event_id)
        await interaction.message.edit(embed=embed) # Редактируем сообщение с кнопками
        await interaction.followup.send(f"✅ Вы заняли слот №{slot_num}!", ephemeral=True)

class EventControlView(ui.View):
    """Постоянные кнопки под постом события"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
    @ui.button(label="Участвовать", style=discord.ButtonStyle.success, custom_id="evt_join")
    async def join(self, button: ui.Button, interaction: discord.Interaction):
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ Сначала зарегистрируйтесь!", ephemeral=True)
            
        event = await self.bot.db.fetchrow("SELECT id FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event: return
        
        # Проверка: не записан ли уже
        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            event['id'], player['id']
        )
        if existing:
            return await interaction.response.send_message(f"❌ Вы уже заняли слот №{existing['slot_number']}.", ephemeral=True)
            
        # Берем свободные слоты
        free_slots = await self.bot.db.fetch(
            "SELECT slot_number, role_name FROM event_signups WHERE event_id = $1 AND player_id IS NULL ORDER BY slot_number",
            event['id']
        )
        
        if not free_slots:
            return await interaction.response.send_message("❌ Мест нет!", ephemeral=True)
            
        view = SlotSelectView(self.bot, event['id'], player['id'], free_slots)
        await interaction.response.send_message("Выберите свободный номер:", view=view, ephemeral=True)

    @ui.button(label="Покинуть", style=discord.ButtonStyle.danger, custom_id="evt_leave")
    async def leave(self, button: ui.Button, interaction: discord.Interaction):
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        event = await self.bot.db.fetchrow("SELECT id FROM events WHERE discord_message_id = $1", interaction.message.id)
        
        if player and event:
            res = await self.bot.db.execute(
                "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
                event['id'], player['id']
            )
            if "UPDATE 0" not in res:
                embed = await build_event_embed(self.bot, event['id'])
                await interaction.message.edit(embed=embed)
                await interaction.response.send_message("✅ Вы покинули группу.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Вас нет в списке.", ephemeral=True)

class EventCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(EventControlView(self.bot))

    event_group = discord.SlashCommandGroup("event", "Управление событиями")

    async def get_template_choices(self, ctx: discord.AutocompleteContext):
        return list(get_templates().keys())

    @event_group.command(name="create", description="Создать новый сбор")
    @option("template", description="Шаблон ролей", autocomplete=get_template_choices)
    async def create(self, ctx: discord.ApplicationContext, channel: discord.TextChannel, content: str, time: str, template: str):
        if not await self.bot.permissions.require_mentor(ctx.author):
            return await ctx.respond("❌ Нет прав.", ephemeral=True)
            
        templates = get_templates()
        if template not in templates:
            return await ctx.respond("❌ Шаблон не найден.", ephemeral=True)
            
        await ctx.defer(ephemeral=True)
        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        
        # 1. Создаем событие в базе
        event_id = await self.bot.db.execute("""
            INSERT INTO events (discord_channel_id, guild_id, content_name, event_time, created_by)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, channel.id, player['guild_id'] if player else None, content, time, player['id'] if player else None)
        
        # 2. Заполняем слоты из шаблона
        for i, role in enumerate(templates[template], 1):
            await self.bot.db.execute(
                "INSERT INTO event_signups (event_id, slot_number, role_name) VALUES ($1, $2, $3)",
                event_id, i, role
            )
            
        # 3. Публикуем сообщение
        embed = await build_event_embed(self.bot, event_id)
        view = EventControlView(self.bot)
        msg = await channel.send(embed=embed, view=view)
        
        # 4. Привязываем ID сообщения
        await self.bot.db.execute("UPDATE events SET discord_message_id = $1 WHERE id = $2", msg.id, event_id)
        await ctx.respond(f"✅ Сбор опубликован в {channel.mention}")

def setup(bot):
    bot.add_cog(Event(bot))
