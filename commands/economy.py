from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import discord
from discord import option
from discord.ext import commands

from web_dashboard.economy_db_sync import get_economy_sync_connection
from web_dashboard.economy_service import (
    create_manual_loot_buyback_from_price,
    create_routed_operation,
    economy_kpis,
    ensure_economy_schema,
    issue_regear_request,
    list_routing_rules,
)


ROUTE_CATEGORY_FALLBACK = [
    "deposit",
    "withdrawal",
    "content_income",
    "buy_gear",
    "reward_payout",
    "loot_buyback",
    "regear_issue",
]


async def get_route_category_choices(ctx: discord.AutocompleteContext):
    raw_value = str(ctx.value or "").strip().casefold()
    bot = getattr(ctx, "bot", None)
    cached = getattr(bot, "_econ_route_categories_cache", None)
    categories = list(cached) if isinstance(cached, list) and cached else list(ROUTE_CATEGORY_FALLBACK)
    out: list[str] = []
    for cat in categories:
        if raw_value and raw_value not in cat.casefold():
            continue
        out.append(cat[:100])
        if len(out) >= 25:
            break
    return out


class RegearTicketView(discord.ui.View):
    def __init__(self, cog: "EconomyCommands"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🗂️",
        custom_id="economy_close_regear_ticket",
    )
    async def close_ticket_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message("❌ This button can be used only in ticket channel.", ephemeral=True)
            return
        allowed, msg, ticket_id = await self.cog._can_close_ticket(interaction)
        if not allowed:
            await interaction.response.send_message(msg, ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Ticket #{ticket_id} marked as closed. Channel will be deleted in 5 seconds.",
            ephemeral=True,
        )
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Regear ticket #{ticket_id} closed via button")
        except Exception:
            pass


class EconomyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _guild_allowed(self, ctx: discord.ApplicationContext, *, use_guild2: bool = False) -> bool:
        if not ctx.guild:
            return False
        target = int(self.bot.guild_id2 if use_guild2 else self.bot.guild_id)
        if target <= 0:
            return True
        return int(ctx.guild.id) == target

    async def _refresh_route_category_cache(self) -> None:
        def _load_categories() -> list[str]:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                rows = list_routing_rules(conn, backend)
            db_categories = [str(r.get("category") or "").strip() for r in rows if str(r.get("category") or "").strip()]
            return list(dict.fromkeys(db_categories + ROUTE_CATEGORY_FALLBACK))

        try:
            cats = await asyncio.to_thread(_load_categories)
        except Exception:
            cats = list(ROUTE_CATEGORY_FALLBACK)
        self.bot._econ_route_categories_cache = cats

    def _is_image_attachment(self, att: discord.Attachment) -> bool:
        ctype = str(getattr(att, "content_type", "") or "").lower()
        if ctype.startswith("image/"):
            return True
        return Path(str(att.filename or "")).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    async def _refresh_ticket_message(self, guild: discord.Guild, ticket_row: dict, status_text: str) -> None:
        mid = int(ticket_row.get("discord_message_id") or 0)
        if mid <= 0:
            return
        channel = guild.get_channel(int(ticket_row["discord_channel_id"]))
        if not channel:
            return
        try:
            msg = await channel.fetch_message(mid)
        except Exception:
            return
        emb = msg.embeds[0] if msg.embeds else discord.Embed(
            title="🛡️ Regear Ticket",
            description="Regear ticket channel.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )
        replaced = False
        close_hint_updated = False
        for i, f in enumerate(emb.fields):
            nm = str(f.name).strip().lower()
            if nm == "status":
                emb.set_field_at(i, name="Status", value=status_text, inline=True)
                replaced = True
            if nm == "how to close":
                emb.set_field_at(i, name="How to close", value="Use button below or `/economy close-ticket`.", inline=False)
                close_hint_updated = True
        if not replaced:
            emb.add_field(name="Status", value=status_text, inline=True)
        if not close_hint_updated:
            emb.add_field(name="How to close", value="Use button below or `/economy close-ticket`.", inline=False)
        try:
            await msg.edit(embed=emb, view=RegearTicketView(self))
        except Exception:
            pass

    async def _can_close_ticket(self, interaction: discord.Interaction) -> tuple[bool, str, int]:
        if not self._guild_allowed(interaction, use_guild2=True):
            return False, "❌ Regear tickets are managed only on the ticket server (GUILD_ID2).", 0
        row = await self.bot.db.fetchrow(
            """
            SELECT t.id, p.discord_id AS owner_discord_id
            FROM tickets t
            LEFT JOIN players p ON p.id = t.player_id
            WHERE t.discord_channel_id = $1
            """,
            interaction.channel.id,
        )
        if not row:
            return False, "❌ This channel is not linked to a ticket.", 0
        is_owner = int(row.get("owner_discord_id") or 0) == int(interaction.user.id)
        is_economy = await self.bot.permissions.require_economy(interaction.user)
        is_mentor = await self.bot.permissions.require_mentor(interaction.user)
        is_founder = await self.bot.permissions.require_founder(interaction.user)
        if not (is_owner or is_economy or is_mentor or is_founder):
            return False, "❌ Only ticket owner or staff can close this ticket.", int(row["id"])
        await self.bot.db.execute(
            "UPDATE tickets SET status = $1, closed_at = $2, updated_at = $2 WHERE id = $3",
            "closed",
            datetime.utcnow(),
            int(row["id"]),
        )
        return True, "", int(row["id"])

    economy_group = discord.SlashCommandGroup("economy", "Economy operations")

    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self.bot, "_economy_regear_view_registered", False):
            return
        self.bot._economy_regear_view_registered = True
        self.bot.add_view(RegearTicketView(self))
        await self._refresh_route_category_cache()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if not self._guild_allowed(message, use_guild2=True):
            return
        if not message.attachments:
            return
        if not any(self._is_image_attachment(a) for a in message.attachments):
            return
        row = await self.bot.db.fetchrow(
            """
            SELECT id, status, role, discord_channel_id, discord_message_id
            FROM tickets
            WHERE discord_channel_id = $1
            """,
            message.channel.id,
        )
        if not row:
            return
        if str(row.get("role") or "").strip().lower() != "regear":
            return
        status = str(row.get("status") or "").strip().lower()
        if status == "closed":
            return
        if status == "available":
            await self.bot.db.execute(
                "UPDATE tickets SET status = $1, updated_at = $2 WHERE id = $3",
                "in_progress",
                datetime.utcnow(),
                int(row["id"]),
            )
        await self._refresh_ticket_message(message.guild, row, "Screenshot received ✅ (in progress)")
        try:
            await message.add_reaction("✅")
        except Exception:
            pass

    @economy_group.command(name="kpi", description="Show current economy KPIs")
    async def economy_kpi(self, ctx: discord.ApplicationContext):
        if not self._guild_allowed(ctx, use_guild2=False):
            await ctx.respond("❌ This command is available only on the main command server (GUILD_ID).", ephemeral=True)
            return
        if not await self.bot.permissions.require_economy(ctx.author):
            await ctx.respond("❌ Economy access required.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        def _read_kpi():
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                return economy_kpis(conn, backend)

        try:
            k = await asyncio.to_thread(_read_kpi)
        except Exception as e:
            await ctx.followup.send(f"❌ KPI read failed: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title="📊 Economy KPI",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Cash", value=f"{int(k.get('cash_balance') or 0):,}", inline=True)
        embed.add_field(name="Energy", value=f"{int(k.get('energy_balance') or 0):,}", inline=True)
        embed.add_field(name="Pending approvals", value=str(int(k.get("pending_entries") or 0)), inline=True)
        embed.add_field(name="Unresolved discrepancies", value=str(int(k.get("unresolved_discrepancies") or 0)), inline=True)
        embed.add_field(name="Open alerts", value=str(int(k.get("open_alerts") or 0)), inline=True)
        embed.add_field(name="Entries total", value=str(int(k.get("entries_count") or 0)), inline=True)
        await ctx.followup.send(embed=embed, ephemeral=True)

    @economy_group.command(name="route-op", description="Create routed economy operation")
    @option("category", description="Operation category", required=True, autocomplete=get_route_category_choices)
    @option("amount", description="Amount (>0)", required=True)
    @option("description", description="Operation description", required=True)
    async def economy_route_op(
        self,
        ctx: discord.ApplicationContext,
        category: str,
        amount: int,
        description: str,
    ):
        if not self._guild_allowed(ctx, use_guild2=False):
            await ctx.respond("❌ This command is available only on the main command server (GUILD_ID).", ephemeral=True)
            return
        if not await self.bot.permissions.require_economy(ctx.author):
            await ctx.respond("❌ Economy access required.", ephemeral=True)
            return
        if amount <= 0:
            await ctx.respond("❌ Amount must be greater than zero.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        def _create():
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                return create_routed_operation(
                    conn,
                    backend,
                    category=category.strip(),
                    amount=int(amount),
                    description=description.strip(),
                    actor=str(ctx.author.display_name),
                    source="discord_command",
                )

        try:
            out = await asyncio.to_thread(_create)
        except Exception as e:
            await ctx.followup.send(f"❌ Operation failed: {e}", ephemeral=True)
            return
        await self._refresh_route_category_cache()

        entry = out.get("entry") or {}
        await ctx.followup.send(
            f"✅ Posted operation #{entry.get('id', '?')} | "
            f"category=`{entry.get('category', category)}` amount=`{int(entry.get('amount') or amount):,}`",
            ephemeral=True,
        )

    @economy_group.command(name="loot-buyback", description="Create loot buyback request")
    @option("buyback_price", description="Buyback payout price", required=True)
    async def economy_loot_buyback(
        self,
        ctx: discord.ApplicationContext,
        buyback_price: int,
    ):
        if not self._guild_allowed(ctx, use_guild2=False):
            await ctx.respond("❌ This command is available only on the main command server (GUILD_ID).", ephemeral=True)
            return
        if not await self.bot.permissions.require_economy(ctx.author):
            await ctx.respond("❌ Economy access required.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = create_manual_loot_buyback_from_price(
                    conn,
                    backend,
                    buyback_price=int(buyback_price),
                    actor=str(ctx.author.display_name),
                )
        except Exception as e:
            await ctx.followup.send(f"❌ Loot buyback failed: {e}", ephemeral=True)
            return
        await ctx.followup.send(
            f"✅ Buyback #{out.get('request_id')} created | payout=`{int(out.get('payout_total') or 0):,}` | "
            f"market(+20%)=`{int(out.get('market_total_plus_20_pct') or 0):,}`",
            ephemeral=True,
        )

    @economy_group.command(name="regear-issue", description="Issue pending regear request")
    @option("request_id", description="Regear request ID", required=True)
    @option("note", description="Optional note", required=False, default="")
    async def economy_regear_issue(self, ctx: discord.ApplicationContext, request_id: int, note: str = ""):
        if not self._guild_allowed(ctx, use_guild2=False):
            await ctx.respond("❌ This command is available only on the main command server (GUILD_ID).", ephemeral=True)
            return
        if not await self.bot.permissions.require_economy(ctx.author):
            await ctx.respond("❌ Economy access required.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        try:
            with get_economy_sync_connection() as (conn, backend):
                ensure_economy_schema(conn, backend)
                out = issue_regear_request(
                    conn,
                    backend,
                    request_id=int(request_id),
                    checked_by=str(ctx.author.display_name),
                    issued_by=str(ctx.author.display_name),
                    note=note,
                )
        except Exception as e:
            await ctx.followup.send(f"❌ Regear issue failed: {e}", ephemeral=True)
            return
        await ctx.followup.send(
            f"✅ Regear request #{out.get('request_id')} issued | entry #{out.get('entry_id')} | total `{int(out.get('total_cost') or 0):,}`",
            ephemeral=True,
        )

    @economy_group.command(name="regear-ticket", description="Open regear ticket channel")
    async def economy_regear_ticket(
        self,
        ctx: discord.ApplicationContext,
    ):
        if not self._guild_allowed(ctx, use_guild2=True):
            await ctx.respond("❌ Regear ticket can be created only on the ticket server (GUILD_ID2).", ephemeral=True)
            return
        if not await self.bot.permissions.require_member(ctx.author):
            await ctx.respond("❌ Member access required.", ephemeral=True)
            return
        guild_id = ctx.guild.id if ctx.guild else 0
        category_id = (
            self.bot.regear_ticket_categories.get(guild_id)
            or self.bot.regear_tickets_category_id
            or self.bot.tickets_category_id
        )
        category = discord.utils.get(ctx.guild.categories, id=category_id) if category_id else None
        if not category:
            await ctx.respond("❌ Regear ticket category not configured for this server.", ephemeral=True)
            return

        player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
        if not player:
            await ctx.respond("❌ Please register first with `/register`.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        _, mentor_ids, founder_ids = await self.bot.permissions.effective_role_sets(ctx.author)
        economy_ids = await self.bot.permissions.economy_role_ids_for_guild(ctx.author)
        for rid in set(mentor_ids) | set(founder_ids) | set(economy_ids):
            role = ctx.guild.get_role(int(rid))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"regear-{ctx.author.name.lower()}-{datetime.utcnow().strftime('%H%M')}"
        try:
            channel = await ctx.guild.create_text_channel(
                name=channel_name[:90],
                category=category,
                overwrites=overwrites,
            )
        except Exception as e:
            await ctx.followup.send(f"❌ Failed to create regear channel: {e}", ephemeral=True)
            return

        desc = "regear_request_opened_from_discord"
        ticket_id = await self.bot.db.execute(
            """
            INSERT INTO tickets (
                discord_channel_id, player_id, replay_link, session_date, role, description, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            channel.id,
            player["id"],
            "regear_pending_screenshot",
            datetime.utcnow().date(),
            "Regear",
            desc,
            "available",
        )

        embed = discord.Embed(
            title="🛡️ Regear Ticket",
            description="Regear ticket created. Please send your death screenshot in this channel.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Player", value=ctx.author.mention, inline=True)
        embed.add_field(name="Status", value="Awaiting screenshot", inline=True)
        embed.add_field(name="How to close", value="Use `/economy close-ticket` in this channel.", inline=False)
        embed.set_footer(text=f"Ticket ID: {ticket_id}")

        msg = await channel.send(content=ctx.author.mention, embed=embed, view=RegearTicketView(self))
        await self.bot.db.execute("UPDATE tickets SET discord_message_id = $1 WHERE id = $2", msg.id, ticket_id)
        await ctx.followup.send(f"✅ Regear ticket created: {channel.mention}", ephemeral=True)

    @economy_group.command(name="close-ticket", description="Close current regear ticket channel")
    async def economy_close_ticket(self, ctx: discord.ApplicationContext):
        if not self._guild_allowed(ctx, use_guild2=True):
            await ctx.respond("❌ Regear tickets are managed only on the ticket server (GUILD_ID2).", ephemeral=True)
            return
        if not ctx.guild or not ctx.channel:
            await ctx.respond("❌ This command can only be used inside ticket channel.", ephemeral=True)
            return
        allowed, msg, ticket_id = await self._can_close_ticket(ctx)
        if not allowed:
            await ctx.respond(msg, ephemeral=True)
            return
        await ctx.respond(f"✅ Ticket #{ticket_id} marked as closed. Channel will be deleted in 5 seconds.", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=f"Regear ticket #{ticket_id} closed")
        except Exception:
            pass


def setup(bot):
    bot.add_cog(EconomyCommands(bot))
