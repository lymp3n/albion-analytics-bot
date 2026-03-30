import os
import re
import discord
from discord import ui, option
from discord.ext import commands

def get_templates():
    """Reads templates from event_templates.txt. Creates default if missing."""
    templates = {}
    filepath = "event_templates.txt"
    
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("[Castle]\n1. Caller\n2. Healer\n3. DPS\n4. Support\n\n[Crystal League]\n1. Tank\n2. Healer\n3. DPS\n4. DPS\n5. DPS\n")
            
    with open(filepath, "r", encoding="utf-8") as f:
        current_template = None
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                current_template = line[1:-1]
                templates[current_template] = []
            elif current_template:
                # Remove number if it exists in the template (e.g., "1. Caller" -> "Caller")
                role_name = re.sub(r'^\d+\.\s*', '', line)
                templates[current_template].append(role_name)
                
    return templates

async def build_event_message(bot, event_id: int) -> str:
    """Generates the text body for the event post based on signups"""
    event = await bot.db.fetchrow("SELECT content_name, event_time FROM events WHERE id = $1", event_id)
    if not event:
        return "❌ Event not found."
        
    signups = await bot.db.fetch("""
        SELECT s.slot_number, s.role_name, p.discord_id 
        FROM event_signups s 
        LEFT JOIN players p ON p.id = s.player_id 
        WHERE s.event_id = $1 
        ORDER BY s.slot_number
    """, event_id)
    
    lines = [
        f"**[{event['content_name']}]**",
        f"📅 {event['event_time']}",
        ""
    ]
    
    for s in signups:
        mention = f" <@{s['discord_id']}>" if s['discord_id'] else ""
        lines.append(f"{s['slot_number']}. {s['role_name']}{mention}")
        
    return "\n".join(lines)


class SlotSelectView(ui.View):
    """Ephemeral view that lets user select a slot"""
    def __init__(self, bot, event_id: int, player_id: int, available_slots: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.player_id = player_id
        
        # Max 25 options per Discord limitations
        options = [
            discord.SelectOption(label=f"{s['slot_number']}. {s['role_name']}", value=str(s['slot_number']))
            for s in available_slots[:25]
        ]
        
        self.select = ui.Select(placeholder="Select your role slot", options=options, min_values=1, max_values=1)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        slot_number = int(self.select.values[0])
        
        # Double check if slot is still empty to prevent race conditions
        slot = await self.bot.db.fetchrow("""
            SELECT id, player_id FROM event_signups 
            WHERE event_id = $1 AND slot_number = $2
        """, self.event_id, slot_number)
        
        if slot['player_id'] is not None:
            await interaction.followup.send("❌ This slot was just taken by someone else!", ephemeral=True)
            return
            
        # Update Database
        await self.bot.db.execute("UPDATE event_signups SET player_id = $1 WHERE id = $2", self.player_id, slot['id'])
        
        # Update Event Message
        msg_text = await build_event_message(self.bot, self.event_id)
        event = await self.bot.db.fetchrow("SELECT discord_channel_id, discord_message_id FROM events WHERE id = $1", self.event_id)
        
        try:
            channel = self.bot.get_channel(event['discord_channel_id'])
            if channel:
                msg = await channel.fetch_message(event['discord_message_id'])
                await msg.edit(content=msg_text)
        except Exception as e:
            print(f"Failed to update event message: {e}")
            
        await interaction.followup.send("✅ You have been added to the roster!", ephemeral=True)


class EventControlView(ui.View):
    """Persistent view attached to the Event message"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
    @ui.button(label="Участвовать", style=discord.ButtonStyle.success, custom_id="event_participate")
    async def participate(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user is registered
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            await interaction.followup.send("❌ You must be registered to participate.", ephemeral=True)
            return
            
        event = await self.bot.db.fetchrow("SELECT id FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            await interaction.followup.send("❌ Event not found in DB.", ephemeral=True)
            return
            
        # Check if already participating
        existing = await self.bot.db.fetchrow("SELECT id FROM event_signups WHERE event_id = $1 AND player_id = $2", event['id'], player['id'])
        if existing:
            await interaction.followup.send("❌ You are already registered for this event. Use 'Не участвовать' to leave your slot.", ephemeral=True)
            return
            
        # Fetch available slots
        available_slots = await self.bot.db.fetch("""
            SELECT slot_number, role_name FROM event_signups 
            WHERE event_id = $1 AND player_id IS NULL ORDER BY slot_number
        """, event['id'])
        
        if not available_slots:
            await interaction.followup.send("❌ Sorry, all slots are currently filled!", ephemeral=True)
            return
            
        view = SlotSelectView(self.bot, event['id'], player['id'], available_slots)
        await interaction.followup.send("Choose your role:", view=view, ephemeral=True)

    @ui.button(label="Не участвовать", style=discord.ButtonStyle.danger, custom_id="event_leave")
    async def leave(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            await interaction.followup.send("❌ You are not registered.", ephemeral=True)
            return
            
        event = await self.bot.db.fetchrow("SELECT id, discord_channel_id, discord_message_id FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            return
            
        # Clear their slot
        updated = await self.bot.db.execute("UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2 RETURNING id", event['id'], player['id'])
        
        if not updated:
            await interaction.followup.send("❌ You are not currently participating in this event.", ephemeral=True)
            return
            
        # Regenerate message
        msg_text = await build_event_message(self.bot, event['id'])
        try:
            channel = self.bot.get_channel(event['discord_channel_id'])
            if channel:
                msg = await channel.fetch_message(event['discord_message_id'])
                await msg.edit(content=msg_text)
        except Exception as e:
            print(f"Failed to update event message: {e}")
            
        await interaction.followup.send("✅ You have left the event roster.", ephemeral=True)


class EventCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✓ EventCommands initialized")
        
    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent view
        self.bot.add_view(EventControlView(self.bot))

    event_group = discord.SlashCommandGroup("event", "Manage content events")

    async def get_template_choices(self, ctx: discord.AutocompleteContext):
        templates = get_templates()
        return list(templates.keys())[:25]

    @event_group.command(name="create", description="Create a new event sign-up post")
    @option("channel", description="Channel to post the event")
    @option("content_name", description="Name of the content (e.g. Castle)")
    @option("event_time", description="Date and time (e.g. 15.02, 18 UTC)")
    @option("template", description="Choose the roster template", autocomplete=get_template_choices)
    async def create_event(self, ctx: discord.ApplicationContext, channel: discord.TextChannel, content_name: str, event_time: str, template: str):
        if not await self.bot.permissions.require_mentor(ctx.author):
            await ctx.respond("❌ Only Mentors and Founders can create events.", ephemeral=True)
            return
            
        templates = get_templates()
        if template not in templates:
            await ctx.respond("❌ Template not found in event_templates.txt.", ephemeral=True)
            return
            
        roles = templates[template]
        
        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        
        # Save event to DB
        event_id = await self.bot.db.execute("""
            INSERT INTO events (discord_channel_id, guild_id, content_name, event_time, created_by)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, channel.id, player['guild_id'] if player else None, content_name, event_time, player['id'] if player else None)
        
        # Insert empty slots
        for i, role in enumerate(roles, start=1):
            await self.bot.db.execute("""
                INSERT INTO event_signups (event_id, slot_number, role_name)
                VALUES ($1, $2, $3)
            """, event_id, i, role)
            
        # Generate initial message
        msg_text = await build_event_message(self.bot, event_id)
        view = EventControlView(self.bot)
        
        try:
            msg = await channel.send(content=msg_text, view=view)
            # Link message id to DB
            await self.bot.db.execute("UPDATE events SET discord_message_id = $1 WHERE id = $2", msg.id, event_id)
            await ctx.respond(f"✅ Event successfully created in {channel.mention}!", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Failed to post message: {e}", ephemeral=True)

def setup(bot):
    bot.add_cog(EventCommands(bot))
