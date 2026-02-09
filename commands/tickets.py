import discord
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
    """Modal for creating a ticket (Replay + Role)"""
    
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
        # Validate Role
        normalized_role = RoleValidator.normalize_role(self.role.value)
        if not normalized_role:
            suggestions = RoleValidator.get_role_suggestions(self.role.value)
            suggestion_text = f"\nDid you mean: {', '.join(suggestions)}?" if suggestions else ""
            await interaction.response.send_message(
                f"❌ Unknown role '{self.role.value}'. Valid roles: {', '.join(PlayerRoles.all())}{suggestion_text}",
                ephemeral=True
            )
            return
        
        # Create Channel Logic
        category_id = self.bot.tickets_category_id or self.bot.config.get('tickets_category_id')
        category = discord.utils.get(interaction.guild.categories, id=category_id)
        
        if not category:
            await interaction.response.send_message("❌ Tickets category not found. Please contact admin.", ephemeral=True)
            return
        
        channel_name = f"ticket-{interaction.user.name}-{hashlib.md5(str(datetime.utcnow()).encode()).hexdigest()[:4]}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        
        # Add permissions for Mentors and Founders based on Role IDs
        mentor_role_id = self.bot.permissions.mentor_role_id
        founder_role_id = self.bot.permissions.founder_role_id
        
        mentor_role = interaction.guild.get_role(mentor_role_id)
        founder_role = interaction.guild.get_role(founder_role_id)
        
        if mentor_role:
            overwrites[mentor_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        if founder_role:
            overwrites[founder_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            
        try:
            channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create channel: {str(e)}", ephemeral=True)
            return
            
        # Save to DB
        ticket_id = await self.bot.db.execute("""
            INSERT INTO tickets (
                discord_channel_id, player_id, replay_link, session_date, 
                role, description, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, channel.id, self.player_id, self.replay_url.value.strip(), datetime.utcnow().date(),
           normalized_role, self.description.value.strip() if self.description.value else None,
           TicketStatus.AVAILABLE.value)
           
        # Initial Message
        embed = discord.Embed(
            title="🎫 New Session Ticket Created",
            description="Please wait for a mentor to review your session.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Replay Link", value=self.replay_url.value.strip(), inline=False)
        embed.add_field(name="Role", value=normalized_role, inline=True)
        embed.add_field(name="Status", value="⏳ Awaiting Mentor", inline=True)
        if self.description.value:
            embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.set_footer(text=f"Ticket ID: {ticket_id} | Created by {interaction.user.display_name}")
        
        view = TicketControlView(self.bot)
        message = await channel.send(f"{interaction.user.mention}", embed=embed, view=view)
        
        await self.bot.db.execute("UPDATE tickets SET discord_message_id = $1 WHERE id = $2", message.id, ticket_id)
        
        try:
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            print(f"⚠️ Failed to send modal success message: {e}")
            # fall back if already acknowledged
            try: await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
            except: pass


# --- Rating Flow (Selects + Modal) ---

class RatingSelectView(ui.View):
    """Step 1 of Rating: Select Content, Role, Score, Errors"""
    
    def __init__(self, bot, ticket_id: int, player_id: int, mentor_id: int, replay_link: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.ticket_id = ticket_id
        self.player_id = player_id
        self.mentor_id = mentor_id
        self.replay_link = replay_link
        self.selections = {
            "content": None,
            "role": None,
            "score": None,
            "errors": []
        }
        
        # Content Select
        content_options = [discord.SelectOption(label=c) for c in ContentTypes.all()]
        self.content_select = ui.Select(placeholder="Select Content Type", options=content_options, min_values=1, max_values=1, row=0)
        self.content_select.callback = self.content_callback
        self.add_item(self.content_select)
        
        # Role Select
        role_options = [discord.SelectOption(label=r) for r in PlayerRoles.all()]
        self.role_select = ui.Select(placeholder="Select Player Role", options=role_options, min_values=1, max_values=1, row=1)
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)
        
        # Score Select
        score_options = [discord.SelectOption(label=str(i), description=f"{i}/10") for i in range(1, 11)]
        self.score_select = ui.Select(placeholder="Select Score (1-10)", options=score_options, min_values=1, max_values=1, row=2)
        self.score_select.callback = self.score_callback
        self.add_item(self.score_select)
        
        # Error Select
        error_options = [discord.SelectOption(label=cat) for cat in ErrorCategorizer.get_all_categories()]
        self.error_select = ui.Select(placeholder="Select Error Categories (Optional)", options=error_options, min_values=0, max_values=len(error_options), row=3)
        self.error_select.callback = self.error_callback
        self.add_item(self.error_select)
    
    async def content_callback(self, interaction: discord.Interaction):
        self.selections["content"] = self.content_select.values[0]
        await interaction.response.defer()
        
    async def role_callback(self, interaction: discord.Interaction):
        self.selections["role"] = self.role_select.values[0]
        await interaction.response.defer()
        
    async def score_callback(self, interaction: discord.Interaction):
        self.selections["score"] = int(self.score_select.values[0])
        await interaction.response.defer()
        
    async def error_callback(self, interaction: discord.Interaction):
        self.selections["errors"] = self.error_select.values
        await interaction.response.defer()

    @ui.button(label="Next: Add Comments", style=discord.ButtonStyle.green, row=4)
    async def next_button(self, button: ui.Button, interaction: discord.Interaction):
        if not self.selections["content"] or not self.selections["role"] or not self.selections["score"]:
            await interaction.response.send_message("❌ Please select Content, Role, and Score first!", ephemeral=True)
            return
            
        modal = FeedbackModal(self.bot, self.ticket_id, self.player_id, self.mentor_id, self.replay_link, self.selections)
        await interaction.response.send_modal(modal)


class FeedbackModal(ui.Modal):
    """Step 2 of Rating: Work On + Comments"""
    
    def __init__(self, bot, ticket_id, player_id, mentor_id, replay_link, selections):
        super().__init__(title="Session Feedback")
        self.bot = bot
        self.ticket_id = ticket_id
        self.player_id = player_id
        self.mentor_id = mentor_id
        self.replay_link = replay_link
        self.selections = selections
        
        self.work_on = ui.InputText(label="What to Work On", style=discord.InputTextStyle.long, required=True, max_length=1000)
        self.comments = ui.InputText(label="Detailed Comments", style=discord.InputTextStyle.long, required=True, max_length=2000)
        self.add_item(self.work_on)
        self.add_item(self.comments)
        
    async def callback(self, interaction: discord.Interaction):
        # Save Session Logic
        content_name = self.selections['content']
        role_name = self.selections['role']
        score = self.selections['score']
        errors = self.selections['errors']
        
        content = await self.bot.db.fetchrow("SELECT id FROM content WHERE name = $1", content_name)
        if not content:
            await interaction.response.send_message("❌ Content type error in DB.", ephemeral=True)
            return

        try:
            await self.bot.db.execute("""
                INSERT INTO sessions (
                    ticket_id, player_id, content_id, score, role, 
                    error_types, work_on, comments, mentor_id, session_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, self.ticket_id, self.player_id, content['id'], score, role_name,
               ','.join(errors) if errors else None, self.work_on.value, self.comments.value,
               self.mentor_id, datetime.utcnow())
               
            await self.bot.db.execute("""
                UPDATE tickets SET status = $1, mentor_id = $2, closed_at = $3 WHERE id = $4
            """, TicketStatus.CLOSED.value, self.mentor_id, datetime.utcnow(), self.ticket_id)
            
            # Send DM to Player
            player_data = await self.bot.db.get_player_by_id(self.player_id)
            if player_data:
                player_user = self.bot.get_user(player_data['discord_id']) or await self.bot.fetch_user(player_data['discord_id'])
                if player_user:
                    embed = discord.Embed(title="✅ Session Evaluated", color=discord.Color.green())
                    embed.add_field(name="Content", value=content_name)
                    embed.add_field(name="Role", value=role_name)
                    embed.add_field(name="Score", value=f"{score}/10")
                    if errors: embed.add_field(name="Errors", value=", ".join(errors), inline=False)
                    embed.add_field(name="Work On", value=self.work_on.value, inline=False)
                    embed.add_field(name="Comments", value=self.comments.value, inline=False)
                    embed.add_field(name="Replay", value=f"[Link]({self.replay_link})")
                    try: await player_user.send(embed=embed)
                    except: pass
            
            await interaction.response.send_message("✅ Evaluation submitted! Channel closing in 10s...", ephemeral=True)
            await asyncio.sleep(10)
            if interaction.channel: await interaction.channel.delete()
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error saving: {e}", ephemeral=True)


class TicketControlView(ui.View):
    """Control buttons in ticket channel (Stateless for persistence)"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
    
    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="claim_ticket")
    async def claim_ticket(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Use new permissions check
        if not await self.bot.permissions.require_mentor(interaction.user):
            await interaction.followup.send("❌ Only mentors can claim tickets.", ephemeral=True)
            return
            
        ticket = await self.bot.db.fetchrow("SELECT id, status, mentor_id, discord_message_id FROM tickets WHERE discord_channel_id = $1", interaction.channel.id)
        if not ticket:
            await interaction.followup.send("❌ Ticket not found for this channel.", ephemeral=True)
            return
            
        mentor = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        if not mentor:
            await interaction.followup.send("❌ You are not registered in the system.", ephemeral=True)
            return

        if ticket['status'] != TicketStatus.AVAILABLE.value:
            if ticket['mentor_id'] == mentor['id']:
                await interaction.followup.send("✅ You already claimed this.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Already claimed by someone else.", ephemeral=True)
            return
            
        await self.bot.db.execute("""
            UPDATE tickets SET status = $1, mentor_id = $2, updated_at = $3 WHERE id = $4
        """, TicketStatus.IN_PROGRESS.value, mentor['id'], datetime.utcnow(), ticket['id'])
        
        # Update Embed
        embed = discord.Embed(
            title="🎫 Session Ticket",
            description=f"Mentor {interaction.user.mention} is reviewing your session.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        t_data = await self.bot.db.fetchrow("""
            SELECT t.replay_link, t.role, t.description, p.nickname 
            FROM tickets t JOIN players p ON p.id = t.player_id WHERE t.id = $1
        """, ticket['id'])
        
        embed.add_field(name="Player", value=t_data['nickname'], inline=True)
        embed.add_field(name="Role", value=t_data['role'], inline=True)
        embed.add_field(name="Status", value="🔍 In Progress", inline=True)
        embed.add_field(name="Replay", value=f"[View Replay]({t_data['replay_link']})", inline=False)
        if t_data['description']:
            embed.add_field(name="Description", value=t_data['description'], inline=False)
        embed.set_footer(text=f"Ticket ID: {ticket['id']} | Claimed by {interaction.user.display_name}")
        
        try:
            # Отключаем кнопку Claim после успешного взятия
            button.disabled = True
            button.label = "Claimed"
            button.style = discord.ButtonStyle.secondary
            
            msg = await interaction.channel.fetch_message(ticket['discord_message_id'])
            await msg.edit(embed=embed, view=self)
        except Exception as e:
            print(f"⚠️ Failed to update ticket message: {e}")
        
        await interaction.followup.send(f"✅ Claimed by {interaction.user.mention}! Use `/ticket rate` to evaluate.", ephemeral=False)
    
    @ui.button(label="Rate Session", style=discord.ButtonStyle.green, emoji="⭐", custom_id="rate_session")
    async def rate_session(self, button: ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ticket = await self.bot.db.fetchrow("""
            SELECT t.id, t.status, t.mentor_id, t.player_id, t.replay_link, p.discord_id as p_did
            FROM tickets t JOIN players p ON p.id = t.player_id
            WHERE t.discord_channel_id = $1
        """, interaction.channel.id)
        
        if not ticket:
            await interaction.followup.send("❌ Ticket not found.", ephemeral=True)
            return
        
        is_mentor = await self.bot.permissions.require_mentor(interaction.user)
        
        # Находим внутреннего игрока для сравнения ID
        mentor = await self.bot.db.get_player_by_discord_id(interaction.user.id)
        is_owner = mentor and ticket['mentor_id'] == mentor['id']
        
        if not is_mentor or not is_owner:
            await interaction.followup.send("❌ Only the claimer can rate.", ephemeral=True)
            return
        
        if ticket['status'] != TicketStatus.IN_PROGRESS.value:
            await interaction.followup.send("❌ Ticket must be 'In Progress'.", ephemeral=True)
            return
        
        if not mentor:
            await interaction.followup.send("❌ You are not registered.", ephemeral=True)
            return
            
        view = RatingSelectView(self.bot, ticket['id'], ticket['player_id'], mentor['id'], ticket['replay_link'])
        await interaction.followup.send("📊 **Session Evaluation**\nPlease select details:", view=view, ephemeral=True)


class TicketsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✓ TicketsCommands initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent view"""
        self.bot.add_view(TicketControlView(self.bot))

    ticket_group = discord.SlashCommandGroup("ticket", "Manage tickets")

    @ticket_group.command(name="create", description="Create a new ticket")
    async def ticket_create(self, ctx: discord.ApplicationContext):
        if not await self.bot.permissions.require_member(ctx.author):
            await ctx.respond("❌ You must be a Member to create tickets.", ephemeral=True)
            return
        
        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        if not player:
            await ctx.respond("❌ Please use `/register <code>` first.", ephemeral=True)
            return
            
        modal = TicketModal(self.bot, player['id'], player['guild_id'])
        await ctx.send_modal(modal)

    @ticket_group.command(name="list", description="List active tickets")
    async def ticket_list(self, ctx: discord.ApplicationContext):
        if not await self.bot.permissions.require_member(ctx.author):
            await ctx.respond("❌ Access denied.", ephemeral=True)
            return
            
        guild_id = await self.bot.permissions.get_guild_id(ctx.author)
        is_mentor = await self.bot.permissions.require_mentor(ctx.author)
        
        if is_mentor:
            tickets = await self.bot.db.fetch("""
            SELECT t.id, t.status, t.created_at, p.discord_id, t.role 
            FROM tickets t JOIN players p ON p.id = t.player_id
            WHERE p.guild_id = $1 AND t.status IN ('available', 'in_progress')
            AND (t.status = 'available' OR t.mentor_id = $2)
            ORDER BY t.created_at ASC
            """, guild_id, ctx.author.id)
        else:
            tickets = await self.bot.db.fetch("""
            SELECT t.id, t.status, t.created_at, p.discord_id, t.role 
            FROM tickets t JOIN players p ON p.id = t.player_id
            WHERE p.discord_id = $1 AND t.status != 'closed'
            ORDER BY t.created_at DESC
            """, ctx.author.id)
            
        if not tickets:
            await ctx.respond("📭 No active tickets found.", ephemeral=True)
            return
            
        embed = discord.Embed(title="🎫 Active Tickets", color=discord.Color.blue())
        for t in tickets[:10]:
            emoji = "⏳" if t['status'] == 'available' else "BETA"
            if t['status'] == 'in_progress': emoji = "🔍"
            embed.add_field(
                name=f"{emoji} #{t['id']} | {t['role']}",
                value=f"By <@{(t['discord_id'])}>\nStatus: {t['status']}",
                inline=False
            )
        await ctx.respond(embed=embed, ephemeral=True)

    @ticket_group.command(name="claim", description="Claim a ticket (Mentors only)")
    @option("ticket_id", description="ID of the ticket to claim")
    async def ticket_claim(self, ctx: discord.ApplicationContext, ticket_id: int):
        if not await self.bot.permissions.require_mentor(ctx.author):
            await ctx.respond("❌ Mentors only.", ephemeral=True)
            return
            
        ticket = await self.bot.db.fetchrow("SELECT discord_channel_id FROM tickets WHERE id = $1 AND status = 'available'", ticket_id)
        if not ticket:
            await ctx.respond("❌ Ticket not found or not available.", ephemeral=True)
            return
            
        await self.bot.db.execute("""
        UPDATE tickets SET status = 'in_progress', mentor_id = $1, updated_at = $2 
        WHERE id = $3
        """, ctx.author.id, datetime.utcnow(), ticket_id)
        
        await ctx.respond(f"✅ Claimed! Go to <#{ticket['discord_channel_id']}>", ephemeral=True)

    @ticket_group.command(name="rate", description="Rate a ticket (Mentors only)")
    async def ticket_rate(self, ctx: discord.ApplicationContext):
        if not await self.bot.permissions.require_mentor(ctx.author):
            await ctx.respond("❌ Only mentors can rate.", ephemeral=True)
            return
            
        ticket = await self.bot.db.fetchrow("""
            SELECT t.*, p.discord_id as p_did FROM tickets t 
            JOIN players p ON p.id = t.player_id 
            WHERE t.discord_channel_id = $1
        """, ctx.channel.id)
        
        if not ticket:
            await ctx.respond("❌ Not a ticket channel.", ephemeral=True)
            return
            
        if ticket['mentor_id'] != ctx.author.id:
            await ctx.respond("❌ You must claim this ticket first.", ephemeral=True)
            return
            
        view = RatingSelectView(self.bot, ticket['id'], ticket['p_did'], ctx.author.id, ticket['replay_link'])
        await ctx.respond("📊 **Session Evaluation**\nPlease select details:", view=view, ephemeral=True)
    
    @ticket_group.command(name="info", description="View ticket details (Mentors only)")
    @option("ticket_id", description="Ticket ID to view")
    async def ticket_info(self, ctx: discord.ApplicationContext, ticket_id: int):
        """Просмотр детальной информации о тикете (для менторов/фаундеров)"""
        # Проверка прав ментора
        if not await self.bot.permissions.require_mentor(ctx.author):
            await ctx.respond("❌ Only mentors and founders can view ticket details.", ephemeral=True)
            return
        
        # Получение данных тикета
        ticket = await self.bot.db.fetchrow("""
            SELECT 
                t.*,
                p1.nickname as player_nickname,
                p1.discord_id as player_discord_id,
                p2.nickname as mentor_nickname,
                p2.discord_id as mentor_discord_id,
                g.name as guild_name
            FROM tickets t
            JOIN players p1 ON p1.id = t.player_id
            LEFT JOIN players p2 ON p2.id = t.mentor_id
            JOIN guilds g ON g.id = p1.guild_id
            WHERE t.id = $1
        """, ticket_id)
        
        if not ticket:
            await ctx.respond(f"❌ Ticket #{ticket_id} not found.", ephemeral=True)
            return
        
        # Embed с детальной информацией
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} Details",
            color=discord.Color.blue(),
            timestamp=ticket['created_at']
        )
        embed.add_field(name="Status", value=ticket['status'].title(), inline=True)
        embed.add_field(name="Guild", value=ticket['guild_name'], inline=True)
        embed.add_field(name="Player", value=f"<@{ticket['player_discord_id']}> ({ticket['player_nickname']})", inline=False)
        embed.add_field(name="Role in Session", value=ticket['role'], inline=True)
        embed.add_field(name="Session Date", value=ticket['session_date'].strftime('%Y-%m-%d'), inline=True)
        if ticket['mentor_discord_id']:
            embed.add_field(name="Mentor", value=f"<@{ticket['mentor_discord_id']}> ({ticket['mentor_nickname'] or 'N/A'})", inline=False)
        embed.add_field(name="Replay", value=f"[View Replay]({ticket['replay_link']})", inline=False)
        if ticket['description']:
            embed.add_field(name="Description", value=ticket['description'], inline=False)
        if ticket['closed_at']:
            embed.add_field(name="Closed At", value=ticket['closed_at'].strftime('%Y-%m-%d %H:%M UTC'), inline=True)
        embed.set_footer(text=f"Channel ID: {ticket['discord_channel_id'] or 'N/A'}")
        
        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(TicketsCommands(bot))