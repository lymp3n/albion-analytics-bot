from __future__ import annotations

import asyncio
from datetime import datetime

import discord
from discord import option
from discord.ext import commands

from web_dashboard.economy_db_sync import get_economy_sync_connection
from web_dashboard.economy_service import (
    create_routed_operation,
    economy_kpis,
    ensure_economy_schema,
    list_routing_rules,
)


async def get_route_category_choices(ctx: discord.AutocompleteContext):
    raw_value = str(ctx.value or "").strip().casefold()
    try:
        with get_economy_sync_connection() as (conn, backend):
            ensure_economy_schema(conn, backend)
            rows = list_routing_rules(conn, backend)
        out = []
        for r in rows:
            cat = str(r.get("category") or "").strip()
            if not cat:
                continue
            if raw_value and raw_value not in cat.casefold():
                continue
            out.append(discord.OptionChoice(name=cat[:100], value=cat))
            if len(out) >= 25:
                break
        return out
    except Exception:
        return []


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

    economy_group = discord.SlashCommandGroup("economy", "Economy operations")

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

        entry = out.get("entry") or {}
        await ctx.followup.send(
            f"✅ Posted operation #{entry.get('id', '?')} | "
            f"category=`{entry.get('category', category)}` amount=`{int(entry.get('amount') or amount):,}`",
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

        msg = await channel.send(content=ctx.author.mention, embed=embed)
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
        is_economy = await self.bot.permissions.require_economy(ctx.author)
        is_mentor = await self.bot.permissions.require_mentor(ctx.author)
        is_founder = await self.bot.permissions.require_founder(ctx.author)
        if not (is_economy or is_mentor or is_founder):
            await ctx.respond("❌ Staff/economy access required to close ticket.", ephemeral=True)
            return
        row = await self.bot.db.fetchrow(
            "SELECT id, status FROM tickets WHERE discord_channel_id = $1",
            ctx.channel.id,
        )
        if not row:
            await ctx.respond("❌ This channel is not linked to a ticket.", ephemeral=True)
            return
        await self.bot.db.execute(
            "UPDATE tickets SET status = $1, closed_at = $2 WHERE id = $3",
            "closed",
            datetime.utcnow(),
            int(row["id"]),
        )
        await ctx.respond("✅ Ticket marked as closed. Channel will be deleted in 5 seconds.", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=f"Regear ticket #{int(row['id'])} closed")
        except Exception:
            pass


def setup(bot):
    bot.add_cog(EconomyCommands(bot))
