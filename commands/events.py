import re
from pathlib import Path
from typing import Union

import discord
from discord import option, ui
from discord.ext import commands
from datetime import datetime

SHOTCALLER_ROLE_IDS = {1469711597827260679, 1488301094609096744}


def get_templates():
    """Reads templates from events_templates.txt."""
    templates = {}
    filepath = Path(__file__).resolve().parent.parent / "events_templates.txt"
    default_text = "[Castle]\n1. Caller\n2. Healer\n3. DPS\n\n[Open World]\n1. Tank\n2. DPS\n"

    try:
        if not filepath.exists():
            filepath.write_text(default_text, encoding="utf-8")
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        content = default_text

    current_template = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_template = line[1:-1]
            templates[current_template] = []
        elif current_template:
            role_name = re.sub(r"^\d+\.\s*", "", line)
            templates[current_template].append(role_name)

    return templates


async def build_event_embed(bot, event_id: int):
    event = await bot.db.fetchrow("SELECT content_name, event_time, status FROM events WHERE id = $1", event_id)
    if not event:
        return discord.Embed(description="❌ Event not found."), None

    signups = await bot.db.fetch(
        """
        SELECT s.slot_number, s.role_name, p.nickname, p.discord_id
        FROM event_signups s
        LEFT JOIN players p ON p.id = s.player_id
        WHERE s.event_id = $1
        ORDER BY s.slot_number
        """,
        event_id,
    )

    embed = discord.Embed(
        title=f"📅 Event: {event['content_name']}",
        description=f"🕒 **Time:** {event['event_time']}\n\n**Group Roster:**",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow(),
    )

    roster_text = ""
    for s in signups:
        mention = f" — <@{s['discord_id']}> ({s['nickname']})" if s["discord_id"] else " — *Open*"
        roster_text += f"`{s['slot_number']}.` **{s['role_name']}**{mention}\n"

    embed.description += f"\n{roster_text}"
    if event.get("status") == "closed":
        embed.title += " (Closed)"
        embed.color = discord.Color.dark_grey()
        embed.set_footer(text=f"Event closed | Event ID: {event_id}")
    else:
        embed.set_footer(text=f"Click 'Join' | Event ID: {event_id}")

    return embed


async def get_or_create_player_profile(bot, member: Union[discord.Member, discord.User], event: dict = None, guild: discord.Guild = None):
    player = await bot.db.get_player_by_discord_id(member.id)
    if player:
        return player

    guild_id = event.get("guild_id") if event else None
    if not guild_id and guild:
        guild_row = await bot.db.get_guild_by_discord_id(guild.id)
        guild_id = guild_row["id"] if guild_row else None
    if not guild_id:
        return None

    display_name = getattr(member, "display_name", member.name)
    await bot.db.execute(
        """
        INSERT INTO players (discord_id, discord_username, nickname, guild_id, status)
        VALUES ($1, $2, $3, $4, 'active')
        """,
        member.id,
        member.name,
        display_name[:64],
        guild_id,
    )
    return await bot.db.get_player_by_discord_id(member.id)


async def refresh_event_message(bot, event_id: int):
    event_row = await bot.db.fetchrow("SELECT discord_channel_id, discord_message_id FROM events WHERE id = $1", event_id)
    if not event_row:
        return

    try:
        channel = bot.get_channel(event_row["discord_channel_id"])
        if not channel:
            channel = await bot.fetch_channel(event_row["discord_channel_id"])
        if not channel:
            return
        msg = await channel.fetch_message(event_row["discord_message_id"])
        embed = await build_event_embed(bot, event_id)
        await msg.edit(embed=embed)
    except Exception:
        return


def is_shotcaller(member: discord.Member) -> bool:
    return any(role.id in SHOTCALLER_ROLE_IDS for role in member.roles)


async def can_manage_event(bot, member: discord.Member) -> bool:
    return bool(await bot.permissions.require_mentor(member) or is_shotcaller(member))


class SlotSelectView(ui.View):
    def __init__(self, bot, event_id: int, player_id: int, available_slots: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.player_id = player_id

        options = [
            discord.SelectOption(label=f"Slot {s['slot_number']}: {s['role_name']}", value=str(s["slot_number"]))
            for s in available_slots[:25]
        ]
        select = ui.Select(placeholder="Select your role slot...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        slot_num = int(interaction.data["values"][0])

        check = await self.bot.db.fetchrow(
            "SELECT player_id FROM event_signups WHERE event_id = $1 AND slot_number = $2",
            self.event_id,
            slot_num,
        )
        if check and check["player_id"] is not None:
            return await interaction.followup.send("❌ This slot is already taken!", ephemeral=True)

        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3",
            self.player_id,
            self.event_id,
            slot_num,
        )
        await refresh_event_message(self.bot, self.event_id)
        await interaction.edit_original_response(content=f"✅ You have taken slot #{slot_num}!", view=None)


class ManageAddModal(ui.Modal):
    def __init__(self, bot, event_id: int):
        super().__init__(title="Manage Event: Add/Move")
        self.bot = bot
        self.event_id = event_id
        self.user_id = ui.InputText(label="User ID", placeholder="Discord user ID", required=True)
        self.slot_number = ui.InputText(label="Slot Number", placeholder="e.g. 3", required=True)
        self.add_item(self.user_id)
        self.add_item(self.slot_number)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            target_id = int(self.user_id.value.strip())
            slot = int(self.slot_number.value.strip())
        except ValueError:
            return await interaction.followup.send("❌ User ID and Slot must be numbers.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status, guild_id FROM events WHERE id = $1", self.event_id)
        if not event or event["status"] == "closed":
            return await interaction.followup.send("❌ Event is not available.", ephemeral=True)

        target_member = interaction.guild.get_member(target_id) if interaction.guild else None
        if not target_member:
            try:
                target_member = await self.bot.fetch_user(target_id)
            except Exception:
                return await interaction.followup.send("❌ User not found.", ephemeral=True)

        player = await get_or_create_player_profile(self.bot, target_member, event=event, guild=interaction.guild)
        if not player:
            return await interaction.followup.send("❌ Failed to create/get player profile.", ephemeral=True)

        slot_row = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND slot_number = $2",
            self.event_id,
            slot,
        )
        if not slot_row:
            return await interaction.followup.send("❌ Slot does not exist. Use Add Extra for new slots.", ephemeral=True)

        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
            self.event_id,
            player["id"],
        )
        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3",
            player["id"],
            self.event_id,
            slot,
        )
        await refresh_event_message(self.bot, self.event_id)
        await interaction.followup.send(f"✅ Assigned <@{target_id}> to slot #{slot}.", ephemeral=True)


class ManageRemoveModal(ui.Modal):
    def __init__(self, bot, event_id: int):
        super().__init__(title="Manage Event: Remove")
        self.bot = bot
        self.event_id = event_id
        self.user_id = ui.InputText(label="User ID", placeholder="Discord user ID", required=True)
        self.add_item(self.user_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            target_id = int(self.user_id.value.strip())
        except ValueError:
            return await interaction.followup.send("❌ User ID must be a number.", ephemeral=True)

        player = await self.bot.db.get_player_by_discord_id(target_id)
        if not player:
            return await interaction.followup.send("❌ Player profile not found.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE id = $1", self.event_id)
        if not event or event["status"] == "closed":
            return await interaction.followup.send("❌ Event is not available.", ephemeral=True)

        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            self.event_id,
            player["id"],
        )
        if not existing:
            return await interaction.followup.send("❌ This player is not in the event.", ephemeral=True)

        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
            self.event_id,
            player["id"],
        )
        await refresh_event_message(self.bot, self.event_id)
        await interaction.followup.send(f"✅ Removed <@{target_id}> from slot #{existing['slot_number']}.", ephemeral=True)


class ManageAddExtraModal(ui.Modal):
    def __init__(self, bot, event_id: int):
        super().__init__(title="Manage Event: Add Extra Slot")
        self.bot = bot
        self.event_id = event_id
        self.user_id = ui.InputText(label="User ID", placeholder="Discord user ID", required=True)
        self.role_name = ui.InputText(label="Role Name", placeholder="e.g. Flex DPS", required=True, max_length=50)
        self.add_item(self.user_id)
        self.add_item(self.role_name)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            target_id = int(self.user_id.value.strip())
        except ValueError:
            return await interaction.followup.send("❌ User ID must be a number.", ephemeral=True)

        role_name = self.role_name.value.strip()
        if not role_name:
            return await interaction.followup.send("❌ Role Name is required.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status, guild_id FROM events WHERE id = $1", self.event_id)
        if not event or event["status"] == "closed":
            return await interaction.followup.send("❌ Event is not available.", ephemeral=True)

        target_member = interaction.guild.get_member(target_id) if interaction.guild else None
        if not target_member:
            try:
                target_member = await self.bot.fetch_user(target_id)
            except Exception:
                return await interaction.followup.send("❌ User not found.", ephemeral=True)

        player = await get_or_create_player_profile(self.bot, target_member, event=event, guild=interaction.guild)
        if not player:
            return await interaction.followup.send("❌ Failed to create/get player profile.", ephemeral=True)

        next_slot_row = await self.bot.db.fetchrow(
            "SELECT COALESCE(MAX(slot_number), 0) + 1 AS next_slot FROM event_signups WHERE event_id = $1",
            self.event_id,
        )
        next_slot = int(next_slot_row["next_slot"]) if next_slot_row and next_slot_row.get("next_slot") else 1

        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
            self.event_id,
            player["id"],
        )
        await self.bot.db.execute(
            "INSERT INTO event_signups (event_id, slot_number, role_name, player_id) VALUES ($1, $2, $3, $4)",
            self.event_id,
            next_slot,
            role_name[:50],
            player["id"],
        )
        await refresh_event_message(self.bot, self.event_id)
        await interaction.followup.send(
            f"✅ Added extra slot #{next_slot} ({role_name}) for <@{target_id}>.",
            ephemeral=True,
        )


class ManageEventView(ui.View):
    def __init__(self, bot, event_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id

    @ui.button(label="Add/Move Player", style=discord.ButtonStyle.primary)
    async def add_move(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ManageAddModal(self.bot, self.event_id))

    @ui.button(label="Remove Player", style=discord.ButtonStyle.danger)
    async def remove(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ManageRemoveModal(self.bot, self.event_id))

    @ui.button(label="Add Extra Slot", style=discord.ButtonStyle.secondary)
    async def add_extra(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(ManageAddExtraModal(self.bot, self.event_id))


class EventControlView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Join", style=discord.ButtonStyle.success, custom_id="evt_join")
    async def join(self, button: ui.Button, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        event = await self.bot.db.fetchrow("SELECT id, status, guild_id FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            return await interaction.followup.send("❌ Event not found.", ephemeral=True)
        if event["status"] == "closed":
            return await interaction.followup.send("❌ Event is already closed!", ephemeral=True)

        player = await get_or_create_player_profile(self.bot, interaction.user, event=event, guild=interaction.guild)
        if not player:
            return await interaction.followup.send(
                "❌ Cannot determine guild for this event. Ask founder to register guild first.",
                ephemeral=True,
            )

        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            event["id"],
            player["id"],
        )
        if existing:
            return await interaction.followup.send(f"❌ You already occupy slot #{existing['slot_number']}.", ephemeral=True)

        free_slots = await self.bot.db.fetch(
            "SELECT slot_number, role_name FROM event_signups WHERE event_id = $1 AND player_id IS NULL ORDER BY slot_number",
            event["id"],
        )
        if not free_slots:
            return await interaction.followup.send("❌ No available slots!", ephemeral=True)

        view = SlotSelectView(self.bot, event["id"], player["id"], free_slots)
        await interaction.followup.send("Select an available slot:", view=view, ephemeral=True)

    @ui.button(label="Leave", style=discord.ButtonStyle.danger, custom_id="evt_leave")
    async def leave(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)

        if not event:
            return await interaction.followup.send("❌ Event not found.", ephemeral=True)
        if event["status"] == "closed":
            return await interaction.followup.send("❌ Event is already closed, you cannot leave!", ephemeral=True)
        if not player:
            return await interaction.followup.send("❌ You are not registered.", ephemeral=True)

        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            event["id"],
            player["id"],
        )
        if not existing:
            return await interaction.followup.send("❌ You are not on the participant list.", ephemeral=True)

        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2",
            event["id"],
            player["id"],
        )
        await refresh_event_message(self.bot, event["id"])
        await interaction.followup.send("✅ You have left the group.", ephemeral=True)

    @ui.button(label="Close Event", style=discord.ButtonStyle.secondary, custom_id="evt_close", row=1)
    async def close_event_btn(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await can_manage_event(self.bot, interaction.user):
            return await interaction.followup.send("❌ Only Shotcaller, Mentor, or Founder can close the event.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            return await interaction.followup.send("❌ Event not found.", ephemeral=True)
        if event["status"] == "closed":
            return await interaction.followup.send("❌ This event is already closed.", ephemeral=True)

        await self.bot.db.execute("UPDATE events SET status = 'closed' WHERE id = $1", event["id"])
        embed = await build_event_embed(self.bot, event["id"])
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("✅ Participants locked and event closed.", ephemeral=True)

    @ui.button(label="Manage", style=discord.ButtonStyle.primary, custom_id="evt_manage", row=1)
    async def manage_event_btn(self, button: ui.Button, interaction: discord.Interaction):
        if not await can_manage_event(self.bot, interaction.user):
            return await interaction.response.send_message(
                "❌ Only Shotcaller, Mentor, or Founder can manage event roster.",
                ephemeral=True,
            )

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE discord_message_id = $1", interaction.message.id)
        if not event:
            return await interaction.response.send_message("❌ Event not found.", ephemeral=True)
        if event["status"] == "closed":
            return await interaction.response.send_message("❌ Event is already closed.", ephemeral=True)

        await interaction.response.send_message(
            "Manage roster: choose an action below.",
            view=ManageEventView(self.bot, event["id"]),
            ephemeral=True,
        )


async def get_template_choices(ctx: discord.AutocompleteContext):
    try:
        return list(get_templates().keys())[:25]
    except Exception:
        return []


class EventCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(EventControlView(self.bot))

    event_group = discord.SlashCommandGroup("event", "Manage events")

    async def _assert_event_manager(self, ctx: discord.ApplicationContext) -> bool:
        if not await can_manage_event(self.bot, ctx.author):
            await ctx.followup.send("❌ Only Shotcaller, Mentor, or Founder can manage event roster.", ephemeral=True)
            return False
        return True

    @event_group.command(name="create", description="Create a new event in this channel or thread")
    @option("template", description="Role template", autocomplete=get_template_choices)
    async def create(self, ctx: discord.ApplicationContext, content: str, time: str, template: str):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return

        if not await self.bot.permissions.require_member(ctx.author):
            return await ctx.followup.send("❌ No permission.", ephemeral=True)

        templates = get_templates()
        if template not in templates:
            return await ctx.followup.send("❌ Template not found.", ephemeral=True)

        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        channel = ctx.channel

        event_id = await self.bot.db.execute(
            """
            INSERT INTO events (discord_channel_id, guild_id, content_name, event_time, created_by)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
            """,
            channel.id,
            player["guild_id"] if player else None,
            content,
            time,
            player["id"] if player else None,
        )

        for i, role in enumerate(templates[template], 1):
            await self.bot.db.execute(
                "INSERT INTO event_signups (event_id, slot_number, role_name) VALUES ($1, $2, $3)",
                event_id,
                i,
                role,
            )

        embed = await build_event_embed(self.bot, event_id)
        msg = await channel.send(embed=embed, view=EventControlView(self.bot))
        await self.bot.db.execute("UPDATE events SET discord_message_id = $1 WHERE id = $2", msg.id, event_id)
        await ctx.followup.send("✅ Event published here!", ephemeral=True)

    @event_group.command(name="close", description="Close an event and lock attendance")
    @option("event_id", description="Event ID (found at the bottom of the post)")
    async def close_event(self, ctx: discord.ApplicationContext, event_id: int):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return

        if not await self._assert_event_manager(ctx):
            return

        event = await self.bot.db.fetchrow(
            "SELECT id, discord_channel_id, discord_message_id, status FROM events WHERE id = $1",
            event_id,
        )
        if not event:
            return await ctx.followup.send("❌ Event not found.", ephemeral=True)
        if event["status"] == "closed":
            return await ctx.followup.send("❌ This event is already closed.", ephemeral=True)

        await self.bot.db.execute("UPDATE events SET status = 'closed' WHERE id = $1", event_id)
        try:
            channel = self.bot.get_channel(event["discord_channel_id"])
            if not channel:
                channel = await self.bot.fetch_channel(event["discord_channel_id"])
            if channel:
                msg = await channel.fetch_message(event["discord_message_id"])
                embed = await build_event_embed(self.bot, event_id)
                class EmptyView(ui.View):
                    pass
                await msg.edit(embed=embed, view=EmptyView())
        except Exception:
            pass

        await ctx.followup.send(f"✅ Event #{event_id} successfully closed. Participant list locked for statistics.", ephemeral=True)

    @event_group.command(name="add_player", description="Manually add/move player to a specific slot")
    @option("event_id", description="Event ID")
    @option("user", description="User to place into slot")
    @option("slot", description="Target slot number")
    async def add_player(self, ctx: discord.ApplicationContext, event_id: int, user: discord.Member, slot: int):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return
        if not await self._assert_event_manager(ctx):
            return

        event = await self.bot.db.fetchrow("SELECT id, status, guild_id FROM events WHERE id = $1", event_id)
        if not event or event["status"] == "closed":
            return await ctx.followup.send("❌ Event not found or already closed.", ephemeral=True)

        slot_row = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND slot_number = $2",
            event_id,
            slot,
        )
        if not slot_row:
            return await ctx.followup.send("❌ Slot not found in this event.", ephemeral=True)

        player = await get_or_create_player_profile(self.bot, user, event=event, guild=ctx.guild)
        if not player:
            return await ctx.followup.send("❌ Failed to create/get player profile.", ephemeral=True)

        await self.bot.db.execute("UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2", event_id, player["id"])
        await self.bot.db.execute(
            "UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3",
            player["id"],
            event_id,
            slot,
        )
        await refresh_event_message(self.bot, event_id)
        await ctx.followup.send(f"✅ Assigned {user.mention} to slot #{slot}.", ephemeral=True)

    @event_group.command(name="remove_player", description="Remove player from event roster")
    @option("event_id", description="Event ID")
    @option("user", description="User to remove")
    async def remove_player(self, ctx: discord.ApplicationContext, event_id: int, user: discord.Member):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return
        if not await self._assert_event_manager(ctx):
            return

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE id = $1", event_id)
        if not event or event["status"] == "closed":
            return await ctx.followup.send("❌ Event not found or already closed.", ephemeral=True)

        player = await self.bot.db.get_player_by_discord_id(user.id)
        if not player:
            return await ctx.followup.send("❌ Player profile not found.", ephemeral=True)

        existing = await self.bot.db.fetchrow(
            "SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2",
            event_id,
            player["id"],
        )
        if not existing:
            return await ctx.followup.send("❌ User is not in this event.", ephemeral=True)

        await self.bot.db.execute("UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2", event_id, player["id"])
        await refresh_event_message(self.bot, event_id)
        await ctx.followup.send(f"✅ Removed {user.mention} from slot #{existing['slot_number']}.", ephemeral=True)

    @event_group.command(name="swap_players", description="Swap two players between their current slots")
    @option("event_id", description="Event ID")
    @option("user_a", description="First user")
    @option("user_b", description="Second user")
    async def swap_players(self, ctx: discord.ApplicationContext, event_id: int, user_a: discord.Member, user_b: discord.Member):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return
        if not await self._assert_event_manager(ctx):
            return
        if user_a.id == user_b.id:
            return await ctx.followup.send("❌ Choose two different users.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status FROM events WHERE id = $1", event_id)
        if not event or event["status"] == "closed":
            return await ctx.followup.send("❌ Event not found or already closed.", ephemeral=True)

        p1 = await self.bot.db.get_player_by_discord_id(user_a.id)
        p2 = await self.bot.db.get_player_by_discord_id(user_b.id)
        if not p1 or not p2:
            return await ctx.followup.send("❌ Both users must have player profiles.", ephemeral=True)

        s1 = await self.bot.db.fetchrow("SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2", event_id, p1["id"])
        s2 = await self.bot.db.fetchrow("SELECT slot_number FROM event_signups WHERE event_id = $1 AND player_id = $2", event_id, p2["id"])
        if not s1 or not s2:
            return await ctx.followup.send("❌ Both users must already be in this event.", ephemeral=True)

        await self.bot.db.execute("UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id IN ($2, $3)", event_id, p1["id"], p2["id"])
        await self.bot.db.execute("UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3", p1["id"], event_id, s2["slot_number"])
        await self.bot.db.execute("UPDATE event_signups SET player_id = $1 WHERE event_id = $2 AND slot_number = $3", p2["id"], event_id, s1["slot_number"])
        await refresh_event_message(self.bot, event_id)
        await ctx.followup.send(
            f"✅ Swapped {user_a.mention} (slot #{s1['slot_number']}) and {user_b.mention} (slot #{s2['slot_number']}).",
            ephemeral=True,
        )

    @event_group.command(name="add_extra", description="Add an extra slot and place a user there")
    @option("event_id", description="Event ID")
    @option("user", description="User to add")
    @option("role_name", description="Role name for the extra slot")
    async def add_extra(self, ctx: discord.ApplicationContext, event_id: int, user: discord.Member, role_name: str):
        try:
            await ctx.defer(ephemeral=True)
        except discord.NotFound:
            return
        if not await self._assert_event_manager(ctx):
            return

        role_name = role_name.strip()
        if not role_name:
            return await ctx.followup.send("❌ Role name is required.", ephemeral=True)

        event = await self.bot.db.fetchrow("SELECT id, status, guild_id FROM events WHERE id = $1", event_id)
        if not event or event["status"] == "closed":
            return await ctx.followup.send("❌ Event not found or already closed.", ephemeral=True)

        player = await get_or_create_player_profile(self.bot, user, event=event, guild=ctx.guild)
        if not player:
            return await ctx.followup.send("❌ Failed to create/get player profile.", ephemeral=True)

        next_slot_row = await self.bot.db.fetchrow(
            "SELECT COALESCE(MAX(slot_number), 0) + 1 AS next_slot FROM event_signups WHERE event_id = $1",
            event_id,
        )
        next_slot = int(next_slot_row["next_slot"]) if next_slot_row and next_slot_row.get("next_slot") else 1

        await self.bot.db.execute("UPDATE event_signups SET player_id = NULL WHERE event_id = $1 AND player_id = $2", event_id, player["id"])
        await self.bot.db.execute(
            "INSERT INTO event_signups (event_id, slot_number, role_name, player_id) VALUES ($1, $2, $3, $4)",
            event_id,
            next_slot,
            role_name[:50],
            player["id"],
        )
        await refresh_event_message(self.bot, event_id)
        await ctx.followup.send(f"✅ Added extra slot #{next_slot} ({role_name}) for {user.mention}.", ephemeral=True)


def setup(bot):
    bot.add_cog(EventCommands(bot))
