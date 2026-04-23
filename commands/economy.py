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
)


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
    @option("category", description="Operation category", required=True)
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
    @option("item_id", description="Albion item id", required=True)
    @option("quantity", description="Quantity", required=True)
    @option("screenshot_url", description="Death screenshot URL", required=True)
    @option("note", description="Optional note", required=False, default="")
    async def economy_regear_ticket(
        self,
        ctx: discord.ApplicationContext,
        item_id: str,
        quantity: int,
        screenshot_url: str,
        note: str = "",
    ):
        if not self._guild_allowed(ctx, use_guild2=True):
            await ctx.respond("❌ Regear ticket can be created only on the ticket server (GUILD_ID2).", ephemeral=True)
            return
        if not await self.bot.permissions.require_member(ctx.author):
            await ctx.respond("❌ Member access required.", ephemeral=True)
            return
        if quantity <= 0:
            await ctx.respond("❌ Quantity must be greater than zero.", ephemeral=True)
            return
        if not str(screenshot_url).strip().startswith(("http://", "https://")):
            await ctx.respond("❌ Screenshot URL must start with http:// or https://", ephemeral=True)
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

        desc = f"item={item_id.strip()} qty={int(quantity)}"
        if note.strip():
            desc += f" | note={note.strip()}"
        ticket_id = await self.bot.db.execute(
            """
            INSERT INTO tickets (
                discord_channel_id, player_id, replay_link, session_date, role, description, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            channel.id,
            player["id"],
            screenshot_url.strip(),
            datetime.utcnow().date(),
            "Regear",
            desc,
            "available",
        )

        embed = discord.Embed(
            title="🛡️ Regear Ticket",
            description="Regear request created and queued for review.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Player", value=ctx.author.mention, inline=True)
        embed.add_field(name="Item", value=item_id.strip(), inline=True)
        embed.add_field(name="Qty", value=str(int(quantity)), inline=True)
        embed.add_field(name="Screenshot", value=screenshot_url.strip(), inline=False)
        if note.strip():
            embed.add_field(name="Note", value=note.strip(), inline=False)
        embed.set_footer(text=f"Ticket ID: {ticket_id}")

        msg = await channel.send(content=ctx.author.mention, embed=embed)
        await self.bot.db.execute("UPDATE tickets SET discord_message_id = $1 WHERE id = $2", msg.id, ticket_id)
        await ctx.followup.send(f"✅ Regear ticket created: {channel.mention}", ephemeral=True)


def setup(bot):
    bot.add_cog(EconomyCommands(bot))
