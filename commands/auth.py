import hashlib
import discord
from discord import option
from discord.ext import commands
from models import PlayerStatus


class AuthCommands(commands.Cog):
    """Registration and Guild Management Commands"""

    players_group = discord.SlashCommandGroup("players", "Registered guild roster")

    def __init__(self, bot):
        self.bot = bot
        print("✓ AuthCommands initialized")

    @staticmethod
    async def _sync_registration_roles(guild: discord.Guild, member: discord.Member, status: str) -> None:
        """Assign Founder/Mentor Discord roles after DB registration (best-effort)."""
        role_name = None
        if status == PlayerStatus.FOUNDER.value:
            role_name = "Founder"
        elif status == PlayerStatus.MENTOR.value:
            role_name = "Mentor"
        if not role_name:
            return
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role not in member.roles:
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_ready(self):
        """Automatically update Guild Discord ID on startup"""
        import asyncio

        for _ in range(10):
            if self.bot.db.is_sqlite or (self.bot.db.pool is not None):
                break
            await asyncio.sleep(1)

        if not self.bot.db.is_sqlite and self.bot.db.pool is None:
            print("⚠️ AuthCommands: Database not connected after wait, skipping on_ready sync")
            return

        pending = await self.bot.db.fetch("SELECT id, name FROM guilds WHERE discord_id = 0")
        for db_guild in pending:
            name = (db_guild.get("name") or "").strip()
            if not name:
                continue
            name_cf = name.casefold()
            match = None
            for dg in self.bot.guilds:
                if dg.name.strip().casefold() == name_cf:
                    match = dg
                    break
            if match:
                await self.bot.db.update_guild_discord_id_by_id(int(db_guild["id"]), match.id)
                print(f"✓ Linked DB guild '{name}' (id={db_guild['id']}) -> Discord {match.id} ({match.name})")

    @players_group.command(name="list", description="List all players registered in the bot for your guild")
    async def players_list(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        if not await self.bot.permissions.require_mentor(ctx.author):
            await ctx.followup.send(
                "❌ Only **Founders** and **Mentors** can view the full roster.", ephemeral=True
            )
            return
        guild_db_id = await self.bot.permissions.get_guild_id(ctx.author)
        if not guild_db_id:
            await ctx.followup.send(
                "❌ You are not linked to a guild in the bot database. Use `/register` first.", ephemeral=True
            )
            return
        rows = await self.bot.db.list_players_by_guild(guild_db_id, limit=500)
        if not rows:
            await ctx.followup.send("No registered players for your guild yet.", ephemeral=True)
            return

        g_row = await self.bot.db.fetchrow("SELECT name FROM guilds WHERE id = $1", guild_db_id)
        gname = str((g_row or {}).get("name") or "Guild")

        max_lines = 60
        lines = []
        for r in rows[:max_lines]:
            nick = str(r.get("nickname") or "").strip() or "?"
            st = str(r.get("status") or "").strip()
            did = int(r.get("discord_id") or 0)
            lines.append(f"`{nick}` · **{st}** · <@{did}>")

        desc = "\n".join(lines)
        if len(rows) > max_lines:
            desc += f"\n\n… *and {len(rows) - max_lines} more (showing first {max_lines}).*"

        embed = discord.Embed(
            title=f"Registered players — {gname}",
            description=desc[:4090],
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(text=f"Total in bot DB for this guild: {len(rows)} (cap 500)")
        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="register", description="Register using a guild invite code")
    @option("code", description="Guild invitation code (member / mentor / founder)")
    @option(
        "member",
        description="Register this @member instead of yourself (Founder/Mentor only)",
        required=False,
    )
    async def register(self, ctx: discord.ApplicationContext, code: str, member: discord.Member = None):
        """Register self, or (staff) register another Discord member."""
        await ctx.defer(ephemeral=True)

        target = member or ctx.author
        registering_other = member is not None and member.id != ctx.author.id

        if registering_other:
            if not await self.bot.permissions.require_mentor(ctx.author):
                await ctx.followup.send(
                    "❌ Only **Founders** and **Mentors** can register another player. "
                    "Use `/register code` without @member for self-registration.",
                    ephemeral=True,
                )
                return

        code_hash = hashlib.sha256(code.encode()).hexdigest()
        guild = await self.bot.db.get_guild_by_code(code_hash)
        if not guild:
            await ctx.followup.send("❌ Invalid guild code. Please check and try again.", ephemeral=True)
            return

        if registering_other:
            staff_player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
            if not staff_player or int(staff_player.get("guild_id") or 0) != int(guild["id"]):
                await ctx.followup.send(
                    "❌ You must be registered in **this** guild (same as the code) to register someone else.",
                    ephemeral=True,
                )
                return

        if code_hash == guild["founder_code"]:
            if registering_other and not await self.bot.permissions.require_founder(ctx.author):
                await ctx.followup.send(
                    "❌ Only a **Founder** can register another user with the **founder** invite code.",
                    ephemeral=True,
                )
                return
            status = PlayerStatus.FOUNDER.value
        elif code_hash == guild["mentor_code"]:
            status = PlayerStatus.MENTOR.value
        else:
            status = PlayerStatus.PENDING.value

        if not registering_other:
            existing_player = await self.bot.db.get_player_by_discord_id(ctx.author.id)
            if existing_player:
                gname = str(existing_player.get("guild_name") or "your guild").strip() or "your guild"
                if existing_player["status"] == "pending":
                    await ctx.followup.send(
                        "⏳ Your registration is pending approval by guild founder.", ephemeral=True
                    )
                else:
                    await ctx.followup.send(
                        f"✅ You are already registered in guild **{gname}**", ephemeral=True
                    )
                return
        else:
            existing_target = await self.bot.db.get_player_by_discord_id(target.id)
            if existing_target:
                gname = str(existing_target.get("guild_name") or "a guild").strip() or "a guild"
                await ctx.followup.send(
                    f"❌ {target.mention} is already registered (**{gname}**, status `{existing_target['status']}`).",
                    ephemeral=True,
                )
                return

        try:
            await self.bot.db.execute(
                """
                INSERT INTO players (discord_id, discord_username, nickname, guild_id, status)
                VALUES ($1, $2, $3, $4, $5)
                """,
                target.id,
                str(target),
                target.display_name,
                guild["id"],
                status,
            )

            if ctx.guild and status in (PlayerStatus.FOUNDER.value, PlayerStatus.MENTOR.value):
                try:
                    await self._sync_registration_roles(ctx.guild, target, status)
                except discord.Forbidden:
                    pass

            who = target.mention if registering_other else "You"

            if status == PlayerStatus.PENDING.value:
                founders = await self.bot.db.fetch(
                    """
                    SELECT discord_id FROM players
                    WHERE guild_id = $1 AND status = 'founder'
                    """,
                    guild["id"],
                )
                founder_mentions = " ".join([f"<@{f['discord_id']}>" for f in founders]) if founders else "@here"

                await ctx.followup.send(
                    f"✅ Registration submitted for {target.mention}! Pending founder approval.\n"
                    f"Founders: {founder_mentions}",
                    ephemeral=True,
                )

                discord_guild = ctx.guild
                if discord_guild:
                    reg_channel = discord.utils.get(discord_guild.channels, name="registration") or discord.utils.get(
                        discord_guild.channels, name="registration-logs"
                    )
                    if reg_channel:
                        by = f"{ctx.author.mention} (staff)" if registering_other else target.mention
                        await reg_channel.send(
                            f"🆕 New registration pending approval:\n"
                            f"Player: {target.mention} (`{target.display_name}`)\n"
                            f"Submitted by: {by}\n"
                            f"Guild: **{guild['name']}**\n"
                            f"Use `/guild approve` with {target.mention} to approve"
                        )
            else:
                role_label = "Founder" if status == PlayerStatus.FOUNDER.value else "Mentor"
                await ctx.followup.send(
                    f"✅ {who} registered as **{role_label}** in guild **{guild['name']}**.",
                    ephemeral=True,
                )

        except Exception as e:
            await ctx.followup.send(f"❌ Registration failed: {str(e)}", ephemeral=True)

    @discord.slash_command(name="guild", description="Guild management commands")
    @option("action", choices=["approve", "promote", "demote", "info"])
    @option("user", required=False, description="Target user (for approve/promote/demote)")
    async def guild_management(self, ctx: discord.ApplicationContext, action: str, user: discord.Member = None):
        """Manage the guild (Founders only)"""
        await ctx.defer(ephemeral=True)
        if not await self.bot.permissions.require_founder(ctx.author):
            await ctx.followup.send("❌ Only guild founders can use this command.", ephemeral=True)
            return

        if action == "info":
            guild_id = await self.bot.permissions.get_guild_id(ctx.author)
            if not guild_id:
                await ctx.followup.send("❌ Unable to determine your guild.", ephemeral=True)
                return

            stats = await self.bot.db.fetchrow(
                """
                SELECT
                    g.name as guild_name,
                    COUNT(CASE WHEN p.status != 'pending' THEN 1 END) as active_members,
                    COUNT(CASE WHEN p.status = 'mentor' THEN 1 END) as mentors,
                    COUNT(CASE WHEN p.status = 'founder' THEN 1 END) as founders,
                    COUNT(s.id) as total_sessions,
                    AVG(s.score) as avg_score
                FROM guilds g
                LEFT JOIN players p ON p.guild_id = g.id
                LEFT JOIN sessions s ON s.player_id = p.id AND s.session_date >= NOW() - INTERVAL '30 days'
                WHERE g.id = $1
                GROUP BY g.id, g.name
                """,
                guild_id,
            )
            if not stats:
                await ctx.followup.send("❌ Unable to load guild statistics.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Guild Statistics: {stats['guild_name']}",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Active Members", value=stats["active_members"] or 0, inline=True)
            embed.add_field(name="Mentors", value=stats["mentors"] or 0, inline=True)
            embed.add_field(name="Founders", value=stats["founders"] or 0, inline=True)
            embed.add_field(name="Sessions (30d)", value=stats["total_sessions"] or 0, inline=True)
            embed.add_field(
                name="Avg Score (30d)",
                value=f"{stats['avg_score']:.2f}" if stats["avg_score"] else "N/A",
                inline=True,
            )
            embed.set_footer(text="Use /guild approve @user to approve pending registrations")

            await ctx.followup.send(embed=embed)
            return

        if not user:
            await ctx.followup.send(f"❌ Please specify a user for action '{action}'.", ephemeral=True)
            return

        target_player = await self.bot.db.get_player_by_discord_id(user.id)
        if not target_player:
            await ctx.followup.send(f"❌ User {user.mention} is not registered in the system.", ephemeral=True)
            return

        if target_player["guild_id"] != await self.bot.permissions.get_guild_id(ctx.author):
            await ctx.followup.send(f"❌ User {user.mention} belongs to a different guild.", ephemeral=True)
            return

        gname_dm = str(target_player.get("guild_name") or "your guild").strip() or "your guild"

        if action == "approve":
            if target_player["status"] != PlayerStatus.PENDING.value:
                await ctx.followup.send(f"❌ User {user.mention} is not pending approval.", ephemeral=True)
                return

            await self.bot.db.execute(
                "UPDATE players SET status = 'active' WHERE id = $1",
                target_player["id"],
            )

            if ctx.guild:
                member_role = discord.utils.get(ctx.guild.roles, name="Member")
                if member_role and member_role not in user.roles:
                    await user.add_roles(member_role)

            await ctx.followup.send(f"✅ User {user.mention} has been approved and granted Member role.")
            try:
                await user.send(
                    f"🎉 Congratulations! Your registration in **{gname_dm}** has been approved. "
                    f"You now have access to all member features."
                )
            except discord.Forbidden:
                pass

        elif action == "promote":
            if target_player["status"] not in [PlayerStatus.ACTIVE.value, PlayerStatus.MENTOR.value]:
                await ctx.followup.send(
                    f"❌ Cannot promote user {user.mention} with status '{target_player['status']}'.",
                    ephemeral=True,
                )
                return

            new_status = (
                PlayerStatus.MENTOR.value
                if target_player["status"] == PlayerStatus.ACTIVE.value
                else PlayerStatus.FOUNDER.value
            )
            await self.bot.db.execute(
                "UPDATE players SET status = $1 WHERE id = $2",
                new_status,
                target_player["id"],
            )

            role_name = "Mentor" if new_status == PlayerStatus.MENTOR.value else "Founder"
            if ctx.guild:
                discord_role = discord.utils.get(ctx.guild.roles, name=role_name)
                if discord_role and discord_role not in user.roles:
                    await user.add_roles(discord_role)

            await ctx.followup.send(f"✅ User {user.mention} has been promoted to **{role_name}**.")
            try:
                await user.send(f"🌟 You have been promoted to **{role_name}** in **{gname_dm}**!")
            except discord.Forbidden:
                pass

        elif action == "demote":
            if target_player["status"] not in [PlayerStatus.MENTOR.value, PlayerStatus.FOUNDER.value]:
                await ctx.followup.send(
                    f"❌ Cannot demote user {user.mention} with status '{target_player['status']}'.",
                    ephemeral=True,
                )
                return

            if target_player["status"] == PlayerStatus.FOUNDER.value and ctx.author.id != user.id:
                await ctx.followup.send(
                    "❌ Only founders can demote other founders (and only themselves).",
                    ephemeral=True,
                )
                return

            new_status = (
                PlayerStatus.ACTIVE.value
                if target_player["status"] == PlayerStatus.MENTOR.value
                else PlayerStatus.MENTOR.value
            )
            await self.bot.db.execute(
                "UPDATE players SET status = $1 WHERE id = $2",
                new_status,
                target_player["id"],
            )

            old_role_name = "Founder" if target_player["status"] == PlayerStatus.FOUNDER.value else "Mentor"
            new_role_name = "Mentor" if new_status == PlayerStatus.MENTOR.value else "Member"
            if ctx.guild:
                old_role = discord.utils.get(ctx.guild.roles, name=old_role_name)
                new_role = discord.utils.get(ctx.guild.roles, name=new_role_name)
                if old_role and old_role in user.roles:
                    await user.remove_roles(old_role)
                if new_role and new_role not in user.roles:
                    await user.add_roles(new_role)

            await ctx.followup.send(f"✅ User {user.mention} has been demoted to **{new_role_name}**.")
            try:
                await user.send(
                    f"⬇️ Your role in **{gname_dm}** has been changed to **{new_role_name}**."
                )
            except discord.Forbidden:
                pass


def setup(bot):
    bot.add_cog(AuthCommands(bot))
