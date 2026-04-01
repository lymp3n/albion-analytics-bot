import os
import re
from pathlib import Path
from typing import Union
import discord
from discord import ui, option
from discord.ext import commands
from datetime import datetime

def get_templates():
    """Reads templates from events_templates.txt."""
    templates = {}
    # Use a stable path regardless of current working directory (Render can differ).
    # Keep file in repo root (one level above /commands).
    filepath = (Path(__file__).resolve().parent.parent / "events_templates.txt")
    
    default_text = "[Castle]\n1. Caller\n2. Healer\n3. DPS\n\n[Open World]\n1. Tank\n2. DPS\n"

    try:
        if not filepath.exists():
            # Create default file if not exists
            filepath.write_text(default_text, encoding="utf-8")

        content = filepath.read_text(encoding="utf-8")
    except Exception:
        # If filesystem is read-only/unavailable, fall back to defaults in-memory.
        content = default_text

    current_template = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            current_template = line[1:-1]
            templates[current_template] = []
        elif current_template:
            role_name = re.sub(r'^\d+\.\s*', '', line)
            templates[current_template].append(role_name)
                
    return templates

async def build_event_embed(bot, event_id: int):
    """Generates an aesthetic Embed for the event post"""
    event = await bot.db.fetchrow("SELECT content_name, event_time, status FROM events WHERE id = $1", event_id)
    if not event:
        return discord.Embed(description="❌ Event not found."), None
        
    signups = await bot.db.fetch("""
        SELECT s.slot_number, s.role_name, p.nickname, p.discord_id 
        FROM event_signups s 
        LEFT JOIN players p ON p.id = s.player_id 
        WHERE s.event_id = $1 
        ORDER BY s.slot_number
    """, event_id)
    
    embed = discord.Embed(
        title=f"📅 Event: {event['content_name']}",
        description=f"🕒 **Time:** {event['event_time']}\n\n**Group Roster:**",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    
    roster_text = ""
    for s in signups:
        mention = f" — <@{s['discord_id']}> ({s['nickname']})" if s['discord_id'] else " — *Open*"
        roster_text += f"`{s['slot_number']}.` **{s['role_name']}**{mention}\n"
    
    embed.description += f"\n{roster_text}"
    status_text = " (Closed)" if event.get('status') == 'closed' else ""
    embed.title += status_text

    if event.get('status') == 'closed':
        embed.color = discord.Color.dark_grey()
        embed.set_footer(text=f"Event closed | Event ID: {event_id}")
    else:
        embed.set_footer(text=f"Click 'Join' | Event ID: {event_id}")
    
    return embed

class SlotSelectView(ui.View):
    """Dropdown menu for selecting a specific slot"""
    def __init__(self, bot, event_id: int, player_id: int, available_slots: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.player_id = player_id
        
        options = [
            discord.SelectOption(
                label=f"Slot {s['slot_number']}: {s['role_name']}", 
                value=str(s['slot_number'])
            ) for s in available_slots[:25] # Discord limit - 25 items
        ]
        
        select = ui.Select(placeholder="Select your role slot...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        slot_num = int(interaction.data['values'][0])
        
        # Check if slot was taken while user was selecting
        check = await self.bot.db.fetchrow(
            "SELECT player_id FROM event_signups WHERE event_id = $1 AND slot_number = $2",
            self.event_id, slot_num
        )
        
        if check and check['player_id'] is not None:
            return await interaction.followup.send("❌ This slot is already taken!", ephemeral=True)
            
        # Update database
        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3",
            self.player_id, self.event_id, slot_num
        )
        
        # Update main message
        event = await self.bot.db.fetchrow("SELECT discord_channel_id, discord_message_id FROM events WHERE id = $1", self.event_id)
        if event:
            try:
                channel = self.bot.get_channel(event['discord_channel_id'])
                if not channel:
                    channel = await self.bot.fetch_channel(event['discord_channel_id'])
                    
                if channel:
                    original_msg = await channel.fetch_message(event['discord_message_id'])
                    embed = await build_event_embed(self.bot, self.event_id)
                    await original_msg.edit(embed=embed)
            except Exception as e:
                print(f"Error editing original message: {e}")

        await interaction.edit_original_response(content=f"✅ You have taken slot #{slot_num}!", view=None)

class EventControlView(ui.View):
    """Persistent buttons under event post"""
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        
    @ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="evt_join")
    async def join(self, button: ui.Button, interaction: discord.Interaction):
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not player:
            return await interaction.response.send_message("❌ Register first!", ephemeral=True)
            
        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event: return
        if event['status'] == 'closed':
            return await interaction.response.send_message("❌ Event is already closed!", ephemeral=True)
        
        # Check if already registered
        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            event['id'], player['id']
        )
        if existing:
            return await interaction.response.send_message(f"❌ You already occupy slot #{existing['slot_number']}.", ephemeral=True)
            
        # Get free slots
        free_slots = await self.bot.db.fetch(
            "SELECT slot_number, role_name FROM event_signups WHERE event_id = $1 AND player_id IS NULL ORDER BY slot_number",
            event['id']
        )
        
        if not free_slots:
            return await interaction.response.send_message("❌ No available slots!", ephemeral=True)
            
        view = SlotSelectView(self.bot, event['id'], player['id'], free_slots)
        await interaction.response.send_message("Select an available slot:", view=view, ephemeral=True)

    @ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="evt_leave")
    async def leave(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)
        
        if not event:
            return await interaction.followup.send("❌ Event not found.", ephemeral=True)
            
        if event['status'] == 'closed':
            return await interaction.followup.send("❌ Event is already closed, you cannot leave!", ephemeral=True)

        if player:
            # Check if recorded
            existing = await self.bot.db.fetchrow(
                "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
                event['id'], player['id']
            )
            
            if not existing:
                return await interaction.followup.send("❌ You are not on the participant list.", ephemeral=True)
                
            await self.bot.db.execute(
                "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
                event['id'], player['id']
            )
            
            # Update embed
            embed = await build_event_embed(self.bot, event['id'])
            await interaction.message.edit(embed=embed)
            await interaction.followup.send("✅ You have left the group.", ephemeral=True)
        else:
            await interaction.followup.send("❌ You are not registered.", ephemeral=True)

    @ui.button(label="Close Event", style=discord.ButtonStyle.secondary, custom_id="evt_close", row=1)
    async def close_event_btn(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Check permissions: role 1488301094609096744 or Founder
        has_role = any(r.id == 1488301094609096744 for r in interaction.user.roles)
        is_founder = await self.bot.permissions.require_founder(interaction.user)
        
        if not (has_role or is_founder):
            return await interaction.followup.send("❌ Only a Content Moderator can close the event.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            return await interaction.followup.send("❌ Event not found.", ephemeral=True)
            
        if event['status'] == 'closed':
            return await interaction.followup.send("❌ This event is already closed.", ephemeral=True)
            
        # Mark as closed
        await self.bot.db.execute("UPDATE events SET status = 'closed' WHERE id = $1", event['id'])
        
        # Update post (change color and remove buttons)
        embed = await build_event_embed(self.bot, event['id'])
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send(f"✅ Participants locked and event closed.", ephemeral=True)

# Standalone autocomplete function — must be outside the class.
# py-cord calls autocomplete handlers as plain functions with only (ctx: AutocompleteContext).
# If defined as a class method (self, ctx), py-cord passes ctx as self and never passes ctx — silent failure.
async def get_template_choices(ctx: discord.AutocompleteContext):
    return list(get_templates().keys())

class EventCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(EventControlView(self.bot))

    event_group = discord.SlashCommandGroup("event", "Manage events")

    @event_group.command(name="create", description="Create a new event in this channel or thread")
    @option("template", description="Role template", autocomplete=get_template_choices)
    async def create(self, ctx: discord.ApplicationContext, content: str, time: str, template: str):
        if not await self.bot.permissions.require_mentor(ctx.author):
            return await ctx.respond("❌ No permission.", ephemeral=True)
            
        templates = get_templates()
        if template not in templates:
            return await ctx.respond("❌ Template not found.", ephemeral=True)
            
        await ctx.defer(ephemeral=True)
        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        
        # Use the current channel or thread where the command was called
        channel = ctx.channel
        
        # 1. Create event in DB
        event_id = await self.bot.db.execute("""
            INSERT INTO events (discord_channel_id, guild_id, content_name, event_time, created_by)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, channel.id, player['guild_id'] if player else None, content, time, player['id'] if player else None)
        
        # 2. Fill slots from template
        for i, role in enumerate(templates[template], 1):
            await self.bot.db.execute(
                "INSERT INTO event_signups (event_id, slot_number, role_name) VALUES ($1, $2, $3)",
                event_id, i, role
            )
            
        # 3. Publish message in this channel/thread
        embed = await build_event_embed(self.bot, event_id)
        view = EventControlView(self.bot)
        msg = await channel.send(embed=embed, view=view)
        
        # 4. Attach message ID
        await self.bot.db.execute("UPDATE events SET discord_message_id = $1 WHERE id = $2", msg.id, event_id)
        await ctx.respond(f"✅ Event published here!")

    @event_group.command(name="close", description="Close an event and lock attendance")
    @option("event_id", description="Event ID (found at the bottom of the post)")
    async def close_event(self, ctx: discord.ApplicationContext, event_id: int):
        if not await self.bot.permissions.require_mentor(ctx.author):
            return await ctx.respond("❌ No permission.", ephemeral=True)
            
        await ctx.defer(ephemeral=True)
        event = await self.bot.db.fetchrow("SELECT id, discord_channel_id, discord_message_id, status FROM events WHERE id = $1", event_id)
        
        if not event:
            return await ctx.respond("❌ Event not found.", ephemeral=True)
            
        if event['status'] == 'closed':
            return await ctx.respond("❌ This event is already closed.", ephemeral=True)
            
        # Mark as closed
        await self.bot.db.execute("UPDATE events SET status = 'closed' WHERE id = $1", event_id)
        
        # Update post (change color and remove buttons)
        try:
            channel = self.bot.get_channel(event['discord_channel_id'])
            if not channel:
                channel = await self.bot.fetch_channel(event['discord_channel_id'])
                
            if channel:
                msg = await channel.fetch_message(event['discord_message_id'])
                embed = await build_event_embed(self.bot, event_id)
                # clear buttons
                class EmptyView(ui.View): pass
                await msg.edit(embed=embed, view=EmptyView())
        except Exception:
            pass
            
        await ctx.respond(f"✅ Event #{event_id} successfully closed. Participant list locked for statistics.")

def setup(bot):
    bot.add_cog(EventCommands(bot))
